from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from universal_cutup.domain.blind_runs import (
    BlindRunInput,
    BlindRunManifest,
    FrozenArtifact,
)
from universal_cutup.hashing import document_sha256

FORBIDDEN_BLIND_PATH_NAMES = frozenset(
    {
        "curated-inputs.json",
        "reference",
        "gate-g-results",
        "universal-cutup-gate-g-review",
        "universal-cutup-gate-g-work",
    }
)
FREEZE_MANIFEST_NAME = "blind-run-manifest.json"


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file_handle:
        for chunk in iter(lambda: file_handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _resolved_within(path: Path, root: Path) -> Path:
    resolved_root = root.resolve(strict=True)
    resolved_path = path.resolve(strict=True)
    if not resolved_path.is_relative_to(resolved_root):
        raise ValueError("blind input must remain inside the declared blind-input root")
    return resolved_path


def assert_blind_path(path: Path, *, blind_input_root: Path) -> Path:
    resolved_path = _resolved_within(path, blind_input_root)
    lowered_parts = {part.casefold() for part in resolved_path.parts}
    if lowered_parts & FORBIDDEN_BLIND_PATH_NAMES:
        raise ValueError("curated/reference paths are forbidden during a blind run")
    if resolved_path.is_symlink():
        raise ValueError("blind input artifacts must not be symlinks")
    return resolved_path


def load_blind_run_input(path: Path, *, blind_input_root: Path) -> BlindRunInput:
    resolved_path = assert_blind_path(path, blind_input_root=blind_input_root)
    payload = json.loads(resolved_path.read_text(encoding="utf-8"))
    blind_input = BlindRunInput.model_validate(payload)
    assert_blind_path(Path(blind_input.transcript_path), blind_input_root=blind_input_root)
    if blind_input.media_path is not None:
        assert_blind_path(Path(blind_input.media_path), blind_input_root=blind_input_root)
    return blind_input


def _frozen_artifacts(result_root: Path) -> tuple[FrozenArtifact, ...]:
    artifacts: list[FrozenArtifact] = []
    for path in sorted(result_root.rglob("*")):
        if path.is_dir() or path.name == FREEZE_MANIFEST_NAME:
            continue
        if path.is_symlink():
            raise ValueError("blind result artifacts must not be symlinks")
        artifacts.append(
            FrozenArtifact(
                relative_path=str(path.relative_to(result_root)),
                sha256=_file_sha256(path),
                size_bytes=path.stat().st_size,
            )
        )
    if not artifacts:
        raise ValueError("cannot freeze an empty blind result directory")
    return tuple(artifacts)


def freeze_blind_run(
    result_root: Path,
    *,
    blind_run_id: str,
    blind_input: BlindRunInput | None = None,
    created_at: datetime | None = None,
) -> BlindRunManifest:
    resolved_root = result_root.resolve(strict=True)
    output_path = resolved_root / FREEZE_MANIFEST_NAME
    if output_path.exists():
        raise FileExistsError(f"blind run is already frozen: {output_path}")
    artifacts = _frozen_artifacts(resolved_root)
    aggregate_sha256 = document_sha256(
        {"artifacts": [artifact.model_dump(mode="json") for artifact in artifacts]}
    )
    manifest = BlindRunManifest(
        document_type="blind_run_manifest",
        created_at=created_at or datetime.now(UTC),
        created_by="universal-cutup",
        blind_run_id=blind_run_id,
        suite_id=blind_input.suite_id if blind_input is not None else None,
        case_id=blind_input.case_id if blind_input is not None else None,
        track=blind_input.track if blind_input is not None else None,
        result_root=str(resolved_root),
        artifacts=artifacts,
        aggregate_sha256=aggregate_sha256,
    )
    with output_path.open("x", encoding="utf-8") as file_handle:
        file_handle.write(manifest.model_dump_json(indent=2))
        file_handle.write("\n")
    return manifest


def verify_frozen_blind_run(manifest_path: Path) -> BlindRunManifest:
    manifest = BlindRunManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
    result_root = Path(manifest.result_root).resolve(strict=True)
    actual = _frozen_artifacts(result_root)
    expected = manifest.artifacts
    if actual != expected:
        raise ValueError("blind run artifacts changed after freeze")
    aggregate_sha256 = document_sha256(
        {"artifacts": [artifact.model_dump(mode="json") for artifact in actual]}
    )
    if aggregate_sha256 != manifest.aggregate_sha256:
        raise ValueError("blind run aggregate hash does not match the frozen manifest")
    return manifest


def load_reference_after_freeze(
    reference_path: Path,
    *,
    manifest_path: Path,
) -> object:
    manifest = verify_frozen_blind_run(manifest_path)
    reference_name = reference_path.name.casefold()
    if reference_name != "curated-inputs.json" and not reference_name.endswith("-reference.json"):
        raise ValueError("blind comparison accepts only a declared reference JSON")
    payload = json.loads(reference_path.read_text(encoding="utf-8"))
    if manifest.suite_id is not None:
        if not isinstance(payload, dict):
            raise ValueError("four-track reference must be a JSON object")
        if (
            payload.get("suite_id") != manifest.suite_id
            or payload.get("case_id") != manifest.case_id
            or payload.get("track")
            != (manifest.track.value if manifest.track is not None else None)
        ):
            raise ValueError("reference identity does not match frozen blind run")
    return payload
