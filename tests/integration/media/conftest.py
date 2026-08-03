from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


@pytest.fixture
def synthetic_media(tmp_path: Path) -> Path:
    media_path = tmp_path / "synthetic-source.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=320x180:rate=25:duration=4",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=880:sample_rate=48000:duration=4",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-shortest",
            str(media_path),
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=20,
    )
    return media_path


@pytest.fixture
def synthetic_audio(tmp_path: Path) -> Path:
    media_path = tmp_path / "synthetic-source.m4a"
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:sample_rate=48000:duration=4",
            "-c:a",
            "aac",
            str(media_path),
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=20,
    )
    return media_path
