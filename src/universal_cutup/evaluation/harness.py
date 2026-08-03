from __future__ import annotations

import json
from pathlib import Path

from pydantic import TypeAdapter

from universal_cutup.hashing import document_sha256

from .models import (
    EvaluationEvidenceClass,
    EvaluationObservation,
    EvaluationSuiteReport,
    EvaluationTrack,
    FourTrackEvaluationReport,
    HumanReviewStatus,
    ScenarioMetrics,
    SyntheticScenario,
    TrackEvaluationEvidence,
    TrackEvaluationMetrics,
)

SCENARIO_ADAPTER = TypeAdapter(tuple[SyntheticScenario, ...])


def load_scenarios(path: Path) -> tuple[SyntheticScenario, ...]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return SCENARIO_ADAPTER.validate_python(payload["scenarios"])


def _rate(results: tuple[bool, ...]) -> float:
    return sum(results) / len(results) if results else 1


def evaluate_observation(
    scenario: SyntheticScenario,
    observation: EvaluationObservation,
) -> ScenarioMetrics:
    if observation.scenario_id != scenario.scenario_id:
        raise ValueError("observation scenario_id must match scenario")
    expected_labels = set(scenario.expected_content_types)
    predicted_labels = set(observation.predicted_content_types)
    label_recall = len(expected_labels & predicted_labels) / len(expected_labels)
    applicability_matches = tuple(
        observation.observed_applicability.get(dimension) == expected
        for dimension, expected in observation.expected_applicability.items()
    )
    stable = observation.selected_candidate_ids == observation.repeated_selected_candidate_ids
    payload_hash = document_sha256(
        {
            "scenario": scenario.model_dump(mode="json"),
            "observation": observation.model_dump(mode="json"),
        }
    )
    return ScenarioMetrics(
        scenario_id=scenario.scenario_id,
        instruction_adherence_rate=_rate(observation.instruction_constraints_passed),
        content_profile_label_recall=label_recall,
        dimension_applicability_consistency=_rate(applicability_matches),
        constraint_satisfaction_rate=_rate(observation.constraints_satisfied),
        duplicate_pair_count=observation.duplicate_pair_count,
        overlap_violation_count=observation.overlap_violation_count,
        ranking_stable=stable,
        reproducible_sha256=payload_hash,
        failure_taxonomy=observation.failure_types,
    )


def evaluate_suite(
    scenarios: tuple[SyntheticScenario, ...],
    observations: tuple[EvaluationObservation, ...],
) -> EvaluationSuiteReport:
    observations_by_id = {observation.scenario_id: observation for observation in observations}
    if set(observations_by_id) != {scenario.scenario_id for scenario in scenarios}:
        raise ValueError("observations must cover every scenario exactly once")
    metrics = tuple(
        evaluate_observation(scenario, observations_by_id[scenario.scenario_id])
        for scenario in scenarios
    )
    report_hash = document_sha256(
        {"metrics": [metric.model_dump(mode="json") for metric in metrics]}
    )
    return EvaluationSuiteReport(
        scenario_count=len(scenarios),
        metrics=metrics,
        report_sha256=report_hash,
    )


def _pass_power_three(evidence: TrackEvaluationEvidence) -> bool:
    if len(evidence.trials) < 3:
        return False
    first_three = evidence.trials[:3]
    return (
        all(trial.passed for trial in first_three)
        and len({trial.structure_sha256 for trial in first_three}) == 1
    )


def evaluate_four_track_suite(
    evidence: tuple[TrackEvaluationEvidence, ...],
) -> FourTrackEvaluationReport:
    case_keys = [(item.track, item.case_id) for item in evidence]
    if len(case_keys) != len(set(case_keys)):
        raise ValueError("four-track evidence case IDs must be unique within a track")
    grouped = {
        track: tuple(item for item in evidence if item.track is track) for track in EvaluationTrack
    }
    if set(item.track for item in evidence) != set(EvaluationTrack):
        raise ValueError("four-track evaluation requires exactly the four required tracks")
    metrics = []
    for track in EvaluationTrack:
        records = grouped[track]
        checks = tuple(passed for record in records for passed in record.capability_checks.values())
        first_trials = tuple(record.trials[0].passed for record in records)
        stable_trials = tuple(_pass_power_three(record) for record in records)
        quality_claim_allowed = all(
            record.evidence_class is EvaluationEvidenceClass.REAL_LOCAL
            and record.human_review_status is HumanReviewStatus.PASSED
            for record in records
        )
        failures = tuple(
            dict.fromkeys(
                failure
                for record in records
                for trial in record.trials
                for failure in trial.failure_types
            )
        )
        metrics.append(
            TrackEvaluationMetrics(
                track=track,
                case_count=len(records),
                capability_pass_rate=_rate(checks),
                pass_at_1=_rate(first_trials),
                pass_power_3=_rate(stable_trials),
                evidence_classes=tuple(dict.fromkeys(record.evidence_class for record in records)),
                failure_taxonomy=failures,
                quality_claim_allowed=quality_claim_allowed,
                human_review_required=not quality_claim_allowed,
            )
        )
    report_payload = {
        "evidence": [item.model_dump(mode="json") for item in evidence],
        "metrics": [metric.model_dump(mode="json") for metric in metrics],
    }
    return FourTrackEvaluationReport(
        evidence_count=len(evidence),
        track_metrics=tuple(metrics),
        deterministic_regression_passed=all(metric.pass_power_3 == 1 for metric in metrics),
        human_review_required=any(metric.human_review_required for metric in metrics),
        report_sha256=document_sha256(report_payload),
    )
