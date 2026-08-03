from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

from universal_cutup.application.sdk import inspect_source
from universal_cutup.domain.sources import RightsAttestation
from universal_cutup.domain.sports import SportsObservationBundle


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate an explicitly synthetic sports-like media fixture."
    )
    parser.add_argument("observations", type=Path)
    parser.add_argument("output_root", type=Path)
    args = parser.parse_args()

    bundle = SportsObservationBundle.model_validate_json(
        args.observations.read_text(encoding="utf-8")
    )
    output_root = args.output_root.resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    media_path = output_root / "synthetic-sports-source.mp4"
    video_filter = ",".join(
        (
            "drawbox=x=0:y=0:w=iw:h=ih:color=green@0.35:t=fill:enable='between(t,10,14)'",
            "drawbox=x=0:y=0:w=iw:h=ih:color=blue@0.35:t=fill:enable='between(t,30,33)'",
            "drawbox=x=0:y=0:w=iw:h=ih:color=yellow@0.30:t=fill:enable='between(t,40,47)'",
        )
    )
    audio_expression = (
        "aevalsrc=0.03*sin(2*PI*220*t)"
        "+0.35*sin(2*PI*880*t)*between(t\\,12.5\\,14)"
        "+0.40*sin(2*PI*660*t)*between(t\\,20\\,21)"
        "+0.30*sin(2*PI*990*t)*between(t\\,31\\,33)"
        ":s=48000:d=60"
    )
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=640x360:rate=25:duration=60",
            "-f",
            "lavfi",
            "-i",
            audio_expression,
            "-vf",
            video_filter,
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
        timeout=120,
    )
    inspection = inspect_source(
        media_path,
        source_id=bundle.source_id,
        rights_attestation=RightsAttestation.OWNED,
    )
    (output_root / "source.json").write_text(
        inspection.source.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )
    print(inspection.source.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
