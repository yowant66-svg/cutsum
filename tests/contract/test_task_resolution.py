from __future__ import annotations

from datetime import UTC, datetime

import pytest

from universal_cutup.application.resolution import resolve_task_profile
from universal_cutup.domain.errors import CutupError, ErrorCode
from universal_cutup.domain.intelligence import (
    CapabilityProfile,
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
    DurationSource,
    HostIntent,
    ResolvedTaskProfile,
    TaskPreset,
)

FIXED_TIME = datetime(2026, 7, 30, tzinfo=UTC)


def make_intent(
    mode: ControlMode = ControlMode.AUTO,
    *,
    outcomes: tuple[str, ...] = (),
    policies: tuple[DimensionPolicy, ...] = (),
) -> HostIntent:
    return HostIntent(
        document_type="host_intent",
        created_at=FIXED_TIME,
        created_by="test-suite",
        intent_id="intent-1",
        raw_instruction="",
        control_mode=mode,
        desired_outcomes=outcomes,
        dimension_policies=policies,
    )


def make_profile(*content_types: str) -> ContentProfile:
    return ContentProfile(
        document_type="content_profile",
        created_at=FIXED_TIME,
        created_by="fixture-provider",
        profile_id="profile-1",
        source_id="source-1",
        content_types=content_types,
        primary_topic="Synthetic topic",
        structure_types=("synthetic",),
        value_sources=("retain_source_value",),
        density=ContentDensity(
            narrative=0.5,
            knowledge=0.5,
            procedural=0.5,
            opinion=0.5,
            emotion=0.5,
        ),
        dependencies=DependencyProfile(visual=0.2, audio=0.8, subtitle=0.8),
        confidence=0.9,
        supporting_evidence_refs=("evidence-1",),
    )


def policy_map(resolved: ResolvedTaskProfile) -> dict[DimensionKey, DimensionPolicy]:
    return {policy.dimension: policy for policy in resolved.dimension_policies}


def test_auto_profiles_adapt_to_course_story_and_manual() -> None:
    course = resolve_task_profile(make_intent(), make_profile("lecture"), created_at=FIXED_TIME)
    story = resolve_task_profile(make_intent(), make_profile("story"), created_at=FIXED_TIME)
    manual = resolve_task_profile(make_intent(), make_profile("manual"), created_at=FIXED_TIME)
    assert policy_map(course)[DimensionKey.INSIGHT].applicability == "weighted"
    assert policy_map(story)[DimensionKey.EMOTION].applicability == "weighted"
    assert story.selection_policy.preserve_time_order is True
    assert policy_map(manual)[DimensionKey.SUBTITLE_RELIABILITY].applicability == "weighted"


def test_auto_uses_content_inferred_objectives_and_clip_constraints() -> None:
    profile = make_profile("interview").model_copy(
        update={
            "auto_objectives": ("representative_leadership_insights",),
            "auto_clip_constraints": ClipConstraints(
                minimum_count=2,
                maximum_count=2,
                target_count=2,
                minimum_duration_ms=30_000,
                maximum_duration_ms=150_000,
            ),
        }
    )
    resolved = resolve_task_profile(make_intent(), profile, created_at=FIXED_TIME)
    assert resolved.final_objectives == ("representative_leadership_insights",)
    assert resolved.hard_constraints.target_count == 2
    traces = {entry.decision_path: entry for entry in resolved.resolution_trace}
    assert traces["final_objectives"].source is DecisionSource.CONTENT_INFERENCE
    assert traces["hard_constraints"].source is DecisionSource.CONTENT_INFERENCE


def test_guided_host_constraints_override_content_recommendations_field_by_field() -> None:
    profile = make_profile("lecture").model_copy(
        update={
            "auto_clip_constraints": ClipConstraints(
                target_count=3,
                minimum_duration_ms=30_000,
                maximum_duration_ms=180_000,
            )
        }
    )
    intent = make_intent(ControlMode.GUIDED).model_copy(
        update={"clip_constraints": ClipConstraints(target_count=1)}
    )
    resolved = resolve_task_profile(intent, profile, created_at=FIXED_TIME)
    assert resolved.hard_constraints.target_count == 1
    assert resolved.hard_constraints.minimum_duration_ms == 30_000
    traces = {entry.decision_path: entry for entry in resolved.resolution_trace}
    assert traces["hard_constraints"].source is DecisionSource.HOST_EXPLICIT


def test_explicit_hook_does_not_inherit_false_completion_gate() -> None:
    resolved = resolve_task_profile(
        make_intent(ControlMode.DIRECTED, outcomes=("three_second_hook",)),
        make_profile("lecture"),
        created_at=FIXED_TIME,
    )
    policies = policy_map(resolved)
    assert policies[DimensionKey.HOOK].applicability == "required"
    assert policies[DimensionKey.COMPLETION].applicability == "advisory"


