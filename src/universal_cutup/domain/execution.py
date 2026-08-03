from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import Field

from .common import SHA256_PATTERN, DocumentHeader, FrozenModel
from .records import ProviderRecord


class ExecutionStatus(StrEnum):
    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"


class StepResult(FrozenModel):
    step_id: str
    candidate_id: str | None = None
    status: Literal["completed", "failed", "cancelled", "timed_out"]
    started_at: datetime | None = None
    completed_at: datetime | None = None
    recoverable: bool = False
    error_code: str | None = None
    message: str | None = None
    details: dict[str, str] = Field(default_factory=dict)


class CutArtifact(FrozenModel):
    artifact_id: str
    execution_id: str
    candidate_id: str
    artifact_type: Literal["video", "audio", "subtitle"]
    relative_path: str
    sha256: str = Field(pattern=SHA256_PATTERN)
    size_bytes: int = Field(ge=0)
    duration_ms: int | None = Field(default=None, gt=0)
    mime_type: str | None = None
    source_resolution: str | None = None
    actual_output_resolution: str | None = None
    scale_reason: str | None = None
    upscale: bool = False
    video_codec: str | None = None
    audio_codec: str | None = None
    quality_preset: str | None = None
    rate_control: str | None = None
    reframe_mode: str | None = None
    crop_box: tuple[int, int, int, int] | None = None
    focus_point: tuple[float, float] | None = None
    output_anchor: tuple[float, float] | None = None
    safe_area: tuple[int, int, int, int] | None = None
    composition_reason: str | None = None


class ExecutionRecord(DocumentHeader):
    execution_id: str
    plan_id: str
    plan_document_sha256: str = Field(pattern=SHA256_PATTERN)
    started_at: datetime
    completed_at: datetime
    status: ExecutionStatus = ExecutionStatus.SUCCESS
    steps: tuple[StepResult, ...]
    artifacts: tuple[CutArtifact, ...] = ()
    provider_records: tuple[ProviderRecord, ...] = ()
    warnings: tuple[str, ...] = ()


class RunManifest(DocumentHeader):
    run_id: str
    plan_id: str
    execution_ids: tuple[str, ...]
    artifact_ids: tuple[str, ...] = ()
    provider_records: tuple[ProviderRecord, ...] = ()
