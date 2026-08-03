from __future__ import annotations

from enum import StrEnum
from typing import Literal, TypeAlias

from pydantic import Field, model_validator

from .common import FrozenModel


class SubtitleMode(StrEnum):
    NONE = "none"
    SOURCE_SIDECAR = "source_sidecar"
    TRANSLATED_SIDECAR = "translated_sidecar"
    BILINGUAL_SIDECAR = "bilingual_sidecar"
    SOURCE_BURN_IN = "source_burn_in"
    TRANSLATED_BURN_IN = "translated_burn_in"
    BILINGUAL_BURN_IN = "bilingual_burn_in"
    SIDECAR = "sidecar"
    BURN_IN = "burn_in"


class SubtitleSidecarFormat(StrEnum):
    SRT = "srt"
    VTT = "vtt"
    ASS = "ass"


class SubtitleSafeAreaPreset(StrEnum):
    NONE = "none"
    YOUTUBE_SHORTS = "youtube_shorts"
    TIKTOK = "tiktok"
    INSTAGRAM_REELS = "instagram_reels"


class SubtitleVerticalPosition(StrEnum):
    BOTTOM = "bottom"
    TOP = "top"


class QualityPreset(StrEnum):
    PREVIEW = "preview"
    REVIEW = "review"
    PUBLISH = "publish"


class ResolutionMode(StrEnum):
    SOURCE = "source"
    P1080 = "1080p"
    P720 = "720p"
    P480 = "480p"
    P360 = "360p"
    P144 = "144p"


class ReframeSafeAreaPreset(StrEnum):
    NONE = "none"
    YOUTUBE_SHORTS = "youtube_shorts"
    TIKTOK = "tiktok"
    INSTAGRAM_REELS = "instagram_reels"


class RateControlSpec(FrozenModel):
    mode: Literal["crf", "bitrate"] = "crf"
    crf: int | None = Field(default=23, ge=0, le=51)
    video_bitrate: str | None = None
    audio_bitrate: str = "128k"

    @model_validator(mode="after")
    def validate_rate_control(self) -> RateControlSpec:
        if self.mode == "crf" and self.crf is None:
            raise ValueError("CRF rate control requires crf")
        if self.mode == "bitrate" and self.video_bitrate is None:
            raise ValueError("bitrate rate control requires video_bitrate")
        return self


class SubtitleSafeAreaSpec(FrozenModel):
    preset: SubtitleSafeAreaPreset = SubtitleSafeAreaPreset.NONE
    vertical_position: SubtitleVerticalPosition = SubtitleVerticalPosition.BOTTOM
    left_ratio: float = Field(default=0.03, ge=0, le=0.45)
    right_ratio: float = Field(default=0.03, ge=0, le=0.45)
    top_ratio: float = Field(default=0.03, ge=0, le=0.45)
    bottom_ratio: float = Field(default=0.03, ge=0, le=0.45)

    @model_validator(mode="after")
    def validate_available_area(self) -> SubtitleSafeAreaSpec:
        if self.left_ratio + self.right_ratio >= 0.9:
            raise ValueError("subtitle horizontal safe area leaves insufficient width")
        if self.top_ratio + self.bottom_ratio >= 0.9:
            raise ValueError("subtitle vertical safe area leaves insufficient height")
        return self


class SubtitleSpec(FrozenModel):
    mode: SubtitleMode = SubtitleMode.NONE
    sidecar_format: SubtitleSidecarFormat = SubtitleSidecarFormat.SRT
    language: str | None = None
    translation_language: str | None = None
    font_family: str = "Arial"
    font_path: str | None = None
    source_font_size: int = Field(default=22, ge=12, le=72)
    translation_font_size: int = Field(default=22, ge=12, le=72)
    margin_vertical: int = Field(default=48, ge=0)
    outline_width: int = Field(default=2, ge=0, le=8)
    background_opacity: float = Field(default=0.35, ge=0, le=1)
    max_width_ratio: float = Field(default=0.9, ge=0.4, le=1)
    max_characters_per_line: int = Field(default=34, ge=10, le=80)
    max_lines: Literal[1, 2] = 2
    bilingual_order: Literal["source_first", "translation_first"] = "source_first"
    safe_area: SubtitleSafeAreaSpec = SubtitleSafeAreaSpec()

    @model_validator(mode="after")
    def reject_font_path(self) -> SubtitleSpec:
        if self.font_path is not None:
            raise ValueError("font_path is not supported; use an installed system font")
        return self


class RenderSpec(FrozenModel):
    container: Literal["mp4", "mov", "mkv"] = "mp4"
    video_codec: str = "libx264"
    audio_codec: str = "aac"
    overwrite: Literal["fail"] = "fail"
    duration_tolerance_ms: int = Field(default=150, ge=0)
    resolution_mode: ResolutionMode = ResolutionMode.P720
    target_width: int | None = Field(default=None, gt=0)
    target_height: int | None = Field(default=None, gt=0)
    allow_upscale: bool = False
    quality_preset: QualityPreset = QualityPreset.REVIEW
    rate_control: RateControlSpec = RateControlSpec()

    @model_validator(mode="after")
    def validate_resolution(self) -> RenderSpec:
        if (self.target_width is None) != (self.target_height is None):
            raise ValueError("target_width and target_height must be set together")
        if self.quality_preset is QualityPreset.REVIEW and self.resolution_mode in {
            ResolutionMode.P144,
            ResolutionMode.P360,
        }:
            raise ValueError("review preset cannot default to 144p or 360p")
        return self


ReframeMode: TypeAlias = Literal[
    "none",
    "center_crop",
    "manual_focus",
    "fit_background",
    "fixed_subject",
    "tracked_focus",
]


class ReframeSpec(FrozenModel):
    mode: ReframeMode = "none"
    focus_x: float | None = Field(default=None, ge=0, le=1)
    focus_y: float | None = Field(default=None, ge=0, le=1)
    safe_area_preset: ReframeSafeAreaPreset = ReframeSafeAreaPreset.NONE

    @model_validator(mode="after")
    def validate_focus_coordinates(self) -> ReframeSpec:
        if self.mode == "manual_focus" and (self.focus_x is None or self.focus_y is None):
            raise ValueError("manual_focus requires focus_x and focus_y")
        if self.mode == "fixed_subject" and ((self.focus_x is None) != (self.focus_y is None)):
            raise ValueError("fixed_subject requires both focus coordinates or neither")
        if self.mode not in {"manual_focus", "fixed_subject"} and (
            self.focus_x is not None or self.focus_y is not None
        ):
            raise ValueError(f"{self.mode} does not use focus coordinates")
        return self


class OutputSpec(FrozenModel):
    render: RenderSpec = RenderSpec()
    subtitle: SubtitleSpec = SubtitleSpec()
    reframe: ReframeSpec = ReframeSpec()
