from __future__ import annotations

from pathlib import Path
from typing import Literal

from universal_cutup.domain.errors import CutupError, ErrorCode
from universal_cutup.domain.specs import RenderSpec

from .process import ProcessRunner, ProcessStatus
from .rendering import ReframeDecision, ResolutionDecision, video_encoding_arguments


def cut_media(
    source_path: Path,
    output_path: Path,
    *,
    start_ms: int,
    end_ms: int,
    render_spec: RenderSpec,
    source_kind: Literal["video", "audio", "transcript"],
    runner: ProcessRunner,
    resolution: ResolutionDecision | None = None,
    reframe: ReframeDecision | None = None,
    timeout_seconds: float = 30,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    duration_ms = end_ms - start_ms
    arguments = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-n",
        "-ss",
        f"{start_ms / 1000:.3f}",
        "-i",
        str(source_path),
        "-t",
        f"{duration_ms / 1000:.3f}",
    ]
    if source_kind == "video":
        arguments.extend(
            [
                "-map",
                "0:v:0",
                "-map",
                "0:a:0?",
                "-c:v",
                render_spec.video_codec,
                "-pix_fmt",
                "yuv420p",
            ]
        )
        if reframe is not None:
            arguments.extend(["-vf", reframe.video_filter])
        elif resolution is not None and resolution.scaled:
            arguments.extend(
                [
                    "-vf",
                    f"scale={resolution.output_width}:{resolution.output_height}",
                ]
            )
        arguments.extend(
            [
                *video_encoding_arguments(render_spec),
                "-c:a",
                render_spec.audio_codec,
                "-b:a",
                render_spec.rate_control.audio_bitrate,
            ]
        )
    else:
        arguments.extend(["-map", "0:a:0", "-c:a", render_spec.audio_codec])
    muxer = {"mp4": "mp4", "mov": "mov", "mkv": "matroska"}[render_spec.container]
    if render_spec.container in {"mp4", "mov"}:
        arguments.extend(["-movflags", "+faststart"])
    arguments.extend(["-f", muxer, str(output_path)])
    outcome = runner.run(arguments, timeout_seconds=timeout_seconds)
    if outcome.status is not ProcessStatus.COMPLETED:
        status_codes = {
            ProcessStatus.CANCELLED: ErrorCode.CANCELLED,
            ProcessStatus.TIMED_OUT: ErrorCode.MEDIA_PROCESS_TIMEOUT,
        }
        raise CutupError(
            status_codes.get(outcome.status, ErrorCode.MEDIA_PROCESS_FAILED),
            "FFmpeg failed to cut media",
            category="media",
            step="cut",
            recoverable=outcome.recoverable,
            details={"command": outcome.redacted_command},
        )
