from __future__ import annotations

from pathlib import Path

import pytest

from universal_cutup.application.demo import DEMO_TRANSCRIPTS, run_demo
from universal_cutup.domain.errors import CutupError, ErrorCode


def test_demo_rejects_existing_output(tmp_path: Path) -> None:
    output = tmp_path / "existing"
    output.mkdir()

    with pytest.raises(CutupError) as raised:
        run_demo(output)

    assert raised.value.code is ErrorCode.OUTPUT_EXISTS
    assert raised.value.step == "demo_preflight"


def test_demo_transcripts_are_maintainer_authored_and_bounded() -> None:
    assert set(DEMO_TRANSCRIPTS) == {"interview", "education", "sports"}
    assert all("00:01:00,000" in content for content in DEMO_TRANSCRIPTS.values())
    assert all(len(content.encode("utf-8")) < 4096 for content in DEMO_TRANSCRIPTS.values())


def test_demo_rejects_unknown_track_before_creating_output(tmp_path: Path) -> None:
    output = tmp_path / "demo"

    with pytest.raises(CutupError) as raised:
        run_demo(output, selected_tracks=("documentary",))

    assert raised.value.code is ErrorCode.PROTOCOL_INVALID
    assert raised.value.step == "demo_preflight"
    assert not output.exists()
