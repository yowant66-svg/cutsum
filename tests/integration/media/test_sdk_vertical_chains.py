from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from typer.testing import CliRunner

from universal_cutup.adapters.transcripts import TranscriptParseContext, parse_srt
from universal_cutup.application.sdk import (
    analyze_transcript,
    create_plan,
    inspect_source,
    run_full_offline,
)
from universal_cutup.cli import app
from universal_cutup.domain.sources import RightsAttestation
from universal_cutup.domain.specs import OutputSpec, SubtitleMode, SubtitleSpec
from universal_cutup.domain.sports import (
    SportsEventType,
    SportsModality,
    SportsObservation,
    SportsObservationBundle,
    SportsObservationType,
    SportsTemporalRole,
)
from universal_cutup.domain.transcript import TranscriptArtifact


def _transcript(source_id: str) -> TranscriptArtifact:
    return parse_srt(
        (
            "1\n00:00:00,500 --> 00:00:01,500\nFirst offline segment\n\n"
            "2\n00:00:01,500 --> 00:00:02,500\nSecond offline segment\n"
        ),
        context=TranscriptParseContext(
            transcript_id="transcript-sdk",
            source_id=source_id,
            created_at=datetime(2026, 7, 30, tzinfo=UTC),
            created_by="test-suite",
        ),
    )


def test_inspect_analyze_plan_chain(synthetic_media: Path) -> None:
    inspection = inspect_source(synthetic_media, source_id="source-sdk")
    transcript = _transcript(inspection.source.source_id)
    analysis = analyze_transcript(transcript)
    plan = create_plan(inspection.source, transcript)
    assert inspection.has_video is True
    assert analysis.segment_count == 2
    assert len(plan.strategy_records) == 3
    assert len(plan.candidates) == 2


def test_full_offline_sidecar_chain(synthetic_media: Path, tmp_path: Path) -> None:
    transcript = _transcript("source-full")
    result = run_full_offline(
        synthetic_media,
        transcript,
        output_root=tmp_path / "full-output",
        rights_attestation=RightsAttestation.OWNED,
        output_spec=OutputSpec(subtitle=SubtitleSpec(mode=SubtitleMode.SOURCE_SIDECAR)),
    )
    assert result.execution.status == "success"
    assert len(result.execution.steps) == 2
    assert {artifact.artifact_type for artifact in result.execution.artifacts} == {
        "video",
        "subtitle",
    }


def test_analysis_only_chain_has_no_media_side_effects(
    synthetic_media: Path,
    tmp_path: Path,
) -> None:
    inspection = inspect_source(synthetic_media, source_id="source-analysis")
    transcript = _transcript(inspection.source.source_id)
    analysis = analyze_transcript(transcript)
    assert analysis.duration_ms == 2500
    assert not (tmp_path / "output").exists()


def test_cli_inspect_plan_and_full_dry_run(
    synthetic_media: Path,
    tmp_path: Path,
) -> None:
    transcript_path = tmp_path / "input.srt"
    transcript_path.write_text(
        "1\n00:00:00,500 --> 00:00:01,500\nCLI offline segment\n",
        encoding="utf-8",
    )
    runner = CliRunner()
    inspected = runner.invoke(app, ["inspect", str(synthetic_media)])
    assert inspected.exit_code == 0
    plan_path = tmp_path / "plan.json"
    planned = runner.invoke(
        app,
        [
            "plan",
            str(synthetic_media),
            str(transcript_path),
            "--output",
            str(plan_path),
            "--rights",
            "owned",
        ],
    )
    assert planned.exit_code == 0
    assert plan_path.exists()
    full = runner.invoke(
        app,
        [
            "full",
            str(synthetic_media),
            str(transcript_path),
            str(tmp_path / "dry-output"),
            "--dry-run",
        ],
    )
    assert full.exit_code == 0
    assert not (tmp_path / "dry-output").exists()
    cut_output = tmp_path / "cut-output"
    cut = runner.invoke(
        app,
        ["cut", str(plan_path), str(synthetic_media), str(cut_output)],
    )
    assert cut.exit_code == 0
    assert (cut_output / "execution-record.json").exists()


def test_cli_inspect_rejects_corrupt_media_with_structured_error(tmp_path: Path) -> None:
    corrupt_media = tmp_path / "损坏 input file.mp4"
    corrupt_media.write_bytes(b"this is not a media container")
    runner = CliRunner()

    inspected = runner.invoke(app, ["inspect", str(corrupt_media)])

    assert inspected.exit_code == 2
    payload = json.loads(inspected.stderr)
    assert payload["code"] == "MEDIA_PROCESS_FAILED"
    assert payload["category"] == "media"
    assert payload["step"] == "probe"
    assert str(tmp_path) not in inspected.stderr


