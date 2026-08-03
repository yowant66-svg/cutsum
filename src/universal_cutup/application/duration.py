from __future__ import annotations

import hashlib

from universal_cutup.domain.assessments import (
    AssessmentBundle,
    CandidateAssessment,
    CandidateProposalBundle,
)
from universal_cutup.domain.candidates import CutCandidate, EvidenceRef
from universal_cutup.domain.intelligence import ControlMode, ResolvedTaskProfile
from universal_cutup.domain.transcript import SubtitleCue
from universal_cutup.hashing import document_sha256

DEFAULT_PART_DURATION_MS = 60_000
ABSOLUTE_PART_DURATION_MS = 120_000
MINIMUM_PART_DURATION_MS = 15_000


def _cue_groups(
    cues: tuple[SubtitleCue, ...],
    *,
    target_duration_ms: int,
) -> tuple[tuple[SubtitleCue, ...], ...]:
    groups: list[list[SubtitleCue]] = []
    current: list[SubtitleCue] = []
    for cue in cues:
        if (
            current
            and cue.end_ms - current[0].start_ms > target_duration_ms
            and current[-1].end_ms - current[0].start_ms >= MINIMUM_PART_DURATION_MS
        ):
            groups.append(current)
            current = []
        current.append(cue)
    if current:
        groups.append(current)
    if len(groups) > 1:
        final_duration = groups[-1][-1].end_ms - groups[-1][0].start_ms
        merged_duration = groups[-1][-1].end_ms - groups[-2][0].start_ms
        if (
            final_duration < MINIMUM_PART_DURATION_MS
            and merged_duration <= ABSOLUTE_PART_DURATION_MS
        ):
            groups[-2].extend(groups.pop())
    return tuple(tuple(group) for group in groups)


def _part_evidence(
    candidate: CutCandidate,
    cues: tuple[SubtitleCue, ...],
    *,
    part_id: str,
) -> EvidenceRef:
    text = " ".join(cue.text for cue in cues)
    source_segments = tuple(
        dict.fromkeys(segment_id for cue in cues for segment_id in cue.source_segment_ids)
    )
    original = candidate.evidence_refs[0]
    return EvidenceRef(
        evidence_id=f"{original.evidence_id}-{part_id}",
        artifact_id=original.artifact_id,
        segment_ids=source_segments,
        start_ms=cues[0].start_ms,
        end_ms=cues[-1].end_ms,
        text_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        snapshot=text[:2048],
    )


