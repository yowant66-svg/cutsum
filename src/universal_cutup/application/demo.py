from __future__ import annotations

import hashlib
import json
import platform
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from universal_cutup import __version__
from universal_cutup.domain.errors import CutupError, ErrorCode
from universal_cutup.domain.execution import ExecutionRecord
from universal_cutup.domain.intelligence import ControlMode
from universal_cutup.domain.plans import CutPlan
from universal_cutup.domain.sources import MediaBinding, RightsAttestation
from universal_cutup.domain.specs import (
    OutputSpec,
    QualityPreset,
    RenderSpec,
    ResolutionMode,
    SubtitleMode,
    SubtitleSpec,
)
from universal_cutup.media.process import ProcessRunner, ProcessStatus
from universal_cutup.providers.sports_text import SportsTextProfile

from .sdk import (
    create_plan,
    execute_cut_plan,
    inspect_source,
    load_transcript,
    plan_educational_content,
    plan_sports_transcript,
)

DEMO_TRACKS = ("interview", "education", "sports")
DEMO_DURATION_SECONDS = 60

INTERVIEW_SRT = """1
00:00:00,000 --> 00:00:05,000
The turning point was realizing that

2
00:00:05,000 --> 00:00:10,000
speed is not the same thing as progress.

3
00:00:10,000 --> 00:00:15,000
We were shipping more features every week,

4
00:00:15,000 --> 00:00:20,000
but users were taking longer to reach a useful result.

5
00:00:20,000 --> 00:00:25,000
So we replaced the feature target with one question:

6
00:00:25,000 --> 00:00:30,000
can a new person succeed in ten minutes?

7
00:00:30,000 --> 00:00:35,000
That constraint felt slower at first

8
00:00:35,000 --> 00:00:40,000
because it forced us to remove work we had already completed.

9
00:00:40,000 --> 00:00:45,000
Within a month, support requests fell

10
00:00:45,000 --> 00:00:50,000
and the team spent less time explaining the product.

11
00:00:50,000 --> 00:00:55,000
The lesson is simple: progress is the distance removed

12
00:00:55,000 --> 00:01:00,000
between a person and a meaningful outcome.
"""

EDUCATION_SRT = (
    """1
00:00:00,000 --> 00:00:10,000
A binary search finds a target in sorted data by repeatedly cutting the possible interval in half.

2
00:00:10,000 --> 00:00:20,000
First compare the target with the middle value, then discard the half that cannot contain it.

3
00:00:20,000 --> 00:00:30,000
For example, to find seven from one through fifteen, compare eight and continue in the lower half.

4
00:00:30,000 --> 00:00:40,000
"""
    "The important invariant is that the remaining interval is sorted and still "
    "contains every possible answer.\n\n"
    "5\n"
    "00:00:40,000 --> 00:00:50,000\n"
    "A common mistake is using binary search on unsorted data, where discarding half "
    "is not logically valid.\n\n"
    "6\n"
    "00:00:50,000 --> 00:01:00,000\n"
    "In summary, the sorted invariant makes each comparison safe and repeated halving "
    "gives logarithmic complexity.\n"
)

SPORTS_SRT = """1
00:00:00,000 --> 00:00:10,000
The teams are level as the final minute begins.

2
00:00:10,000 --> 00:00:20,000
The guard drives toward the lane but the shot misses off the rim.

3
00:00:20,000 --> 00:00:30,000
The rebound is secured and the offense resets near half court.

4
00:00:30,000 --> 00:00:40,000
They might have one final chance if they manage the clock correctly.

5
00:00:40,000 --> 00:00:50,000
Five seconds remain and she steps back beyond the line.

6
00:00:50,000 --> 00:01:00,000
BUZZER BEATER! She scores the game winner as time expires!
"""

DEMO_TRANSCRIPTS = {
    "interview": INTERVIEW_SRT,
    "education": EDUCATION_SRT,
    "sports": SPORTS_SRT,
}


