from __future__ import annotations

import platform
from dataclasses import dataclass
from typing import Literal, Protocol

from .process import ProcessOutcome, ProcessRunner, ProcessStatus


class CapabilityProcessRunner(Protocol):
    def run(
        self,
        arguments: list[str],
        *,
        timeout_seconds: float,
    ) -> ProcessOutcome: ...


@dataclass(frozen=True, slots=True)
class SubtitleBackendCapabilities:
    platform_name: str
    ffmpeg_available: bool
    libass_available: bool
    macos_system_overlay_available: bool
    sidecar_available: bool
    burn_in_available: bool
    selected_backend: Literal[
        "ffmpeg-libass",
        "macos-system-overlay",
        "unavailable",
    ]
    limitations: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class MediaRuntimeCapabilities:
    platform_name: str
    ffmpeg_available: bool
    ffprobe_available: bool
    media_execution_available: bool
    limitations: tuple[str, ...]


def detect_media_runtime_capabilities(
    *,
    runner: CapabilityProcessRunner | None = None,
    platform_name: str | None = None,
) -> MediaRuntimeCapabilities:
    process_runner = runner or ProcessRunner()
    current_platform = platform_name or platform.system()
    ffmpeg_available = (
        process_runner.run(["ffmpeg", "-version"], timeout_seconds=10).status
        is ProcessStatus.COMPLETED
    )
    ffprobe_available = (
        process_runner.run(["ffprobe", "-version"], timeout_seconds=10).status
        is ProcessStatus.COMPLETED
    )
    limitations = tuple(
        name
        for name, available in (
            ("install_ffmpeg", ffmpeg_available),
            ("install_ffprobe", ffprobe_available),
        )
        if not available
    )
    return MediaRuntimeCapabilities(
        platform_name=current_platform,
        ffmpeg_available=ffmpeg_available,
        ffprobe_available=ffprobe_available,
        media_execution_available=ffmpeg_available and ffprobe_available,
        limitations=limitations,
    )


def detect_subtitle_capabilities(
    *,
    runner: CapabilityProcessRunner | None = None,
    platform_name: str | None = None,
) -> SubtitleBackendCapabilities:
    process_runner = runner or ProcessRunner()
    current_platform = platform_name or platform.system()
    ffmpeg_outcome = process_runner.run(
        ["ffmpeg", "-version"],
        timeout_seconds=10,
    )
    ffmpeg_available = ffmpeg_outcome.status is ProcessStatus.COMPLETED
    filter_outcome = (
        process_runner.run(
            ["ffmpeg", "-hide_banner", "-filters"],
            timeout_seconds=10,
        )
        if ffmpeg_available
        else None
    )
    libass_available = bool(
        filter_outcome is not None
        and filter_outcome.status is ProcessStatus.COMPLETED
        and " subtitles " in filter_outcome.stdout
    )
    swift_outcome = (
        process_runner.run(["swift", "--version"], timeout_seconds=10)
        if current_platform == "Darwin" and not libass_available
        else None
    )
    macos_overlay_available = bool(
        swift_outcome is not None and swift_outcome.status is ProcessStatus.COMPLETED
    )
    selected_backend: Literal[
        "ffmpeg-libass",
        "macos-system-overlay",
        "unavailable",
    ]
    if libass_available:
        selected_backend = "ffmpeg-libass"
        limitations: tuple[str, ...] = ()
    elif macos_overlay_available:
        selected_backend = "macos-system-overlay"
        limitations = ("font_family_not_supported",)
    else:
        selected_backend = "unavailable"
        limitations = ("install_ffmpeg_with_libass",)
    return SubtitleBackendCapabilities(
        platform_name=current_platform,
        ffmpeg_available=ffmpeg_available,
        libass_available=libass_available,
        macos_system_overlay_available=macos_overlay_available,
        sidecar_available=True,
        burn_in_available=selected_backend != "unavailable",
        selected_backend=selected_backend,
        limitations=limitations,
    )
