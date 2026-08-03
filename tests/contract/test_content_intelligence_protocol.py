from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from universal_cutup.domain.errors import CutupError, ErrorCode
from universal_cutup.domain.intelligence import (
    ALL_DIMENSION_KEYS,
    ClipConstraints,
    ContentDensity,
    ContentProfile,
    ControlMode,
    DecisionSource,
    DependencyProfile,
    DimensionApplicability,
    DimensionKey,
    DimensionPolicy,
    HostIntent,
)

FIXED_TIME = datetime(2026, 7, 30, tzinfo=UTC)


def test_content_profile_is_multilabel_and_supports_tracks() -> None:
    profile = ContentProfile(
        document_type="content_profile",
        created_at=FIXED_TIME,
        created_by="test-suite",
        profile_id="profile-1",
        source_id="source-1",
        content_types=("lecture", "interview"),
        primary_topic="Hybrid teaching discussion",
        structure_types=("exposition", "dialogue"),
        density=ContentDensity(
            narrative=0.2,
            knowledge=0.9,
            procedural=0.3,
            opinion=0.5,
            emotion=0.2,
        ),
        dependencies=DependencyProfile(visual=0.2, audio=0.8, subtitle=0.8),
        confidence=0.8,
        supporting_evidence_refs=("evidence-1",),
    )
    assert profile.content_types == ("lecture", "interview")


def test_host_intent_preserves_raw_instruction_and_rejects_internal_conflict() -> None:
    raw = "Find one three-second hook and avoid controversial content"
    intent = HostIntent(
        document_type="host_intent",
        created_at=FIXED_TIME,
        created_by="test-suite",
        intent_id="intent-1",
        raw_instruction=raw,
        control_mode=ControlMode.DIRECTED,
        clip_constraints=ClipConstraints(target_count=1, target_duration_ms=3000),
    )
    assert intent.raw_instruction == raw
    conflicting = intent.model_dump()
    conflicting["hard_include_candidate_ids"] = ("candidate-1",)
    conflicting["hard_exclude_candidate_ids"] = ("candidate-1",)
    with pytest.raises(CutupError) as conflict:
        HostIntent.model_validate(conflicting)
    assert conflict.value.code is ErrorCode.HOST_INTENT_CONFLICT


def test_dimension_policy_enforces_applicability_semantics() -> None:
    assert len(ALL_DIMENSION_KEYS) == 14
    with pytest.raises(ValidationError):
        DimensionPolicy(
            dimension=DimensionKey.EMOTION,
            applicability=DimensionApplicability.NOT_APPLICABLE,
            weight=1,
            rationale="not used",
            source=DecisionSource.CONTENT_INFERENCE,
        )
    with pytest.raises(ValidationError):
        DimensionPolicy(
            dimension=DimensionKey.CLARITY,
            applicability=DimensionApplicability.REQUIRED,
            rationale="must be clear",
            source=DecisionSource.HOST_EXPLICIT,
        )
