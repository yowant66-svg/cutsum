from __future__ import annotations

import hashlib
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).parents[1]


def test_fixture_manifest_has_only_governed_entries() -> None:
    manifest_path = PROJECT_ROOT / "tests" / "fixtures" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["schema_version"] == "1.0"
    assert len(manifest["fixtures"]) == 1


def test_each_persisted_fixture_has_license_provenance_and_hash() -> None:
    manifest_path = PROJECT_ROOT / "tests" / "fixtures" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    required_fields = {
        "path",
        "spdx_license",
        "provenance",
        "generator_version",
        "sha256",
    }
    for fixture in manifest["fixtures"]:
        assert required_fields <= fixture.keys()
        fixture_path = PROJECT_ROOT / "tests" / "fixtures" / fixture["path"]
        assert fixture_path.is_file()
        assert hashlib.sha256(fixture_path.read_bytes()).hexdigest() == fixture["sha256"]
