from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import AnyHttpUrl, Field, field_validator, model_validator

from .common import SHA256_PATTERN, DocumentHeader, FrozenModel, TimeRange
from .intelligence import (
    ClipConstraints,
    ContentDensity,
    ControlMode,
    DependencyProfile,
)


class BenchmarkCategory(StrEnum):
    INTERVIEW_OR_TALK = "interview_or_talk"
    FILM_OR_DRAMA = "film_or_drama"
    EDUCATION_OR_KNOWLEDGE = "education_or_knowledge"


class BenchmarkSourceKind(StrEnum):
    YOUTUBE_VIDEO = "youtube_video"
    OFFICIAL_CLIP = "official_clip"
    OFFICIAL_TRAILER = "official_trailer"
    PUBLIC_TRANSCRIPT = "public_transcript"
    SUBTITLE_FILE = "subtitle_file"
    OPEN_COURSE_MEDIA = "open_course_media"
    PUBLIC_DOMAIN_MEDIA = "public_domain_media"
    OTHER_PUBLIC_SOURCE = "other_public_source"


class AvailabilityStatus(StrEnum):
    AVAILABLE = "available"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"
    NOT_VERIFIED = "not_verified"


class BenchmarkEvaluationStatus(StrEnum):
    SELECTED = "selected"
    READY = "ready"
    BLOCKED = "blocked"
    COMPLETED = "completed"


class BenchmarkScoreProfile(StrEnum):
    HOOK = "hook"
    CONCEPT = "concept"
    COMPLETE = "complete"
    STORY = "story"
    VISUAL = "visual"
    CONFLICT = "conflict"
    EMOTION = "emotion"


class BenchmarkTaskSpec(FrozenModel):
    task_id: str
    control_mode: ControlMode
    raw_instruction: str
    desired_outcomes: tuple[str, ...] = ()
    prohibited_outcomes: tuple[str, ...] = ()
    clip_constraints: ClipConstraints = ClipConstraints()
    preserve_time_order: bool | None = None
    require_track_diversity: bool | None = None
    hard_include_candidate_ids: tuple[str, ...] = ()
    hard_exclude_candidate_ids: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_candidate_controls(self) -> BenchmarkTaskSpec:
        overlap = set(self.hard_include_candidate_ids) & set(self.hard_exclude_candidate_ids)
        if overlap:
            raise ValueError("a benchmark task cannot include and exclude the same candidate")
        return self


class BenchmarkExecutionPolicy(FrozenModel):
    analysis_window: TimeRange
    plan_only: bool = True
    media_download_permitted: bool = False
    media_execution_permitted: bool = False
    network_provider_permitted: bool = False
    maximum_cost_minor_units: int = Field(default=0, ge=0)
    currency: str = "USD"
    rationale: str


class BenchmarkItem(FrozenModel):
    benchmark_id: str
    benchmark_version: str
    item_id: str
    category: BenchmarkCategory
    title: str
    canonical_subject: str
    source_url: AnyHttpUrl
    source_kind: BenchmarkSourceKind
    media_availability: AvailabilityStatus
    transcript_availability: AvailabilityStatus
    duration_ms: int = Field(gt=0)
    language: str
    publication_or_release_date: str = Field(pattern=r"^\d{4}(?:-\d{2}-\d{2})?$")
    accessed_at: datetime
    content_hash: str = Field(pattern=SHA256_PATTERN)
    source_notes: tuple[str, ...] = Field(min_length=1)
    rights_notes: tuple[str, ...] = Field(min_length=1)
    selection_rationale: tuple[str, ...] = Field(min_length=1)
    expected_content_structure: tuple[str, ...] = Field(min_length=1)
    known_difficulties: tuple[str, ...] = ()
    auto_task: BenchmarkTaskSpec
    directed_tasks: tuple[BenchmarkTaskSpec, ...] = Field(min_length=2)
    execution_policy: BenchmarkExecutionPolicy
    evaluation_status: BenchmarkEvaluationStatus

    @field_validator("accessed_at")
    @classmethod
    def validate_accessed_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() != UTC.utcoffset(value):
            raise ValueError("accessed_at must be timezone-aware UTC")
        return value

    @model_validator(mode="after")
    def validate_tasks_and_window(self) -> BenchmarkItem:
        if self.auto_task.control_mode is not ControlMode.AUTO:
            raise ValueError("auto_task must use AUTO control mode")
        if any(task.control_mode is not ControlMode.DIRECTED for task in self.directed_tasks):
            raise ValueError("directed_tasks must use DIRECTED control mode")
        task_ids = [self.auto_task.task_id, *(task.task_id for task in self.directed_tasks)]
        if len(task_ids) != len(set(task_ids)):
            raise ValueError("benchmark task IDs must be unique within an item")
        if self.category in {
            BenchmarkCategory.FILM_OR_DRAMA,
            BenchmarkCategory.EDUCATION_OR_KNOWLEDGE,
        }:
            window = self.execution_policy.analysis_window
            if window.end_ms - window.start_ms > 1_800_000:
                raise ValueError("film and education analysis windows cannot exceed 30 minutes")
        return self