def test_cli_education_and_sports_planning_share_sdk_workflows(
    synthetic_media: Path,
    tmp_path: Path,
) -> None:
    runner = CliRunner()
    transcript_path = tmp_path / "education.srt"
    transcript_path.write_text(
        (
            "1\n00:00:00,000 --> 00:00:02,000\n"
            "Definition: an algorithm is a precise procedure for solving a problem.\n\n"
            "2\n00:00:02,000 --> 00:00:04,000\n"
            "For example, binary search repeatedly halves the remaining search space.\n"
        ),
        encoding="utf-8",
    )
    education_plan = tmp_path / "education-plan.json"
    education = runner.invoke(
        app,
        [
            "education-plan",
            str(synthetic_media),
            str(transcript_path),
            "--instruction",
            "只要一个定义",
            "--mode",
            "directed",
            "--output",
            str(education_plan),
        ],
    )
    assert education.exit_code == 0, education.stderr
    education_payload = json.loads(education.stdout)
    assert education_payload["request"]["control_mode"] == "directed"
    assert education_payload["plan"]["document_type"] == "cut_plan"
    assert education_plan.exists()

    source_id = "source-cli-sports"
    provider_record_id = "provider-cli-sports"
    sports_bundle = SportsObservationBundle(
        document_type="sports_observation_bundle",
        created_at=datetime(2026, 7, 31, tzinfo=UTC),
        created_by="sdk-cli-test",
        bundle_id="bundle-cli-sports",
        source_id=source_id,
        provider_kind="fixture",
        provider_record_refs=(provider_record_id,),
        observations=(
            SportsObservation(
                observation_id="sports-motion",
                source_id=source_id,
                observation_type=SportsObservationType.MOTION_BURST,
                modality=SportsModality.VIDEO,
                temporal_role=SportsTemporalRole.ACTION,
                start_ms=1000,
                end_ms=1500,
                confidence=0.9,
                label="scoring action",
                event_type_hint=SportsEventType.SCORE,
                correlation_key="score-1",
                provider_record_ref=provider_record_id,
            ),
            SportsObservation(
                observation_id="sports-commentary",
                source_id=source_id,
                observation_type=SportsObservationType.COMMENTATOR_EMPHASIS,
                modality=SportsModality.TEXT,
                temporal_role=SportsTemporalRole.REACTION,
                start_ms=1300,
                end_ms=1800,
                confidence=0.9,
                label="goal call",
                event_type_hint=SportsEventType.SCORE,
                correlation_key="score-1",
                provider_record_ref=provider_record_id,
            ),
        ),
    )
    observations_path = tmp_path / "sports-observations.json"
    observations_path.write_text(sports_bundle.model_dump_json(), encoding="utf-8")
    sports_plan = tmp_path / "sports-plan.json"
    sports = runner.invoke(
        app,
        [
            "sports-plan",
            str(synthetic_media),
            str(observations_path),
            "--instruction",
            "只要一个进球，不要回放",  # noqa: RUF001
            "--mode",
            "directed",
            "--output",
            str(sports_plan),
        ],
    )
    assert sports.exit_code == 0, sports.stderr
    sports_payload = json.loads(sports.stdout)
    assert sports_payload["request"]["control_mode"] == "directed"
    assert sports_payload["selection"]["selected_candidate_ids"]
    assert sports_payload["plan"]["provider_records"][0]["provider_record_id"] == provider_record_id
    assert sports_plan.exists()


def test_cli_sports_transcript_plan_executes_playable_clip(
    synthetic_media: Path,
    tmp_path: Path,
) -> None:
    transcript_path = tmp_path / "basketball.srt"
    transcript_path.write_text(
        (
            "1\n00:00:00,500 --> 00:00:01,500\n"
            "BUZZER BEATER! The game winner drops as time expires!\n\n"
            "2\n00:00:02,000 --> 00:00:03,000\n"
            "What a block at the rim!\n"
        ),
        encoding="utf-8",
    )
    plan_path = tmp_path / "sports-text-plan.json"
    runner = CliRunner()

    planned = runner.invoke(
        app,
        [
            "sports-transcript-plan",
            str(synthetic_media),
            str(transcript_path),
            "basketball",
            "--instruction",
            "只要一个绝杀。",
            "--mode",
            "directed",
            "--rights",
            "owned",
            "--output",
            str(plan_path),
        ],
    )

    assert planned.exit_code == 0, planned.stderr
    payload = json.loads(planned.stdout)
    assert payload["observations"]["provider_kind"] == "local_detector"
    assert payload["selection"]["selected_candidate_ids"]
    output_root = tmp_path / "sports-text-output"
    cut = runner.invoke(
        app,
        ["cut", str(plan_path), str(synthetic_media), str(output_root)],
    )
    assert cut.exit_code == 0, cut.stderr
    execution = json.loads(cut.stdout)
    assert execution["status"] == "success"
    assert execution["provider_records"][0]["provider_id"] == "sports-text-basketball"
    assert any(artifact["artifact_type"] == "video" for artifact in execution["artifacts"])
