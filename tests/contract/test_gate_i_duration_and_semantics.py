from __future__ import annotations

from datetime import UTC, datetime

import pytest

from universal_cutup.application.duration import (
    ABSOLUTE_PART_DURATION_MS,
    prepare_candidates_for_task,
)
from universal_cutup.application.resolution import resolve_task_profile
from universal_cutup.domain.assessments import (
    AssessmentBundle,
    CandidateAssessment,
    CandidateProposalBundle,
    DimensionAssessment,
)
from universal_cutup.domain.candidates import CutCandidate, EvidenceRef
from universal_cutup.domain.intelligence import (
    ClipConstraints,
    ContentDensity,
    ContentProfile,
    ControlMode,
    DependencyProfile,
    DimensionKey,
    HostIntent,
    SemanticType,
)
from universal_cutup.domain.transcript import SubtitleCue
from universal_cutup.hashing import document_sha256
from universal_cutup.strategies.adaptive import aggregate_bundle, select_adaptive

FIXED_TIME = datetime(2026, 7, 31, tzinfo=UTC)


def candidate(
    candidate_id: str,
    *,
    duration_ms: int,
    semantic_types: tuple[SemanticType, ...],
) -> CutCandidate:
    cues = tuple(
        SubtitleCue(
            cue_id=f"cue-{candidate_id}-{index}",
            source_id="source-1",
            start_ms=start,
            end_ms=min(start + 10_000, duration_ms),
            text=f"Sentence {index}",
            language="en",
            source_segment_ids=(f"segment-{index}",),
        )
        for index, start in enumerate(range(0, duration_ms, 10_000), start=1)
    )
    evidence = EvidenceRef(
        evidence_id=f"evidence-{candidate_id}",
        artifact_id="transcript-1",
        segment_ids=tuple(f"segment-{index}" for index in range(1, len(cues) + 1)),
        start_ms=0,
        end_ms=duration_ms,
        text_sha256="a" * 64,
        snapshot="Synthetic evidence",
    )
    return CutCandidate(
        candidate_id=candidate_id,
        source_id="source-1",
        start_ms=0,
        end_ms=duration_ms,
        summary=f"Synthetic {candidate_id}",
        evidence_refs=(evidence,),
        subtitle_cues=cues,
        semantic_types=semantic_types,
        semantic_structure=("premise", "reasoning", "conclusion"),
    )


def assessment(item: CutCandidate) -> CandidateAssessment:
    return CandidateAssessment(
        candidate_id=item.candidate_id,
        dimensions=tuple(
            DimensionAssessment(
                dimension=dimension,
                score=8,
                evidence_refs=(item.evidence_refs[0].evidence_id,),
                explanation="Synthetic assessment",
            )
            for dimension in DimensionKey
        ),
    )


def bundles(
    candidates: tuple[CutCandidate, ...],
) -> tuple[CandidateProposalBundle, AssessmentBundle]:
    proposals = CandidateProposalBundle(
        document_type="candidate_proposal_bundle",
        created_at=FIXED_TIME,
        created_by="test",
        proposal_bundle_id="proposals",
        source_id="source-1",
        provider_record_ref="provider-proposals",
        provider_kind="fixture",
        is_fixture=True,
        candidates=candidates,
        input_document_sha256=document_sha256({"input": "test"}),
    )
    assessments = AssessmentBundle(
        document_type="assessment_bundle",
        created_at=FIXED_TIME,
        created_by="test",
        assessment_bundle_id="assessments",
        source_id="source-1",
        provider_record_ref="provider-assessments",
        provider_kind="fixture",
        is_fixture=True,
        candidates=tuple(assessment(item) for item in candidates),
        input_document_sha256=document_sha256(proposals),
    )
    return proposals, assessments


def intent(
    outcomes: tuple[str, ...],
    *,
    count: int = 1,
    mode: ControlMode = ControlMode.AUTO,
) -> HostIntent:
    return HostIntent(
        document_type="host_intent",
        created_at=FIXED_TIME,
        created_by="test",
        intent_id="intent",
        raw_instruction="Synthetic task",
        control_mode=mode,
        desired_outcomes=outcomes,
        clip_constraints=ClipConstraints(
            target_count=count,
            minimum_count=count,
            maximum_count=count,
        ),
    )


def content_profile(content_type: str = "lecture") -> ContentProfile:
    return ContentProfile(
        document_type="content_profile",
        created_at=FIXED_TIME,
        created_by="test",
        profile_id="profile",
        source_id="source-1",
        content_types=(content_type,),
        primary_topic="Synthetic",
        structure_types=("exposition",),
        density=ContentDensity(
            narrative=0.5,
            knowledge=0.8,
            procedural=0.5,
            opinion=0.2,
            emotion=0.3,
        ),
        dependencies=DependencyProfile(visual=0.2, audio=0.8, subtitle=0.8),
        confidence=0.9,
        supporting_evidence_refs=("evidence-long-story",),
    )


