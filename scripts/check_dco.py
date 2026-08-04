from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

SIGNOFF_PATTERN = re.compile(
    r"^Signed-off-by:\s+[^<>\r\n]+\s+<[^<>\s]+@[^<>\s]+>\s*$",
    flags=re.IGNORECASE | re.MULTILINE,
)


def has_dco_signoff(message: str) -> bool:
    return SIGNOFF_PATTERN.search(message) is not None


def _git(repository: Path, *arguments: str) -> str:
    return subprocess.run(
        ["git", *arguments],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def commits_missing_signoff(repository: Path, base: str, head: str) -> tuple[str, ...]:
    commits = _git(repository, "rev-list", "--reverse", f"{base}..{head}").splitlines()
    return tuple(
        commit
        for commit in commits
        if not has_dco_signoff(_git(repository, "show", "-s", "--format=%B", commit))
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify DCO sign-off on a Git commit range.")
    parser.add_argument("base")
    parser.add_argument("head")
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    args = parser.parse_args()
    try:
        missing = commits_missing_signoff(args.repository.resolve(), args.base, args.head)
    except subprocess.CalledProcessError as error:
        print(error.stderr.strip() or "unable to inspect Git commit range", file=sys.stderr)
        return 2
    if missing:
        for commit in missing:
            print(f"missing DCO sign-off: {commit}", file=sys.stderr)
        return 1
    print(f"DCO sign-off verified for {args.base}..{args.head}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
