from __future__ import annotations

from pathlib import Path

import pytest

from universal_cutup.domain.specs import SubtitleSidecarFormat, SubtitleSpec
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
