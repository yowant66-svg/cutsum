from __future__ import annotations

from datetime import UTC, datetime

import pytest

from universal_cutup.application.intelligence import (
    aggregate_intelligence,
    create_adaptive_plan,
    select_intelligence,
)
from universal_cutup.application.resolution import resolve_task_profile
from universal_cutup.domain.assessments import (
    AssessmentBundle,
    CandidateAssessment,
    CandidateProposalBundle,
    DimensionAssessment,
)
from universal_cutup.domain.candidates import CutCandidate, EvidenceRef
from universal_cutup.domain.errors import CutupError, ErrorCode
from universal_cutup.domain.intelligence import (
    ClipConstraints,
    ContentDensity,
    ContentProfile,
    ContentTrack,
    ControlMode,
    DecisionSource,
    DependencyProfile,
    DimensionApplicability,
    DimensionKey,
    DimensionPolicy,
    HostIntent,
)
from universal_cutup.domain.sources import MediaSource, RightsAttestation
from universal_cutup.hashing import document_sha256
from universal_cutup.strategies.adaptive import (
    aggregate_bundle,
    aggregate_candidate,
    select_adaptive,
)

FIXED_TIME = datetime(2026, 7, 30, tzinfo=UTC)


def make_candidate(candidate_id: str, start_ms: int, summary: str) -> CutCandidate:
    evidence = EvidenceRef(
        evidence_id=f"evidence-{candidate_id}",
        artifact_id="transcript-1",
        segment_ids=(f"segment-{candidate_id}",),
        start_ms=start_ms,
        end_ms=start_ms + 3000,
        text_sha256="a" * 64,
        snapshot=summary,
    )
    return CutCandidate(
        candidate_id=candidate_id,
        source_id="source-1",
        start_ms=start_ms,
        end_ms=start_ms + 3000,
        summary=summary,
        evidence_refs=(evidence,),
    )


def make_profile() -> ContentProfile:
    return ContentProfile(
        document_type="content_profile",
        created_at=FIXED_TIME,
        created_by="fixture-provider",
        profile_id="profile-1",
        source_id="source-1",
        content_types=("interview",),
        primary_topic="Synthetic adaptive test",
        structure_types=("dialogue",),
        value_sources=("independent_arguments",),
        density=ContentDensity(
            narrative=0.2,
            knowledge=0.7,
            procedural=0.1,
            opinion=0.8,
            emotion=0.5,
        ),
        dependencies=DependencyProfile(visual=0.1, audio=0.9, subtitle=0.8),
        confidence=0.9,
        supporting_evidence_refs=("evidence-candidate-1",),
    )


def make_intent(
    *,
    constraints: ClipConstraints | None = None,
    policies: tuple[DimensionPolicy, ...] = (),
) -> HostIntent:
    return HostIntent(
        document_type="host_intent",
        created_at=FIXED_TIME,
        created_by="test-suite",
        intent_id="intent-1",
        raw_instruction="Select the best synthetic segment",
        control_mode=ControlMode.GUIDED,
        clip_constraints=constraints or ClipConstraints(target_count=1),
        dimension_policies=policies,
    )


def make_assessment(
    candidate: CutCandidate,
    *,
    default_score: float,
    track_id: str = "track-1",
    overrides: dict[DimensionKey, float | None] | None = None,
    model_overall: float | None = None,
) -> CandidateAssessment:
    scores = overrides or {}
    dimensions = []
    for dimension in DimensionKey:
        score = scores.get(dimension, default_score)
        dimensions.append(
            DimensionAssessment(
                dimension=dimension,
                score=score,
                evidence_refs=(
                    (candidate.evidence_refs[0].evidence_id,) if score is not None else ()
                ),
                explanation="Synthetic evidence-backed assessment",
                unavailable_reason=("not applicable" if score is None else None),
            )
        )
    return CandidateAssessment(
        candidate_id=candidate.candidate_id,
        dimensions=tuple(dimensions),
        content_track_ids=(track_id,),
        model_reported_overall=model_overall,
    )


