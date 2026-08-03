from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel

from universal_cutup.domain.intelligence import ControlMode
from universal_cutup.domain.sources import RightsAttestation
from universal_cutup.domain.specs import (
    OutputSpec,
    ReframeSafeAreaPreset,
    ReframeSpec,
    RenderSpec,
    SubtitleMode,
    SubtitleSpec,
)
from universal_cutup.domain.transcript import TranscriptArtifact, TranscriptSegment
from universal_cutup.sdk import (
    configure_reframe,
    create_plan,
    execute_cut_plan,
    inspect_source,
)


def _write_json(path: Path, value: BaseModel | dict[str, object]) -> None:
    if isinstance(value, BaseModel):
        payload = value.model_dump_json(indent=2, exclude_none=True)
    else:
        payload = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)
    path.write_text(payload + "\n", encoding="utf-8")


def _generate_source(path: Path) -> None:
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=c=0x162033:s=640x360:r=25:d=6",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=660:sample_rate=48000:duration=6",
            "-vf",
            (
                "drawgrid=w=80:h=60:t=2:c=white@0.16,"
                "drawbox=x=40:y=40:w=120:h=280:t=fill:c=0x36c36a,"
                "drawbox=x=270:y=30:w=100:h=300:t=fill:c=0xf05a5a,"
                "drawbox=x=500:y=100:w=90:h=180:t=fill:c=0x4b8df8"
            ),
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-shortest",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )


def _extract_frame(video: Path, frame: Path) -> None:
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-ss",
            "2",
            "-i",
            str(video),
            "-frames:v",
            "1",
            str(frame),
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=20,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate offline basic 9:16 review evidence.")
    parser.add_argument("output_root", type=Path)
    args = parser.parse_args()
    output_root = args.output_root.resolve()
    output_root.mkdir(parents=True, exist_ok=False)
    source_path = output_root / "synthetic-landscape-source.mp4"
    _generate_source(source_path)
    inspection = inspect_source(
        source_path,
        source_id="source-vertical-diagnostic",
        rights_attestation=RightsAttestation.OWNED,
    )
    text = "A fixed-focus composition test keeps subtitles inside the visible safe area."
    transcript = TranscriptArtifact(
        document_type="transcript_artifact",
        created_at=datetime.now(UTC),
        created_by="vertical-reframe-diagnostic",
        transcript_id="transcript-vertical-diagnostic",
        source_id=inspection.source.source_id,
        language="en",
        segments=(
            TranscriptSegment(
                segment_id="segment-vertical-diagnostic",
                source_id=inspection.source.source_id,
                start_ms=500,
                end_ms=5500,
                text=text,
                text_sha256=hashlib.sha256(text.encode()).hexdigest(),
            ),
        ),
    )
    base_plan = create_plan(
        inspection.source,
        transcript,
        output_spec=OutputSpec(
            subtitle=SubtitleSpec(
                mode=SubtitleMode.SOURCE_BURN_IN,
                language="en",
            )
        ),
    )
    modes = {
        "center_crop": ReframeSpec(
            mode="center_crop",
            safe_area_preset=ReframeSafeAreaPreset.YOUTUBE_SHORTS,
        ),
        "manual_focus": ReframeSpec(
            mode="manual_focus",
            focus_x=0.15,
            focus_y=0.45,
            safe_area_preset=ReframeSafeAreaPreset.YOUTUBE_SHORTS,
        ),
        "fit_background": ReframeSpec(
            mode="fit_background",
            safe_area_preset=ReframeSafeAreaPreset.YOUTUBE_SHORTS,
        ),
        "fixed_subject": ReframeSpec(
            mode="fixed_subject",
            safe_area_preset=ReframeSafeAreaPreset.YOUTUBE_SHORTS,
        ),
    }
    manifest: dict[str, object] = {
        "control_mode": ControlMode.DIRECTED.value,
        "source": str(source_path),
        "modes": {},
    }
    mode_records: dict[str, object] = {}
    for mode, reframe_spec in modes.items():
        mode_root = output_root / mode
        plan = configure_reframe(
            base_plan,
            reframe_spec,
            render_spec=RenderSpec(
                target_width=360,
                target_height=640,
                allow_upscale=True,
            ),
        )
        execution = execute_cut_plan(
            plan,
            binding=inspection.binding,
            output_root=mode_root,
        )
        if execution.status != "success":
            raise RuntimeError(f"{mode} execution failed: {execution.model_dump_json()}")
        _write_json(mode_root / "cut-plan.json", plan)
        _write_json(mode_root / "execution-record.json", execution)
        video_artifact = next(
            artifact for artifact in execution.artifacts if artifact.artifact_type == "video"
        )
        video_path = mode_root / video_artifact.relative_path
        frame_path = mode_root / "review-frame.png"
        _extract_frame(video_path, frame_path)
        mode_records[mode] = {
            "video": str(video_path),
            "frame": str(frame_path),
            "sha256": video_artifact.sha256,
            "resolution": video_artifact.actual_output_resolution,
            "crop_box": video_artifact.crop_box,
            "safe_area": video_artifact.safe_area,
            "composition_reason": video_artifact.composition_reason,
            "subtitle_backend": execution.steps[0].details.get("subtitle_backend"),
        }
    manifest["modes"] = mode_records
    _write_json(output_root / "manifest.json", manifest)
    lines = [
        "# Basic 9:16 maintainer review",
        "",
        "Synthetic owned input; deterministic FFmpeg execution; no detector or tracking claim.",
        "",
    ]
    for mode, record in mode_records.items():
        typed_record = record if isinstance(record, dict) else {}
        lines.extend(
            [
                f"## {mode}",
                "",
                f"- Video: {typed_record.get('video')}",
                f"- Frame: {typed_record.get('frame')}",
                f"- Resolution: {typed_record.get('resolution')}",
                f"- Crop: {typed_record.get('crop_box')}",
                f"- Safe area: {typed_record.get('safe_area')}",
                f"- Reason: {typed_record.get('composition_reason')}",
                "- Maintainer decision: pending",
                "",
            ]
        )
    (output_root / "maintainer-review.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
