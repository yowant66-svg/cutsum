from __future__ import annotations

from pathlib import Path

from universal_cutup.application.four_track_evaluation import (
    run_four_track_evaluation,
)
from universal_cutup.evaluation.models import EvaluationTrack

REPOSITORY_ROOT = Path(__file__).parents[2]
MANIFEST = REPOSITORY_ROOT / "evaluation" / "four-track-v1-manifest.json"


def test_four_track_runner_passes_three_consecutive_deterministic_trials(
    tmp_path: Path,
) -> None:
    output_root = tmp_path / "four-track"

    report = run_four_track_evaluation(MANIFEST, output_root, trial_count=3)

    assert report.deterministic_regression_passed
    assert report.human_review_required
    assert {metric.track for metric in report.track_metrics} == set(EvaluationTrack)
    assert all(metric.pass_at_1 == 1 for metric in report.track_metrics)
    assert all(metric.pass_power_3 == 1 for metric in report.track_metrics)
    assert all(not metric.quality_claim_allowed for metric in report.track_metrics)
    assert (output_root / "four-track-report.json").is_file()
    assert (output_root / "maintainer-review.md").is_file()
    assert "not final content-quality approval" in (output_root / "maintainer-review.md").read_text(
        encoding="utf-8"
    )
