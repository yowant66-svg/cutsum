from __future__ import annotations

import argparse
from pathlib import Path

from universal_cutup.application.demo import DEMO_TRACKS, run_demo
from universal_cutup.domain.errors import CutupError

TRACKS = DEMO_TRACKS


def run_quickstart(
    output_root: Path,
    *,
    selected_tracks: tuple[str, ...] = TRACKS,
) -> Path:
    return run_demo(output_root, selected_tracks=selected_tracks).report_path


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
    except (CutupError, OSError, RuntimeError, ValueError) as error:
        parser.exit(2, f"Quickstart failed: {error}\n")
    print(f"Quickstart passed. Shareable report: {report_path}")


if __name__ == "__main__":
    main()
