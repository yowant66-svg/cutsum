from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from universal_cutup.application.benchmarking import (
    load_benchmark_inputs,
    run_standard_benchmark,
)
from universal_cutup.application.educational import (
    propose_educational_candidates,
    resolve_educational_request,
    select_educational_for_request,
)
from universal_cutup.application.sports import (
    propose_sports_candidates,
    resolve_sports_request,
    select_sports_for_request,
)
from universal_cutup.domain.benchmarks import BenchmarkCategory
from universal_cutup.domain.intelligence import ControlMode
from universal_cutup.domain.sports import SportsObservationBundle
from universal_cutup.domain.transcript import TranscriptArtifact, TranscriptSegment
from universal_cutup.evaluation.harness import evaluate_four_track_suite
from universal_cutup.evaluation.models import (
    EvaluationTrack,
    EvaluationTrial,
    FourTrackCaseDefinition,
    FourTrackEvaluationManifest,
    FourTrackEvaluationReport,
    TrackEvaluationEvidence,
)
from universal_cutup.hashing import document_sha256

REPOSITORY_ROOT = Path(__file__).parents[3]


def load_four_track_manifest(path: Path) -> FourTrackEvaluationManifest:
    return FourTrackEvaluationManifest.model_validate_json(path.read_text(encoding="utf-8"))


def _resolve_input(path_value: str) -> Path:
    path = Path(path_value)
    return path if path.is_absolute() else REPOSITORY_ROOT / path


def _write_json(path: Path, value: Any) -> None:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _standard_track_trial(
    case: FourTrackCaseDefinition,
    *,
    trial_root: Path,
) -> tuple[str, dict[str, bool], tuple[str, ...]]:
    manifest_path, curated_path = tuple(_resolve_input(value) for value in case.input_refs)
    manifest, _ = load_benchmark_inputs(manifest_path, curated_path)
    result = run_standard_benchmark(
        manifest_path,
        curated_path,
        trial_root / "standard-v1",
    )
    category = (
        BenchmarkCategory.INTERVIEW_OR_TALK
        if case.track is EvaluationTrack.INTERVIEW
        else BenchmarkCategory.FILM_OR_DRAMA
    )
    item_ids = {item.item_id for item in manifest.items if item.category is category}
    relevant_runs = tuple(run for run in result["runs"] if run["item_id"] in item_ids)
    structure_hash = document_sha256(
        {
            "case_id": case.case_id,
            "runs": [
                {
                    "item_id": run["item_id"],
                    "task_id": run["task_id"],
                    "selected_candidate_ids": run["selected_candidate_ids"],
                    "stable_structure_sha256": run["stable_structure_sha256"],
                }
                for run in relevant_runs
            ],
        }
    )
    checks = {
        "three_items_present": len(item_ids) == 3,
        "nine_tasks_executed": len(relevant_runs) == 9,
        "all_tasks_have_structure_hash": all(
            bool(run["stable_structure_sha256"]) for run in relevant_runs
        ),
        "zero_external_model_calls": result["external_model_api_calls"] == 0,
        "zero_incremental_cost": result["actual_cost_minor_units"] == 0,
    }
    failures = tuple(key for key, passed in checks.items() if not passed)
    return structure_hash, checks, failures


def _educational_transcript(payload: dict[str, Any]) -> TranscriptArtifact:
    segments = tuple(
        TranscriptSegment(
            segment_id=f"segment-{index:02d}",
            source_id="source-four-track-education",
            start_ms=int(segment["start_ms"]),
            end_ms=int(segment["end_ms"]),
            text=str(segment["text"]),
            text_sha256=hashlib.sha256(str(segment["text"]).encode()).hexdigest(),
        )
        for index, segment in enumerate(payload["transcript"], start=1)
    )
    return TranscriptArtifact(
        document_type="transcript_artifact",
        created_at=datetime(2026, 7, 31, tzinfo=UTC),
        created_by="four-track-evaluation",
        transcript_id="transcript-four-track-education",
        source_id="source-four-track-education",
        language="en",
        segments=segments,
    )


