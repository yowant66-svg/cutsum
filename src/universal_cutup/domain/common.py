from __future__ import annotations

from datetime import UTC, datetime
from typing import ClassVar

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    field_validator,
    model_validator,
)

from .errors import CutupError, ErrorCode

SHA256_PATTERN = r"^[0-9a-f]{64}$"
SUPPORTED_SCHEMA_VERSIONS = frozenset({"0.1.0"})


class FrozenModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
        use_enum_values=False,
    )


class TimeRange(FrozenModel):
    start_ms: int = Field(ge=0)
    end_ms: int = Field(gt=0)

    @model_validator(mode="after")
    def validate_order(self) -> TimeRange:
        if self.end_ms <= self.start_ms:
            raise ValueError("end_ms must be greater than start_ms")
        return self


class DocumentHeader(FrozenModel):
    schema_version: str = "0.1.0"
    document_type: str
    created_at: datetime
    created_by: str
    extensions: dict[str, JsonValue] = Field(default_factory=dict)
    required_extensions: tuple[str, ...] = ()

    registered_extensions: ClassVar[frozenset[str]] = frozenset({"org.universal-cutup.core"})

    @field_validator("created_at")
    @classmethod
    def validate_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() != UTC.utcoffset(value):
            raise ValueError("created_at must be timezone-aware UTC")
        return value

    @model_validator(mode="after")
    def validate_extensions(self) -> DocumentHeader:
        if self.schema_version not in SUPPORTED_SCHEMA_VERSIONS:
            raise CutupError(
                ErrorCode.PROTOCOL_VERSION_UNSUPPORTED,
                f"Unsupported schema version: {self.schema_version}",
                details={"supported_versions": sorted(SUPPORTED_SCHEMA_VERSIONS)},
            )
        extension_keys = set(self.extensions)
        required_keys = set(self.required_extensions)
        if len(required_keys) != len(self.required_extensions):
            raise ValueError("required_extensions must not contain duplicates")
        if not required_keys <= extension_keys:
            raise ValueError("required_extensions must be a subset of extensions")
        unknown_required = required_keys - self.registered_extensions
        if unknown_required:
            raise CutupError(
                ErrorCode.PROTOCOL_UNSUPPORTED_EXTENSION,
                f"Unsupported required extension: {sorted(unknown_required)[0]}",
                details={"extension_ids": sorted(unknown_required)},
            )
        core_fields = set(type(self).model_fields) - {"extensions", "required_extensions"}
        if extension_keys & core_fields:
            raise ValueError("extensions cannot override core fields")
        return self