@dataclass(frozen=True, slots=True)
class DemoResult:
    output_root: Path
    report_path: Path
    report: dict[str, Any]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file_handle:
        for chunk in iter(lambda: file_handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as file_handle:
        file_handle.write(content)


def generate_demo_media(output: Path, *, duration_seconds: int = DEMO_DURATION_SECONDS) -> None:
    if duration_seconds <= 0:
        raise ValueError("duration_seconds must be positive")
    if output.exists():
        raise CutupError(
            ErrorCode.OUTPUT_EXISTS,
            f"demo media already exists: {output.name}",
            category="output",
            step="demo_media",
            recoverable=True,
        )
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise CutupError(
            ErrorCode.FFMPEG_NOT_FOUND,
            "ffmpeg is required to generate demo media",
            category="environment",
            step="demo_media",
            recoverable=True,
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    outcome = ProcessRunner().run(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-n",
            "-f",
            "lavfi",
            "-i",
            f"testsrc2=size=640x360:rate=25:duration={duration_seconds}",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency=440:sample_rate=48000:duration={duration_seconds}",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-shortest",
            str(output),
        ],
        timeout_seconds=max(30, duration_seconds * 3),
    )
    if outcome.status is ProcessStatus.COMPLETED:
        return
    code = (
        ErrorCode.MEDIA_PROCESS_TIMEOUT
        if outcome.status is ProcessStatus.TIMED_OUT
        else ErrorCode.MEDIA_PROCESS_FAILED
    )
    raise CutupError(
        code,
        "ffmpeg could not generate demo media",
        category="environment",
        step="demo_media",
        recoverable=True,
        details={"diagnostic": outcome.stderr[-500:]},
    )


def _preview_output(*, subtitles: bool = False) -> OutputSpec:
    return OutputSpec(
        render=RenderSpec(
            quality_preset=QualityPreset.PREVIEW,
            resolution_mode=ResolutionMode.P360,
        ),
        subtitle=SubtitleSpec(mode=SubtitleMode.SOURCE_SIDECAR if subtitles else SubtitleMode.NONE),
    )


def _plan_for_track(
    track: str,
    *,
    source_path: Path,
    transcript_path: Path,
) -> tuple[CutPlan, MediaBinding]:
    inspection = inspect_source(source_path, rights_attestation=RightsAttestation.OWNED)
    transcript = load_transcript(
        transcript_path,
        source_id=inspection.source.source_id,
        created_by="cutsum-demo",
    )
    if track == "interview":
        return (
            create_plan(
                inspection.source,
                transcript,
                output_spec=_preview_output(subtitles=True),
            ),
            inspection.binding,
        )
    if track == "education":
        education_result = plan_educational_content(
            inspection.source,
            transcript,
            control_mode=ControlMode.AUTO,
            raw_instruction="",
            output_spec=_preview_output(),
        )
        return education_result.plan, inspection.binding
    sports_result = plan_sports_transcript(
        inspection.source,
        transcript,
        profile=SportsTextProfile.BASKETBALL,
        control_mode=ControlMode.DIRECTED,
        raw_instruction="只要一个绝杀",
        output_spec=_preview_output(),
    )
    return sports_result.plan, inspection.binding


def _track_report(
    execution: ExecutionRecord,
    *,
    track_root: Path,
    report_root: Path,
) -> dict[str, Any]:
    artifacts = []
    for artifact in execution.artifacts:
        artifact_path = track_root / artifact.relative_path
        artifacts.append(
            {
                "path": artifact_path.relative_to(report_root).as_posix(),
                "sha256": artifact.sha256,
                "artifact_type": artifact.artifact_type,
                "duration_ms": artifact.duration_ms,
                "video_codec": artifact.video_codec,
                "audio_codec": artifact.audio_codec,
                "resolution": artifact.actual_output_resolution,
            }
        )
    return {
        "status": execution.status.value,
        "execution_record": (track_root / "execution-record.json")
        .relative_to(report_root)
        .as_posix(),
        "artifact_count": len(artifacts),
        "artifacts": artifacts,
    }


def run_demo(
    output_root: Path,
    *,
    selected_tracks: tuple[str, ...] = DEMO_TRACKS,
) -> DemoResult:
    tracks = tuple(dict.fromkeys(selected_tracks))
    unknown_tracks = sorted(set(tracks) - set(DEMO_TRACKS))
    if not tracks or unknown_tracks:
        raise CutupError(
            ErrorCode.PROTOCOL_INVALID,
            "demo requires one or more supported tracks",
            step="demo_preflight",
            recoverable=True,
            details={"supported_tracks": list(DEMO_TRACKS), "unknown_tracks": unknown_tracks},
        )
    if output_root.exists():
        raise CutupError(
            ErrorCode.OUTPUT_EXISTS,
            f"demo output already exists: {output_root.name}",
            category="output",
            step="demo_preflight",
            recoverable=True,
        )

    source_path = output_root / "owned-synthetic-source.mp4"
    generate_demo_media(source_path)
    track_reports: dict[str, Any] = {}
    for track in tracks:
        transcript_path = output_root / "transcripts" / f"{track}.srt"
        _write_text(transcript_path, DEMO_TRANSCRIPTS[track])
        plan, binding = _plan_for_track(
            track,
            source_path=source_path,
            transcript_path=transcript_path,
        )
        plan_path = output_root / f"{track}-plan.json"
        _write_text(plan_path, plan.model_dump_json(exclude_none=True) + "\n")
        track_root = output_root / track
        execution = execute_cut_plan(plan, binding=binding, output_root=track_root)
        _write_text(
            track_root / "execution-record.json",
            execution.model_dump_json(exclude_none=True) + "\n",
        )
        if execution.status.value != "success":
            raise CutupError(
                ErrorCode.MEDIA_PROCESS_FAILED,
                f"{track} demo execution failed",
                category="media",
                step="demo_execute",
                recoverable=True,
                details={"track": track},
            )
        track_reports[track] = {
            **_track_report(execution, track_root=track_root, report_root=output_root),
            "plan": plan_path.relative_to(output_root).as_posix(),
        }

    report = {
        "schema_version": "1.0",
        "result": "success",
        "cutsum_version": __version__,
        "python_version": platform.python_version(),
        "platform": platform.system(),
        "evidence_class": "maintainer_authored_synthetic",
        "rights_attestation": "owned",
        "network_provider_calls": 0,
        "third_party_media_included": False,
        "source": {
            "path": source_path.relative_to(output_root).as_posix(),
            "sha256": _sha256(source_path),
        },
        "tracks": track_reports,
    }
    report_path = output_root / "demo-report.json"
    _write_text(
        report_path, json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    )
    return DemoResult(output_root=output_root, report_path=report_path, report=report)
