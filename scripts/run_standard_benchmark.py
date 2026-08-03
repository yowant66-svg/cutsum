from __future__ import annotations

import argparse
from pathlib import Path

from universal_cutup.application.benchmarking import run_standard_benchmark


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the controlled Gate G benchmark.")
    parser.add_argument("manifest", type=Path)
    parser.add_argument("curated_inputs", type=Path)
    parser.add_argument("output_directory", type=Path)
    args = parser.parse_args()
    result = run_standard_benchmark(
        args.manifest,
        args.curated_inputs,
        args.output_directory,
    )
    print(
        f"completed {result['item_count']} items and {result['task_count']} tasks "
        f"at {args.output_directory}"
    )


if __name__ == "__main__":
    main()