class BenchmarkManifest(DocumentHeader):
    benchmark_id: str
    benchmark_version: str
    items: tuple[BenchmarkItem, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_items(self) -> BenchmarkManifest:
        item_ids = [item.item_id for item in self.items]
        if len(item_ids) != len(set(item_ids)):
            raise ValueError("benchmark item IDs must be unique")
        mismatches = [
            item.item_id
            for item in self.items
            if item.benchmark_id != self.benchmark_id
            or item.benchmark_version != self.benchmark_version
        ]
        if mismatches:
            raise ValueError("benchmark item identity must match its parent manifest")
        return self


class CuratedProvider(FrozenModel):
    provider_id: str
    model_id: str
    operation: str
    cost_minor_units: int = Field(ge=0)
    currency: str
    warnings: tuple[str, ...] = ()


class CuratedTrack(FrozenModel):
    track_id: str
    label: str
    topic: str


class CuratedCandidate(FrozenModel):
    candidate_id: str
    start_ms: int = Field(ge=0)
    end_ms: int = Field(gt=0)
    track_id: str
    score_profile: BenchmarkScoreProfile
    summary: str
    transcript_paraphrase: str

    @model_validator(mode="after")
    def validate_range(self) -> CuratedCandidate:
        if self.end_ms <= self.start_ms:
            raise ValueError("curated candidate end_ms must exceed start_ms")
        return self


class CuratedBenchmarkItem(FrozenModel):
    item_id: str
    content_types: tuple[str, ...] = Field(min_length=1)
    primary_topic: str
    subtopics: tuple[str, ...] = ()
    structure_types: tuple[str, ...] = Field(min_length=1)
    value_sources: tuple[str, ...] = Field(min_length=1)
    density: ContentDensity
    dependencies: DependencyProfile
    tracks: tuple[CuratedTrack, ...] = Field(min_length=1)
    candidates: tuple[CuratedCandidate, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_references(self) -> CuratedBenchmarkItem:
        track_ids = [track.track_id for track in self.tracks]
        if len(track_ids) != len(set(track_ids)):
            raise ValueError("curated track IDs must be unique")
        if not {candidate.track_id for candidate in self.candidates} <= set(track_ids):
            raise ValueError("curated candidate references unknown track")
        candidate_ids = [candidate.candidate_id for candidate in self.candidates]
        if len(candidate_ids) != len(set(candidate_ids)):
            raise ValueError("curated candidate IDs must be unique")
        return self


class CuratedInputCollection(FrozenModel):
    curation_version: str
    created_at: datetime
    provider: CuratedProvider
    items: tuple[CuratedBenchmarkItem, ...] = Field(min_length=1)

    @field_validator("created_at")
    @classmethod
    def validate_created_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() != UTC.utcoffset(value):
            raise ValueError("curated input created_at must be timezone-aware UTC")
        return value
