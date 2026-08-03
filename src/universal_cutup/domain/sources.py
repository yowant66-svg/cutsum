from __future__ import annotations

from enum import StrEnum
from pathlib import Path, PurePath
from typing import Literal

from pydantic import Field, model_validator

from .common import SHA256_PATTERN, FrozenModel

RIGHTS_ATTESTATION_NOTICE = "Self-attestation only; the tool does not make a legal determination."


class RightsAttestation(StrEnum):
    OWNED = "owned"
    LICENSED = "licensed"
    PUBLIC_DOMAIN = "public_domain"
    AUTHORIZED_OTHER = "authorized_other"
    ANALYSIS_ONLY = "analysis_only"


class MediaSource(FrozenModel):
    source_id: str
    media_id: str
    kind: Literal["video", "audio", "transcript"]
    sha256: str = Field(pattern=SHA256_PATTERN)
    basename_hint: str
    rights_attestation: RightsAttestation | None = None
    duration_ms: int | None = Field(default=None, gt=0)
    mime_type: str | None = None

    @model_validator(mode="after")
    def validate_identity(self) -> MediaSource:
        if PurePath(self.basename_hint).name != self.basename_hint:
            raise ValueError("basename_hint must not contain directories")
        return self


class MediaBinding(FrozenModel):
    source_id: str
    local_path: str | None = None
    uri: str | None = None

    @model_validator(mode="after")
    def validate_location(self) -> MediaBinding:
        if (self.local_path is None) == (self.uri is None):
            raise ValueError("exactly one of local_path or uri is required")
        if self.local_path is not None and not Path(self.local_path).is_absolute():
            raise ValueError("local_path must be absolute")
        return self
