from __future__ import annotations

from dataclasses import dataclass

from universal_cutup.domain.errors import CutupError, ErrorCode
from universal_cutup.domain.specs import (
    ReframeSafeAreaPreset,
    ReframeSpec,
    RenderSpec,
    ResolutionMode,
)

TARGET_HEIGHTS = {
    ResolutionMode.P1080: 1080,
    ResolutionMode.P720: 720,
    ResolutionMode.P480: 480,
    ResolutionMode.P360: 360,
    ResolutionMode.P144: 144,
}


@dataclass(frozen=True, slots=True)
class ResolutionDecision:
    source_width: int
    source_height: int
    output_width: int
    output_height: int
    scaled: bool
    upscale: bool
    scale_reason: str


@dataclass(frozen=True, slots=True)
class ReframeDecision:
    mode: str
    resolution: ResolutionDecision
    video_filter: str
    crop_box: tuple[int, int, int, int] | None
    source_focus: tuple[float, float] | None
    output_anchor: tuple[float, float] | None
    safe_area: tuple[int, int, int, int]
    composition_reason: str


SAFE_AREA_RATIOS = {
    ReframeSafeAreaPreset.NONE: (0.0, 0.0, 0.0, 0.0),
    ReframeSafeAreaPreset.YOUTUBE_SHORTS: (0.05, 0.05, 0.12, 0.20),
    ReframeSafeAreaPreset.TIKTOK: (0.05, 0.12, 0.10, 0.22),
    ReframeSafeAreaPreset.INSTAGRAM_REELS: (0.05, 0.05, 0.12, 0.18),
}


def _even(value: float) -> int:
    rounded = round(value)
    return rounded if rounded % 2 == 0 else rounded + 1


def _even_floor(value: float) -> int:
    floored = int(value)
    return max(2, floored if floored % 2 == 0 else floored - 1)


def _bounded_even(value: float, maximum: int) -> int:
    return min(_even(value), _even_floor(maximum))


def resolve_resolution(
    render_spec: RenderSpec,
    *,
    source_width: int,
    source_height: int,
) -> ResolutionDecision:
    if render_spec.target_width is not None and render_spec.target_height is not None:
        target_width = render_spec.target_width
        target_height = render_spec.target_height
        reason = "host_explicit_dimensions"
    elif render_spec.resolution_mode is ResolutionMode.SOURCE:
        target_width = source_width
        target_height = source_height
        reason = "source_mode"
    else:
        target_height = TARGET_HEIGHTS[render_spec.resolution_mode]
        target_width = _even(source_width * target_height / source_height)
        reason = f"{render_spec.quality_preset.value}:{render_spec.resolution_mode.value}"
    would_upscale = target_width > source_width or target_height > source_height
    if would_upscale and not render_spec.allow_upscale:
        return ResolutionDecision(
            source_width=source_width,
            source_height=source_height,
            output_width=source_width,
            output_height=source_height,
            scaled=False,
            upscale=False,
            scale_reason="target_exceeds_source;upscale_disabled",
        )
    return ResolutionDecision(
        source_width=source_width,
        source_height=source_height,
        output_width=target_width,
        output_height=target_height,
        scaled=(target_width, target_height) != (source_width, source_height),
        upscale=would_upscale,
        scale_reason=reason,
    )


def _vertical_crop_size(source_width: int, source_height: int) -> tuple[int, int]:
    normalized_width = _even_floor(source_width)
    normalized_height = _even_floor(source_height)
    target_ratio = 9 / 16
    source_ratio = normalized_width / normalized_height
    if source_ratio >= target_ratio:
        return min(normalized_width, _even(normalized_height * target_ratio)), normalized_height
    return normalized_width, min(normalized_height, _even(normalized_width / target_ratio))


