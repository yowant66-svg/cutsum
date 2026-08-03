from __future__ import annotations

from enum import StrEnum

from pydantic import Field, JsonValue, model_validator

from .common import DocumentHeader, FrozenModel
from .errors import CutupError, ErrorCode


class ControlMode(StrEnum):
    AUTO = "auto"
    GUIDED = "guided"
    DIRECTED = "directed"


class DecisionSource(StrEnum):
    HOST_EXPLICIT = "host_explicit"
    HOST_PRESET = "host_preset"
    CONTENT_INFERENCE = "content_inference"
    SYSTEM_CAPABILITY = "system_capability"
    FALLBACK = "fallback"


class DurationSource(StrEnum):
    HOST_EXPLICIT = "host_explicit"
    CONTENT_INFERENCE = "content_inference"
    DEFAULT_POLICY = "default_policy"
    AUTOMATIC_EXTENSION = "automatic_extension"


class SemanticType(StrEnum):
    DEFINITION = "definition"
    REASONING_CHAIN = "reasoning_chain"
    CONFLICT = "conflict"
    HOOK = "hook"
    STEP = "step"
    STORY_ARC = "story_arc"


class DimensionKey(StrEnum):
    INSIGHT = "insight"
    NOVELTY = "novelty"
    EMOTION = "emotion"
    QUOTABILITY = "quotability"
    HOOK = "hook"
    STANDALONE = "standalone"
    CLARITY = "clarity"
    COMPLETION = "completion"
    SHAREABILITY = "shareability"
    SILENT_WATCHABILITY = "silent_watchability"
    PACE = "pace"
    EDITABILITY = "editability"
    SUBTITLE_RELIABILITY = "subtitle_reliability"
    VISUAL_INDEPENDENCE = "visual_independence"


ALL_DIMENSION_KEYS = tuple(DimensionKey)


class DimensionApplicability(StrEnum):
    REQUIRED = "required"
    WEIGHTED = "weighted"
    ADVISORY = "advisory"
    NOT_APPLICABLE = "not_applicable"


class DimensionPolicy(FrozenModel):
    dimension: DimensionKey
    applicability: DimensionApplicability
    weight: float | None = Field(default=None, ge=0)
    minimum: float | None = Field(default=None, ge=0, le=10)
    rationale: str
    source: DecisionSource
    confidence: float | None = Field(default=None, ge=0, le=1)

    @model_validator(mode="after")
    def validate_policy(self) -> DimensionPolicy:
        if self.applicability is DimensionApplicability.NOT_APPLICABLE and (
            self.weight is not None or self.minimum is not None
        ):
            raise ValueError("not_applicable dimensions cannot have weight or minimum")
        if self.applicability is DimensionApplicability.ADVISORY and self.minimum is not None:
            raise ValueError("advisory dimensions cannot have a hard minimum")
        if self.applicability is DimensionApplicability.WEIGHTED and self.weight is None:
            raise ValueError("weighted dimensions require a weight")
        if self.applicability is DimensionApplicability.REQUIRED and self.minimum is None:
            raise ValueError("required dimensions require a minimum")
        return self


