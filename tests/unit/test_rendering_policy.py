from __future__ import annotations

import pytest

from universal_cutup.domain.specs import (
    QualityPreset,
    RenderSpec,
    ResolutionMode,
)
from universal_cutup.media.rendering import resolve_resolution


@pytest.mark.parametrize(
    ("source", "mode", "expected"),
    [
        ((1920, 1080), ResolutionMode.SOURCE, (1920, 1080)),
        ((1920, 1080), ResolutionMode.P720, (1280, 720)),
        ((1920, 1080), ResolutionMode.P144, (256, 144)),
    ],
)
def test_resolution_modes_preserve_aspect_ratio(
    source: tuple[int, int],
    mode: ResolutionMode,
    expected: tuple[int, int],
) -> None:
    preset = QualityPreset.PREVIEW if mode is ResolutionMode.P144 else QualityPreset.REVIEW
    decision = resolve_resolution(
        RenderSpec(resolution_mode=mode, quality_preset=preset),
        source_width=source[0],
        source_height=source[1],
    )
    assert (decision.output_width, decision.output_height) == expected


def test_low_resolution_source_is_not_upscaled_without_permission() -> None:
    decision = resolve_resolution(
        RenderSpec(resolution_mode=ResolutionMode.P1080),
        source_width=854,
        source_height=480,
    )
    assert (decision.output_width, decision.output_height) == (854, 480)
    assert decision.upscale is False
    assert decision.scale_reason == "target_exceeds_source;upscale_disabled"


def test_explicit_upscale_is_recorded() -> None:
    decision = resolve_resolution(
        RenderSpec(
            resolution_mode=ResolutionMode.P1080,
            allow_upscale=True,
        ),
        source_width=854,
        source_height=480,
    )
    assert (decision.output_width, decision.output_height) == (1922, 1080)
    assert decision.upscale is True


def test_review_rejects_low_resolution_default_modes() -> None:
    with pytest.raises(ValueError, match="review preset"):
        RenderSpec(
            resolution_mode=ResolutionMode.P144,
            quality_preset=QualityPreset.REVIEW,
        )