def test_not_applicable_is_excluded_from_denominator_and_model_overall_is_ignored() -> None:
    candidate = make_candidate("candidate-1", 0, "Unique explanation")
    host_policy = DimensionPolicy(
        dimension=DimensionKey.NOVELTY,
        applicability=DimensionApplicability.NOT_APPLICABLE,
        rationale="Host says novelty is irrelevant",
        source=DecisionSource.HOST_EXPLICIT,
    )
    task = resolve_task_profile(
        make_intent(policies=(host_policy,)),
        make_profile(),
        created_at=FIXED_TIME,
    )
    assessment = make_assessment(
        candidate,
        default_score=8,
        overrides={DimensionKey.NOVELTY: None},
        model_overall=1,
    )
    aggregate = aggregate_candidate(candidate, assessment, task)
    assert DimensionKey.NOVELTY not in aggregate.normalized_weights
    assert sum(aggregate.normalized_weights.values()) == pytest.approx(1)
    assert aggregate.overall == pytest.approx(8)
    assert aggregate.model_reported_overall_ignored == 1


def test_three_second_hook_is_not_rejected_for_low_completion() -> None:
    candidate = make_candidate("candidate-1", 0, "Immediate synthetic hook")
    intent = make_intent().model_copy(
        update={
            "control_mode": ControlMode.DIRECTED,
            "desired_outcomes": ("three_second_hook",),
            "clip_constraints": ClipConstraints(target_count=1, target_duration_ms=3000),
        }
    )
    task = resolve_task_profile(intent, make_profile(), created_at=FIXED_TIME)
    assessment = make_assessment(
        candidate,
        default_score=7,
        overrides={DimensionKey.HOOK: 9, DimensionKey.COMPLETION: 0},
    )
    aggregate = aggregate_candidate(candidate, assessment, task)
    assert aggregate.required_passed is True
    assert aggregate.advisory_scores[DimensionKey.COMPLETION] == 0


def test_current_task_weights_are_normalized_without_global_gate() -> None:
    candidate = make_candidate("candidate-1", 0, "Complete synthetic point")
    policies = (
        DimensionPolicy(
            dimension=DimensionKey.INSIGHT,
            applicability=DimensionApplicability.WEIGHTED,
            weight=3,
            rationale="Host priority",
            source=DecisionSource.HOST_EXPLICIT,
        ),
        DimensionPolicy(
            dimension=DimensionKey.CLARITY,
            applicability=DimensionApplicability.WEIGHTED,
            weight=1,
            rationale="Host secondary priority",
            source=DecisionSource.HOST_EXPLICIT,
        ),
    )
    task = resolve_task_profile(
        make_intent(policies=policies),
        make_profile(),
        created_at=FIXED_TIME,
    )
    assessment = make_assessment(
        candidate,
        default_score=5,
        overrides={DimensionKey.INSIGHT: 10, DimensionKey.CLARITY: 2},
    )
    aggregate = aggregate_candidate(candidate, assessment, task)
    assert sum(aggregate.normalized_weights.values()) == pytest.approx(1)
    assert aggregate.normalized_weights[DimensionKey.INSIGHT] / aggregate.normalized_weights[
        DimensionKey.CLARITY
    ] == pytest.approx(3)
    assert aggregate.required_passed is True


def test_selector_applies_count_overlap_diversity_and_reports_unsatisfied() -> None:
    candidates = (
        make_candidate("candidate-1", 0, "Alpha unique idea"),
        make_candidate("candidate-2", 1000, "Alpha unique idea"),
        make_candidate("candidate-3", 5000, "Beta different method"),
    )
    task = resolve_task_profile(
        make_intent(constraints=ClipConstraints(minimum_count=3, maximum_count=3)),
        make_profile().model_copy(
            update={
                "tracks": (
                    ContentTrack(
                        track_id="track-1",
                        label="Alpha",
                        topic="Alpha",
                        evidence_refs=("evidence-candidate-1",),
                    ),
                    ContentTrack(
                        track_id="track-2",
                        label="Beta",
                        topic="Beta",
                        evidence_refs=("evidence-candidate-3",),
                    ),
                )
            }
        ),
        created_at=FIXED_TIME,
    )
    assessments = (
        make_assessment(candidates[0], default_score=9, track_id="track-1"),
        make_assessment(candidates[1], default_score=8, track_id="track-1"),
        make_assessment(candidates[2], default_score=7, track_id="track-2"),
    )
    bundle = AssessmentBundle(
        document_type="assessment_bundle",
        created_at=FIXED_TIME,
        created_by="fixture-provider",
        assessment_bundle_id="bundle-1",
        source_id="source-1",
        provider_record_ref="provider-record-1",
        provider_kind="fixture",
        is_fixture=True,
        candidates=assessments,
        input_document_sha256=document_sha256({"fixture": "adaptive"}),
    )
    aggregates = aggregate_bundle(candidates, bundle, task)
    result = select_adaptive(
        candidates,
        assessments,
        aggregates,
        task,
        created_at=FIXED_TIME,
    )
    assert result.selected_candidate_ids == ("candidate-1", "candidate-3")
    assert result.unsatisfied_constraints == ("minimum_count:3",)
    rejected = next(
        decision for decision in result.decisions if decision.candidate_id == "candidate-2"
    )
    assert "overlap_limit" in rejected.reasons


