from __future__ import annotations

import argparse
import json
from pathlib import Path

from universal_cutup.application.four_track_evaluation import (
    run_four_track_evaluation,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the four-track capability and deterministic regression suite."
    )
    parser.add_argument("manifest", type=Path)
    parser.add_argument("output_root", type=Path)
    parser.add_argument("--trials", type=int, default=3)
    args = parser.parse_args()
    report = run_four_track_evaluation(
        args.manifest,
        args.output_root,
        trial_count=args.trials,
    )
    print(json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
