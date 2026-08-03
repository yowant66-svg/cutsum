from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import Field, model_validator

from .common import DocumentHeader, FrozenModel
from .intelligence import ControlMode


class SportsModality(StrEnum):
    AUDIO = "audio"
    VIDEO = "video"
    OCR = "ocr"
    TEXT = "text"
    METADATA = "metadata"


class SportsObservationType(StrEnum):
    AUDIO_PEAK = "audio_peak"
    SHOT_CHANGE = "shot_change"
    MOTION_BURST = "motion_burst"
    SCOREBOARD_CHANGE = "scoreboard_change"
    OCR_TEXT = "ocr_text"
    COMMENTATOR_EMPHASIS = "commentator_emphasis"
    REPLAY_START = "replay_start"
    REPLAY_END = "replay_end"
    EVENT_CLASSIFICATION = "event_classification"


class SportsEventType(StrEnum):
    SCORE = "score"
    ATTEMPT = "attempt"
    SAVE = "save"
    BLOCK = "block"
    OVERTAKE = "overtake"
    FINISH = "finish"
    CELEBRATION = "celebration"
    CONTROVERSY = "controversy"
    UNKNOWN = "unknown"


class SportsNarrativeCue(StrEnum):
    DECISIVE_SCORE = "decisive_score"


class SportsTemporalRole(StrEnum):
    BUILDUP = "buildup"
    ACTION = "action"
    OUTCOME = "outcome"
    REACTION = "reaction"
    REPLAY = "replay"


class SportsObservation(FrozenModel):
    observation_id: str
    source_id: str
    observation_type: SportsObservationType
    modality: SportsModality
    temporal_role: SportsTemporalRole
    start_ms: int = Field(ge=0)
    end_ms: int = Field(gt=0)
    confidence: float = Field(ge=0, le=1)
    label: str = Field(min_length=1, max_length=500)
    value: str | float | int | bool | None = None
    event_type_hint: SportsEventType | None = None
    narrative_cues: tuple[SportsNarrativeCue, ...] = ()
    correlation_key: str | None = None
    replay_of_correlation_key: str | None = None
    provider_record_ref: str

    @model_validator(mode="after")
    def validate_observation(self) -> SportsObservation:
        if self.end_ms <= self.start_ms:
            raise ValueError("sports observation end_ms must be greater than start_ms")
        is_replay = self.temporal_role is SportsTemporalRole.REPLAY or self.observation_type in {
            SportsObservationType.REPLAY_START,
            SportsObservationType.REPLAY_END,
        }
        if is_replay and self.replay_of_correlation_key is None:
            raise ValueError("replay observation requires replay_of_correlation_key")
        if self.replay_of_correlation_key is not None and not is_replay:
            raise ValueError("replay_of_correlation_key is only valid for replay observations")
        return self


class SportsObservationBundle(DocumentHeader):
    bundle_id: str
    source_id: str
    provider_kind: Literal["fixture", "host_ai_file", "human_file", "local_detector"]
    provider_record_refs: tuple[str, ...] = Field(min_length=1)
    observations: tuple[SportsObservation, ...]

    @model_validator(mode="after")
    def validate_observations(self) -> SportsObservationBundle:
        if len(self.provider_record_refs) != len(set(self.provider_record_refs)):
            raise ValueError("sports provider record refs must be unique")
        observation_ids = [item.observation_id for item in self.observations]
        if len(observation_ids) != len(set(observation_ids)):
            raise ValueError("sports observation IDs must be unique")
        provider_refs = set(self.provider_record_refs)
        primary_correlations = {
            observation.correlation_key
            for observation in self.observations
            if observation.temporal_role is not SportsTemporalRole.REPLAY
            and observation.correlation_key is not None
        }
        for observation in self.observations:
            if observation.source_id != self.source_id:
                raise ValueError("sports observation source_id must match bundle")
            if observation.provider_record_ref not in provider_refs:
                raise ValueError("sports observation references unknown provider record")
            if (
                observation.replay_of_correlation_key is not None
                and observation.replay_of_correlation_key not in primary_correlations
            ):
                raise ValueError("sports replay references unknown primary correlation")
        return self


class SportsEvent(FrozenModel):
    event_id: str
    source_id: str
    event_type: SportsEventType
    start_ms: int = Field(ge=0)
    end_ms: int = Field(gt=0)
    observation_ids: tuple[str, ...] = Field(min_length=1)
    temporal_roles: tuple[SportsTemporalRole, ...]
    modalities: tuple[SportsModality, ...]
    observation_types: tuple[SportsObservationType, ...]
    confidence: float = Field(ge=0, le=1)
    narrative_cues: tuple[SportsNarrativeCue, ...] = ()
    replay_of_event_id: str | None = None

    @model_validator(mode="after")
    def validate_event(self) -> SportsEvent:
        if self.end_ms <= self.start_ms:
            raise ValueError("sports event end_ms must be greater than start_ms")
        for values, label in (
            (self.observation_ids, "observation IDs"),
            (self.temporal_roles, "temporal roles"),
            (self.modalities, "modalities"),
            (self.observation_types, "observation types"),
        ):
            if len(values) != len(set(values)):
                raise ValueError(f"sports event {label} must be unique")
        if self.replay_of_event_id is not None and SportsTemporalRole.REPLAY not in (
            self.temporal_roles
        ):
            raise ValueError("replay_of_event_id requires replay temporal role")
        return self


class SportsCandidateProfile(FrozenModel):
    candidate_id: str
    event_id: str
    qualified: bool
    event_type: SportsEventType
    temporal_roles: tuple[SportsTemporalRole, ...]
    modalities: tuple[SportsModality, ...]
    observation_types: tuple[SportsObservationType, ...]
    cross_modal_confirmations: int = Field(ge=0)
    replay_only: bool
    completeness_confidence: float = Field(ge=0, le=1)
    narrative_cues: tuple[SportsNarrativeCue, ...] = ()


class SportsQualification(FrozenModel):
    candidate_id: str
    qualified: bool
    reasons: tuple[str, ...] = ()


class SportsTaskRequest(FrozenModel):
    control_mode: ControlMode
    raw_instruction: str
    required_event_types: tuple[SportsEventType, ...] = ()
    forbidden_event_types: tuple[SportsEventType, ...] = ()
    required_narrative_cues: tuple[SportsNarrativeCue, ...] = ()
    include_replays: bool = False
    target_count: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_request(self) -> SportsTaskRequest:
        if set(self.required_event_types) & set(self.forbidden_event_types):
            raise ValueError("sports event type cannot be both required and forbidden")
        return self


class SportsSelectionResult(FrozenModel):
    strategy_id: str = "sports_highlight"
    strategy_version: str = "alpha-0.2.0"
    selected_candidate_ids: tuple[str, ...]
    qualifications: tuple[SportsQualification, ...]
    unsatisfied_requirements: tuple[str, ...] = ()
