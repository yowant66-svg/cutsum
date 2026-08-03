from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from universal_cutup.domain.errors import CutupError, ErrorCode

from .process import ProcessRunner, ProcessStatus


@dataclass(frozen=True, slots=True)
class MediaProbe:
    duration_ms: int
    has_video: bool
    has_audio: bool
    video_codec: str | None
    audio_codec: str | None
    width: int | None
    height: int | None


def probe_media(
    media_path: Path,
    *,
    runner: ProcessRunner | None = None,
    timeout_seconds: float = 10,
) -> MediaProbe:
    process_runner = runner or ProcessRunner()
    outcome = process_runner.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_streams",
            "-show_format",
            "-of",
            "json",
            str(media_path),
        ],
        timeout_seconds=timeout_seconds,
    )
    if outcome.status is not ProcessStatus.COMPLETED:
        raise CutupError(
            ErrorCode.MEDIA_PROCESS_FAILED,
            "ffprobe could not inspect media",
            category="media",
            step="probe",
            recoverable=outcome.recoverable,
            details={"command": outcome.redacted_command},
        )
    parsed = json.loads(outcome.stdout)
    streams = parsed.get("streams", [])
    video_stream = next(
        (stream for stream in streams if stream.get("codec_type") == "video"),
        None,
    )
    audio_stream = next(
        (stream for stream in streams if stream.get("codec_type") == "audio"),
        None,
    )
    duration_seconds = float(parsed.get("format", {}).get("duration", 0))
    return MediaProbe(
        duration_ms=round(duration_seconds * 1000),
        has_video=video_stream is not None,
        has_audio=audio_stream is not None,
        video_codec=video_stream.get("codec_name") if video_stream else None,
        audio_codec=audio_stream.get("codec_name") if audio_stream else None,
        width=video_stream.get("width") if video_stream else None,
        height=video_stream.get("height") if video_stream else None,
    )
