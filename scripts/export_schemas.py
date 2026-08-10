from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).parents[1]
SOURCE_ROOT = REPOSITORY_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from universal_cutup.schema import export_schemas  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Export deterministic CutSum schemas.")
    parser.add_argument(
        "output_directory",
        nargs="?",
        type=Path,
        default=REPOSITORY_ROOT / "schemas",
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
