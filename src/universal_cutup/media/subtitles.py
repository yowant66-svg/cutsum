from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from universal_cutup.domain.errors import CutupError, ErrorCode
from universal_cutup.domain.specs import (
    RenderSpec,
    SubtitleMode,
    SubtitleSafeAreaPreset,
    SubtitleSafeAreaSpec,
    SubtitleSidecarFormat,
    SubtitleSpec,
)
from universal_cutup.domain.subtitles import SubtitleDisplayUnit, SubtitleSemanticSpan
from universal_cutup.domain.transcript import SubtitleCue

from .capabilities import detect_subtitle_capabilities
from .probe import probe_media
from .process import ProcessRunner, ProcessStatus

CJK_RANGE_START = "\u3400"
CJK_RANGE_END = "\u9fff"
CJK_SEMANTIC_BREAKS = frozenset("。！？；：，、")  # noqa: RUF001


def _srt_timestamp(milliseconds: int) -> str:
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"


@dataclass(frozen=True, slots=True)
class RelativeSubtitleCue:
    start_ms: int
    end_ms: int
    text: str


@dataclass(frozen=True, slots=True)
class RelativeBilingualCue:
    start_ms: int
    end_ms: int
    source_text: str
    translation_text: str


@dataclass(frozen=True, slots=True)
class ResolvedSafeArea:
    left: int
    right: int
    top: int
    bottom: int


PLATFORM_SAFE_AREA_RATIOS = {
    SubtitleSafeAreaPreset.NONE: (0.0, 0.0),
    SubtitleSafeAreaPreset.YOUTUBE_SHORTS: (0.10, 0.20),
    SubtitleSafeAreaPreset.TIKTOK: (0.10, 0.25),
    SubtitleSafeAreaPreset.INSTAGRAM_REELS: (0.12, 0.20),
}
PLATFORM_HORIZONTAL_SAFE_AREA_RATIO = 0.075
SUBTITLE_FONT_REFERENCE_HEIGHT = 720
SINGLE_LANGUAGE_BLOCK_HEIGHT_RATIO = 0.14
BILINGUAL_BLOCK_HEIGHT_RATIO = 0.20


def _scaled_font_size(preferred_size: int, *, height: int) -> int:
    return max(10, round(preferred_size * height / SUBTITLE_FONT_REFERENCE_HEIGHT))


def resolve_safe_area_pixels(
    spec: SubtitleSafeAreaSpec,
    *,
    width: int,
    height: int,
) -> ResolvedSafeArea:
    preset_top, preset_bottom = PLATFORM_SAFE_AREA_RATIOS[spec.preset]
    platform_horizontal = (
        0.0 if spec.preset is SubtitleSafeAreaPreset.NONE else PLATFORM_HORIZONTAL_SAFE_AREA_RATIO
    )
    return ResolvedSafeArea(
        left=round(width * max(spec.left_ratio, platform_horizontal)),
        right=round(width * max(spec.right_ratio, platform_horizontal)),
        top=round(height * max(spec.top_ratio, preset_top)),
        bottom=round(height * max(spec.bottom_ratio, preset_bottom)),
    )


def semantic_two_line_text(value: str) -> str:
    """Add one visual-only CJK line break at a semantic punctuation boundary."""
    contains_cjk = any(CJK_RANGE_START <= character <= CJK_RANGE_END for character in value)
    if "\n" in value or not contains_cjk:
        return value
    candidate_positions = [
        index + 1 for index, character in enumerate(value) if character in CJK_SEMANTIC_BREAKS
    ]
    if not candidate_positions:
        return value
    length = len(value)
    balanced_candidates = [
        position for position in candidate_positions if length * 0.25 <= position <= length * 0.75
    ]
    if not balanced_candidates:
        return value
    position = min(balanced_candidates, key=lambda item: abs(length - (2 * item)))
    return f"{value[:position]}\n{value[position:]}"


