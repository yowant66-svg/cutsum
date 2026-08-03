from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from universal_cutup.application.resolution import resolve_task_profile
from universal_cutup.domain.intelligence import (
    ContentDensity,
    ContentProfile,
    ControlMode,
    DependencyProfile,
    HostIntent,
)
from universal_cutup.evaluation.harness import load_scenarios

FIXED_TIME = datetime(2026, 7, 30, tzinfo=UTC)
SCENARIO_PATH = Path(__file__).parents[1] / "fixtures" / "gate_f" / "scenarios.json"


def test_skill_auto_dry_run_produces_core_validated_profile_and_resolution() -> None:
    scenario = next(
        item
        for item in load_scenarios(SCENARIO_PATH)
        if item.scenario_id == "auto-university-lecture"
    )
    intent = HostIntent(
        document_type="host_intent",
        created_at=FIXED_TIME,
        created_by="skill-dry-run",
        intent_id="intent-skill-dry-run",
        raw_instruction=scenario.host_instruction,
        control_mode=ControlMode.AUTO,
    )
    profile = ContentProfile(
        document_type="content_profile",
        created_at=FIXED_TIME,
        created_by="skill-dry-run-fixture",
        profile_id="profile-skill-dry-run",
        source_id="source-skill-dry-run",
        content_types=scenario.expected_content_types,
        primary_topic="Feedback loops",
        structure_types=("definition_example_conclusion",),
        value_sources=("definition", "example", "conclusion"),
        density=ContentDensity(
            narrative=0.1,
            knowledge=0.9,
            procedural=0.2,
            opinion=0.2,
            emotion=0.1,
        ),
        dependencies=DependencyProfile(visual=0.2, audio=0.9, subtitle=0.8),
        confidence=0.9,
        supporting_evidence_refs=("segment-1", "segment-2", "segment-3"),
        provider_record_ref="provider-skill-dry-run",
    )
    resolved = resolve_task_profile(intent, profile, created_at=FIXED_TIME)
    assert resolved.control_mode is ControlMode.AUTO
    assert resolved.content_profile_id == profile.profile_id
    assert len(resolved.dimension_policies) == 14
    assert len(resolved.resolution_trace) >= 16