class ClipConstraints(FrozenModel):
    minimum_count: int | None = Field(default=None, ge=0)
    maximum_count: int | None = Field(default=None, ge=1)
    target_count: int | None = Field(default=None, ge=1)
    minimum_duration_ms: int | None = Field(default=None, gt=0)
    maximum_duration_ms: int | None = Field(default=None, gt=0)
    target_duration_ms: int | None = Field(default=None, gt=0)
    preferred_duration_ms: int | None = Field(default=None, gt=0)
    default_max_duration_ms: int | None = Field(default=None, gt=0)
    absolute_auto_max_duration_ms: int | None = Field(default=None, gt=0)
    host_requested_duration_ms: int | None = Field(default=None, gt=0)
    duration_source: DurationSource | None = None
    extension_reason: str | None = None

    @model_validator(mode="after")
    def validate_constraints(self) -> ClipConstraints:
        if (
            self.minimum_count is not None
            and self.maximum_count is not None
            and self.minimum_count > self.maximum_count
        ):
            raise CutupError(
                ErrorCode.HOST_INTENT_CONFLICT,
                "minimum_count cannot exceed maximum_count",
                details={
                    "paths": [
                        "clip_constraints.minimum_count",
                        "clip_constraints.maximum_count",
                    ]
                },
            )
        if (
            self.minimum_duration_ms is not None
            and self.maximum_duration_ms is not None
            and self.minimum_duration_ms > self.maximum_duration_ms
        ):
            raise CutupError(
                ErrorCode.HOST_INTENT_CONFLICT,
                "minimum_duration_ms cannot exceed maximum_duration_ms",
                details={
                    "paths": [
                        "clip_constraints.minimum_duration_ms",
                        "clip_constraints.maximum_duration_ms",
                    ]
                },
            )
        if self.target_count is not None:
            if self.minimum_count is not None and self.target_count < self.minimum_count:
                raise CutupError(
                    ErrorCode.HOST_INTENT_CONFLICT,
                    "target_count cannot be below minimum_count",
                )
            if self.maximum_count is not None and self.target_count > self.maximum_count:
                raise CutupError(
                    ErrorCode.HOST_INTENT_CONFLICT,
                    "target_count cannot exceed maximum_count",
                )
        if self.target_duration_ms is not None:
            if (
                self.minimum_duration_ms is not None
                and self.target_duration_ms < self.minimum_duration_ms
            ):
                raise CutupError(
                    ErrorCode.HOST_INTENT_CONFLICT,
                    "target_duration_ms cannot be below minimum_duration_ms",
                )
            if (
                self.maximum_duration_ms is not None
                and self.target_duration_ms > self.maximum_duration_ms
            ):
                raise CutupError(
                    ErrorCode.HOST_INTENT_CONFLICT,
                    "target_duration_ms cannot exceed maximum_duration_ms",
                )
        if (
            self.default_max_duration_ms is not None
            and self.absolute_auto_max_duration_ms is not None
            and self.default_max_duration_ms > self.absolute_auto_max_duration_ms
        ):
            raise ValueError("default_max_duration_ms cannot exceed absolute_auto_max_duration_ms")
        if (
            self.extension_reason is not None
            and self.duration_source is not DurationSource.AUTOMATIC_EXTENSION
        ):
            raise ValueError("extension_reason requires duration_source=automatic_extension")
        return self


class SemanticRequirements(FrozenModel):
    semantic_type: SemanticType | None = None
    required_count: int = Field(default=1, ge=1)
    required_structure: tuple[str, ...] = ()
    forbidden_types: tuple[SemanticType, ...] = ()
    topic_constraint: str | None = None
    speaker_constraint: str | None = None
    sequence_constraint: str | None = None

    @model_validator(mode="after")
    def validate_requirements(self) -> SemanticRequirements:
        if self.semantic_type is not None and self.semantic_type in self.forbidden_types:
            raise ValueError("semantic_type cannot also be forbidden")
        return self


class HostIntent(DocumentHeader):
    intent_id: str
    raw_instruction: str
    control_mode: ControlMode
    desired_outcomes: tuple[str, ...] = ()
    prohibited_outcomes: tuple[str, ...] = ()
    clip_constraints: ClipConstraints = ClipConstraints()
    target_audience: str | None = None
    platform: str | None = None
    language: str | None = None
    subtitle_requirements: tuple[str, ...] = ()
    visual_requirements: tuple[str, ...] = ()
    preserve_time_order: bool | None = None
    require_track_diversity: bool | None = None
    allow_context_dependency: bool | None = None
    dimension_policies: tuple[DimensionPolicy, ...] = ()
    hard_include_candidate_ids: tuple[str, ...] = ()
    hard_exclude_candidate_ids: tuple[str, ...] = ()
    unrecognized_requirements: tuple[str, ...] = ()
    preset_id: str | None = None
    semantic_requirements: SemanticRequirements | None = None

    @model_validator(mode="after")
    def validate_intent(self) -> HostIntent:
        dimensions = [policy.dimension for policy in self.dimension_policies]
        if len(dimensions) != len(set(dimensions)):
            raise ValueError("host dimension policies must use unique dimension keys")
        overlap = set(self.hard_include_candidate_ids) & set(self.hard_exclude_candidate_ids)
        if overlap:
            raise CutupError(
                ErrorCode.HOST_INTENT_CONFLICT,
                "a candidate cannot be both hard-included and hard-excluded",
                details={"candidate_ids": sorted(overlap)},
            )
        return self


class ContentDensity(FrozenModel):
    narrative: float = Field(ge=0, le=1)
    knowledge: float = Field(ge=0, le=1)
    procedural: float = Field(ge=0, le=1)
    opinion: float = Field(ge=0, le=1)
    emotion: float = Field(ge=0, le=1)


class DependencyProfile(FrozenModel):
    visual: float = Field(ge=0, le=1)
    audio: float = Field(ge=0, le=1)
    subtitle: float = Field(ge=0, le=1)