def clip_cues_to_candidate(
    cues: tuple[SubtitleCue, ...],
    *,
    candidate_start_ms: int,
    candidate_end_ms: int,
) -> tuple[RelativeSubtitleCue, ...]:
    clipped: list[RelativeSubtitleCue] = []
    for cue in cues:
        start_ms = max(cue.start_ms, candidate_start_ms) - candidate_start_ms
        end_ms = min(cue.end_ms, candidate_end_ms) - candidate_start_ms
        if end_ms > start_ms:
            clipped.append(RelativeSubtitleCue(start_ms=start_ms, end_ms=end_ms, text=cue.text))
    return tuple(clipped)


def clip_semantic_spans_to_candidate(
    spans: tuple[SubtitleSemanticSpan, ...],
    *,
    candidate_start_ms: int,
    candidate_end_ms: int,
) -> tuple[RelativeSubtitleCue, ...]:
    clipped: list[RelativeSubtitleCue] = []
    for span in spans:
        start_ms = max(span.start_ms, candidate_start_ms) - candidate_start_ms
        end_ms = min(span.end_ms, candidate_end_ms) - candidate_start_ms
        if end_ms > start_ms:
            clipped.append(
                RelativeSubtitleCue(
                    start_ms=start_ms,
                    end_ms=end_ms,
                    text=span.text,
                )
            )
    return tuple(clipped)


def write_sidecar(
    output_path: Path,
    *,
    cues: tuple[RelativeSubtitleCue, ...],
    sidecar_format: SubtitleSidecarFormat = SubtitleSidecarFormat.SRT,
    spec: SubtitleSpec | None = None,
    width: int = 1920,
    height: int = 1080,
) -> None:
    if not cues:
        raise CutupError(
            ErrorCode.SUBTITLE_CUES_REQUIRED,
            "subtitle output requires at least one source-timeline cue",
            category="validation",
            step="subtitle",
        )
    if sidecar_format is SubtitleSidecarFormat.ASS:
        _write_single_ass(
            output_path,
            cues=cues,
            spec=spec or SubtitleSpec(sidecar_format=sidecar_format),
            width=width,
            height=height,
        )
        return
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if sidecar_format is SubtitleSidecarFormat.VTT:
        blocks = [
            (
                f"{index}\n{_vtt_timestamp(cue.start_ms)} --> "
                f"{_vtt_timestamp(cue.end_ms)}\n{cue.text}"
            )
            for index, cue in enumerate(cues, start=1)
        ]
        output_path.write_text("WEBVTT\n\n" + "\n\n".join(blocks) + "\n", encoding="utf-8")
        return
    blocks = [
        (f"{index}\n{_srt_timestamp(cue.start_ms)} --> {_srt_timestamp(cue.end_ms)}\n{cue.text}")
        for index, cue in enumerate(cues, start=1)
    ]
    output_path.write_text("\n\n".join(blocks) + "\n", encoding="utf-8")


def _vtt_timestamp(milliseconds: int) -> str:
    return _srt_timestamp(milliseconds).replace(",", ".")


def pair_bilingual_cues(
    source_cues: tuple[RelativeSubtitleCue, ...],
    translated_cues: tuple[RelativeSubtitleCue, ...],
) -> tuple[RelativeBilingualCue, ...]:
    if len(source_cues) != len(translated_cues):
        raise CutupError(
            ErrorCode.SUBTITLE_CUES_REQUIRED,
            "bilingual subtitles require one translated cue per source cue",
            category="validation",
            step="subtitle",
        )
    pairs = []
    for source, translation in zip(source_cues, translated_cues, strict=True):
        if (source.start_ms, source.end_ms) != (translation.start_ms, translation.end_ms):
            raise CutupError(
                ErrorCode.SUBTITLE_CUES_REQUIRED,
                "translated cues must preserve source cue timing",
                category="validation",
                step="subtitle",
            )
        pairs.append(
            RelativeBilingualCue(
                start_ms=source.start_ms,
                end_ms=source.end_ms,
                source_text=source.text,
                translation_text=translation.text,
            )
        )
    return tuple(pairs)


