from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path


def ffmpeg_command(executable: str, output: Path, duration_seconds: int) -> list[str]:
    return [
        executable,
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
    ]


def generate_demo_media(output: Path, *, duration_seconds: int = 60) -> None:
    if duration_seconds <= 0:
        raise ValueError("duration_seconds must be positive")
    if output.exists():
        raise FileExistsError(f"demo media already exists: {output.name}")
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise RuntimeError("ffmpeg is required to generate the demo media")
    output.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ffmpeg_command(ffmpeg, output, duration_seconds),
        check=True,
        timeout=max(30, duration_seconds * 3),
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate rights-safe synthetic CutSum demo media."
    )
    parser.add_argument("output", type=Path)
    parser.add_argument("--duration", type=int, default=60)
    args = parser.parse_args()
    generate_demo_media(args.output.resolve(), duration_seconds=args.duration)
    print(args.output.resolve())


if __name__ == "__main__":
    main()
