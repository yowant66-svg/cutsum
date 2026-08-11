from __future__ import annotations

import argparse
import shutil
import stat
import zipfile
from pathlib import Path

PLUGIN_TIMESTAMP = (2026, 8, 11, 0, 0, 0)


def _write_reproducible_zip(source: Path, archive_path: Path) -> None:
    with zipfile.ZipFile(
        archive_path,
        mode="x",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
    ) as archive:
        for path in sorted(item for item in source.rglob("*") if item.is_file()):
            relative_path = path.relative_to(source.parent).as_posix()
            info = zipfile.ZipInfo(relative_path, date_time=PLUGIN_TIMESTAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            info.create_system = 3
            archive.writestr(info, path.read_bytes(), compresslevel=9)


def build_openai_plugin(repository: Path, output_directory: Path) -> Path:
    if output_directory.exists():
        raise FileExistsError(f"plugin output already exists: {output_directory.name}")
    output_directory.mkdir(parents=True)
    staging = output_directory / "cutsum"
    shutil.copytree(repository / "distribution/openai-plugin", staging)
    shutil.copytree(
        repository / ".agents/skills/cutsum-intelligence",
        staging / "skills/cutsum-intelligence",
    )
    archive = output_directory.with_suffix(".zip")
    _write_reproducible_zip(staging, archive)
    return archive


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the deterministic CutSum plugin ZIP.")
    parser.add_argument("output_directory", type=Path)
    parser.add_argument("--repository", type=Path, default=Path(__file__).parents[1])
    args = parser.parse_args()
    archive = build_openai_plugin(
        args.repository.resolve(),
        args.output_directory.resolve(),
    )
    print(archive)


if __name__ == "__main__":
    main()
