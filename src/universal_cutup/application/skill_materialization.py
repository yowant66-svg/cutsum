from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from universal_cutup.adapters.transcripts import (
    TranscriptParseContext,
    parse_json_transcript,
    parse_srt,
    parse_vtt,
)
from universal_cutup.application.blind_runs import load_blind_run_input
from universal_cutup.application.sdk import inspect_source
from universal_cutup.domain.assessments import (
    AssessmentBundle,
    CandidateAssessment,
    CandidateProposalBundle,
    DimensionAssessment,
)
from universal_cutup.domain.blind_runs import BlindRunInput
from universal_cutup.domain.candidates import CutCandidate, EvidenceRef
from universal_cutup.domain.intelligence import (
    ALL_DIMENSION_KEYS,
    ContentProfile,
    DimensionKey,
    HostIntent,
)
from universal_cutup.domain.sources import RightsAttestation
from universal_cutup.domain.transcript import SubtitleCue, TranscriptArtifact
from universal_cutup.hashing import document_sha256

FORBIDDEN_TASK_INTERPRETATION_KEYS = frozenset(
    {
        "candidate_id",
        "candidate_ids",
        "hard_include_candidate_ids",
        "hard_exclude_candidate_ids",
        "start_ms",
        "end_ms",
        "time_range",
        "score",
    }
)
DIMENSION_EXPLANATIONS: dict[DimensionKey, str] = {
    DimensionKey.INSIGHT: "information or reasoning value",
    DimensionKey.NOVELTY: "fresh or non-obvious value",
    DimensionKey.EMOTION: "emotional force",
    DimensionKey.QUOTABILITY: "memorability and quotability",
    DimensionKey.HOOK: "immediate attention value",
    DimensionKey.STANDALONE: "ability to stand without missing context",
    DimensionKey.CLARITY: "clarity of expression and structure",
    DimensionKey.COMPLETION: "completion of the relevant thought or beat",
    DimensionKey.SHAREABILITY: "likelihood of prompting useful sharing or discussion",
    DimensionKey.SILENT_WATCHABILITY: "comprehensibility with weak or absent audio",
    DimensionKey.PACE: "pace for the intended clip",
    DimensionKey.EDITABILITY: "availability of natural edit boundaries",
    DimensionKey.SUBTITLE_RELIABILITY: "reliability of transcript and subtitle evidence",
    DimensionKey.VISUAL_INDEPENDENCE: "independence from unseen visual context",
}


def _read_transcript(
    path: Path,
    *,
    source_id: str,
    transcript_id: str,
    created_at: datetime,
) -> TranscriptArtifact:
    content = path.read_text(encoding="utf-8-sig")
    context = TranscriptParseContext(
        transcript_id=transcript_id,
        source_id=source_id,
        created_at=created_at,
        created_by="codex-host-repo-local-skill",
        language="en",
    )
    parsers = {".json": parse_json_transcript, ".srt": parse_srt, ".vtt": parse_vtt}
    try:
        parser = parsers[path.suffix.casefold()]
    except KeyError as error:
        raise ValueError("blind Skill transcript must use JSON, SRT, or VTT") from error
    return parser(content, context=context)


