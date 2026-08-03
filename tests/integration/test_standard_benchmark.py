from __future__ import annotations

import json
from pathlib import Path

from universal_cutup.application.benchmarking import (
    load_benchmark_inputs,
    run_standard_benchmark,
)
from universal_cutup.domain.benchmarks import BenchmarkCategory

REPOSITORY_ROOT = Path(__file__).parents[2]
MANIFEST = REPOSITORY_ROOT / "benchmarks" / "standard-v1" / "manifest.json"
CURATED_INPUTS = REPOSITORY_ROOT / "benchmarks" / "standard-v1" / "curated-inputs.json"


def test_standard_manifest_has_three_tracks_and_bounded_windows() -> None:
    manifest, curated = load_benchmark_inputs(MANIFEST, CURATED_INPUTS)
    assert len(manifest.items) == 9
    assert len(curated.items) == 9
    for category in BenchmarkCategory:
        assert sum(item.category is category for item in manifest.items) == 3
    for item in manifest.items:
        assert item.auto_task.control_mode.value == "auto"
        assert len(item.directed_tasks) >= 2
        if item.category in {
            BenchmarkCategory.FILM_OR_DRAMA,
            BenchmarkCategory.EDUCATION_OR_KNOWLEDGE,
        }:
            window = item.execution_policy.analysis_window
            assert window.end_ms - window.start_ms <= 1_800_000


def test_standard_run_is_structurally_reproducible_and_honors_host_controls(
    tmp_path: Path,
) -> None:
    first = run_standard_benchmark(MANIFEST, CURATED_INPUTS, tmp_path / "first")
    second = run_standard_benchmark(MANIFEST, CURATED_INPUTS, tmp_path / "second")
    assert first["item_count"] == 9
    assert first["task_count"] == 27
    assert first["external_model_api_calls"] == 0
    assert first["actual_cost_minor_units"] == 0
    first_hashes = {run["task_id"]: run["stable_structure_sha256"] for run in first["runs"]}
    second_hashes = {run["task_id"]: run["stable_structure_sha256"] for run in second["runs"]}
    assert first_hashes == second_hashes

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    runs = {run["task_id"]: run for run in first["runs"]}
    for item in manifest["items"]:
        for task in item["directed_tasks"]:
            selected = set(runs[task["task_id"]]["selected_candidate_ids"])
            assert set(task.get("hard_include_candidate_ids", ())) <= selected
            assert not set(task.get("hard_exclude_candidate_ids", ())) & selected

    result_pages = tuple((tmp_path / "first" / "results").glob("*/*/00-result.md"))
    assert len(result_pages) == 27
    assert all("请维护者评价" in page.read_text(encoding="utf-8") for page in result_pages)
