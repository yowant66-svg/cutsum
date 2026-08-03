from __future__ import annotations

from enum import StrEnum

from pydantic import model_validator

from .common import FrozenModel


class SelectionStatus(StrEnum):
    SELECTED = "selected"
    REJECTED = "rejected"
    DEFERRED = "deferred"


class SelectionDecision(FrozenModel):
    candidate_id: str
    status: SelectionStatus
    reason: str
    rule_ids: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    overridden: bool = False
    override_reason: str | None = None

    @model_validator(mode="after")
    def validate_override(self) -> SelectionDecision:
        if self.overridden != (self.override_reason is not None):
            raise ValueError("overridden and override_reason must be set together")
        return self


class SelectionResult(FrozenModel):
    selection_id: str
    selection_strategy_id: str
    selection_strategy_version: str
    decisions: tuple[SelectionDecision, ...]
    warnings: tuple[str, ...] = ()
    provider_record_refs: tuple[str, ...] = ()
    strategy_record_ref: str | None = None

    @model_validator(mode="after")
    def validate_unique_candidates(self) -> SelectionResult:
        candidate_ids = [decision.candidate_id for decision in self.decisions]
        if len(candidate_ids) != len(set(candidate_ids)):
            raise ValueError("each candidate may have only one selection decision")
        return self

    @property
    def selected_candidate_ids(self) -> tuple[str, ...]:
        return tuple(
            decision.candidate_id
            for decision in self.decisions
            if decision.status is SelectionStatus.SELECTED
        )