def _vertical_target_size(
    render_spec: RenderSpec,
    *,
    crop_width: int,
    crop_height: int,
) -> tuple[int, int, str]:
    if render_spec.target_width is not None and render_spec.target_height is not None:
        if render_spec.target_width % 2 != 0 or render_spec.target_height % 2 != 0:
            raise CutupError(
                ErrorCode.PROTOCOL_INVALID,
                "reframe target dimensions must be even for codec-safe output",
                category="validation",
                step="reframe",
                details={
                    "target_width": render_spec.target_width,
                    "target_height": render_spec.target_height,
                },
            )
        ratio = render_spec.target_width / render_spec.target_height
        if abs(ratio - (9 / 16)) > 0.002:
            raise CutupError(
                ErrorCode.PROTOCOL_INVALID,
                "reframe target dimensions must use a 9:16 aspect ratio",
                category="validation",
                step="reframe",
                details={
                    "target_width": render_spec.target_width,
                    "target_height": render_spec.target_height,
                },
            )
        return render_spec.target_width, render_spec.target_height, "host_explicit_9_16"
    if render_spec.resolution_mode is ResolutionMode.SOURCE:
        return crop_width, crop_height, "reframe_source_mode"
    target_width = TARGET_HEIGHTS[render_spec.resolution_mode]
    return (
        target_width,
        _even(target_width * 16 / 9),
        (f"reframe:{render_spec.quality_preset.value}:{render_spec.resolution_mode.value}"),
    )


def _safe_area(
    preset: ReframeSafeAreaPreset,
    *,
    width: int,
    height: int,
) -> tuple[tuple[int, int, int, int], tuple[float, float, float, float]]:
    left_ratio, right_ratio, top_ratio, bottom_ratio = SAFE_AREA_RATIOS[preset]
    pixels = (
        round(width * left_ratio),
        round(height * top_ratio),
        width - round(width * right_ratio),
        height - round(height * bottom_ratio),
    )
    return pixels, (left_ratio, right_ratio, top_ratio, bottom_ratio)


def _clamp(value: float, minimum: int, maximum: int) -> int:
    clamped = round(max(minimum, min(maximum, value)))
    return max(minimum, clamped if clamped % 2 == 0 else clamped - 1)