def clip_display_units_to_candidate(
    units: tuple[SubtitleDisplayUnit, ...],
    *,
    candidate_start_ms: int,
    candidate_end_ms: int,
) -> tuple[RelativeBilingualCue, ...]:
    clipped = []
    for unit in units:
        start_ms = max(unit.start_ms, candidate_start_ms) - candidate_start_ms
        end_ms = min(unit.end_ms, candidate_end_ms) - candidate_start_ms
        if end_ms > start_ms:
            clipped.append(
                RelativeBilingualCue(
                    start_ms=start_ms,
                    end_ms=end_ms,
                    source_text=unit.source_text,
                    translation_text=unit.translated_text,
                )
            )
    return tuple(clipped)


def _ass_timestamp(milliseconds: int) -> str:
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, millis = divmod(remainder, 1000)
    return f"{hours}:{minutes:02d}:{seconds:02d}.{millis // 10:02d}"


def _ass_text(value: str) -> str:
    return value.replace("\\", r"\\").replace("{", r"\{").replace("}", r"\}").replace("\n", r"\N")


def _ass_background_style(opacity: float) -> tuple[str, int]:
    alpha = round((1 - opacity) * 255)
    return f"&H{alpha:02X}000000", 3 if opacity > 0 else 1


def _write_single_ass(
    output_path: Path,
    *,
    cues: tuple[RelativeSubtitleCue, ...],
    spec: SubtitleSpec,
    width: int,
    height: int,
) -> None:
    safe_area = resolve_safe_area_pixels(spec.safe_area, width=width, height=height)
    horizontal_margin = max(
        safe_area.left,
        safe_area.right,
        round(width * (1 - spec.max_width_ratio) / 2),
        32,
    )
    alignment = 8 if spec.safe_area.vertical_position == "top" else 2
    vertical_margin = max(
        spec.margin_vertical,
        safe_area.top if alignment == 8 else safe_area.bottom,
    )
    back_color, border_style = _ass_background_style(spec.background_opacity)
    source_font_size = _scaled_font_size(spec.source_font_size, height=height)
    header = "\n".join(
        [
            "[Script Info]",
            "ScriptType: v4.00+",
            f"PlayResX: {width}",
            f"PlayResY: {height}",
            "WrapStyle: 2",
            "",
            "[V4+ Styles]",
            (
                "Format: Name,Fontname,Fontsize,PrimaryColour,OutlineColour,"
                "BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,"
                "Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,"
                "MarginR,MarginV,Encoding"
            ),
            (
                f"Style: Default,{spec.font_family},{source_font_size},"
                f"&H00FFFFFF,&H00000000,{back_color},0,0,0,0,100,100,0,0,"
                f"{border_style},"
                f"{spec.outline_width},0,{alignment},{horizontal_margin},"
                f"{horizontal_margin},{vertical_margin},1"
            ),
            "",
            "[Events]",
            "Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text",
            "",
        ]
    )
    events = [
        (
            f"Dialogue: 0,{_ass_timestamp(cue.start_ms)},{_ass_timestamp(cue.end_ms)},"
            f"Default,,0,0,0,,{_ass_text(semantic_two_line_text(cue.text))}"
        )
        for cue in cues
    ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(header + "\n".join(events) + "\n", encoding="utf-8")


def write_bilingual_ass(
    output_path: Path,
    *,
    cues: tuple[RelativeBilingualCue, ...],
    spec: SubtitleSpec,
    width: int,
    height: int,
) -> None:
    if not cues:
        raise CutupError(
            ErrorCode.SUBTITLE_CUES_REQUIRED,
            "bilingual subtitle output requires timed source and translated cues",
            category="validation",
            step="subtitle",
        )
    safe_area = resolve_safe_area_pixels(spec.safe_area, width=width, height=height)
    horizontal_margin = max(
        safe_area.left,
        safe_area.right,
        round(width * (1 - spec.max_width_ratio) / 2),
        32,
    )
    alignment = 8 if spec.safe_area.vertical_position == "top" else 2
    base_margin = max(
        spec.margin_vertical,
        safe_area.top if alignment == 8 else safe_area.bottom,
    )
    source_font_size = _scaled_font_size(spec.source_font_size, height=height)
    translation_font_size = _scaled_font_size(spec.translation_font_size, height=height)
    line_offset = max(source_font_size, translation_font_size) + 14
    source_is_first = spec.bilingual_order == "source_first"
    if alignment == 2:
        source_margin = base_margin + line_offset if source_is_first else base_margin
        translation_margin = base_margin if source_is_first else base_margin + line_offset
    else:
        source_margin = base_margin if source_is_first else base_margin + line_offset
        translation_margin = base_margin + line_offset if source_is_first else base_margin
    outline = spec.outline_width
    back_color, border_style = _ass_background_style(spec.background_opacity)
    style_format = (
        "Format: Name,Fontname,Fontsize,PrimaryColour,OutlineColour,BackColour,"
        "Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,"
        "Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding"
    )
    source_style = (
        f"Style: Source,{spec.font_family},{source_font_size},"
        f"&H00FFFFFF,&H00000000,{back_color},0,0,0,0,100,100,0,0,"
        f"{border_style},{outline},"
        f"0,{alignment},{horizontal_margin},{horizontal_margin},{source_margin},1"
    )
    translation_style = (
        f"Style: Translation,{spec.font_family},{translation_font_size},"
        f"&H0000FFFF,&H00000000,{back_color},0,0,0,0,100,100,0,0,"
        f"{border_style},{outline},"
        f"0,{alignment},{horizontal_margin},{horizontal_margin},{translation_margin},1"
    )
    header = "\n".join(
        [
            "[Script Info]",
            "ScriptType: v4.00+",
            f"PlayResX: {width}",
            f"PlayResY: {height}",
            "WrapStyle: 2",
            "",
            "[V4+ Styles]",
            style_format,
            source_style,
            translation_style,
            "",
            "[Events]",
            "Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text",
            "",
        ]
    )
    events = []
    for cue in cues:
        start = _ass_timestamp(cue.start_ms)
        end = _ass_timestamp(cue.end_ms)
        first = ("Source", cue.source_text)
        second = ("Translation", cue.translation_text)
        if spec.bilingual_order == "translation_first":
            first, second = second, first
        events.extend(
            [
                (
                    f"Dialogue: 0,{start},{end},{first[0]},,0,0,0,,"
                    f"{_ass_text(semantic_two_line_text(first[1]))}"
                ),
                (
                    f"Dialogue: 0,{start},{end},{second[0]},,0,0,0,,"
                    f"{_ass_text(semantic_two_line_text(second[1]))}"
                ),
            ]
        )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(header + "\n".join(events) + "\n", encoding="utf-8")


def write_bilingual_sidecar(
    output_path: Path,
    *,
    cues: tuple[RelativeBilingualCue, ...],
    sidecar_format: SubtitleSidecarFormat,
    spec: SubtitleSpec,
    width: int,
    height: int,
) -> None:
    if sidecar_format is SubtitleSidecarFormat.ASS:
        write_bilingual_ass(
            output_path,
            cues=cues,
            spec=spec,
            width=width,
            height=height,
        )
        return
    combined = tuple(
        RelativeSubtitleCue(
            start_ms=cue.start_ms,
            end_ms=cue.end_ms,
            text=f"{cue.source_text}\n{cue.translation_text}",
        )
        for cue in cues
    )
    write_sidecar(
        output_path,
        cues=combined,
        sidecar_format=sidecar_format,
        spec=spec,
        width=width,
        height=height,
    )


def _escape_filter_path(path: Path) -> str:
    return (
        str(path).replace("\\", r"\\").replace(":", r"\:").replace("'", r"\'").replace(",", r"\,")
    )


def _burn_with_libass(
    source_path: Path,
    sidecar_path: Path,
    output_path: Path,
    *,
    render_spec: RenderSpec,
    subtitle_spec: SubtitleSpec,
    runner: ProcessRunner,
) -> None:
    outcome = runner.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-n",
            "-i",
            str(source_path),
            "-vf",
            (
                f"subtitles=filename='{_escape_filter_path(sidecar_path)}'"
                if sidecar_path.suffix == ".ass"
                else (
                    f"subtitles=filename='{_escape_filter_path(sidecar_path)}':"
                    f"force_style='FontName={subtitle_spec.font_family},"
                    f"FontSize={subtitle_spec.source_font_size},"
                    f"Outline={subtitle_spec.outline_width},"
                    f"MarginV={subtitle_spec.margin_vertical}'"
                )
            ),
            "-c:v",
            render_spec.video_codec,
            "-c:a",
            "copy",
            str(output_path),
        ],
        timeout_seconds=30,
    )
    if outcome.status is not ProcessStatus.COMPLETED:
        raise CutupError(
            ErrorCode.MEDIA_PROCESS_FAILED,
            "FFmpeg libass subtitle burn-in failed",
            category="media",
            step="subtitle",
            details={"command": outcome.redacted_command},
        )


