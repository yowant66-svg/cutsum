from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

import pytest
from typer.testing import CliRunner

from universal_cutup.cli import app
from universal_cutup.domain.candidates import (
    CutCandidate,
    EvidenceArtifactIdentity,
    EvidenceRef,
)
from universal_cutup.domain.plans import CutPlan
from universal_cutup.domain.selection import (
    SelectionDecision,
    SelectionResult,
    SelectionStatus,
)
from universal_cutup.domain.sources import (
    MediaBinding,
    MediaSource,
    RightsAttestation,
)
from universal_cutup.domain.specs import (
    OutputSpec,
    ReframeSafeAreaPreset,
    ReframeSpec,
    RenderSpec,
    SubtitleMode,
    SubtitleSafeAreaPreset,
    SubtitleSafeAreaSpec,
    SubtitleSidecarFormat,
    SubtitleSpec,
)
from universal_cutup.domain.transcript import SubtitleCue
from universal_cutup.media.executor import execute_external_plan
from universal_cutup.media.probe import probe_media
from universal_cutup.sdk import configure_reframe


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _plan(source_path: Path) -> CutPlan:
    evidence = EvidenceRef(
        evidence_id="evidence-vertical",
        artifact_id="transcript-vertical",
        segment_ids=("segment-vertical",),
        start_ms=500,
        end_ms=2500,
        text_sha256="a" * 64,
        snapshot="Vertical synthetic subtitle",
    )
    candidate = CutCandidate(
        candidate_id="candidate-vertical",
        source_id="source-vertical",
        start_ms=500,
        end_ms=2500,
        summary="Vertical synthetic subtitle",
        evidence_refs=(evidence,),
        subtitle_cues=(
            SubtitleCue(
                cue_id="cue-vertical",
                source_id="source-vertical",
                start_ms=500,
                end_ms=2500,
                text="Vertical safe-area subtitle",
                source_segment_ids=("segment-vertical",),
            ),
        ),
    )
    return CutPlan(
        document_type="cut_plan",
        created_at=datetime(2026, 8, 1, tzinfo=UTC),
        created_by="vertical-reframe-test",
        plan_id="plan-vertical",
        source=MediaSource(
            source_id="source-vertical",
            media_id="media-vertical",
            kind="video",
            sha256=_file_hash(source_path),
            basename_hint=source_path.name,
            rights_attestation=RightsAttestation.OWNED,
        ),
        evidence_artifacts=(
            EvidenceArtifactIdentity(
                artifact_id="transcript-vertical",
                source_id="source-vertical",
                segment_ids=("segment-vertical",),
            ),
        ),
        candidates=(candidate,),
        selection_result=SelectionResult(
            selection_id="selection-vertical",
            selection_strategy_id="external",
            selection_strategy_version="0.1.0",
            decisions=(
                SelectionDecision(
                    candidate_id=candidate.candidate_id,
                    status=SelectionStatus.SELECTED,
                    reason="vertical test",
                    evidence_refs=(evidence.evidence_id,),
                ),
            ),
        ),
    )


@pytest.mark.parametrize(
    ("reframe", "expected_crop", "expected_reason"),
    [
        (ReframeSpec(mode="center_crop"), (108, 0, 102, 180), "center_crop"),
        (
            ReframeSpec(mode="manual_focus", focus_x=0.2, focus_y=0.4),
            (12, 0, 102, 180),
            "manual_focus_centered",
        ),
        (
            ReframeSpec(mode="fit_background"),
            None,
            "fit_full_frame_over_blurred_background",
        ),
        (
            ReframeSpec(
                mode="fixed_subject",
                safe_area_preset=ReframeSafeAreaPreset.YOUTUBE_SHORTS,
            ),
            (108, 0, 102, 180),
            "fixed_subject_assumed_focus_no_detection",
        ),
    ],
)
def test_four_basic_reframe_modes_render_playable_vertical_media(
    synthetic_media: Path,
    tmp_path: Path,
    reframe: ReframeSpec,
    expected_crop: tuple[int, int, int, int] | None,
    expected_reason: str,
) -> None:
    plan = _plan(synthetic_media).model_copy(
        update={
            "output_spec": OutputSpec(
                render=RenderSpec(
                    target_width=180,
                    target_height=320,
                    allow_upscale=True,
                    duration_tolerance_ms=200,
                ),
                reframe=reframe,
            )
        }
    )
    output_root = tmp_path / reframe.mode

    execution = execute_external_plan(
        plan,
        binding=MediaBinding(source_id=plan.source.source_id, local_path=str(synthetic_media)),
        output_root=output_root,
    )

    assert execution.status == "success"
    artifact = next(item for item in execution.artifacts if item.artifact_type == "video")
    output_path = output_root / artifact.relative_path
    output_probe = probe_media(output_path)
    assert (output_probe.width, output_probe.height) == (180, 320)
    assert artifact.actual_output_resolution == "180x320"
    assert artifact.reframe_mode == reframe.mode
    assert artifact.crop_box == expected_crop
    assert artifact.composition_reason == expected_reason
    assert output_path.stat().st_size > 0


