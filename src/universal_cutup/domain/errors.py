from __future__ import annotations

from enum import StrEnum
from typing import Any


class ErrorCode(StrEnum):
    PROTOCOL_INVALID = "PROTOCOL_INVALID"
    PROTOCOL_VERSION_UNSUPPORTED = "PROTOCOL_VERSION_UNSUPPORTED"
    PROTOCOL_UNSUPPORTED_EXTENSION = "PROTOCOL_UNSUPPORTED_EXTENSION"
    SOURCE_NOT_FOUND = "SOURCE_NOT_FOUND"
    SOURCE_HASH_MISMATCH = "SOURCE_HASH_MISMATCH"
    RIGHTS_ATTESTATION_REQUIRED = "RIGHTS_ATTESTATION_REQUIRED"
    PATH_OUTSIDE_ROOT = "PATH_OUTSIDE_ROOT"
    OUTPUT_EXISTS = "OUTPUT_EXISTS"
    OUTPUT_NOT_WRITABLE = "OUTPUT_NOT_WRITABLE"
    FFMPEG_NOT_FOUND = "FFMPEG_NOT_FOUND"
    FFPROBE_NOT_FOUND = "FFPROBE_NOT_FOUND"
    MEDIA_PROCESS_FAILED = "MEDIA_PROCESS_FAILED"
    MEDIA_PROCESS_TIMEOUT = "MEDIA_PROCESS_TIMEOUT"
    CANCELLED = "CANCELLED"
    PROVIDER_REQUIRED = "PROVIDER_REQUIRED"
    CAPABILITY_UNAVAILABLE = "CAPABILITY_UNAVAILABLE"
    SUBTITLE_CUES_REQUIRED = "SUBTITLE_CUES_REQUIRED"
    HOST_INTENT_CONFLICT = "HOST_INTENT_CONFLICT"
    CAPABILITY_CONFLICT = "CAPABILITY_CONFLICT"
    CONTENT_PROFILE_REQUIRED = "CONTENT_PROFILE_REQUIRED"
    ASSESSMENT_INVALID = "ASSESSMENT_INVALID"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class CutupError(Exception):
    def __init__(
        self,
        code: ErrorCode,
        message: str,
        *,
        category: str = "validation",
        step: str | None = None,
        recoverable: bool = False,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.category = category
        self.step = step
        self.recoverable = recoverable
        self.details = details or {}

    def as_dict(self) -> dict[str, Any]:
        return {
            "code": self.code.value,
            "category": self.category,
            "message": str(self),
            "step": self.step,
            "recoverable": self.recoverable,
            "details": self.details,
        }
