from __future__ import annotations

import hashlib
import json
from pathlib import Path

from scripts.build_public_release import build_release_assets

REPOSITORY_ROOT = Path(__file__).parents[2]


def test_public_release_assets_are_manifested_and_checksummed(tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "cutsum-0.1.0a4-py3-none-any.whl").write_bytes(b"wheel")
    (dist / "cutsum-0.1.0a4.tar.gz").write_bytes(b"sdist")
    plugin_archive = tmp_path / "cutsum-0.1.0a4-openai-plugin.zip"
    plugin_archive.write_bytes(b"plugin")
    output = tmp_path / "release"
    source_commit = "a" * 40

    manifest = build_release_assets(
        REPOSITORY_ROOT,
        dist,
        output,
        source_commit=source_commit,
        plugin_archive=plugin_archive,
    )

    assert manifest["tag"] == "v0.1.0a4"
    assert manifest["source_commit"] == source_commit
    assert manifest["pypi_published"] is False
    assert manifest["publication_targets"] == ["github", "pypi", "testpypi"]
    assert manifest["publication_state"] == "built_not_published"
    assert "cutsum-0.1.0a4-openai-plugin.zip" in manifest["assets"]
    sbom = json.loads((output / "cutsum-0.1.0a4.cdx.json").read_text(encoding="utf-8"))
    assert sbom["bomFormat"] == "CycloneDX"
    assert sbom["specVersion"] == "1.6"
    assert sbom["metadata"]["component"]["name"] == "cutsum"
    checksums = (output / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines()
    assert len(checksums) == 5
    for line in checksums:
        expected, name = line.split("  ", maxsplit=1)
        assert hashlib.sha256((output / name).read_bytes()).hexdigest() == expected
