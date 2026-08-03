from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from .candidates import CutCandidate
from .common import SHA256_PATTERN, DocumentHeader, FrozenModel
from .intelligence import DimensionKey


class DimensionAssessment(FrozenModel):
    dimension: DimensionKey
    score: float | None = Field(default=None, ge=0, le=10)
    evidence_refs: tuple[str, ...] = ()
    explanation: str
    confidence: float | None = Field(default=None, ge=0, le=1)
    unavailable_reason: str | None = None

    @model_validator(mode="after")
    def validate_availability(self) -> DimensionAssessment:
        if (self.score is None) == (self.unavailable_reason is None):
            raise ValueError("exactly one of score or unavailable_reason is required")
        if self.score is not None and not self.evidence_refs:
            raise ValueError("scored dimensions require evidence_refs")
        return self


class CandidateAssessment(FrozenModel):
    candidate_id: str
    dimensions: tuple[DimensionAssessment, ...]
    content_track_ids: tuple[str, ...] = ()
    model_reported_overall: float | None = Field(default=None, ge=0, le=10)

    @model_validator(mode="after")
    def validate_dimensions(self) -> CandidateAssessment:
        dimensions = [assessment.dimension for assessment in self.dimensions]
        if len(dimensions) != len(set(dimensions)):
            raise ValueError("candidate dimension assessments must be unique")
        return self


class AssessmentBundle(DocumentHeader):
    assessment_bundle_id: str
    source_id: str
    provider_record_ref: str
    provider_kind: Literal["fixture", "host_ai_file", "human_file"]
    is_fixture: bool = False
    candidates: tuple[CandidateAssessment, ...]
    input_document_sha256: str = Field(pattern=SHA256_PATTERN)

    @model_validator(mode="after")
    def validate_candidates(self) -> AssessmentBundle:
        candidate_ids = [candidate.candidate_id for candidate in self.candidates]
        if len(candidate_ids) != len(set(candidate_ids)):
            raise ValueError("candidate assessments must use unique candidate IDs")
        if self.is_fixture != (self.provider_kind == "fixture"):
            raise ValueError("is_fixture must match provider_kind=fixture")
        return self


class CandidateProposalBundle(DocumentHeader):
    proposal_bundle_id: str
    source_id: str
    provider_record_ref: str
    provider_kind: Literal["fixture", "host_ai_file", "human_file"]
    is_fixture: bool = False
    candidates: tuple[CutCandidate, ...]
    input_document_sha256: str = Field(pattern=SHA256_PATTERN)

    @model_validator(mode="after")
    def validate_candidates(self) -> CandidateProposalBundle:
        candidate_ids = [candidate.candidate_id for candidate in self.candidates]
        if len(candidate_ids) != len(set(candidate_ids)):
            raise ValueError("proposed candidates must use unique candidate IDs")
        if self.is_fixture != (self.provider_kind == "fixture"):
            raise ValueError("is_fixture must match provider_kind=fixture")
        return self


class CandidateAggregate(FrozenModel):
    candidate_id: str
    overall: float | None = Field(default=None, ge=0, le=10)
    normalized_weights: dict[DimensionKey, float] = Field(default_factory=dict)
    required_passed: bool
    exclusion_reasons: tuple[str, ...] = ()
    advisory_scores: dict[DimensionKey, float] = Field(default_factory=dict)
    calculation_version: str
    input_sha256: str = Field(pattern=SHA256_PATTERN)
    model_reported_overall_ignored: float | None = Field(default=None, ge=0, le=10)


class AggregateBundle(DocumentHeader):
    aggregate_bundle_id: str
    source_id: str
    resolved_task_id: str
    aggregates: tuple[CandidateAggregate, ...]
    input_document_sha256: str = Field(pattern=SHA256_PATTERN)

    @model_validator(mode="after")
    def validate_aggregates(self) -> AggregateBundle:
        candidate_ids = [aggregate.candidate_id for aggregate in self.aggregates]
        if len(candidate_ids) != len(set(candidate_ids)):
            raise ValueError("aggregates must use unique candidate IDs")
        return self


class AdaptiveSelectionDecision(FrozenModel):
    candidate_id: str
    selected: bool
    rank: int | None = Field(default=None, ge=1)
    reasons: tuple[str, ...]
    overall: float | None = Field(default=None, ge=0, le=10)
    semantic_qualified: bool = True
    missing_qualifications: tuple[str, ...] = ()


class AdaptiveSelectionResult(DocumentHeader):
    selection_id: str
    decisions: tuple[AdaptiveSelectionDecision, ...]
    selected_candidate_ids: tuple[str, ...]
    unsatisfied_constraints: tuple[str, ...] = ()
    nearest_candidate_ids: tuple[str, ...] = ()
    calculation_version: str
    input_sha256: str = Field(pattern=SHA256_PATTERN)