def _education_trial(
    case: FourTrackCaseDefinition,
) -> tuple[str, dict[str, bool], tuple[str, ...]]:
    payload = json.loads(_resolve_input(case.input_refs[0]).read_text(encoding="utf-8"))
    candidates = propose_educational_candidates(_educational_transcript(payload))
    auto = select_educational_for_request(
        candidates,
        resolve_educational_request(ControlMode.AUTO, ""),
    )
    directed = select_educational_for_request(
        candidates,
        resolve_educational_request(
            ControlMode.DIRECTED,
            "只要两个例题，不要定义。",  # noqa: RUF001
        ),
    )
    candidates_by_id = {candidate.candidate_id: candidate for candidate in candidates}
    auto_types = {
        signal.signal_type.value
        for candidate_id in auto.selected_candidate_ids
        for signal in candidates_by_id[candidate_id].education_signals
    }
    directed_types = {
        signal.signal_type.value
        for candidate_id in directed.selected_candidate_ids
        for signal in candidates_by_id[candidate_id].education_signals
    }
    checks = {
        "auto_selected_candidates": bool(auto.selected_candidate_ids),
        "auto_has_definition": "definition" in auto_types,
        "auto_has_example": "worked_example" in auto_types,
        "directed_selected_two": len(directed.selected_candidate_ids) == 2,
        "directed_excluded_definition": "definition" not in directed_types,
        "no_unsatisfied_requirements": not auto.unsatisfied_requirements
        and not directed.unsatisfied_requirements,
    }
    structure_hash = document_sha256(
        {
            "case_id": case.case_id,
            "auto": auto.model_dump(mode="json"),
            "directed": directed.model_dump(mode="json"),
        }
    )
    failures = tuple(key for key, passed in checks.items() if not passed)
    return structure_hash, checks, failures


def _sports_trial(
    case: FourTrackCaseDefinition,
) -> tuple[str, dict[str, bool], tuple[str, ...]]:
    bundle = SportsObservationBundle.model_validate_json(
        _resolve_input(case.input_refs[0]).read_text(encoding="utf-8")
    )
    candidates = propose_sports_candidates(bundle, media_duration_ms=60_000)
    auto = select_sports_for_request(
        candidates,
        resolve_sports_request(ControlMode.AUTO, ""),
    )
    directed = select_sports_for_request(
        candidates,
        resolve_sports_request(
            ControlMode.DIRECTED,
            "只要一个进球，不要回放。",  # noqa: RUF001
        ),
    )
    candidates_by_id = {candidate.candidate_id: candidate for candidate in candidates}
    auto_profiles = tuple(
        candidates_by_id[candidate_id].sports_profile
        for candidate_id in auto.selected_candidate_ids
    )
    directed_profiles = tuple(
        candidates_by_id[candidate_id].sports_profile
        for candidate_id in directed.selected_candidate_ids
    )
    checks = {
        "auto_selected_two_primary_events": len(auto.selected_candidate_ids) == 2,
        "auto_excluded_replay": all(
            profile is not None and not profile.replay_only for profile in auto_profiles
        ),
        "directed_selected_one": len(directed.selected_candidate_ids) == 1,
        "directed_selected_score": all(
            profile is not None and profile.event_type.value == "score"
            for profile in directed_profiles
        ),
        "no_unsatisfied_requirements": not auto.unsatisfied_requirements
        and not directed.unsatisfied_requirements,
    }
    structure_hash = document_sha256(
        {
            "case_id": case.case_id,
            "auto": auto.model_dump(mode="json"),
            "directed": directed.model_dump(mode="json"),
        }
    )
    failures = tuple(key for key, passed in checks.items() if not passed)
    return structure_hash, checks, failures


def _human_review_page(
    manifest: FourTrackEvaluationManifest,
    report: FourTrackEvaluationReport,
) -> str:
    metrics = {metric.track: metric for metric in report.track_metrics}
    lines = [
        "# Four-track maintainer review",
        "",
        (
            "Automated checks below are protocol/capability evidence, "
            "not final content-quality approval."
        ),
        "",
    ]
    for case in manifest.cases:
        metric = metrics[case.track]
        lines.extend(
            [
                f"## {case.track.value}: {case.case_id}",
                "",
                f"- Evidence class: `{case.evidence_class.value}`",
                f"- pass@1: {metric.pass_at_1:.2f}",
                f"- pass^3: {metric.pass_power_3:.2f}",
                f"- Capability pass rate: {metric.capability_pass_rate:.2f}",
                f"- Supplemental artifacts: {', '.join(case.supplemental_artifact_refs) or 'none'}",
                f"- Limitations: {'; '.join(case.limitations)}",
                "- Maintainer quality decision: pending",
                "- Best behavior:",
                "- Largest failure:",
                "- Keep / revise / reject:",
                "",
            ]
        )
    return "\n".join(lines)


