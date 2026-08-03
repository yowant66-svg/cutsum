from __future__ import annotations

import pytest
from pydantic import ValidationError

from universal_cutup.domain.specs import ReframeSpec, RenderSpec, SubtitleSpec


def test_render_defaults_to_fail_if_exists() -> None:
    assert RenderSpec().overwrite == "fail"


def test_tracked_focus_is_protocol_valid_but_requires_runtime_capability() -> None:
    assert ReframeSpec(mode="tracked_focus").mode == "tracked_focus"


def test_manual_focus_requires_normalized_coordinates() -> None:
    with pytest.raises(ValidationError):
        ReframeSpec(mode="manual_focus")


def test_replace_and_font_path_are_rejected() -> None:
    with pytest.raises(ValidationError):
        RenderSpec(overwrite="replace")  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        SubtitleSpec(font_path="/tmp/font.ttf")
