from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from universal_cutup.domain.candidates import (
    CutCandidate,
    EvidenceArtifactIdentity,
    EvidenceRef,
)
from universal_cutup.domain.plans import CutPlan, derive_plan
from universal_cutup.domain.records import ProviderRecord
from universal_cutup.domain.selection import (
    SelectionDecision,
    SelectionResult,
    SelectionStatus,
)
from universal_cutup.domain.sources import MediaSource
from universal_cutup.hashing import document_sha256, semantic_fingerprint

FIXED_TIME = datetime(2026, 7, 30, 12, 0, tzinfo=UTC)


def make_plan(
    *,
    plan_id: str,
    created_at: datetime,
    source_duration_ms: int | None = None,
) -> CutPlan:
    evidence = EvidenceRef(
        evidence_id="evidence-1",
        artifact_id="transcript-1",
        segment_ids=("segment-1",),
        start_ms=0,
        end_ms=1000,
        text_sha256="a" * 64,
    )
    candidate = CutCandidate(
        candidate_id="candidate-1",
        source_id="source-1",
        start_ms=0,
        end_ms=1000,
        summary="Stable meaning",
        evidence_refs=(evidence,),
    )
    selection = SelectionResult(
        selection_id="selection-1",
        selection_strategy_id="deterministic",
        selection_strategy_version="0.1.0",
        decisions=(
            SelectionDecision(
                candidate_id="candidate-1",
                status=SelectionStatus.SELECTED,
                reason="stable",
                evidence_refs=("evidence-1",),
            ),
        ),
    )
    provider_record = ProviderRecord(
        provider_record_id="provider-record-1",
        provider_id="mock",
        operation="transcribe",
        started_at=FIXED_TIME,
        completed_at=FIXED_TIME,
        input_hashes=("b" * 64,),
        output_hashes=("c" * 64,),
    )
    return CutPlan(
        document_type="cut_plan",
        created_at=created_at,
        created_by="test-suite",
        plan_id=plan_id,
        source=MediaSource(
            source_id="source-1",
            media_id="media-1",
            kind="video",
            sha256="d" * 64,
            basename_hint="input.mp4",
            duration_ms=source_duration_ms,
        ),
        evidence_artifacts=(
            EvidenceArtifactIdentity(
                artifact_id="transcript-1",
                source_id="source-1",
                segment_ids=("segment-1",),
            ),
        ),
        candidates=(candidate,),
        selection_result=selection,
        provider_records=(provider_record,),
    )


def test_document_hash_and_semantic_fingerprint_are_stable_but_distinct() -> None:
    plan = make_plan(plan_id="plan-1", created_at=FIXED_TIME)
    assert document_sha256(plan) == document_sha256(plan)
    assert semantic_fingerprint(plan) == semantic_fingerprint(plan)
    assert document_sha256(plan) != semantic_fingerprint(plan)


def test_semantically_equal_plans_ignore_identity_fields() -> None:
    first = make_plan(plan_id="plan-1", created_at=FIXED_TIME)
    second = make_plan(
        plan_id="plan-2",
        created_at=datetime(2026, 7, 30, 13, 0, tzinfo=UTC),
    )
    assert document_sha256(first) != document_sha256(second)
    assert semantic_fingerprint(first) == semantic_fingerprint(second)


def test_manual_override_derives_plan_without_mutating_original() -> None:
    original = make_plan(plan_id="plan-1", created_at=FIXED_TIME)
    original_hash = document_sha256(original)
    original_scores = original.candidates[0].strategy_scores
    decision = original.selection_result.decisions[0].model_copy(
        update={
            "status": SelectionStatus.REJECTED,
            "overridden": True,
            "override_reason": "Maintainer review",
        }
    )
    derived = derive_plan(
        original,
        plan_id="plan-2",
        created_at=datetime(2026, 7, 30, 14, 0, tzinfo=UTC),
        selection_result=original.selection_result.model_copy(
            update={"selection_id": "selection-2", "decisions": (decision,)}
        ),
    )
    assert derived.derived_from_plan_id == original.plan_id
    assert document_sha256(original) == original_hash
    assert original.candidates[0].strategy_scores == original_scores
    assert derived.selection_result.decisions[0].overridden is True


def test_cut_plan_is_frozen() -> None:
    plan = make_plan(plan_id="plan-1", created_at=FIXED_TIME)
    with pytest.raises(ValidationError):
        plan.plan_id = "changed"


def test_candidate_cannot_extend_beyond_declared_source_duration() -> None:
    with pytest.raises(ValidationError, match="candidate range exceeds source duration"):
        make_plan(
            plan_id="plan-out-of-range",
            created_at=FIXED_TIME,
            source_duration_ms=500,
        )


def test_candidate_allows_small_container_duration_rounding_difference() -> None:
    plan = make_plan(
        plan_id="plan-rounded-duration",
        created_at=FIXED_TIME,
        source_duration_ms=900,
    )

    assert plan.candidates[0].end_ms == 1000
