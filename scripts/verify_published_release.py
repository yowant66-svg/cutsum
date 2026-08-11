from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any
from urllib.request import urlopen


def verify_pypi_release(
    *,
    repository_url: str,
    version: str,
    expected_hashes: dict[str, str],
) -> dict[str, str]:
    endpoint = f"{repository_url.rstrip('/')}/pypi/cutsum/{version}/json"
    with urlopen(endpoint, timeout=30) as response:
        payload: Any = json.load(response)
    if payload.get("info", {}).get("version") != version:
        raise ValueError("published project version does not match the requested release")
    observed = {item["filename"]: item["digests"]["sha256"] for item in payload.get("urls", [])}
    if observed != expected_hashes:
        raise ValueError("published distribution hashes do not match the release build")
    return observed


def expected_distribution_hashes(checksum_file: Path) -> dict[str, str]:
    expected: dict[str, str] = {}
    for raw_line in checksum_file.read_text(encoding="utf-8").splitlines():
        digest, filename = raw_line.split("  ", maxsplit=1)
        if filename.endswith((".whl", ".tar.gz")):
            expected[filename] = digest
    if len(expected) != 2:
        raise ValueError("release checksums must contain exactly one wheel and one sdist")
    return expected


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify published CutSum distribution hashes.")
    parser.add_argument("version")
    parser.add_argument("checksum_file", type=Path)
    parser.add_argument("--repository-url", default="https://pypi.org")
    args = parser.parse_args()
    observed = verify_pypi_release(
        repository_url=args.repository_url,
        version=args.version,
        expected_hashes=expected_distribution_hashes(args.checksum_file),
    )
    print(json.dumps(observed, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
