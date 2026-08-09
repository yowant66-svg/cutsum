from __future__ import annotations

from universal_cutup.domain.specs import (
    SubtitleSafeAreaPreset,
    SubtitleSafeAreaSpec,
    SubtitleVerticalPosition,
)
from universal_cutup.media.capabilities import (
    detect_media_runtime_capabilities,
    detect_subtitle_capabilities,
)
from universal_cutup.media.process import ProcessOutcome, ProcessStatus
from universal_cutup.media.subtitles import resolve_safe_area_pixels


class CapabilityRunner:
    def __init__(self, *, ffmpeg: bool, libass: bool, swift: bool) -> None:
        self.ffmpeg = ffmpeg
        self.libass = libass
        self.swift = swift

    def run(
        self,
        arguments: list[str],
        *,
        timeout_seconds: float,
    ) -> ProcessOutcome:
        del timeout_seconds
        available = (
            self.ffmpeg
            if arguments[:2] == ["ffmpeg", "-version"]
            else (
                self.ffmpeg and self.libass
                if arguments[:3] == ["ffmpeg", "-hide_banner", "-filters"]
                else self.swift
            )
        )
        return ProcessOutcome(
            status=ProcessStatus.COMPLETED if available else ProcessStatus.FAILED,
            return_code=0 if available else 1,
            stdout=" subtitles " if available and "-filters" in arguments else "",
            stderr="" if available else "unavailable",
            redacted_command=tuple(arguments),
            recoverable=not available,
        )


def test_libass_is_cross_platform_preferred_backend() -> None:
    capabilities = detect_subtitle_capabilities(
        runner=CapabilityRunner(ffmpeg=True, libass=True, swift=False),
        platform_name="Linux",
    )

    assert capabilities.burn_in_available
    assert capabilities.selected_backend == "ffmpeg-libass"
    assert capabilities.limitations == ()


def test_macos_system_overlay_is_explicit_fallback() -> None:
    capabilities = detect_subtitle_capabilities(
        runner=CapabilityRunner(ffmpeg=True, libass=False, swift=True),
        platform_name="Darwin",
    )

    assert capabilities.burn_in_available
    assert capabilities.selected_backend == "macos-system-overlay"
    assert "font_family_not_supported" in capabilities.limitations


def test_linux_without_libass_reports_unavailable_instead_of_silent_fallback() -> None:
    capabilities = detect_subtitle_capabilities(
        runner=CapabilityRunner(ffmpeg=True, libass=False, swift=False),
        platform_name="Linux",
    )

    assert not capabilities.burn_in_available
    assert capabilities.selected_backend == "unavailable"
    assert "install_ffmpeg_with_libass" in capabilities.limitations


def test_vertical_safe_area_resolves_platform_ui_insets() -> None:
    spec = SubtitleSafeAreaSpec(
        preset=SubtitleSafeAreaPreset.TIKTOK,
        vertical_position=SubtitleVerticalPosition.BOTTOM,
        left_ratio=0.05,
        right_ratio=0.05,
    )

    resolved = resolve_safe_area_pixels(spec, width=1080, height=1920)

    assert resolved.left == 81
    assert resolved.right == 81
    assert resolved.bottom == 480
    assert resolved.top == 192


def test_media_runtime_requires_both_ffmpeg_and_ffprobe() -> None:
    class RuntimeRunner:
        def run(self, arguments: list[str], *, timeout_seconds: float) -> ProcessOutcome:
            del timeout_seconds
            available = arguments[0] == "ffmpeg"
            return ProcessOutcome(
                status=ProcessStatus.COMPLETED if available else ProcessStatus.FAILED,
                return_code=0 if available else 1,
                stdout="",
                stderr="" if available else "unavailable",
                redacted_command=tuple(arguments),
                recoverable=not available,
            )

    capabilities = detect_media_runtime_capabilities(
        runner=RuntimeRunner(),
        platform_name="Windows",
    )

    assert capabilities.ffmpeg_available is True
    assert capabilities.ffprobe_available is False
    assert capabilities.media_execution_available is False
    assert capabilities.limitations == ("install_ffprobe",)