def run_four_track_evaluation(
    manifest_path: Path,
    output_root: Path,
    *,
    trial_count: int = 3,
) -> FourTrackEvaluationReport:
    if trial_count < 3:
        raise ValueError("four-track deterministic evaluation requires at least three trials")
    if output_root.exists():
        raise FileExistsError(f"four-track output already exists: {output_root}")
    manifest = load_four_track_manifest(manifest_path)
    output_root.mkdir(parents=True)
    trial_results: dict[str, list[EvaluationTrial]] = {case.case_id: [] for case in manifest.cases}
    case_checks: dict[str, dict[str, bool]] = {}
    for trial_index in range(1, trial_count + 1):
        trial_root = output_root / "trials" / f"trial-{trial_index}"
        trial_root.mkdir(parents=True)
        standard_cache: dict[str, tuple[str, dict[str, bool], tuple[str, ...]]] = {}
        for case in manifest.cases:
            if case.runner.startswith("standard_v1"):
                if "standard-v1" not in standard_cache:
                    standard_cache["standard-v1"] = _standard_track_trial(
                        case,
                        trial_root=trial_root,
                    )
                    other_case = next(
                        item
                        for item in manifest.cases
                        if item.track
                        is (
                            EvaluationTrack.DRAMA
                            if case.track is EvaluationTrack.INTERVIEW
                            else EvaluationTrack.INTERVIEW
                        )
                    )
                    standard_cache[other_case.case_id] = _standard_track_trial_from_index(
                        other_case,
                        trial_root=trial_root,
                    )
                result = (
                    standard_cache["standard-v1"]
                    if case.case_id not in standard_cache
                    else standard_cache[case.case_id]
                )
            elif case.runner == "educational_v1":
                result = _education_trial(case)
            else:
                result = _sports_trial(case)
            structure_hash, checks, failures = result
            case_checks[case.case_id] = checks
            trial_results[case.case_id].append(
                EvaluationTrial(
                    trial_index=trial_index,
                    passed=all(checks.values()),
                    structure_sha256=structure_hash,
                    failure_types=failures,
                )
            )
    evidence = tuple(
        TrackEvaluationEvidence(
            case_id=case.case_id,
            track=case.track,
            evaluation_type=case.evaluation_type,
            evidence_class=case.evidence_class,
            trials=tuple(trial_results[case.case_id]),
            capability_checks=case_checks[case.case_id],
            limitations=case.limitations,
            artifact_refs=(*case.input_refs, *case.supplemental_artifact_refs),
        )
        for case in manifest.cases
    )
    report = evaluate_four_track_suite(evidence)
    _write_json(output_root / "manifest.json", manifest)
    _write_json(
        output_root / "evidence-records.json",
        [item.model_dump(mode="json") for item in evidence],
    )
    _write_json(output_root / "four-track-report.json", report)
    (output_root / "maintainer-review.md").write_text(
        _human_review_page(manifest, report),
        encoding="utf-8",
    )
    return report


def _standard_track_trial_from_index(
    case: FourTrackCaseDefinition,
    *,
    trial_root: Path,
) -> tuple[str, dict[str, bool], tuple[str, ...]]:
    manifest_path, curated_path = tuple(_resolve_input(value) for value in case.input_refs)
    manifest, _ = load_benchmark_inputs(manifest_path, curated_path)
    run_index = json.loads(
        (trial_root / "standard-v1" / "run-index.json").read_text(encoding="utf-8")
    )
    category = (
        BenchmarkCategory.INTERVIEW_OR_TALK
        if case.track is EvaluationTrack.INTERVIEW
        else BenchmarkCategory.FILM_OR_DRAMA
    )
    item_ids = {item.item_id for item in manifest.items if item.category is category}
    relevant_runs = tuple(run for run in run_index["runs"] if run["item_id"] in item_ids)
    structure_hash = document_sha256(
        {
            "case_id": case.case_id,
            "runs": [
                {
                    "item_id": run["item_id"],
                    "task_id": run["task_id"],
                    "selected_candidate_ids": run["selected_candidate_ids"],
                    "stable_structure_sha256": run["stable_structure_sha256"],
                }
                for run in relevant_runs
            ],
        }
    )
    checks = {
        "three_items_present": len(item_ids) == 3,
        "nine_tasks_executed": len(relevant_runs) == 9,
        "all_tasks_have_structure_hash": all(
            bool(run["stable_structure_sha256"]) for run in relevant_runs
        ),
        "zero_external_model_calls": run_index["external_model_api_calls"] == 0,
        "zero_incremental_cost": run_index["actual_cost_minor_units"] == 0,
    }
    failures = tuple(key for key, passed in checks.items() if not passed)
    return structure_hash, checks, failures
