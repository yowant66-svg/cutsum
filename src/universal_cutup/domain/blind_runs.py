from __future__ import annotations

import re
from enum import StrEnum
from pathlib import Path

from pydantic import Field, field_validator, model_validator

from .common import SHA256_PATTERN, DocumentHeader, FrozenModel
from .intelligence import ControlMode

_TIMESTAMP_PATTERN = re.compile(r"(?<!\d)(?:\d{1,2}:)?\d{1,2}:\d{2}(?!\d)")
_CANDIDATE_REFERENCE_PATTERN = re.compile(
    r"(?:candidate[\s_-]*id|候选\s*(?:id|编号)|(?:^|[\s_-])c\d+(?:$|[\s_-]))",
    re.IGNORECASE,
)


class BlindRunState(StrEnum):
    FROZEN = "frozen"


class BlindEvaluationTrack(StrEnum):
    INTERVIEW = "interview"
    DRAMA = "drama"
    EDUCATION = "education"
    SPORTS = "sports"


class BlindTaskInput(FrozenModel):
    task_id: str
    control_mode: ControlMode
    raw_instruction: str

    @field_validator("raw_instruction")
    @classmethod
    def reject_reference_answers(cls, value: str) -> str:
        if _TIMESTAMP_PATTERN.search(value):
            raise ValueError("blind task instructions must not contain timestamps")
        if _CANDIDATE_REFERENCE_PATTERN.search(value):
            raise ValueError("blind task instructions must not contain candidate references")
        return value

    @model_validator(mode="after")
    def validate_supported_mode(self) -> BlindTaskInput:
        if self.control_mode not in {ControlMode.AUTO, ControlMode.DIRECTED}:
            raise ValueError("Gate H blind tasks support only AUTO and DIRECTED")
        if self.control_mode is ControlMode.DIRECTED and not self.raw_instruction:
            raise ValueError("DIRECTED blind tasks require a natural-language instruction")
        return self


class BlindRunInput(DocumentHeader):
    blind_run_id: str
    suite_id: str | None = None
    case_id: str | None = None
    track: BlindEvaluationTrack | None = None
    sample_id: str
    source_id: str
    transcript_path: str
    media_path: str | None = None
    tasks: tuple[BlindTaskInput, ...] = Field(min_length=3, max_length=3)

    @field_validator("transcript_path", "media_path")
    @classmethod
    def require_absolute_paths(cls, value: str | None) -> str | None:
        if value is not None and not Path(value).is_absolute():
            raise ValueError("blind input artifact paths must be absolute")
        return value

    @model_validator(mode="after")
    def validate_task_matrix(self) -> BlindRunInput:
        if (self.suite_id is None) != (self.case_id is None):
            raise ValueError("blind suite_id and case_id must be set together")
        if self.track is not None and self.case_id is None:
            raise ValueError("blind track requires suite_id and case_id")
        task_ids = [task.task_id for task in self.tasks]
        if len(task_ids) != len(set(task_ids)):
            raise ValueError("blind task IDs must be unique")
        modes = [task.control_mode for task in self.tasks]
        if modes.count(ControlMode.AUTO) != 1 or modes.count(ControlMode.DIRECTED) != 2:
            raise ValueError("each Gate H sample requires one AUTO and two DIRECTED tasks")
        return self


class FrozenArtifact(FrozenModel):
    relative_path: str
    sha256: str = Field(pattern=SHA256_PATTERN)
    size_bytes: int = Field(ge=0)


class BlindRunManifest(DocumentHeader):
    blind_run_id: str
    suite_id: str | None = None
    case_id: str | None = None
    track: BlindEvaluationTrack | None = None
    state: BlindRunState = BlindRunState.FROZEN
    result_root: str
    artifacts: tuple[FrozenArtifact, ...] = Field(min_length=1)
    aggregate_sha256: str = Field(pattern=SHA256_PATTERN)

    @model_validator(mode="after")
    def validate_artifacts(self) -> BlindRunManifest:
        if (self.suite_id is None) != (self.case_id is None):
            raise ValueError("frozen suite_id and case_id must be set together")
        if self.track is not None and self.case_id is None:
            raise ValueError("frozen track requires suite_id and case_id")
        paths = [artifact.relative_path for artifact in self.artifacts]
        if len(paths) != len(set(paths)):
            raise ValueError("frozen artifact paths must be unique")
        if any(Path(path).is_absolute() or ".." in Path(path).parts for path in paths):
            raise ValueError("frozen artifact paths must remain relative to result_root")
        return self
