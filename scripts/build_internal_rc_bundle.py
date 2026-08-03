from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import tomllib
import zipfile
from pathlib import Path
from typing import Any


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _git(repository: Path, *arguments: str) -> str:
    return subprocess.run(
        ["git", *arguments],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _zip_info(name: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, date_time=(2020, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o100644 << 16
    return info


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a private internal-RC review bundle.")
    parser.add_argument("output_zip", type=Path)
    parser.add_argument("install_evidence_manifest", type=Path)
    args = parser.parse_args()
    repository = Path(__file__).parents[1].resolve()
    output_zip = args.output_zip.resolve()
    evidence_manifest = args.install_evidence_manifest.resolve(strict=True)
    if output_zip.exists():
        raise FileExistsError(f"review bundle already exists: {output_zip.name}")
    if _git(repository, "status", "--porcelain"):
        raise RuntimeError("internal RC bundle requires a clean Git working tree")
    project = tomllib.loads((repository / "pyproject.toml").read_text(encoding="utf-8"))
    version = project["project"]["version"]
    if version != "0.1.0rc2":
        raise RuntimeError(f"unexpected internal RC version: {version}")
    external_evidence = json.loads(evidence_manifest.read_text(encoding="utf-8"))
    if external_evidence.get("package_version") != version:
        raise RuntimeError("install evidence does not match the RC distribution version")
    files = {
        f"dist/universal_cutup-{version}-py3-none-any.whl": (
            repository / f"dist/universal_cutup-{version}-py3-none-any.whl"
        ),
        f"dist/universal_cutup-{version}.tar.gz": (
            repository / f"dist/universal_cutup-{version}.tar.gz"
        ),
        "schemas/manifest.json": repository / "schemas/manifest.json",
        "docs/internal-rc-evidence-index.md": repository / "docs/internal-rc-evidence-index.md",
        "docs/release-readiness.md": repository / "docs/release-readiness.md",
        "docs/risk-register.md": repository / "docs/risk-register.md",
        "docs/decisions.md": repository / "docs/decisions.md",
        "docs/open-source-readiness.md": repository / "docs/open-source-readiness.md",
        "provenance/ledger.yaml": repository / "provenance/ledger.yaml",
        "README.md": repository / "README.md",
        "CHANGELOG.md": repository / "CHANGELOG.md",
        "LICENSE": repository / "LICENSE",
        "NOTICE": repository / "NOTICE",
        "evidence/install-rc2-manifest.json": evidence_manifest,
    }
    payloads: dict[str, bytes] = {
        archive_name: source.read_bytes() for archive_name, source in files.items()
    }
    bundle_manifest: dict[str, Any] = {
        "bundle_type": "internal_review_only",
        "distribution_version": version,
        "source_commit": _git(repository, "rev-parse", "HEAD"),
        "public_release": False,
        "media_included": False,
        "files": {
            name: {"sha256": _sha256(content), "size_bytes": len(content)}
            for name, content in sorted(payloads.items())
        },
    }
    payloads["bundle-manifest.json"] = (
        json.dumps(bundle_manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode()
    output_zip.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output_zip, "x") as archive:
        for name, content in sorted(payloads.items()):
            archive.writestr(_zip_info(name), content)
    print(
        json.dumps(
            {
                "path": str(output_zip),
                "sha256": _sha256(output_zip.read_bytes()),
                "source_commit": bundle_manifest["source_commit"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
