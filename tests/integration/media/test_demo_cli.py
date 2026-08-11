from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from universal_cutup import __version__
from universal_cutup.cli import app


@pytest.mark.timeout(180)
def test_installed_style_demo_generates_three_playable_tracks(tmp_path: Path) -> None:
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        pytest.skip("FFmpeg runtime is unavailable")
    output = tmp_path / "demo"

    result = CliRunner().invoke(app, ["demo", str(output)])

    assert result.exit_code == 0, result.stderr
    payload = json.loads(result.stdout)
    report = json.loads((output / "demo-report.json").read_text(encoding="utf-8"))
    assert payload["result"] == "success"
    assert report["cutsum_version"] == __version__
    assert report["network_provider_calls"] == 0
    assert set(report["tracks"]) == {"interview", "education", "sports"}
    assert all(item["status"] == "success" for item in report["tracks"].values())
    assert all(item["artifact_count"] >= 1 for item in report["tracks"].values())
    assert str(tmp_path) not in json.dumps(report, ensure_ascii=False)