def test_priority_is_explicit_then_preset_then_content() -> None:
    explicit = DimensionPolicy(
        dimension=DimensionKey.EMOTION,
        applicability=DimensionApplicability.NOT_APPLICABLE,
        rationale="host excludes emotional framing",
        source=DecisionSource.HOST_EXPLICIT,
    )
    preset = TaskPreset(
        preset_id="test-preset",
        objectives=("preset_objective",),
        dimension_policies=(
            DimensionPolicy(
                dimension=DimensionKey.EMOTION,
                applicability=DimensionApplicability.WEIGHTED,
                weight=2,
                rationale="preset",
                source=DecisionSource.HOST_PRESET,
            ),
        ),
    )
    resolved = resolve_task_profile(
        make_intent(ControlMode.GUIDED, policies=(explicit,)),
        make_profile("story"),
        preset=preset,
        created_at=FIXED_TIME,
    )
    assert resolved.final_objectives == ("preset_objective",)
    assert policy_map(resolved)[DimensionKey.EMOTION].source is DecisionSource.HOST_EXPLICIT
    assert "overrides content inference" in resolved.warnings[0]


def test_auto_requires_profile_and_capability_conflicts_are_explicit() -> None:
    with pytest.raises(CutupError) as missing:
        resolve_task_profile(make_intent(), None)
    assert missing.value.code is ErrorCode.PROVIDER_REQUIRED

    intent = make_intent(ControlMode.DIRECTED).model_copy(
        update={"visual_requirements": ("tracked_focus",)}
    )
    with pytest.raises(CutupError) as conflict:
        resolve_task_profile(
            intent,
            None,
            capability_profile=CapabilityProfile(unavailable_features=("tracked_focus",)),
        )
    assert conflict.value.code is ErrorCode.CAPABILITY_CONFLICT


def test_resolution_trace_records_all_dimension_sources() -> None:
    resolved = resolve_task_profile(make_intent(), make_profile("lecture"), created_at=FIXED_TIME)
    paths = {entry.decision_path for entry in resolved.resolution_trace}
    assert len(resolved.dimension_policies) == 14
    for dimension in DimensionKey:
        assert f"dimension_policies.{dimension.value}" in paths
    assert {
        "hard_constraints",
        "prohibited_outcomes",
        "candidate_policy.allow_context_dependency",
        "selection_policy.prefer_track_diversity",
        "selection_policy.require_track_diversity",
        "selection_policy.maximum_overlap_ratio",
        "selection_policy.duplicate_similarity_threshold",
        "capability_profile",
        "semantic_requirements",
    } <= paths


def test_auto_duration_contract_defaults_to_sixty_seconds_and_caps_at_two_minutes() -> None:
    resolved = resolve_task_profile(
        make_intent(ControlMode.AUTO),
        make_profile("lecture"),
        created_at=FIXED_TIME,
    )
    constraints = resolved.hard_constraints
    assert constraints.preferred_duration_ms == 60_000
    assert constraints.default_max_duration_ms == 60_000
    assert constraints.absolute_auto_max_duration_ms == 120_000
    assert constraints.maximum_duration_ms == 120_000
    assert constraints.duration_source is DurationSource.DEFAULT_POLICY


def test_directed_explicit_three_minutes_is_preserved_and_disclosed() -> None:
    intent = make_intent(ControlMode.DIRECTED).model_copy(
        update={
            "clip_constraints": ClipConstraints(
                target_count=1,
                target_duration_ms=180_000,
                maximum_duration_ms=180_000,
            )
        }
    )
    resolved = resolve_task_profile(intent, make_profile("lecture"), created_at=FIXED_TIME)
    assert resolved.hard_constraints.maximum_duration_ms == 180_000
    assert resolved.hard_constraints.host_requested_duration_ms == 180_000
    assert resolved.hard_constraints.duration_source is DurationSource.HOST_EXPLICIT


def test_definition_outcome_becomes_verifiable_semantic_requirement() -> None:
    intent = make_intent(
        ControlMode.DIRECTED,
        outcomes=("two_review_definitions",),
    ).model_copy(update={"clip_constraints": ClipConstraints(target_count=2, minimum_count=2)})
    resolved = resolve_task_profile(intent, make_profile("lecture"), created_at=FIXED_TIME)
    assert resolved.semantic_requirements is not None
    assert resolved.semantic_requirements.semantic_type == "definition"
    assert resolved.semantic_requirements.required_count == 2


def test_track_diversity_is_soft_until_host_or_preset_requires_it() -> None:
    profile = make_profile("interview").model_copy(
        update={
            "tracks": (
                ContentTrack(
                    track_id="track-1",
                    label="First",
                    topic="First",
                    evidence_refs=("evidence-1",),
                ),
                ContentTrack(
                    track_id="track-2",
                    label="Second",
                    topic="Second",
                    evidence_refs=("evidence-1",),
                ),
            )
        }
    )
    default = resolve_task_profile(make_intent(), profile, created_at=FIXED_TIME)
    assert default.selection_policy.prefer_track_diversity is True
    assert default.selection_policy.require_track_diversity is False

    preset = resolve_task_profile(
        make_intent(),
        profile,
        preset=TaskPreset(preset_id="strict", require_track_diversity=True),
        created_at=FIXED_TIME,
    )
    assert preset.selection_policy.require_track_diversity is True

    host = resolve_task_profile(
        make_intent().model_copy(update={"require_track_diversity": False}),
        profile,
        preset=TaskPreset(preset_id="strict", require_track_diversity=True),
        created_at=FIXED_TIME,
    )
    assert host.selection_policy.require_track_diversity is False
