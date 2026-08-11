from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import tomllib
import uuid
from pathlib import Path
from typing import Any

REPOSITORY_URL = "https://github.com/yowant66-svg/cutsum"
COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40}$")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _purl(name: str, version: str) -> str:
    return f"pkg:pypi/{name.replace('_', '-').lower()}@{version}"


def _runtime_packages(lock: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    packages = {package["name"]: package for package in lock["package"]}
    pending = ["cutsum"]
    selected: set[str] = set()
    while pending:
        name = pending.pop()
        if name in selected:
            continue
        package = packages.get(name)
        if package is None:
            raise ValueError(f"runtime dependency is absent from uv.lock: {name}")
        selected.add(name)
        pending.extend(
            dependency["name"]
            for dependency in package.get("dependencies", [])
            if dependency["name"] not in selected
        )
    return tuple(packages[name] for name in sorted(selected))


def _component(package: dict[str, Any], *, root: bool = False) -> dict[str, Any]:
    name = package["name"]
    version = package["version"]
    component: dict[str, Any] = {
        "bom-ref": _purl(name, version),
        "name": name,
        "purl": _purl(name, version),
        "type": "application" if root else "library",
        "version": version,
    }
    if root:
        component["licenses"] = [{"license": {"id": "Apache-2.0"}}]
    sdist = package.get("sdist")
    if isinstance(sdist, dict):
        source_hash = sdist.get("hash")
        if isinstance(source_hash, str) and source_hash.startswith("sha256:"):
            component["hashes"] = [
                {"alg": "SHA-256", "content": source_hash.removeprefix("sha256:")}
            ]
    return component


def _sbom(lock: dict[str, Any], *, source_commit: str) -> dict[str, Any]:
    packages = _runtime_packages(lock)
    root = next(package for package in packages if package["name"] == "cutsum")
    release_identity = f"{REPOSITORY_URL}/commit/{source_commit}"
    dependencies = []
    selected_names = {package["name"] for package in packages}
    for package in packages:
        dependency_refs = sorted(
            _purl(
                dependency["name"],
                next(item["version"] for item in packages if item["name"] == dependency["name"]),
            )
            for dependency in package.get("dependencies", [])
            if dependency["name"] in selected_names
        )
        dependencies.append(
            {"ref": _purl(package["name"], package["version"]), "dependsOn": dependency_refs}
        )
    return {
        "$schema": "https://cyclonedx.org/schema/bom-1.6.schema.json",
        "bomFormat": "CycloneDX",
        "components": [_component(package) for package in packages if package["name"] != "cutsum"],
        "dependencies": dependencies,
        "metadata": {
            "component": _component(root, root=True),
            "properties": [
                {"name": "cutsum:source-commit", "value": source_commit},
                {"name": "cutsum:repository", "value": REPOSITORY_URL},
            ],
        },
        "serialNumber": f"urn:uuid:{uuid.uuid5(uuid.NAMESPACE_URL, release_identity)}",
        "specVersion": "1.6",
        "version": 1,
    }


def build_release_assets(
    repository: Path,
    dist_directory: Path,
    output_directory: Path,
    *,
    source_commit: str,
    plugin_archive: Path,
) -> dict[str, Any]:
    if COMMIT_PATTERN.fullmatch(source_commit) is None:
        raise ValueError("source_commit must be a full lowercase Git SHA-1")
    if output_directory.exists():
        raise FileExistsError(f"release output already exists: {output_directory.name}")
    project = tomllib.loads((repository / "pyproject.toml").read_text(encoding="utf-8"))
    lock = tomllib.loads((repository / "uv.lock").read_text(encoding="utf-8"))
    version = project["project"]["version"]
    tag = f"v{version}"
    wheel = dist_directory / f"cutsum-{version}-py3-none-any.whl"
    sdist = dist_directory / f"cutsum-{version}.tar.gz"
    for artifact in (wheel, sdist, plugin_archive):
        if not artifact.is_file():
            raise FileNotFoundError(f"missing release artifact: {artifact.name}")
    output_directory.mkdir(parents=True)
    copied = []
    for artifact in (wheel, sdist, plugin_archive):
        target = output_directory / artifact.name
        shutil.copyfile(artifact, target)
        copied.append(target)
    sbom_path = output_directory / f"cutsum-{version}.cdx.json"
    _write_json(sbom_path, _sbom(lock, source_commit=source_commit))
    copied.append(sbom_path)
    evidence_files = {
        "license": repository / "LICENSE",
        "maintainer_approval": repository / "docs" / "maintainer-release-approval.md",
        "provenance_ledger": repository / "provenance" / "ledger.yaml",
        "schema_manifest": repository / "schemas" / "manifest.json",
    }
    manifest = {
        "release_type": "public_github_alpha",
        "version": version,
        "tag": tag,
        "source_commit": source_commit,
        "repository": REPOSITORY_URL,
        "pypi_published": False,
        "publication_targets": ["github", "pypi", "testpypi"],
        "publication_state": "built_not_published",
        "media_included": False,
        "runtime_python": project["project"]["requires-python"],
        "assets": {
            path.name: {"sha256": _sha256(path), "size_bytes": path.stat().st_size}
            for path in sorted(copied)
        },
        "evidence": {
            name: {"path": str(path.relative_to(repository)), "sha256": _sha256(path)}
            for name, path in sorted(evidence_files.items())
        },
        "limitations": [
            "sports support is transcript-only heuristic Alpha",
            "no bundled ASR, translation model, downloader, publisher, or model weights",
            "automated evidence is not an editorial-quality claim",
        ],
    }
    manifest_path = output_directory / "release-manifest.json"
    _write_json(manifest_path, manifest)
    checksum_paths = [*copied, manifest_path]
    checksums = "".join(
        f"{_sha256(path)}  {path.name}\n"
        for path in sorted(checksum_paths, key=lambda item: item.name)
    )
    (output_directory / "SHA256SUMS.txt").write_text(checksums, encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build deterministic CutSum GitHub release assets."
    )
    parser.add_argument("dist_directory", type=Path)
    parser.add_argument("output_directory", type=Path)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--plugin-archive", type=Path, required=True)
    parser.add_argument("--repository", type=Path, default=Path(__file__).parents[1])
    args = parser.parse_args()
    manifest = build_release_assets(
        args.repository.resolve(),
        args.dist_directory.resolve(),
        args.output_directory.resolve(),
        source_commit=args.source_commit,
        plugin_archive=args.plugin_archive.resolve(),
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