def resolve_reframe(
    render_spec: RenderSpec,
    reframe_spec: ReframeSpec,
    *,
    source_width: int,
    source_height: int,
) -> ReframeDecision:
    if reframe_spec.mode in {"none", "tracked_focus"}:
        raise CutupError(
            ErrorCode.CAPABILITY_UNAVAILABLE,
            f"reframe mode {reframe_spec.mode!r} is not an executable basic 9:16 mode",
            category="capability",
            step="reframe",
            details={"mode": reframe_spec.mode},
        )
    crop_width, crop_height = _vertical_crop_size(source_width, source_height)
    desired_width, desired_height, scale_reason = _vertical_target_size(
        render_spec,
        crop_width=crop_width,
        crop_height=crop_height,
    )
    available_width = source_width if reframe_spec.mode == "fit_background" else crop_width
    available_height = source_height if reframe_spec.mode == "fit_background" else crop_height
    scale = min(available_width / desired_width, available_height / desired_height)
    explicit_dimensions = (
        render_spec.target_width is not None and render_spec.target_height is not None
    )
    if explicit_dimensions and not render_spec.allow_upscale and scale < 1:
        raise CutupError(
            ErrorCode.CAPABILITY_CONFLICT,
            "explicit reframe dimensions require upscaling beyond the source",
            category="capability",
            step="reframe",
            recoverable=True,
            details={
                "requested_width": desired_width,
                "requested_height": desired_height,
                "maximum_without_upscale_width": _bounded_even(
                    desired_width * scale,
                    available_width,
                ),
                "maximum_without_upscale_height": _bounded_even(
                    desired_height * scale,
                    available_height,
                ),
            },
        )
    if render_spec.allow_upscale or scale >= 1:
        output_width, output_height = desired_width, desired_height
    else:
        output_width = _bounded_even(desired_width * scale, available_width)
        output_height = _bounded_even(desired_height * scale, available_height)
    upscale = output_width > available_width or output_height > available_height
    resolution = ResolutionDecision(
        source_width=source_width,
        source_height=source_height,
        output_width=output_width,
        output_height=output_height,
        scaled=(output_width, output_height) != (source_width, source_height),
        upscale=upscale,
        scale_reason=(
            scale_reason
            if render_spec.allow_upscale or scale >= 1
            else f"{scale_reason};upscale_disabled"
        ),
    )
    safe_area, safe_ratios = _safe_area(
        reframe_spec.safe_area_preset,
        width=output_width,
        height=output_height,
    )
    if reframe_spec.mode == "fit_background":
        video_filter = (
            f"split=2[bg][fg];[bg]scale={output_width}:{output_height}:"
            "force_original_aspect_ratio=increase,"
            f"crop={output_width}:{output_height},boxblur=20:2[background];"
            f"[fg]scale={output_width}:{output_height}:"
            "force_original_aspect_ratio=decrease[foreground];"
            "[background][foreground]overlay=(W-w)/2:(H-h)/2"
        )
        return ReframeDecision(
            mode=reframe_spec.mode,
            resolution=resolution,
            video_filter=video_filter,
            crop_box=None,
            source_focus=None,
            output_anchor=None,
            safe_area=safe_area,
            composition_reason="fit_full_frame_over_blurred_background",
        )
    if reframe_spec.mode == "center_crop":
        source_focus = None
        output_anchor = None
        crop_x = _clamp(
            (source_width - crop_width) / 2,
            0,
            source_width - crop_width,
        )
        crop_y = _clamp(
            (source_height - crop_height) / 2,
            0,
            source_height - crop_height,
        )
        reason = "center_crop"
    else:
        source_focus = (
            (
                reframe_spec.focus_x if reframe_spec.focus_x is not None else 0.5,
                reframe_spec.focus_y if reframe_spec.focus_y is not None else 0.35,
            )
            if reframe_spec.mode == "fixed_subject"
            else (
                reframe_spec.focus_x if reframe_spec.focus_x is not None else 0.0,
                reframe_spec.focus_y if reframe_spec.focus_y is not None else 0.0,
            )
        )
        if reframe_spec.mode == "fixed_subject":
            left_ratio, right_ratio, top_ratio, bottom_ratio = safe_ratios
            output_anchor = (
                left_ratio + (1 - left_ratio - right_ratio) / 2,
                top_ratio + (1 - top_ratio - bottom_ratio) * 0.33,
            )
            reason = (
                "fixed_subject_explicit_focus_no_tracking"
                if reframe_spec.focus_x is not None
                else "fixed_subject_assumed_focus_no_detection"
            )
        else:
            output_anchor = (0.5, 0.5)
            reason = "manual_focus_centered"
        crop_x = _clamp(
            source_focus[0] * source_width - output_anchor[0] * crop_width,
            0,
            source_width - crop_width,
        )
        crop_y = _clamp(
            source_focus[1] * source_height - output_anchor[1] * crop_height,
            0,
            source_height - crop_height,
        )
    crop_box = (crop_x, crop_y, crop_width, crop_height)
    return ReframeDecision(
        mode=reframe_spec.mode,
        resolution=resolution,
        video_filter=(
            f"crop={crop_width}:{crop_height}:{crop_x}:{crop_y},"
            f"scale={output_width}:{output_height}"
        ),
        crop_box=crop_box,
        source_focus=source_focus,
        output_anchor=output_anchor,
        safe_area=safe_area,
        composition_reason=reason,
    )


def video_encoding_arguments(render_spec: RenderSpec) -> list[str]:
    rate_control = render_spec.rate_control
    if rate_control.mode == "crf":
        return ["-crf", str(rate_control.crf)]
    return ["-b:v", rate_control.video_bitrate or ""]
