from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from universal_cutup.cli import app
from universal_cutup.domain.errors import CutupError
from universal_cutup.sdk import require_operation

runner = CliRunner()


def test_cli_exposes_all_gate_e1_commands() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "CutSum offline media planning and execution engine" in result.stdout
    for command in (
        "inspect",
        "analyze",
        "propose",
        "score",
        "plan",
        "cut",
        "subtitle",
        "subtitle-capabilities",
        "capabilities",
        "education-plan",
        "sports-plan",
        "sports-transcript-plan",
        "transcribe",
        "translate",
        "reframe",
        "package",
        "full",
    ):
        assert command in result.stdout


def test_provider_and_capability_stubs_use_stable_json_errors() -> None:
    transcribe_result = runner.invoke(app, ["transcribe"])
    assert transcribe_result.exit_code == 2
    transcribe_error = json.loads(transcribe_result.stderr)
    try:
        require_operation("transcribe")
    except CutupError as sdk_error:
        assert transcribe_error == sdk_error.as_dict()
    else:
        raise AssertionError("transcribe must require a provider")

    package_result = runner.invoke(app, ["package"])
    assert package_result.exit_code == 3
    package_error = json.loads(package_result.stderr)
    assert package_error["code"] == "CAPABILITY_UNAVAILABLE"
    assert package_error["step"] == "package"
    assert package_error["details"]["operation"] == "package"


def test_cli_capabilities_match_sdk_operation_states() -> None:
    result = runner.invoke(app, ["capabilities"])

    assert result.exit_code == 0
    operations = {item["operation"]: item for item in json.loads(result.stdout)["operations"]}
    assert operations["education_plan"]["state"] == "available"
    assert operations["sports_plan"]["state"] == "available"
    assert operations["sports_transcript_plan"]["state"] == "available"
    assert operations["transcribe"]["state"] == "provider_required"
    assert operations["package"]["state"] == "unavailable"


def test_subtitle_capabilities_reports_explicit_backend() -> None:
    result = runner.invoke(app, ["subtitle-capabilities"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["sidecar_available"] is True
    assert payload["selected_backend"] in {
        "ffmpeg-libass",
        "macos-system-overlay",
        "unavailable",
    }


def test_analyze_writes_only_json_to_stdout(tmp_path: Path) -> None:
    transcript_path = tmp_path / "sample.srt"
    transcript_path.write_text(
        "1\n00:00:00,000 --> 00:00:01,000\nOffline cue\n",
        encoding="utf-8",
    )
    result = runner.invoke(app, ["analyze", str(transcript_path)])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["segment_count"] == 1
    assert payload["character_count"] == len("Offline cue")


def test_deterministic_commands_and_reframe_none(tmp_path: Path) -> None:
    transcript_path = tmp_path / "sample.vtt"
    transcript_path.write_text(
        "WEBVTT\n\ncue-a\n00:00.000 --> 00:01.000\nOffline cue\n",
        encoding="utf-8",
    )
    for command in ("propose", "score"):
        result = runner.invoke(app, [command, str(transcript_path)])
        assert result.exit_code == 0
        assert len(json.loads(result.stdout)) == 1
    reframe_result = runner.invoke(app, ["reframe", "--mode", "none"])
    assert reframe_result.exit_code == 0
    assert json.loads(reframe_result.stdout)["available"] is True
    center_crop = runner.invoke(app, ["reframe", "--mode", "center_crop"])
    assert center_crop.exit_code == 0
    assert json.loads(center_crop.stdout)["available"] is True
    unsupported = runner.invoke(app, ["reframe", "--mode", "tracked_focus"])
    assert unsupported.exit_code == 3
    error = json.loads(unsupported.stderr)
    assert error["step"] == "reframe"
    assert error["details"]["requested_mode"] == "tracked_focus"
