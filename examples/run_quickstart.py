from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from generate_demo_media import generate_demo_media

EXAMPLE_ROOT = Path(__file__).resolve().parent
TRACKS = ("interview", "education", "sports")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file_handle:
        for chunk in iter(lambda: file_handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _run_cli(arguments: list[str], *, timeout_seconds: int = 300) -> dict[str, Any]:
    command = [sys.executable, "-m", "universal_cutup.cli", *arguments]
    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or "no diagnostic output"
        raise RuntimeError(f"CutSum command failed with exit code {completed.returncode}: {detail}")
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError("CutSum command did not return valid JSON") from error
    if not isinstance(payload, dict):
        raise RuntimeError("CutSum command returned a non-object JSON payload")
    return payload


def _probe_video(path: Path, *, report_root: Path) -> dict[str, Any]:
    completed = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=codec_name,width,height:format=duration",
            "-of",
            "json",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    probe = json.loads(completed.stdout)
    stream = probe["streams"][0]
    return {
        "path": path.relative_to(report_root).as_posix(),
        "sha256": _sha256(path),
        "codec": stream["codec_name"],
        "width": stream["width"],
        "height": stream["height"],
        "duration_seconds": round(float(probe["format"]["duration"]), 3),
    }


def _track_report(track_root: Path, *, report_root: Path) -> dict[str, Any]:
    execution_record = track_root / "execution-record.json"
    if not execution_record.is_file():
        raise RuntimeError(f"missing execution record for {track_root.name}")
    execution = json.loads(execution_record.read_text(encoding="utf-8"))
    videos = [
        _probe_video(path, report_root=report_root) for path in sorted(track_root.rglob("*.mp4"))
    ]
    if execution.get("status") != "success" or not videos:
        raise RuntimeError(f"{track_root.name} did not produce a successful playable result")
    return {
        "status": execution["status"],
        "execution_record": execution_record.relative_to(report_root).as_posix(),
        "artifact_count": len(videos),
        "artifacts": videos,
    }


def _run_interview(source: Path, output_root: Path) -> dict[str, Any]:
    track_root = output_root / "interview"
    _run_cli(
        [
            "full",
            str(source),
            str(EXAMPLE_ROOT / "transcripts" / "interview.srt"),
            str(track_root),
            "--rights",
            "owned",
            "--subtitle-mode",
            "source_sidecar",
        ]
    )
    return _track_report(track_root, report_root=output_root)


def _run_education(source: Path, output_root: Path) -> dict[str, Any]:
    plan = output_root / "education-plan.json"
    track_root = output_root / "education"
    _run_cli(
        [
            "education-plan",
            str(source),
            str(EXAMPLE_ROOT / "transcripts" / "education.srt"),
            "--mode",
            "auto",
            "--rights",
            "owned",
            "--quality-preset",
            "preview",
            "--resolution-mode",
            "360p",
            "--output",
            str(plan),
        ]
    )
    _run_cli(["cut", str(plan), str(source), str(track_root)])
    report = _track_report(track_root, report_root=output_root)
    return {**report, "plan": plan.relative_to(output_root).as_posix()}


def _run_sports(source: Path, output_root: Path) -> dict[str, Any]:
    plan = output_root / "sports-plan.json"
    track_root = output_root / "sports"
    _run_cli(
        [
            "sports-transcript-plan",
            str(source),
            str(EXAMPLE_ROOT / "transcripts" / "sports.srt"),
            "basketball",
            "--mode",
            "directed",
            "--instruction",
            "只要一个绝杀",
            "--rights",
            "owned",
            "--quality-preset",
            "preview",
            "--resolution-mode",
            "360p",
            "--output",
            str(plan),
        ]
    )
    _run_cli(["cut", str(plan), str(source), str(track_root)])
    report = _track_report(track_root, report_root=output_root)
    return {**report, "plan": plan.relative_to(output_root).as_posix()}


def run_quickstart(output_root: Path, *, selected_tracks: tuple[str, ...] = TRACKS) -> Path:
    if output_root.exists():
        raise FileExistsError(f"output directory already exists: {output_root}")
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        raise RuntimeError("ffmpeg and ffprobe must both be available on PATH")
    unknown_tracks = sorted(set(selected_tracks) - set(TRACKS))
    if unknown_tracks:
        raise ValueError(f"unsupported tracks: {', '.join(unknown_tracks)}")
    if not selected_tracks:
        raise ValueError("at least one track must be selected")

    source = output_root / "owned-synthetic-source.mp4"
    generate_demo_media(source, duration_seconds=60)
    runners = {
        "interview": _run_interview,
        "education": _run_education,
        "sports": _run_sports,
    }
    track_reports: dict[str, Any] = {}
    for track in selected_tracks:
        print(f"Running {track} example...", flush=True)
        track_reports[track] = runners[track](source, output_root)

    report = {
        "schema_version": "1.0",
        "result": "success",
        "cutsum_version": importlib.metadata.version("cutsum"),
        "python_version": platform.python_version(),
        "platform": platform.system(),
        "evidence_class": "maintainer_authored_synthetic",
        "rights_attestation": "owned",
        "network_provider_calls": 0,
        "third_party_media_included": False,
        "source": {
            "path": source.relative_to(output_root).as_posix(),
            "sha256": _sha256(source),
        },
        "tracks": track_reports,
    }
    report_path = output_root / "quickstart-report.json"
    with report_path.open("x", encoding="utf-8") as file_handle:
        json.dump(report, file_handle, ensure_ascii=False, indent=2, sort_keys=True)
        file_handle.write("\n")
    return report_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run CutSum's rights-safe interview, education, and sports quickstart."
    )
    parser.add_argument("output", type=Path)
    parser.add_argument(
        "--track",
        action="append",
        choices=TRACKS,
        dest="tracks",
        help="Run only this track; repeat to select multiple tracks.",
    )
    args = parser.parse_args()
    tracks = tuple(dict.fromkeys(args.tracks)) if args.tracks else TRACKS
    try:
        report_path = run_quickstart(args.output.resolve(), selected_tracks=tracks)
    except (FileExistsError, RuntimeError, ValueError) as error:
        parser.exit(2, f"Quickstart failed: {error}\n")
    print(f"Quickstart passed. Shareable report: {report_path}")


if __name__ == "__main__":
    main()
