from __future__ import annotations

from pathlib import Path
from typing import Literal

import pytest

from universal_cutup.domain.specs import (
    SubtitleSafeAreaPreset,
    SubtitleSafeAreaSpec,
    SubtitleSidecarFormat,
    SubtitleSpec,
)
from universal_cutup.media.subtitles import (
    RelativeBilingualCue,
    RelativeSubtitleCue,
    write_bilingual_sidecar,
    write_sidecar,
)

SOURCE_CUES = (
    RelativeSubtitleCue(
        start_ms=0,
        end_ms=2_500,
        text="An algorithm maps inputs to outputs.",
    ),
)
PAIRS = (
    RelativeBilingualCue(
        start_ms=0,
        end_ms=2_500,
        source_text="An algorithm maps inputs to outputs.",
        translation_text="算法把输入映射为输出。",
    ),
)


@pytest.mark.parametrize(
    ("sidecar_format", "expected_header", "expected_timestamp"),
    [
        (SubtitleSidecarFormat.SRT, "1\n", "00:00:00,000 --> 00:00:02,500"),
        (SubtitleSidecarFormat.VTT, "WEBVTT\n", "00:00:00.000 --> 00:00:02.500"),
        (SubtitleSidecarFormat.ASS, "[Script Info]", "0:00:00.00,0:00:02.50"),
    ],
)
def test_source_sidecar_formats(
    tmp_path: Path,
    sidecar_format: SubtitleSidecarFormat,
    expected_header: str,
    expected_timestamp: str,
) -> None:
    output = tmp_path / f"source.{sidecar_format.value}"

    write_sidecar(
        output,
        cues=SOURCE_CUES,
        sidecar_format=sidecar_format,
        spec=SubtitleSpec(sidecar_format=sidecar_format),
        width=1280,
        height=720,
    )

    content = output.read_text(encoding="utf-8")
    assert content.startswith(expected_header)
    assert expected_timestamp in content
    assert SOURCE_CUES[0].text in content
    if sidecar_format is SubtitleSidecarFormat.ASS:
        assert "&HA6000000" in content


def test_vertical_single_ass_reserves_one_pixel_for_libass_block_rounding(
    tmp_path: Path,
) -> None:
    output = tmp_path / "vertical-source.ass"

    write_sidecar(
        output,
        cues=SOURCE_CUES,
        sidecar_format=SubtitleSidecarFormat.ASS,
        spec=SubtitleSpec(sidecar_format=SubtitleSidecarFormat.ASS),
        width=720,
        height=1280,
    )

    content = output.read_text(encoding="utf-8")
    assert "Style: Default,Arial,38," in content


@pytest.mark.parametrize(
    "sidecar_format",
    [
        SubtitleSidecarFormat.SRT,
        SubtitleSidecarFormat.VTT,
        SubtitleSidecarFormat.ASS,
    ],
)
def test_bilingual_sidecar_keeps_one_semantic_timeline(
    tmp_path: Path,
    sidecar_format: SubtitleSidecarFormat,
) -> None:
    output = tmp_path / f"bilingual.{sidecar_format.value}"

    write_bilingual_sidecar(
        output,
        cues=PAIRS,
        sidecar_format=sidecar_format,
        spec=SubtitleSpec(sidecar_format=sidecar_format),
        width=1280,
        height=720,
    )

    content = output.read_text(encoding="utf-8")
    assert PAIRS[0].source_text in content
    assert PAIRS[0].translation_text in content
    assert content.count("00:00:02") <= 1


@pytest.mark.parametrize(
    (
        "width",
        "height",
        "bilingual_order",
        "source_margin",
        "translation_margin",
        "font_size",
        "first_dialogue_style",
    ),
    [
        (720, 1280, "source_first", 309, 256, 39, "Source"),
        (720, 1280, "translation_first", 256, 309, 39, "Translation"),
        (1080, 1920, "source_first", 457, 384, 59, "Source"),
        (1080, 1920, "translation_first", 384, 457, 59, "Translation"),
    ],
)
def test_vertical_bilingual_ass_contract_scales_and_preserves_order(
    tmp_path: Path,
    width: int,
    height: int,
    bilingual_order: Literal["source_first", "translation_first"],
    source_margin: int,
    translation_margin: int,
    font_size: int,
    first_dialogue_style: str,
) -> None:
    output = tmp_path / "vertical-bilingual.ass"

    write_bilingual_sidecar(
        output,
        cues=PAIRS,
        sidecar_format=SubtitleSidecarFormat.ASS,
        spec=SubtitleSpec(
            sidecar_format=SubtitleSidecarFormat.ASS,
            bilingual_order=bilingual_order,
            safe_area=SubtitleSafeAreaSpec(
                preset=SubtitleSafeAreaPreset.YOUTUBE_SHORTS,
            ),
        ),
        width=width,
        height=height,
    )

    content = output.read_text(encoding="utf-8")
    assert f"PlayResX: {width}" in content
    assert f"PlayResY: {height}" in content
    assert (
        f"Style: Source,Arial,{font_size},&H00FFFFFF,&H00000000,&HA6000000,"
        f"0,0,0,0,100,100,0,0,3,2,0,2,{round(width * 0.075)},"
        f"{round(width * 0.075)},{source_margin},1"
    ) in content
    assert (
        f"Style: Translation,Arial,{font_size},&H0000FFFF,&H00000000,&HA6000000,"
        f"0,0,0,0,100,100,0,0,3,2,0,2,{round(width * 0.075)},"
        f"{round(width * 0.075)},{translation_margin},1"
    ) in content
    first_dialogue = next(line for line in content.splitlines() if line.startswith("Dialogue:"))
    assert f",{first_dialogue_style}," in first_dialogue
