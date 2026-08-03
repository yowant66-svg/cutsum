from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from typer.testing import CliRunner

from universal_cutup.cli import app
from universal_cutup.domain.intelligence import (
    ContentDensity,
    ContentProfile,
    ControlMode,
    DependencyProfile,
    HostIntent,
)

FIXED_TIME = datetime(2026, 7, 30, tzinfo=UTC)
runner = CliRunner()


def test_intelligence_commands_are_discoverable_without_key() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for command in (
        "blind-validate",
        "blind-freeze",
        "blind-verify",
        "blind-reference-open",
        "intelligence-validate",
        "intelligence-resolve",
        "intelligence-aggregate",
        "intelligence-select",
        "intelligence-plan",
    ):
        assert command in result.stdout
        assert runner.invoke(app, [command, "--help"]).exit_code == 0


def test_auto_without_content_profile_returns_provider_boundary(tmp_path: Path) -> None:
    intent = HostIntent(
        document_type="host_intent",
        created_at=FIXED_TIME,
        created_by="test-suite",
        intent_id="intent-auto",
        raw_instruction="",
        control_mode=ControlMode.AUTO,
    )
    path = tmp_path / "intent.json"
    path.write_text(intent.model_dump_json(), encoding="utf-8")
    result = runner.invoke(app, ["intelligence-resolve", str(path)])
    assert result.exit_code == 2
    error = json.loads(result.stderr)
    assert error["code"] == "PROVIDER_REQUIRED"
    assert error["category"] == "provider"
    assert error["recoverable"] is True


def test_validate_and_resolve_strict_local_json(tmp_path: Path) -> None:
    intent = HostIntent(
        document_type="host_intent",
        created_at=FIXED_TIME,
        created_by="test-suite",
        intent_id="intent-guided",
        raw_instruction="Return one clip",
        control_mode=ControlMode.GUIDED,
    )
    profile = ContentProfile(
        document_type="content_profile",
        created_at=FIXED_TIME,
        created_by="host-ai-file",
        profile_id="profile-1",
        source_id="source-1",
        content_types=("lecture",),
        primary_topic="Synthetic local JSON",
        structure_types=("exposition",),
        density=ContentDensity(
            narrative=0.1,
            knowledge=0.9,
            procedural=0.1,
            opinion=0.2,
            emotion=0.1,
        ),
        dependencies=DependencyProfile(visual=0.1, audio=0.9, subtitle=0.8),
        confidence=0.9,
        supporting_evidence_refs=("evidence-1",),
        provider_record_ref="provider-profile-1",
    )
    intent_path = tmp_path / "intent.json"
    profile_path = tmp_path / "profile.json"
    resolved_path = tmp_path / "resolved.json"
    intent_path.write_text(intent.model_dump_json(), encoding="utf-8")
    profile_path.write_text(profile.model_dump_json(), encoding="utf-8")
    validated = runner.invoke(
        app,
        ["intelligence-validate", "content-profile", str(profile_path)],
    )
    assert validated.exit_code == 0
    resolved = runner.invoke(
        app,
        [
            "intelligence-resolve",
            str(intent_path),
            "--content-profile",
            str(profile_path),
            "--output",
            str(resolved_path),
        ],
    )
    assert resolved.exit_code == 0
    assert json.loads(resolved_path.read_text())["document_type"] == "resolved_task_profile"