@pytest.mark.parametrize("content_type", ["interview", "drama", "lecture"])
def test_long_auto_candidate_splits_on_real_cue_boundaries(
    content_type: str,
) -> None:
    original = candidate(
        "long-story",
        duration_ms=185_000,
        semantic_types=(SemanticType.STORY_ARC,),
    )
    proposals, assessments = bundles((original,))
    task = resolve_task_profile(
        intent(("story_arc",)),
        content_profile=content_profile(content_type),
        created_at=FIXED_TIME,
    )
    prepared, prepared_assessments = prepare_candidates_for_task(
        proposals,
        assessments,
        task,
    )
    assert len(prepared.candidates) >= 2
    assert len(prepared.candidates) == len(prepared_assessments.candidates)
    assert all(
        item.end_ms - item.start_ms <= ABSOLUTE_PART_DURATION_MS for item in prepared.candidates
    )
    assert [item.series_index for item in prepared.candidates] == list(
        range(1, len(prepared.candidates) + 1)
    )


def test_semantic_qualification_filters_before_fourteen_dimension_ranking() -> None:
    explanation = candidate(
        "high-score-explanation",
        duration_ms=40_000,
        semantic_types=(),
    )
    definition = candidate(
        "qualified-definition",
        duration_ms=45_000,
        semantic_types=(SemanticType.DEFINITION,),
    )
    proposals, assessments = bundles((explanation, definition))
    task = resolve_task_profile(
        intent(("definition",)),
        content_profile=content_profile(),
        created_at=FIXED_TIME,
    )
    aggregates = aggregate_bundle(proposals.candidates, assessments, task)
    result = select_adaptive(
        proposals.candidates,
        assessments.candidates,
        aggregates,
        task,
        created_at=FIXED_TIME,
    )
    assert result.selected_candidate_ids == ("qualified-definition",)
    rejected = next(
        item for item in result.decisions if item.candidate_id == "high-score-explanation"
    )
    assert rejected.semantic_qualified is False
    assert rejected.missing_qualifications == ("semantic_type:definition",)


def test_two_definitions_return_only_one_qualified_instead_of_substitution() -> None:
    definition = candidate(
        "only-definition",
        duration_ms=45_000,
        semantic_types=(SemanticType.DEFINITION,),
    )
    explanation = candidate(
        "not-a-definition",
        duration_ms=45_000,
        semantic_types=(),
    )
    proposals, assessments = bundles((definition, explanation))
    task = resolve_task_profile(
        intent(("two_review_definitions",), count=2, mode=ControlMode.DIRECTED),
        content_profile=None,
        created_at=FIXED_TIME,
    )
    aggregates = aggregate_bundle(proposals.candidates, assessments, task)
    result = select_adaptive(
        proposals.candidates,
        assessments.candidates,
        aggregates,
        task,
        created_at=FIXED_TIME,
    )
    assert result.selected_candidate_ids == ("only-definition",)
    assert "semantic_required_count:2" in result.unsatisfied_constraints
    assert result.nearest_candidate_ids == ("not-a-definition",)


def test_ordered_series_parts_are_not_rejected_as_duplicates() -> None:
    first = candidate(
        "reasoning-part-1",
        duration_ms=45_000,
        semantic_types=(SemanticType.REASONING_CHAIN,),
    ).model_copy(
        update={
            "series_group_id": "reasoning-series",
            "series_index": 1,
            "series_total": 2,
            "semantic_structure": ("premise", "reasoning"),
        }
    )
    second = candidate(
        "reasoning-part-2",
        duration_ms=45_000,
        semantic_types=(SemanticType.REASONING_CHAIN,),
    ).model_copy(
        update={
            "series_group_id": "reasoning-series",
            "series_index": 2,
            "series_total": 2,
            "semantic_structure": ("reasoning", "conclusion"),
        }
    )
    proposals, assessments = bundles((first, second))
    task = resolve_task_profile(
        intent(
            ("complete_reasoning_chain",),
            count=2,
            mode=ControlMode.DIRECTED,
        ).model_copy(update={"preserve_time_order": True}),
        content_profile=None,
        created_at=FIXED_TIME,
    )
    aggregates = aggregate_bundle(proposals.candidates, assessments, task)
    result = select_adaptive(
        proposals.candidates,
        assessments.candidates,
        aggregates,
        task,
        created_at=FIXED_TIME,
    )
    assert result.selected_candidate_ids == ("reasoning-part-1", "reasoning-part-2")
    assert result.unsatisfied_constraints == ()