def test_hard_include_bypasses_score_gate_and_soft_target() -> None:
    candidates = (
        make_candidate("candidate-1", 0, "High-scoring candidate"),
        make_candidate("candidate-2", 5000, "Host-required candidate"),
    )
    required = DimensionPolicy(
        dimension=DimensionKey.INSIGHT,
        applicability=DimensionApplicability.REQUIRED,
        minimum=8,
        rationale="Explicit quality floor",
        source=DecisionSource.HOST_EXPLICIT,
    )
    intent = make_intent(
        constraints=ClipConstraints(target_count=1),
        policies=(required,),
    ).model_copy(update={"hard_include_candidate_ids": ("candidate-2",)})
    task = resolve_task_profile(intent, make_profile(), created_at=FIXED_TIME)
    assessments = (
        make_assessment(candidates[0], default_score=9),
        make_assessment(
            candidates[1],
            default_score=9,
            overrides={DimensionKey.INSIGHT: 1},
        ),
    )
    aggregates = tuple(
        aggregate_candidate(candidate, assessment, task)
        for candidate, assessment in zip(candidates, assessments, strict=True)
    )
    result = select_adaptive(candidates, assessments, aggregates, task, created_at=FIXED_TIME)
    assert result.selected_candidate_ids[0] == "candidate-2"
    decision = next(item for item in result.decisions if item.candidate_id == "candidate-2")
    assert decision.reasons == ("host_hard_include",)


@pytest.mark.parametrize(
    ("constraints", "included"),
    [
        (ClipConstraints(maximum_count=1), ("candidate-1", "candidate-2")),
        (ClipConstraints(maximum_duration_ms=2000), ("candidate-1",)),
    ],
)
def test_conflicting_hard_include_requirements_raise_explicit_error(
    constraints: ClipConstraints,
    included: tuple[str, ...],
) -> None:
    candidates = (
        make_candidate("candidate-1", 0, "First"),
        make_candidate("candidate-2", 5000, "Second"),
    )
    intent = make_intent(constraints=constraints).model_copy(
        update={"hard_include_candidate_ids": included}
    )
    task = resolve_task_profile(intent, make_profile(), created_at=FIXED_TIME)
    assessments = tuple(make_assessment(candidate, default_score=8) for candidate in candidates)
    aggregates = tuple(
        aggregate_candidate(candidate, assessment, task)
        for candidate, assessment in zip(candidates, assessments, strict=True)
    )
    with pytest.raises(CutupError) as conflict:
        select_adaptive(candidates, assessments, aggregates, task, created_at=FIXED_TIME)
    assert conflict.value.code is ErrorCode.HOST_INTENT_CONFLICT


