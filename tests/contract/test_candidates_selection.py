from __future__ import annotations

from universal_cutup.domain.candidates import CutCandidate, EvidenceRef
from universal_cutup.domain.selection import (
    SelectionDecision,
    SelectionResult,
    SelectionStatus,
)


def test_cut_candidate_has_no_canonical_selection_state() -> None:
    fields = CutCandidate.model_fields
    assert "decision" not in fields
    assert "decision_reason" not in fields
    assert "selected" not in fields


def test_selection_result_is_the_only_selection_authority() -> None:
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
        summary="A complete thought",
        evidence_refs=(evidence,),
    )
    selection = SelectionResult(
        selection_id="selection-1",
        selection_strategy_id="deterministic",
        selection_strategy_version="0.1.0",
        decisions=(
            SelectionDecision(
                candidate_id=candidate.candidate_id,
                status=SelectionStatus.SELECTED,
                reason="meets deterministic threshold",
                rule_ids=("duration-ok",),
                evidence_refs=(evidence.evidence_id,),
            ),
        ),
    )
    assert selection.selected_candidate_ids == ("candidate-1",)
