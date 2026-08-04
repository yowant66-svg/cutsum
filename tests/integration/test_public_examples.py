from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

from universal_cutup.adapters.transcripts import TranscriptParseContext, parse_srt

REPOSITORY_ROOT = Path(__file__).parents[2]
TRANSCRIPT_ROOT = REPOSITORY_ROOT / "examples" / "transcripts"


@pytest.mark.parametrize("name", ["interview.srt", "education.srt", "sports.srt"])
def test_public_example_transcripts_are_valid_and_bounded(name: str) -> None:
    transcript = parse_srt(
        (TRANSCRIPT_ROOT / name).read_text(encoding="utf-8"),
        context=TranscriptParseContext(
            transcript_id=f"example-{name}",
            source_id="example-source",
            created_at=datetime(2026, 8, 4, tzinfo=UTC),
            created_by="CutSum public examples",
        ),
    )

    assert len(transcript.segments) == 6
    assert transcript.segments[0].start_ms == 0
    assert transcript.segments[-1].end_ms == 60_000


def test_public_demo_generator_creates_decodable_owned_synthetic_media(tmp_path: Path) -> None:
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        pytest.skip("FFmpeg runtime is unavailable")
    output = tmp_path / "demo.mp4"
    subprocess.run(
        [
            sys.executable,
            str(REPOSITORY_ROOT / "examples" / "generate_demo_media.py"),
            str(output),
            "--duration",
            "1",
        ],
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", output],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert output.is_file()
    assert 0.8 <= float(probe.stdout.strip()) <= 1.2


@pytest.mark.timeout(180)
def test_public_quickstart_runs_all_tracks_and_writes_shareable_report(tmp_path: Path) -> None:
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        pytest.skip("FFmpeg runtime is unavailable")
    output = tmp_path / "quickstart"
    subprocess.run(
        [
            sys.executable,
            str(REPOSITORY_ROOT / "examples" / "run_quickstart.py"),
            str(output),
        ],
        cwd=REPOSITORY_ROOT,
        env={**os.environ, "PYTHONPATH": str(REPOSITORY_ROOT / "src")},
        check=True,
        capture_output=True,
        text=True,
        timeout=170,
    )

    report = json.loads((output / "quickstart-report.json").read_text(encoding="utf-8"))
    assert report["result"] == "success"
    assert report["network_provider_calls"] == 0
    assert report["third_party_media_included"] is False
    assert set(report["tracks"]) == {"interview", "education", "sports"}
    assert all(track["status"] == "success" for track in report["tracks"].values())
    assert all(track["artifact_count"] >= 1 for track in report["tracks"].values())
    serialized = json.dumps(report, ensure_ascii=False)
    assert str(tmp_path) not in serialized
