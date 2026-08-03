from __future__ import annotations

import pytest

from universal_cutup.domain.errors import CutupError, ErrorCode
from universal_cutup.domain.specs import (
    ReframeSafeAreaPreset,
    ReframeSpec,
    RenderSpec,
    ResolutionMode,
)
from universal_cutup.media.rendering import resolve_reframe


def test_reframe_spec_distinguishes_manual_fixed_and_unused_focus() -> None:
    with pytest.raises(ValueError, match="manual_focus"):
        ReframeSpec(mode="manual_focus")
    with pytest.raises(ValueError, match="both focus"):
        ReframeSpec(mode="fixed_subject", focus_x=0.4)
    with pytest.raises(ValueError, match="does not use focus"):
        ReframeSpec(mode="center_crop", focus_x=0.5, focus_y=0.5)

    assert ReframeSpec(mode="fixed_subject").mode == "fixed_subject"
    assert ReframeSpec(mode="manual_focus", focus_x=0.2, focus_y=0.4).focus_x == 0.2
    edge_focus = ReframeSpec(mode="fixed_subject", focus_x=0.0, focus_y=0.0)
    assert resolve_reframe(
        RenderSpec(), edge_focus, source_width=1920, source_height=1080
    ).source_focus == (0.0, 0.0)


def test_center_crop_is_vertical_without_silent_upscale() -> None:
    decision = resolve_reframe(
        RenderSpec(resolution_mode=ResolutionMode.P720),
        ReframeSpec(mode="center_crop"),
        source_width=1920,
        source_height=1080,
    )

    assert (decision.resolution.output_width, decision.resolution.output_height) == (608, 1080)
    assert decision.resolution.upscale is False
    assert decision.crop_box == (656, 0, 608, 1080)
    assert decision.video_filter == "crop=608:1080:656:0,scale=608:1080"
    assert decision.composition_reason == "center_crop"


def test_manual_focus_changes_horizontal_crop_and_records_focus() -> None:
    decision = resolve_reframe(
        RenderSpec(resolution_mode=ResolutionMode.P720),
        ReframeSpec(mode="manual_focus", focus_x=0.2, focus_y=0.4),
        source_width=1920,
        source_height=1080,
    )

    assert decision.crop_box == (80, 0, 608, 1080)
    assert decision.source_focus == (0.2, 0.4)
    assert decision.output_anchor == (0.5, 0.5)
    assert decision.composition_reason == "manual_focus_centered"


def test_fixed_subject_uses_safe_upper_third_without_claiming_detection() -> None:
    decision = resolve_reframe(
        RenderSpec(resolution_mode=ResolutionMode.P720),
        ReframeSpec(
            mode="fixed_subject",
            safe_area_preset=ReframeSafeAreaPreset.YOUTUBE_SHORTS,
        ),
        source_width=1920,
        source_height=1080,
    )

    assert decision.source_focus == (0.5, 0.35)
    assert decision.output_anchor is not None
    assert decision.output_anchor[0] == pytest.approx(0.5)
    assert decision.output_anchor[1] == pytest.approx(0.3444)
    assert decision.safe_area == (30, 130, 578, 864)
    assert decision.composition_reason == "fixed_subject_assumed_focus_no_detection"


def test_fit_background_preserves_full_frame_over_blurred_vertical_canvas() -> None:
    decision = resolve_reframe(
        RenderSpec(
            resolution_mode=ResolutionMode.P720,
            allow_upscale=True,
        ),
        ReframeSpec(mode="fit_background"),
        source_width=1920,
        source_height=1080,
    )

    assert (decision.resolution.output_width, decision.resolution.output_height) == (720, 1280)
    assert decision.crop_box is None
    assert "split=2" in decision.video_filter
    assert "boxblur" in decision.video_filter
    assert "overlay=(W-w)/2:(H-h)/2" in decision.video_filter
    assert decision.composition_reason == "fit_full_frame_over_blurred_background"


def test_reframe_rejects_non_vertical_target_and_tracked_focus() -> None:
    with pytest.raises(CutupError) as wrong_ratio:
        resolve_reframe(
            RenderSpec(target_width=1000, target_height=1000),
            ReframeSpec(mode="center_crop"),
            source_width=1920,
            source_height=1080,
        )
    assert wrong_ratio.value.code is ErrorCode.PROTOCOL_INVALID

    with pytest.raises(CutupError) as odd_dimensions:
        resolve_reframe(
            RenderSpec(target_width=719, target_height=1278),
            ReframeSpec(mode="center_crop"),
            source_width=1920,
            source_height=1080,
        )
    assert odd_dimensions.value.code is ErrorCode.PROTOCOL_INVALID

    with pytest.raises(CutupError) as tracked:
        resolve_reframe(
            RenderSpec(resolution_mode=ResolutionMode.P720),
            ReframeSpec(mode="tracked_focus"),
            source_width=1920,
            source_height=1080,
        )
    assert tracked.value.code is ErrorCode.CAPABILITY_UNAVAILABLE


def test_odd_source_dimensions_still_produce_even_codec_safe_geometry() -> None:
    decision = resolve_reframe(
        RenderSpec(resolution_mode=ResolutionMode.P720),
        ReframeSpec(mode="center_crop"),
        source_width=607,
        source_height=1081,
    )

    assert all(value % 2 == 0 for value in decision.crop_box or ())
    assert decision.resolution.output_width % 2 == 0
    assert decision.resolution.output_height % 2 == 0
