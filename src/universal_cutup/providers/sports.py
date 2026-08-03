from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, Protocol

from pydantic import ValidationError

from universal_cutup.domain.errors import CutupError, ErrorCode
from universal_cutup.domain.records import ProviderRecord
from universal_cutup.domain.sources import MediaSource
from universal_cutup.domain.sports import SportsObservationBundle
from universal_cutup.hashing import document_sha256

SportsFileProviderKind = Literal["fixture", "host_ai_file", "human_file"]


class SportsObservationProvider(Protocol):
    provider_id: str

    def observe(self, media_path: Path, source: MediaSource) -> SportsObservationBundle: ...


@dataclass(frozen=True, slots=True)
class ImportedSportsObservations:
    artifact: SportsObservationBundle
    provider_record: ProviderRecord
    canonical_sha256: str
    raw_file_sha256: str


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file_handle:
        for chunk in iter(lambda: file_handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class FileSportsObservationProvider:
    def __init__(
        self,
        *,
        provider_kind: SportsFileProviderKind,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.provider_kind = provider_kind
        self.provider_id = f"sports-{provider_kind}-provider"
        self._clock = clock or (lambda: datetime.now(UTC))

    def import_observations(self, path: Path) -> ImportedSportsObservations:
        resolved = path.resolve(strict=True)
        raw_hash = _file_sha256(resolved)
        try:
            artifact = SportsObservationBundle.model_validate_json(
                resolved.read_text(encoding="utf-8")
            )
        except (json.JSONDecodeError, UnicodeDecodeError, ValidationError) as error:
            raise CutupError(
                ErrorCode.ASSESSMENT_INVALID,
                "invalid SportsObservationBundle file",
                category="validation",
                step="import_sports_observations",
                details={"path": resolved.name, "validation_error": str(error)},
            ) from error
        if artifact.provider_kind != self.provider_kind:
            raise CutupError(
                ErrorCode.ASSESSMENT_INVALID,
                "sports artifact provider_kind does not match file provider",
                category="validation",
                step="import_sports_observations",
            )
        if len(artifact.provider_record_refs) != 1:
            raise CutupError(
                ErrorCode.ASSESSMENT_INVALID,
                "file sports artifact must contain exactly one provider record ref",
                category="validation",
                step="import_sports_observations",
            )
        canonical_hash = document_sha256(artifact)
        occurred_at = self._clock()
        record = ProviderRecord(
            provider_record_id=artifact.provider_record_refs[0],
            provider_id=self.provider_id,
            operation="observe_sports_events",
            started_at=occurred_at,
            completed_at=occurred_at,
            input_hashes=(raw_hash,),
            output_hashes=(canonical_hash,),
            warnings=("fixture sports observations; not real detector output",)
            if self.provider_kind == "fixture"
            else (),
        )
        return ImportedSportsObservations(
            artifact=artifact,
            provider_record=record,
            canonical_sha256=canonical_hash,
            raw_file_sha256=raw_hash,
        )
