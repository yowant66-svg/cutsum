from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

from scripts.build_openai_plugin import build_openai_plugin

REPOSITORY_ROOT = Path(__file__).parents[2]
PLUGIN_MANIFEST = REPOSITORY_ROOT / "distribution/openai-plugin/.codex-plugin/plugin.json"


def test_plugin_build_copies_repo_skill_byte_for_byte(tmp_path: Path) -> None:
    archive = build_openai_plugin(REPOSITORY_ROOT, tmp_path / "plugin-build")

    with zipfile.ZipFile(archive) as package:
        names = set(package.namelist())
        assert "cutsum/.codex-plugin/plugin.json" in names
        assert "cutsum/skills/cutsum-intelligence/SKILL.md" in names
        assert (
            package.read("cutsum/skills/cutsum-intelligence/SKILL.md")
            == (REPOSITORY_ROOT / ".agents/skills/cutsum-intelligence/SKILL.md").read_bytes()
        )


def test_plugin_manifest_keeps_capability_boundary() -> None:
    manifest = json.loads(PLUGIN_MANIFEST.read_text(encoding="utf-8"))

    assert manifest["name"] == "cutsum"
    assert manifest["version"] == "0.1.0-alpha.4"
    assert manifest["license"] == "Apache-2.0"
    assert manifest["skills"] == "./skills/"
    assert "transcript" in manifest["description"].lower()
    serialized = json.dumps(manifest, ensure_ascii=False).lower()
    assert "visual tracking" not in serialized
    assert "mcpservers" not in manifest
    assert "apps" not in manifest


def test_plugin_archive_is_reproducible(tmp_path: Path) -> None:
    first = build_openai_plugin(REPOSITORY_ROOT, tmp_path / "first")
    second = build_openai_plugin(REPOSITORY_ROOT, tmp_path / "second")

    assert (
        hashlib.sha256(first.read_bytes()).digest() == hashlib.sha256(second.read_bytes()).digest()
    )