def _burn_with_macos_system_font(
    source_path: Path,
    output_path: Path,
    *,
    render_spec: RenderSpec,
    subtitle_spec: SubtitleSpec,
    runner: ProcessRunner,
    working_directory: Path,
    timed_cues: tuple[RelativeSubtitleCue, ...],
) -> None:
    if not timed_cues:
        raise CutupError(
            ErrorCode.SUBTITLE_CUES_REQUIRED,
            "timed macOS subtitle fallback requires source-timeline cues",
            category="validation",
            step="subtitle",
        )
    probe = probe_media(source_path, runner=runner)
    width = probe.width or 640
    height = probe.height or 360
    safe_area = resolve_safe_area_pixels(
        subtitle_spec.safe_area,
        width=width,
        height=height,
    )
    available_height = height - safe_area.top - safe_area.bottom
    is_bilingual = subtitle_spec.mode is SubtitleMode.BILINGUAL_BURN_IN
    source_font_size = _scaled_font_size(subtitle_spec.source_font_size, height=height)
    translation_font_size = _scaled_font_size(
        subtitle_spec.translation_font_size,
        height=height,
    )
    block_height_ratio = (
        BILINGUAL_BLOCK_HEIGHT_RATIO if is_bilingual else SINGLE_LANGUAGE_BLOCK_HEIGHT_RATIO
    )
    maximum_block_height = min(round(height * block_height_ratio), available_height)
    desired_block_height = round(
        (source_font_size + (translation_font_size if is_bilingual else 0))
        * subtitle_spec.max_lines
        * 1.35
        + 16
    )
    overlay_height = max(
        1,
        min(max(32, desired_block_height), maximum_block_height),
    )
    maximum_text_width_ratio = min(
        subtitle_spec.max_width_ratio,
        (width - safe_area.left - safe_area.right) / width,
    )
    overlays = tuple(
        working_directory / f"subtitle-overlay-{index:04d}.png"
        for index in range(1, len(timed_cues) + 1)
    )
    render_manifest = working_directory / "subtitle-overlays.json"
    render_manifest.write_text(
        json.dumps(
            [
                {
                    "sourceText": cue.text.partition("\n")[0],
                    "translationText": semantic_two_line_text(cue.text.partition("\n")[2]),
                    "sourceIsFirst": subtitle_spec.bilingual_order == "source_first",
                    "sourceFontSize": source_font_size,
                    "translationFontSize": translation_font_size,
                    "maxLines": subtitle_spec.max_lines,
                    "backgroundOpacity": subtitle_spec.background_opacity,
                    "maxWidthRatio": maximum_text_width_ratio,
                    "outputPath": str(path),
                }
                for cue, path in zip(timed_cues, overlays, strict=True)
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    swift_script = Path(__file__).with_name("render_cues.swift")
    render_outcome = runner.run(
        [
            "swift",
            str(swift_script),
            str(render_manifest),
            str(width),
            str(overlay_height),
        ],
        timeout_seconds=max(30, len(timed_cues) * 2),
    )
    if render_outcome.status is not ProcessStatus.COMPLETED:
        raise CutupError(
            ErrorCode.MEDIA_PROCESS_FAILED,
            "macOS system-font subtitle rasterization failed",
            category="media",
            step="subtitle",
            details={"command": render_outcome.redacted_command},
        )
    arguments = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-n", "-i", str(source_path)]
    for overlay in overlays:
        arguments.extend(["-loop", "1", "-i", str(overlay)])
    chains = []
    previous = "0:v"
    for index, cue in enumerate(timed_cues, start=1):
        output_label = f"subtitle-{index}"
        start = cue.start_ms / 1000
        end = cue.end_ms / 1000
        vertical_position = (
            str(max(safe_area.top, subtitle_spec.margin_vertical))
            if subtitle_spec.safe_area.vertical_position == "top"
            else f"H-h-{max(safe_area.bottom, subtitle_spec.margin_vertical)}"
        )
        chains.append(
            f"[{previous}][{index}:v]overlay=(W-w)/2:{vertical_position}:"
            f"enable='between(t,{start:.3f},{end:.3f})'[{output_label}]"
        )
        previous = output_label
    arguments.extend(
        [
            "-filter_complex",
            ";".join(chains),
            "-map",
            f"[{previous}]",
            "-map",
            "0:a:0?",
            "-c:v",
            render_spec.video_codec,
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "copy",
            "-shortest",
            str(output_path),
        ]
    )
    burn_outcome = runner.run(
        arguments,
        timeout_seconds=max(30, probe.duration_ms / 500),
    )
    if burn_outcome.status is not ProcessStatus.COMPLETED:
        raise CutupError(
            ErrorCode.MEDIA_PROCESS_FAILED,
            "FFmpeg overlay subtitle burn-in failed",
            category="media",
            step="subtitle",
            details={"command": burn_outcome.redacted_command},
        )


def burn_in_subtitle(
    source_path: Path,
    sidecar_path: Path,
    output_path: Path,
    *,
    render_spec: RenderSpec,
    subtitle_spec: SubtitleSpec,
    timed_cues: tuple[RelativeSubtitleCue, ...],
    runner: ProcessRunner,
    working_directory: Path,
) -> str:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    capabilities = detect_subtitle_capabilities(runner=runner)
    if capabilities.selected_backend == "ffmpeg-libass":
        _burn_with_libass(
            source_path,
            sidecar_path,
            output_path,
            render_spec=render_spec,
            subtitle_spec=subtitle_spec,
            runner=runner,
        )
        return "ffmpeg-libass"
    if capabilities.selected_backend == "macos-system-overlay":
        _burn_with_macos_system_font(
            source_path,
            output_path,
            render_spec=render_spec,
            subtitle_spec=subtitle_spec,
            runner=runner,
            working_directory=working_directory,
            timed_cues=timed_cues,
        )
        return "macos-system-overlay"
    raise CutupError(
        ErrorCode.CAPABILITY_UNAVAILABLE,
        "burn-in unavailable; install FFmpeg with libass or use a supported fallback",
        category="dependency",
        step="subtitle",
        details={"limitations": list(capabilities.limitations)},
    )