class ContentTrack(FrozenModel):
    track_id: str
    label: str
    topic: str
    evidence_refs: tuple[str, ...] = Field(min_length=1)


class ContentProfile(DocumentHeader):
    profile_id: str
    source_id: str
    content_types: tuple[str, ...] = Field(min_length=1)
    primary_topic: str
    subtopics: tuple[str, ...] = ()
    structure_types: tuple[str, ...] = Field(min_length=1)
    typical_audiences: tuple[str, ...] = ()
    value_sources: tuple[str, ...] = ()
    density: ContentDensity
    dependencies: DependencyProfile
    language: str | None = None
    confidence: float = Field(ge=0, le=1)
    supporting_evidence_refs: tuple[str, ...] = Field(min_length=1)
    tracks: tuple[ContentTrack, ...] = ()
    provider_record_ref: str | None = None
    auto_objectives: tuple[str, ...] = ()
    auto_clip_constraints: ClipConstraints | None = None

    @model_validator(mode="after")
    def validate_profile(self) -> ContentProfile:
        if len(self.content_types) != len(set(self.content_types)):
            raise ValueError("content_types must be unique")
        track_ids = [track.track_id for track in self.tracks]
        if len(track_ids) != len(set(track_ids)):
            raise ValueError("content track IDs must be unique")
        return self


class CandidateProposalPolicy(FrozenModel):
    allow_cross_segment: bool = True
    allow_context_dependency: bool = False
    preferred_track_ids: tuple[str, ...] = ()


class SelectionPolicy(FrozenModel):
    maximum_overlap_ratio: float = Field(default=0.2, ge=0, le=1)
    duplicate_similarity_threshold: float = Field(default=0.85, ge=0, le=1)
    prefer_track_diversity: bool = False
    require_track_diversity: bool = False
    preserve_time_order: bool = False


class ExplanationPolicy(FrozenModel):
    explain_content_profile: bool = True
    explain_dimension_scores: bool = True
    explain_selection: bool = True
    disclose_assumptions: bool = True


class ResolutionTraceEntry(FrozenModel):
    decision_path: str
    source: DecisionSource
    value: JsonValue
    rationale: str


class ResolvedTaskProfile(DocumentHeader):
    resolved_task_id: str
    host_intent_id: str
    content_profile_id: str | None
    control_mode: ControlMode
    final_objectives: tuple[str, ...]
    prohibited_outcomes: tuple[str, ...] = ()
    hard_constraints: ClipConstraints
    hard_include_candidate_ids: tuple[str, ...] = ()
    hard_exclude_candidate_ids: tuple[str, ...] = ()
    dimension_policies: tuple[DimensionPolicy, ...]
    candidate_policy: CandidateProposalPolicy
    selection_policy: SelectionPolicy
    explanation_policy: ExplanationPolicy
    resolution_trace: tuple[ResolutionTraceEntry, ...] = Field(min_length=1)
    warnings: tuple[str, ...] = ()
    unsatisfied_constraints: tuple[str, ...] = ()
    semantic_requirements: SemanticRequirements | None = None

    @model_validator(mode="after")
    def validate_dimensions(self) -> ResolvedTaskProfile:
        dimensions = [policy.dimension for policy in self.dimension_policies]
        if len(dimensions) != len(set(dimensions)):
            raise ValueError("resolved dimension policies must be unique")
        if set(dimensions) != set(ALL_DIMENSION_KEYS):
            raise ValueError("resolved task profile must register all 14 dimensions")
        return self


class CapabilityProfile(FrozenModel):
    supported_features: tuple[str, ...] = ()
    unavailable_features: tuple[str, ...] = ()
    maximum_clip_duration_ms: int | None = Field(default=None, gt=0)


class TaskPreset(FrozenModel):
    preset_id: str
    objectives: tuple[str, ...] = ()
    dimension_policies: tuple[DimensionPolicy, ...] = ()
    preserve_time_order: bool | None = None
    require_track_diversity: bool | None = None

    @model_validator(mode="after")
    def validate_dimensions(self) -> TaskPreset:
        dimensions = [policy.dimension for policy in self.dimension_policies]
        if len(dimensions) != len(set(dimensions)):
            raise ValueError("preset dimension policies must be unique")
        return self


class TaskConflict(FrozenModel):
    conflict_id: str
    conflict_type: str
    paths: tuple[str, ...] = Field(min_length=1)
    message: str
    capability: str | None = None
    recoverable: bool = False