def split_candidate(candidate: CutCandidate) -> tuple[CutCandidate, ...]:
    duration_ms = candidate.end_ms - candidate.start_ms
    if duration_ms <= ABSOLUTE_PART_DURATION_MS:
        return (candidate,)
    cues = tuple(
        cue
        for cue in candidate.subtitle_cues
        if cue.end_ms > candidate.start_ms and cue.start_ms < candidate.end_ms
    )
    if not cues:
        return (
            candidate.model_copy(
                update={
                    "warnings": (
                        *candidate.warnings,
                        "duration_split_unavailable:no_source_timeline_cues",
                    )
                }
            ),
        )
    groups = _cue_groups(cues, target_duration_ms=DEFAULT_PART_DURATION_MS)
    series_group_id = f"series-{candidate.candidate_id}"
    total = len(groups)
    parts = []
    for index, group in enumerate(groups, start=1):
        part_id = f"part-{index}"
        part_start_ms = group[0].start_ms
        part_end_ms = group[-1].end_ms
        part_duration = group[-1].end_ms - group[0].start_ms
        if part_duration > ABSOLUTE_PART_DURATION_MS:
            raise ValueError(
                f"candidate {candidate.candidate_id} contains an unsplittable cue group"
            )
        part_evidence = _part_evidence(candidate, group, part_id=part_id)
        display_units = tuple(
            unit
            for unit in candidate.subtitle_display_units
            if unit.start_ms >= part_start_ms and unit.end_ms <= part_end_ms
        )
        translation_record_ids = {unit.translation_record_ref for unit in display_units}
        parts.append(
            candidate.model_copy(
                update={
                    "candidate_id": f"{candidate.candidate_id}-{part_id}",
                    "start_ms": part_start_ms,
                    "end_ms": part_end_ms,
                    "summary": f"{candidate.summary} (Part {index}/{total})",
                    "evidence_refs": (part_evidence,),
                    "subtitle_cues": group,
                    "translated_subtitle_cues": tuple(
                        cue
                        for cue in candidate.translated_subtitle_cues
                        if cue.end_ms > group[0].start_ms and cue.start_ms < group[-1].end_ms
                    ),
                    "subtitle_word_timings": tuple(
                        timing
                        for timing in candidate.subtitle_word_timings
                        if timing.start_ms >= part_start_ms and timing.end_ms <= part_end_ms
                    ),
                    "subtitle_semantic_spans": tuple(
                        span
                        for span in candidate.subtitle_semantic_spans
                        if span.start_ms >= part_start_ms and span.end_ms <= part_end_ms
                    ),
                    "subtitle_display_units": display_units,
                    "contextual_translation_records": tuple(
                        record
                        for record in candidate.contextual_translation_records
                        if record.translation_record_id in translation_record_ids
                    ),
                    "education_signals": tuple(
                        signal.model_copy(
                            update={
                                "start_ms": max(signal.start_ms, part_start_ms),
                                "end_ms": min(signal.end_ms, part_end_ms),
                                "evidence_refs": (part_evidence.evidence_id,),
                            }
                        )
                        for signal in candidate.education_signals
                        if signal.end_ms > part_start_ms and signal.start_ms < part_end_ms
                    ),
                    "education_visual_dependencies": tuple(
                        dependency.model_copy(
                            update={
                                "start_ms": max(dependency.start_ms, part_start_ms),
                                "end_ms": min(dependency.end_ms, part_end_ms),
                                "evidence_refs": (part_evidence.evidence_id,),
                            }
                        )
                        for dependency in candidate.education_visual_dependencies
                        if dependency.end_ms > part_start_ms and dependency.start_ms < part_end_ms
                    ),
                    "educational_profile": None,
                    "extension_reason": (
                        "Sentence-safe series part requires more than the preferred 60 seconds"
                        if part_duration > DEFAULT_PART_DURATION_MS
                        else None
                    ),
                    "series_group_id": series_group_id,
                    "series_index": index,
                    "series_total": total,
                }
            )
        )
    return tuple(parts)


def _allows_explicit_long_form(task_profile: ResolvedTaskProfile) -> bool:
    constraints = task_profile.hard_constraints
    return (
        task_profile.control_mode is ControlMode.DIRECTED
        and constraints.host_requested_duration_ms is not None
        and constraints.host_requested_duration_ms > ABSOLUTE_PART_DURATION_MS
    )


def prepare_candidates_for_task(
    proposals: CandidateProposalBundle,
    assessments: AssessmentBundle,
    task_profile: ResolvedTaskProfile,
) -> tuple[CandidateProposalBundle, AssessmentBundle]:
    if _allows_explicit_long_form(task_profile):
        return proposals, assessments
    assessments_by_id = {
        assessment.candidate_id: assessment for assessment in assessments.candidates
    }
    candidates: list[CutCandidate] = []
    prepared_assessments: list[CandidateAssessment] = []
    for candidate in proposals.candidates:
        parts = split_candidate(candidate)
        candidates.extend(parts)
        original_assessment = assessments_by_id[candidate.candidate_id]
        prepared_assessments.extend(
            original_assessment.model_copy(update={"candidate_id": part.candidate_id})
            for part in parts
        )
    if tuple(candidates) == proposals.candidates:
        return proposals, assessments
    prepared_proposals = proposals.model_copy(
        update={
            "proposal_bundle_id": f"{proposals.proposal_bundle_id}-duration-prepared",
            "candidates": tuple(candidates),
            "input_document_sha256": document_sha256(
                {
                    "original": proposals.model_dump(mode="json"),
                    "task": task_profile.model_dump(mode="json"),
                }
            ),
        }
    )
    prepared_bundle = assessments.model_copy(
        update={
            "assessment_bundle_id": f"{assessments.assessment_bundle_id}-duration-prepared",
            "candidates": tuple(prepared_assessments),
            "input_document_sha256": document_sha256(prepared_proposals),
        }
    )
    return prepared_proposals, prepared_bundle
