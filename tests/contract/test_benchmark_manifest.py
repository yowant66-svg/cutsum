from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import AnyHttpUrl

from universal_cutup.domain.benchmarks import (
    AvailabilityStatus,
    BenchmarkCategory,
    BenchmarkEvaluationStatus,
    BenchmarkExecutionPolicy,
    BenchmarkItem,
    BenchmarkManifest,
    BenchmarkSourceKind,
    BenchmarkTaskSpec,
)
from universal_cutup.domain.common import TimeRange
from universal_cutup.domain.intelligence import ClipConstraints, ControlMode

FIXED_TIME = datetime(2026, 7, 30, tzinfo=UTC)


def make_task(task_id: str, mode: ControlMode) -> BenchmarkTaskSpec:
    return BenchmarkTaskSpec(
        task_id=task_id,
        control_mode=mode,
        raw_instruction="Use only the supplied source material",
        clip_constraints=ClipConstraints(target_count=1),
    )


def make_item(
    *,
    category: BenchmarkCategory = BenchmarkCategory.EDUCATION_OR_KNOWLEDGE,
    window: TimeRange | None = None,
) -> BenchmarkItem:
    return BenchmarkItem(
        benchmark_id="standard-benchmark",
        benchmark_version="1.0.0",
        item_id="education-1",
        category=category,
        title="Public benchmark source",
        canonical_subject="Public subject",
        source_url=AnyHttpUrl("https://example.org/source"),
        source_kind=BenchmarkSourceKind.OPEN_COURSE_MEDIA,
        media_availability=AvailabilityStatus.AVAILABLE,
        transcript_availability=AvailabilityStatus.AVAILABLE,
        duration_ms=3_600_000,
        language="en",
        publication_or_release_date="2020",
        accessed_at=FIXED_TIME,
        content_hash="a" * 64,
        source_notes=("Official public source page.",),
        rights_notes=("Analysis-only benchmark; this is not a legal conclusion.",),
        selection_rationale=("Tests structured explanation.",),
        expected_content_structure=("concept", "example", "recap"),
        known_difficulties=("domain terminology",),
        auto_task=make_task("auto", ControlMode.AUTO),
        directed_tasks=(
            make_task("directed-1", ControlMode.DIRECTED),
            make_task("directed-2", ControlMode.DIRECTED),
        ),
        execution_policy=BenchmarkExecutionPolicy(
            analysis_window=window or TimeRange(start_ms=0, end_ms=1_800_000),
            rationale="Use no more than the approved 30-minute window.",
        ),
        evaluation_status=BenchmarkEvaluationStatus.READY,
    )


def test_manifest_identity_and_task_modes_are_validated() -> None:
    item = make_item()
    manifest = BenchmarkManifest(
        document_type="benchmark_manifest",
        created_at=FIXED_TIME,
        created_by="test-suite",
        benchmark_id="standard-benchmark",
        benchmark_version="1.0.0",
        items=(item,),
    )
    assert manifest.items[0].auto_task.control_mode is ControlMode.AUTO
    assert len(manifest.items[0].directed_tasks) == 2


def test_film_and_education_windows_cannot_exceed_thirty_minutes() -> None:
    with pytest.raises(ValueError, match="30 minutes"):
        make_item(window=TimeRange(start_ms=0, end_ms=1_800_001))


def test_interview_window_may_represent_a_longer_source() -> None:
    item = make_item(
        category=BenchmarkCategory.INTERVIEW_OR_TALK,
        window=TimeRange(start_ms=0, end_ms=2_400_000),
    )
    assert item.execution_policy.analysis_window.end_ms == 2_400_000
