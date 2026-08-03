from __future__ import annotations

from pathlib import Path

from universal_cutup.evaluation.harness import (
    evaluate_observation,
    evaluate_suite,
    load_scenarios,
)
from universal_cutup.evaluation.models import EvaluationObservation

PROJECT_ROOT = Path(__file__).parents[2]
SCENARIO_PATH = PROJECT_ROOT / "tests" / "fixtures" / "gate_f" / "scenarios.json"


def make_observation(scenario_id: str) -> EvaluationObservation:
    return EvaluationObservation(
        scenario_id=scenario_id,
        instruction_constraints_passed=(True, True),
        predicted_content_types=("lecture",),
        expected_applicability={},
        observed_applicability={},
        constraints_satisfied=(True,),
        duplicate_pair_count=0,
        overlap_violation_count=0,
        selected_candidate_ids=("candidate-1",),
        repeated_selected_candidate_ids=("candidate-1",),
    )


def test_synthetic_suite_covers_all_twelve_required_scenarios() -> None:
    scenarios = load_scenarios(SCENARIO_PATH)
    assert len(scenarios) == 12
    categories = {scenario.category for scenario in scenarios}
    assert categories == {"auto", "guided", "directed"}
    assert all(scenario.spdx_license == "Apache-2.0" for scenario in scenarios)
    assert all("synthetic" in scenario.provenance.lower() for scenario in scenarios)


def test_metrics_report_protocol_behavior_without_quality_claims() -> None:
    scenarios = load_scenarios(SCENARIO_PATH)
    observations = tuple(make_observation(scenario.scenario_id) for scenario in scenarios)
    report = evaluate_suite(scenarios, observations)
    assert report.scenario_count == 12
    assert report.synthetic_only is True
    assert "not a claim" in report.disclaimer
    assert all(metric.ranking_stable for metric in report.metrics)
    assert all(metric.reproducible_sha256 for metric in report.metrics)


def test_failure_taxonomy_and_ranking_instability_are_preserved() -> None:
    scenario = load_scenarios(SCENARIO_PATH)[0]
    observation = make_observation(scenario.scenario_id).model_copy(
        update={
            "instruction_constraints_passed": (False,),
            "selected_candidate_ids": ("candidate-1",),
            "repeated_selected_candidate_ids": ("candidate-2",),
            "failure_types": ("IGNORED_HOST_INTENT",),
        }
    )
    metrics = evaluate_observation(scenario, observation)
    assert metrics.instruction_adherence_rate == 0
    assert metrics.ranking_stable is False
    assert metrics.failure_taxonomy == ("IGNORED_HOST_INTENT",)
