from __future__ import annotations

import argparse
from pathlib import Path

from universal_cutup.application.demo import generate_demo_media


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate rights-safe synthetic CutSum demo media."
    )
    parser.add_argument("output", type=Path)
    parser.add_argument("--duration", type=int, default=60)
    args = parser.parse_args()
    output = args.output.resolve()
    generate_demo_media(output, duration_seconds=args.duration)
    print(output)


if __name__ == "__main__":
    main()
