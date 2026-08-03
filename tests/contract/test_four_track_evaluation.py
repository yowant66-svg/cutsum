from __future__ import annotations

import pytest

from universal_cutup.evaluation.harness import evaluate_four_track_suite
from universal_cutup.evaluation.models import (
    EvaluationEvidenceClass,
    EvaluationTrack,
    EvaluationTrial,
    EvaluationType,
    HumanReviewStatus,
    TrackEvaluationEvidence,
)


def _evidence(
    track: EvaluationTrack,
    *,
    evidence_class: EvaluationEvidenceClass = EvaluationEvidenceClass.CURATED_PROTOCOL,
    hashes: tuple[str, str, str] = ("a" * 64, "a" * 64, "a" * 64),
    human_review_status: HumanReviewStatus = HumanReviewStatus.PENDING,
) -> TrackEvaluationEvidence:
    return TrackEvaluationEvidence(
        case_id=f"case-{track.value}",
        track=track,
        evaluation_type=EvaluationType.REGRESSION,
        evidence_class=evidence_class,
        trials=tuple(
            EvaluationTrial(
                trial_index=index,
                passed=True,
                structure_sha256=structure_hash,
            )
            for index, structure_hash in enumerate(hashes, start=1)
        ),
        capability_checks={
            "produced_selection": True,
            "preserved_provenance": True,
        },
        limitations=("Human content-quality review remains required.",),
        artifact_refs=(f"evidence/{track.value}",),
        human_review_status=human_review_status,
    )


def test_four_track_report_separates_stability_from_quality_claims() -> None:
    evidence = (
        _evidence(EvaluationTrack.INTERVIEW),
        _evidence(EvaluationTrack.DRAMA),
        _evidence(
            EvaluationTrack.EDUCATION,
            evidence_class=EvaluationEvidenceClass.REAL_LOCAL,
        ),
        _evidence(
            EvaluationTrack.SPORTS,
            evidence_class=EvaluationEvidenceClass.SYNTHETIC,
        ),
    )

    report = evaluate_four_track_suite(evidence)

    assert {metric.track for metric in report.track_metrics} == set(EvaluationTrack)
    assert all(metric.pass_at_1 == 1 for metric in report.track_metrics)
    assert all(metric.pass_power_3 == 1 for metric in report.track_metrics)
    assert all(not metric.quality_claim_allowed for metric in report.track_metrics)
    assert report.deterministic_regression_passed
    assert "not a content-quality claim" in report.disclaimer


def test_four_track_report_rejects_missing_track() -> None:
    evidence = tuple(
        _evidence(track) for track in EvaluationTrack if track is not EvaluationTrack.SPORTS
    )

    with pytest.raises(ValueError, match="exactly the four required tracks"):
        evaluate_four_track_suite(evidence)


def test_pass_power_three_requires_three_matching_successful_trials() -> None:
    evidence = tuple(
        _evidence(
            track,
            hashes=("a" * 64, "a" * 64, ("b" * 64 if track is EvaluationTrack.DRAMA else "a" * 64)),
        )
        for track in EvaluationTrack
    )

    report = evaluate_four_track_suite(evidence)
    drama = next(metric for metric in report.track_metrics if metric.track is EvaluationTrack.DRAMA)

    assert drama.pass_at_1 == 1
    assert drama.pass_power_3 == 0
    assert not report.deterministic_regression_passed


def test_quality_claim_requires_real_local_evidence_and_completed_human_review() -> None:
    evidence = tuple(
        _evidence(
            track,
            evidence_class=EvaluationEvidenceClass.REAL_LOCAL,
            human_review_status=HumanReviewStatus.PASSED,
        )
        for track in EvaluationTrack
    )

    report = evaluate_four_track_suite(evidence)

    assert all(metric.quality_claim_allowed for metric in report.track_metrics)
    assert not report.human_review_required
