from __future__ import annotations

import argparse
import json
from pathlib import Path

from universal_cutup.schema import export_schemas


def main() -> None:
    parser = argparse.ArgumentParser(description="Export deterministic CutSum schemas.")
    parser.add_argument(
        "output_directory",
        nargs="?",
        type=Path,
        default=Path(__file__).parents[1] / "schemas",
    )
    args = parser.parse_args()
    output_directory = args.output_directory.resolve()
    manifest = export_schemas(output_directory)
    (output_directory / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