def _write_model(path: Path, model: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as file_handle:
        file_handle.write(model.model_dump_json(indent=2, exclude_none=True))
        file_handle.write("\n")


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as file_handle:
        json.dump(payload, file_handle, ensure_ascii=False, indent=2)
        file_handle.write("\n")


def _candidate_evidence(
    transcript: TranscriptArtifact,
    *,
    candidate_id: str,
    start_ms: int,
    end_ms: int,
) -> tuple[EvidenceRef, tuple[SubtitleCue, ...]]:
    segments = tuple(
        segment
        for segment in transcript.segments
        if segment.end_ms > start_ms and segment.start_ms < end_ms
    )
    if not segments:
        raise ValueError(f"candidate {candidate_id} has no transcript evidence")
    evidence_id = f"evidence-{candidate_id}"
    complete_text = " ".join(segment.text for segment in segments)
    evidence = EvidenceRef(
        evidence_id=evidence_id,
        artifact_id=transcript.transcript_id,
        segment_ids=tuple(segment.segment_id for segment in segments),
        start_ms=max(start_ms, segments[0].start_ms),
        end_ms=min(end_ms, segments[-1].end_ms),
        text_sha256=hashlib.sha256(complete_text.encode("utf-8")).hexdigest(),
        snapshot=complete_text[:2048],
    )
    cues = tuple(
        SubtitleCue(
            cue_id=f"cue-{candidate_id}-{index:03d}",
            source_id=transcript.source_id,
            start_ms=segment.start_ms,
            end_ms=segment.end_ms,
            text=segment.text,
            language=transcript.language,
            speaker=segment.speaker,
            source_segment_ids=(segment.segment_id,),
        )
        for index, segment in enumerate(segments, start=1)
    )
    return evidence, cues


def _candidate_documents(
    transcript: TranscriptArtifact,
    raw_candidates: list[dict[str, Any]],
) -> tuple[
    tuple[CutCandidate, ...],
    tuple[CandidateAssessment, ...],
    dict[str, tuple[int, int, int, int]],
]:
    candidates: list[CutCandidate] = []
    assessments: list[CandidateAssessment] = []
    boundaries: dict[str, tuple[int, int, int, int]] = {}
    for raw_candidate in raw_candidates:
        candidate_id = str(raw_candidate["candidate_id"])
        start_ms = int(raw_candidate["start_ms"])
        end_ms = int(raw_candidate["end_ms"])
        initial_start_ms = int(raw_candidate["initial_start_ms"])
        initial_end_ms = int(raw_candidate["initial_end_ms"])
        evidence, cues = _candidate_evidence(
            transcript,
            candidate_id=candidate_id,
            start_ms=start_ms,
            end_ms=end_ms,
        )
        raw_translations = raw_candidate.get("translations", [])
        if not isinstance(raw_translations, list):
            raise ValueError(f"candidate {candidate_id} translations must be an array")
        if raw_translations and len(raw_translations) != len(cues):
            raise ValueError(
                f"candidate {candidate_id} must translate every source cue without retiming"
            )
        translated_cues = (
            tuple(
                cue.model_copy(
                    update={
                        "cue_id": f"{cue.cue_id}-zh-CN",
                        "text": str(translation),
                        "language": "zh-CN",
                    }
                )
                for cue, translation in zip(cues, raw_translations, strict=True)
            )
            if raw_translations
            else ()
        )
        candidates.append(
            CutCandidate(
                candidate_id=candidate_id,
                source_id=transcript.source_id,
                start_ms=start_ms,
                end_ms=end_ms,
                summary=str(raw_candidate["summary"]),
                evidence_refs=(evidence,),
                subtitle_cues=cues,
                translated_subtitle_cues=translated_cues,
                tags=tuple(str(tag) for tag in raw_candidate.get("tags", [])),
                warnings=tuple(str(item) for item in raw_candidate.get("warnings", [])),
                semantic_types=tuple(raw_candidate.get("semantic_types", [])),
                semantic_structure=tuple(raw_candidate.get("semantic_structure", [])),
                topics=tuple(str(item) for item in raw_candidate.get("topics", [])),
                speakers=tuple(str(item) for item in raw_candidate.get("speakers", [])),
                extension_reason=raw_candidate.get("extension_reason"),
                series_group_id=raw_candidate.get("series_group_id"),
                series_index=raw_candidate.get("series_index"),
                series_total=raw_candidate.get("series_total"),
            )
        )
        scores = raw_candidate["scores"]
        if not isinstance(scores, list) or len(scores) != len(ALL_DIMENSION_KEYS):
            raise ValueError(f"candidate {candidate_id} must supply all 14 scores in stable order")
        confidence = float(raw_candidate.get("confidence", 0.8))
        dimensions = tuple(
            DimensionAssessment(
                dimension=dimension,
                score=float(score),
                evidence_refs=(evidence.evidence_id,),
                explanation=(
                    f"The candidate evidence supports {DIMENSION_EXPLANATIONS[dimension]}; "
                    f"the host judgment is specific to: {raw_candidate['summary']}."
                ),
                confidence=confidence,
            )
            for dimension, score in zip(ALL_DIMENSION_KEYS, scores, strict=True)
        )
        assessments.append(
            CandidateAssessment(
                candidate_id=candidate_id,
                dimensions=dimensions,
                content_track_ids=tuple(
                    str(track_id) for track_id in raw_candidate.get("track_ids", [])
                ),
            )
        )
        boundaries[candidate_id] = (
            initial_start_ms,
            initial_end_ms,
            start_ms,
            end_ms,
        )
    return tuple(candidates), tuple(assessments), boundaries


def _assert_task_interpretation_is_blind(value: object) -> None:
    if isinstance(value, dict):
        forbidden = {str(key) for key in value} & FORBIDDEN_TASK_INTERPRETATION_KEYS
        if forbidden:
            raise ValueError(
                f"blind task interpretation contains forbidden answer fields: {sorted(forbidden)}"
            )
        for nested in value.values():
            _assert_task_interpretation_is_blind(nested)
    elif isinstance(value, list):
        for nested in value:
            _assert_task_interpretation_is_blind(nested)


def _host_intents(
    blind_input: BlindRunInput,
    task_interpretations: list[dict[str, Any]],
) -> tuple[HostIntent, ...]:
    interpretations = {str(item["task_id"]): item for item in task_interpretations}
    if set(interpretations) != {task.task_id for task in blind_input.tasks}:
        raise ValueError("Skill task interpretations must cover the three blind tasks exactly")
    intents: list[HostIntent] = []
    for task in blind_input.tasks:
        interpretation = interpretations[task.task_id]
        _assert_task_interpretation_is_blind(interpretation)
        body = {key: value for key, value in interpretation.items() if key != "task_id"}
        intents.append(
            HostIntent(
                document_type="host_intent",
                created_at=blind_input.created_at,
                created_by="codex-host-repo-local-skill",
                intent_id=f"intent-{task.task_id}",
                raw_instruction=task.raw_instruction,
                control_mode=task.control_mode,
                **body,
            )
        )
    return tuple(intents)


def materialize_skill_output(
    blind_input_path: Path,
    skill_output_path: Path,
    output_root: Path,
    *,
    rights_attestation: RightsAttestation,
) -> dict[str, object]:
    blind_input = load_blind_run_input(
        blind_input_path,
        blind_input_root=blind_input_path.parent,
    )
    skill_output = json.loads(skill_output_path.read_text(encoding="utf-8"))
    if not isinstance(skill_output, dict):
        raise ValueError("Skill output must be a JSON object")
    transcript = _read_transcript(
        Path(blind_input.transcript_path),
        source_id=blind_input.source_id,
        transcript_id=f"transcript-{blind_input.sample_id}",
        created_at=blind_input.created_at,
    )
    raw_candidates = skill_output.get("candidates")
    if not isinstance(raw_candidates, list):
        raise ValueError("Skill output must contain a candidates array")
    candidates, assessments, boundaries = _candidate_documents(transcript, raw_candidates)
    if not 10 <= len(candidates) <= 24:
        raise ValueError("Gate H requires 10-24 autonomous candidates per sample")
    provider_record_ref = f"provider-{blind_input.sample_id}-skill-generated"
    proposal_bundle = CandidateProposalBundle(
        document_type="candidate_proposal_bundle",
        created_at=blind_input.created_at,
        created_by="codex-host-repo-local-skill",
        proposal_bundle_id=f"proposals-{blind_input.sample_id}",
        source_id=blind_input.source_id,
        provider_record_ref=f"{provider_record_ref}-proposal",
        provider_kind="host_ai_file",
        is_fixture=False,
        candidates=candidates,
        input_document_sha256=document_sha256(transcript),
    )
    assessment_bundle = AssessmentBundle(
        document_type="assessment_bundle",
        created_at=blind_input.created_at,
        created_by="codex-host-repo-local-skill",
        assessment_bundle_id=f"assessments-{blind_input.sample_id}",
        source_id=blind_input.source_id,
        provider_record_ref=f"{provider_record_ref}-assessment",
        provider_kind="host_ai_file",
        is_fixture=False,
        candidates=assessments,
        input_document_sha256=document_sha256(proposal_bundle),
    )
    profile_body = skill_output.get("content_profile")
    if not isinstance(profile_body, dict):
        raise ValueError("Skill output must contain a content_profile object")
    content_profile = ContentProfile(
        document_type="content_profile",
        created_at=blind_input.created_at,
        created_by="codex-host-repo-local-skill",
        profile_id=f"profile-{blind_input.sample_id}",
        source_id=blind_input.source_id,
        supporting_evidence_refs=tuple(
            candidate.evidence_refs[0].evidence_id for candidate in candidates
        ),
        provider_record_ref=provider_record_ref,
        **profile_body,
    )
    raw_interpretations = skill_output.get("task_interpretations")
    if not isinstance(raw_interpretations, list):
        raise ValueError("Skill output must contain task_interpretations")
    intents = _host_intents(blind_input, raw_interpretations)
    if blind_input.media_path is None:
        raise ValueError("Gate H playable review requires a local media path")
    inspection = inspect_source(
        Path(blind_input.media_path),
        source_id=blind_input.source_id,
        rights_attestation=rights_attestation,
    )

    output_root.mkdir(parents=True, exist_ok=False)
    _write_model(output_root / "transcript-artifact.json", transcript)
    _write_model(output_root / "source.json", inspection.source)
    _write_model(output_root / "binding.json", inspection.binding)
    _write_model(output_root / "content-profile.json", content_profile)
    _write_model(output_root / "proposals.json", proposal_bundle)
    _write_model(output_root / "assessments.json", assessment_bundle)
    for intent in intents:
        _write_model(output_root / "host-intents" / f"{intent.intent_id}.json", intent)
    _write_json(
        output_root / "boundary-records.json",
        {
            candidate_id: {
                "initial_start_ms": values[0],
                "initial_end_ms": values[1],
                "refined_start_ms": values[2],
                "refined_end_ms": values[3],
            }
            for candidate_id, values in boundaries.items()
        },
    )
    return {
        "sample_id": blind_input.sample_id,
        "candidate_count": len(candidates),
        "task_count": len(intents),
        "transcript_sha256": document_sha256(transcript),
        "skill_output_sha256": hashlib.sha256(skill_output_path.read_bytes()).hexdigest(),
        "output_root": str(output_root),
    }
