from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import Field, model_validator

from universal_cutup.domain.common import SHA256_PATTERN, DocumentHeader, FrozenModel
from universal_cutup.domain.intelligence import DimensionKey


class SyntheticSegment(FrozenModel):
    start_ms: int = Field(ge=0)
    end_ms: int = Field(gt=0)
    text: str


class SyntheticScenario(FrozenModel):
    scenario_id: str
    title: str
    category: str
    transcript_segments: tuple[SyntheticSegment, ...] = Field(min_length=1)
    host_instruction: str
    expected_content_types: tuple[str, ...] = Field(min_length=1)
    expected_constraints: tuple[str, ...]
    debatable_items: tuple[str, ...] = ()
    creation_method: str
    spdx_license: str
    provenance: str


class EvaluationObservation(FrozenModel):
    scenario_id: str
    instruction_constraints_passed: tuple[bool, ...]
    predicted_content_types: tuple[str, ...]
    expected_applicability: dict[DimensionKey, str]
    observed_applicability: dict[DimensionKey, str]
    constraints_satisfied: tuple[bool, ...]
    duplicate_pair_count: int = Field(ge=0)
    overlap_violation_count: int = Field(ge=0)
    selected_candidate_ids: tuple[str, ...]
    repeated_selected_candidate_ids: tuple[str, ...]
    failure_types: tuple[str, ...] = ()


class ScenarioMetrics(FrozenModel):
    scenario_id: str
    instruction_adherence_rate: float = Field(ge=0, le=1)
    content_profile_label_recall: float = Field(ge=0, le=1)
    dimension_applicability_consistency: float = Field(ge=0, le=1)
    constraint_satisfaction_rate: float = Field(ge=0, le=1)
    duplicate_pair_count: int = Field(ge=0)
    overlap_violation_count: int = Field(ge=0)
    ranking_stable: bool
    reproducible_sha256: str = Field(pattern=SHA256_PATTERN)
    failure_taxonomy: tuple[str, ...]


class EvaluationSuiteReport(FrozenModel):
    scenario_count: int = Field(ge=1)
    metrics: tuple[ScenarioMetrics, ...]
    report_sha256: str = Field(pattern=SHA256_PATTERN)
    synthetic_only: bool = True
    disclaimer: str = (
        "Synthetic protocol evaluation only; not a claim of real model or content quality."
    )


class HumanAnnotation(FrozenModel):
    scenario_id: str
    candidate_id: str
    reviewer_id: str
    instruction_adherence: int = Field(ge=0, le=4)
    content_profile_fit: int = Field(ge=0, le=4)
    selection_value: int = Field(ge=0, le=4)
    context_integrity: int = Field(ge=0, le=4)
    boundary_quality: int = Field(ge=0, le=4)
    duration_compliance: int = Field(ge=0, le=4)
    evidence_quality: int = Field(ge=0, le=4)
    diversity: int = Field(ge=0, le=4)
    title_summary_accuracy: int = Field(ge=0, le=4)
    overall_usefulness: int = Field(ge=0, le=4)
    reviewer_notes: str = ""


class EvaluationTrack(StrEnum):
    INTERVIEW = "interview"
    DRAMA = "drama"
    EDUCATION = "education"
    SPORTS = "sports"


class EvaluationType(StrEnum):
    CAPABILITY = "capability"
    REGRESSION = "regression"
    HUMAN_REVIEW = "human_review"


class EvaluationEvidenceClass(StrEnum):
    REAL_LOCAL = "real_local"
    SYNTHETIC = "synthetic"
    CURATED_PROTOCOL = "curated_protocol"


class HumanReviewStatus(StrEnum):
    NOT_REQUIRED = "not_required"
    PENDING = "pending"
    PASSED = "passed"
    FAILED = "failed"


