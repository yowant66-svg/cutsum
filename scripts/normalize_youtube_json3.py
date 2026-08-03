from __future__ import annotations

import argparse
import json
from pathlib import Path

from universal_cutup.adapters.youtube_json3 import normalize_youtube_json3


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert raw YouTube JSON3 captions into CutSum JSON transcript input."
    )
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--maximum-end-ms", type=int)
    args = parser.parse_args()
    payload = json.loads(args.source.read_text(encoding="utf-8"))
    normalized = normalize_youtube_json3(payload, maximum_end_ms=args.maximum_end_ms)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as file_handle:
        json.dump(normalized, file_handle, ensure_ascii=False, indent=2)
        file_handle.write("\n")


if __name__ == "__main__":
    main()