def test_vertical_ass_sidecar_uses_output_canvas_and_platform_safe_area(
    synthetic_media: Path,
    tmp_path: Path,
) -> None:
    base = _plan(synthetic_media)
    plan = base.model_copy(
        update={
            "output_spec": OutputSpec(
                render=RenderSpec(
                    target_width=180,
                    target_height=320,
                    allow_upscale=True,
                    duration_tolerance_ms=200,
                ),
                reframe=ReframeSpec(
                    mode="fixed_subject",
                    safe_area_preset=ReframeSafeAreaPreset.YOUTUBE_SHORTS,
                ),
                subtitle=SubtitleSpec(
                    mode=SubtitleMode.SOURCE_SIDECAR,
                    sidecar_format=SubtitleSidecarFormat.ASS,
                    safe_area=SubtitleSafeAreaSpec(
                        preset=SubtitleSafeAreaPreset.YOUTUBE_SHORTS,
                    ),
                ),
            )
        }
    )
    output_root = tmp_path / "safe-area"

    execution = execute_external_plan(
        plan,
        binding=MediaBinding(source_id=plan.source.source_id, local_path=str(synthetic_media)),
        output_root=output_root,
    )

    assert execution.status == "success"
    sidecar = (output_root / "subtitles/candidate-vertical.ass").read_text(encoding="utf-8")
    assert "PlayResX: 180" in sidecar
    assert "PlayResY: 320" in sidecar
    video = next(item for item in execution.artifacts if item.artifact_type == "video")
    assert video.safe_area == (9, 38, 171, 256)


def test_vertical_burn_in_remains_playable_inside_safe_area(
    synthetic_media: Path,
    tmp_path: Path,
) -> None:
    base = _plan(synthetic_media)
    plan = base.model_copy(
        update={
            "output_spec": OutputSpec(
                render=RenderSpec(
                    target_width=180,
                    target_height=320,
                    allow_upscale=True,
                    duration_tolerance_ms=200,
                ),
                reframe=ReframeSpec(
                    mode="fixed_subject",
                    safe_area_preset=ReframeSafeAreaPreset.YOUTUBE_SHORTS,
                ),
                subtitle=SubtitleSpec(
                    mode=SubtitleMode.SOURCE_BURN_IN,
                    safe_area=SubtitleSafeAreaSpec(
                        preset=SubtitleSafeAreaPreset.YOUTUBE_SHORTS,
                    ),
                ),
            )
        }
    )
    output_root = tmp_path / "burn-in"

    execution = execute_external_plan(
        plan,
        binding=MediaBinding(source_id=plan.source.source_id, local_path=str(synthetic_media)),
        output_root=output_root,
    )

    assert execution.status == "success"
    assert execution.steps[0].details["subtitle_backend"] in {
        "ffmpeg-libass",
        "macos-system-overlay",
    }
    video = next(item for item in execution.artifacts if item.artifact_type == "video")
    probe = probe_media(output_root / video.relative_path)
    assert (probe.width, probe.height) == (180, 320)


def test_sdk_and_cli_derive_new_reframe_plan_without_mutating_original(
    synthetic_media: Path,
    tmp_path: Path,
) -> None:
    original = _plan(synthetic_media)
    reframe_spec = ReframeSpec(
        mode="manual_focus",
        focus_x=0.2,
        focus_y=0.4,
        safe_area_preset=ReframeSafeAreaPreset.TIKTOK,
    )
    derived = configure_reframe(
        original,
        reframe_spec,
        render_spec=RenderSpec(
            target_width=180,
            target_height=320,
            allow_upscale=True,
        ),
        created_at=datetime(2026, 8, 1, tzinfo=UTC),
    )

    assert original.output_spec.reframe.mode == "none"
    assert derived.derived_from_plan_id == original.plan_id
    assert derived.plan_id != original.plan_id
    assert derived.output_spec.reframe == reframe_spec
    assert derived.output_spec.subtitle.safe_area.preset == SubtitleSafeAreaPreset.TIKTOK

    original_path = tmp_path / "original-plan.json"
    derived_path = tmp_path / "derived-plan.json"
    original_path.write_text(original.model_dump_json(), encoding="utf-8")
    cli_result = CliRunner().invoke(
        app,
        [
            "reframe",
            "--mode",
            "manual_focus",
            "--plan",
            str(original_path),
            "--output",
            str(derived_path),
            "--focus-x",
            "0.2",
            "--focus-y",
            "0.4",
            "--safe-area",
            "tiktok",
            "--target-width",
            "180",
            "--target-height",
            "320",
            "--allow-upscale",
        ],
    )

    assert cli_result.exit_code == 0, cli_result.stderr
    cli_plan = CutPlan.model_validate_json(derived_path.read_text(encoding="utf-8"))
    assert cli_plan.derived_from_plan_id == original.plan_id
    assert cli_plan.output_spec.reframe == reframe_spec