def test_multi_track_profile_prefers_diversity_without_rejecting_same_track() -> None:
    candidates = (
        make_candidate("candidate-1", 0, "Best alpha"),
        make_candidate("candidate-2", 5000, "Second alpha"),
        make_candidate("candidate-3", 10000, "Beta"),
    )
    profile = make_profile().model_copy(
        update={
            "tracks": (
                ContentTrack(
                    track_id="track-1",
                    label="Alpha",
                    topic="Alpha",
                    evidence_refs=("evidence-candidate-1",),
                ),
                ContentTrack(
                    track_id="track-2",
                    label="Beta",
                    topic="Beta",
                    evidence_refs=("evidence-candidate-3",),
                ),
            )
        }
    )
    task = resolve_task_profile(
        make_intent(constraints=ClipConstraints(target_count=3)),
        profile,
        created_at=FIXED_TIME,
    )
    assessments = (
        make_assessment(candidates[0], default_score=9, track_id="track-1"),
        make_assessment(candidates[1], default_score=8, track_id="track-1"),
        make_assessment(candidates[2], default_score=7, track_id="track-2"),
    )
    aggregates = tuple(
        aggregate_candidate(candidate, assessment, task)
        for candidate, assessment in zip(candidates, assessments, strict=True)
    )
    result = select_adaptive(candidates, assessments, aggregates, task, created_at=FIXED_TIME)
    assert result.selected_candidate_ids == (
        "candidate-1",
        "candidate-3",
        "candidate-2",
    )
    assert not any("track_diversity" in decision.reasons for decision in result.decisions)


def test_host_can_require_strong_track_diversity() -> None:
    candidates = (
        make_candidate("candidate-1", 0, "Best alpha"),
        make_candidate("candidate-2", 5000, "Second alpha"),
        make_candidate("candidate-3", 10000, "Beta"),
    )
    intent = make_intent(constraints=ClipConstraints(target_count=3)).model_copy(
        update={"require_track_diversity": True}
    )
    task = resolve_task_profile(intent, make_profile(), created_at=FIXED_TIME)
    assessments = (
        make_assessment(candidates[0], default_score=9, track_id="track-1"),
        make_assessment(candidates[1], default_score=8, track_id="track-1"),
        make_assessment(candidates[2], default_score=7, track_id="track-2"),
    )
    aggregates = tuple(
        aggregate_candidate(candidate, assessment, task)
        for candidate, assessment in zip(candidates, assessments, strict=True)
    )
    result = select_adaptive(candidates, assessments, aggregates, task, created_at=FIXED_TIME)
    assert result.selected_candidate_ids == ("candidate-1", "candidate-3")
    rejected = next(
        decision for decision in result.decisions if decision.candidate_id == "candidate-2"
    )
    assert "track_diversity" in rejected.reasons


def test_adaptive_sdk_emits_protocol_valid_cut_plan() -> None:
    candidate = make_candidate("candidate-1", 0, "Protocol-valid adaptive result")
    task = resolve_task_profile(
        make_intent(),
        make_profile(),
        created_at=FIXED_TIME,
    )
    proposals = CandidateProposalBundle(
        document_type="candidate_proposal_bundle",
        created_at=FIXED_TIME,
        created_by="fixture-provider",
        proposal_bundle_id="proposals-1",
        source_id="source-1",
        provider_record_ref="provider-proposal-1",
        provider_kind="fixture",
        is_fixture=True,
        candidates=(candidate,),
        input_document_sha256="b" * 64,
    )
    assessments = AssessmentBundle(
        document_type="assessment_bundle",
        created_at=FIXED_TIME,
        created_by="fixture-provider",
        assessment_bundle_id="assessments-1",
        source_id="source-1",
        provider_record_ref="provider-assessment-1",
        provider_kind="fixture",
        is_fixture=True,
        candidates=(make_assessment(candidate, default_score=8),),
        input_document_sha256="c" * 64,
    )
    aggregates = aggregate_intelligence(
        proposals,
        assessments,
        task,
        created_at=FIXED_TIME,
    )
    selection = select_intelligence(
        proposals,
        assessments,
        aggregates,
        task,
        created_at=FIXED_TIME,
    )
    plan = create_adaptive_plan(
        MediaSource(
            source_id="source-1",
            media_id="media-1",
            kind="video",
            sha256="d" * 64,
            basename_hint="synthetic.mp4",
            rights_attestation=RightsAttestation.OWNED,
        ),
        proposals,
        assessments,
        task,
        selection,
        created_at=FIXED_TIME,
    )
    assert plan.selection_result.selected_candidate_ids == ("candidate-1",)
    assert plan.strategy_records[0].strategy_id == "adaptive-highlight14"
    assert plan.evidence_artifacts[0].artifact_id == "transcript-1"
