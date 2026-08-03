from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, ValidationError

from universal_cutup.domain.assessments import (
    AssessmentBundle,
    CandidateProposalBundle,
)
from universal_cutup.domain.errors import CutupError, ErrorCode
from universal_cutup.domain.intelligence import ContentProfile
from universal_cutup.domain.records import ProviderRecord
from universal_cutup.hashing import document_sha256

ArtifactType = TypeVar("ArtifactType", bound=BaseModel)
FileProviderKind = Literal["fixture", "host_ai_file", "human_file"]


@dataclass(frozen=True, slots=True)
class ImportedArtifact(Generic[ArtifactType]):
    artifact: ArtifactType
    provider_record: ProviderRecord
    canonical_sha256: str
    raw_file_sha256: str


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file_handle:
        for chunk in iter(lambda: file_handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class FileContentIntelligenceProvider:
    def __init__(
        self,
        *,
        provider_kind: FileProviderKind,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.provider_kind = provider_kind
        self.provider_id = f"{provider_kind}-provider"
        self._clock = clock or (lambda: datetime.now(UTC))

    def _import(
        self,
        path: Path,
        model: type[ArtifactType],
        *,
        operation: str,
    ) -> ImportedArtifact[ArtifactType]:
        resolved = path.resolve(strict=True)
        raw_hash = _file_sha256(resolved)
        try:
            payload = json.loads(resolved.read_text(encoding="utf-8"))
            artifact = model.model_validate(payload)
        except (json.JSONDecodeError, UnicodeDecodeError, ValidationError) as error:
            raise CutupError(
                ErrorCode.ASSESSMENT_INVALID,
                f"invalid {model.__name__} file",
                category="validation",
                step=operation,
                details={"path": resolved.name, "validation_error": str(error)},
            ) from error
        canonical_hash = document_sha256(artifact)
        provider_record_ref = getattr(artifact, "provider_record_ref", None)
        if not isinstance(provider_record_ref, str) or not provider_record_ref:
            raise CutupError(
                ErrorCode.ASSESSMENT_INVALID,
                f"{model.__name__} must include provider_record_ref",
                category="validation",
                step=operation,
            )
        artifact_kind = getattr(artifact, "provider_kind", self.provider_kind)
        if artifact_kind != self.provider_kind:
            raise CutupError(
                ErrorCode.ASSESSMENT_INVALID,
                "artifact provider_kind does not match file provider",
                category="validation",
                step=operation,
            )
        occurred_at = self._clock()
        record = ProviderRecord(
            provider_record_id=provider_record_ref,
            provider_id=self.provider_id,
            operation=operation,
            started_at=occurred_at,
            completed_at=occurred_at,
            input_hashes=(raw_hash,),
            output_hashes=(canonical_hash,),
            warnings=("fixture data; not a real AI provider result",)
            if self.provider_kind == "fixture"
            else (),
        )
        return ImportedArtifact(
            artifact=artifact,
            provider_record=record,
            canonical_sha256=canonical_hash,
            raw_file_sha256=raw_hash,
        )

    def import_content_profile(self, path: Path) -> ImportedArtifact[ContentProfile]:
        return self._import(path, ContentProfile, operation="profile_content")

    def import_proposals(self, path: Path) -> ImportedArtifact[CandidateProposalBundle]:
        return self._import(path, CandidateProposalBundle, operation="propose_candidates")

    def import_assessments(self, path: Path) -> ImportedArtifact[AssessmentBundle]:
        return self._import(path, AssessmentBundle, operation="assess_candidates")