class EvaluationTrial(FrozenModel):
    trial_index: int = Field(ge=1)
    passed: bool
    structure_sha256: str = Field(pattern=SHA256_PATTERN)
    failure_types: tuple[str, ...] = ()


class TrackEvaluationEvidence(FrozenModel):
    case_id: str
    track: EvaluationTrack
    evaluation_type: EvaluationType
    evidence_class: EvaluationEvidenceClass
    trials: tuple[EvaluationTrial, ...] = Field(min_length=1)
    capability_checks: dict[str, bool] = Field(min_length=1)
    limitations: tuple[str, ...] = ()
    artifact_refs: tuple[str, ...] = Field(min_length=1)
    human_review_status: HumanReviewStatus = HumanReviewStatus.PENDING

    @model_validator(mode="after")
    def validate_trials(self) -> TrackEvaluationEvidence:
        trial_indices = [trial.trial_index for trial in self.trials]
        if len(trial_indices) != len(set(trial_indices)):
            raise ValueError("evaluation trial indices must be unique")
        if trial_indices != sorted(trial_indices):
            raise ValueError("evaluation trials must be ordered")
        return self


class TrackEvaluationMetrics(FrozenModel):
    track: EvaluationTrack
    case_count: int = Field(ge=1)
    capability_pass_rate: float = Field(ge=0, le=1)
    pass_at_1: float = Field(ge=0, le=1)
    pass_power_3: float = Field(ge=0, le=1)
    evidence_classes: tuple[EvaluationEvidenceClass, ...]
    failure_taxonomy: tuple[str, ...]
    quality_claim_allowed: bool
    human_review_required: bool


class FourTrackEvaluationReport(FrozenModel):
    evidence_count: int = Field(ge=4)
    track_metrics: tuple[TrackEvaluationMetrics, ...] = Field(min_length=4, max_length=4)
    deterministic_regression_passed: bool
    human_review_required: bool
    report_sha256: str = Field(pattern=SHA256_PATTERN)
    disclaimer: str = (
        "Automated pass rates cover capability and deterministic regression; "
        "they are not a content-quality claim."
    )

    @model_validator(mode="after")
    def validate_tracks(self) -> FourTrackEvaluationReport:
        tracks = [metric.track for metric in self.track_metrics]
        if set(tracks) != set(EvaluationTrack) or len(tracks) != len(set(tracks)):
            raise ValueError("four-track report requires each evaluation track exactly once")
        return self


class FourTrackCaseDefinition(FrozenModel):
    case_id: str
    track: EvaluationTrack
    evaluation_type: EvaluationType
    evidence_class: EvaluationEvidenceClass
    runner: Literal[
        "standard_v1_interview",
        "standard_v1_drama",
        "educational_v1",
        "sports_alpha",
    ]
    input_refs: tuple[str, ...] = Field(min_length=1)
    supplemental_artifact_refs: tuple[str, ...] = ()
    limitations: tuple[str, ...] = Field(min_length=1)


class FourTrackEvaluationManifest(DocumentHeader):
    suite_id: str
    suite_version: str
    cases: tuple[FourTrackCaseDefinition, ...] = Field(min_length=4)

    @model_validator(mode="after")
    def validate_cases(self) -> FourTrackEvaluationManifest:
        case_ids = [case.case_id for case in self.cases]
        if len(case_ids) != len(set(case_ids)):
            raise ValueError("four-track case IDs must be unique")
        if {case.track for case in self.cases} != set(EvaluationTrack):
            raise ValueError("four-track manifest must cover all tracks")
        expected_runner_track = {
            "standard_v1_interview": EvaluationTrack.INTERVIEW,
            "standard_v1_drama": EvaluationTrack.DRAMA,
            "educational_v1": EvaluationTrack.EDUCATION,
            "sports_alpha": EvaluationTrack.SPORTS,
        }
        if any(case.track is not expected_runner_track[case.runner] for case in self.cases):
            raise ValueError("four-track runner does not match case track")
        return self
