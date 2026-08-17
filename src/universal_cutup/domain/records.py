from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import Field, field_validator, model_validator

from .common import SHA256_PATTERN, FrozenModel
from .model_routing import (
    EscalationReason,
    ModelTask,
    ModelTier,
    model_task_base_tier,
)


class StrategyRole(StrEnum):
    PROPOSAL = "proposal"
    SCORING = "scoring"
    SELECTION = "selection"


class TimestampedRecord(FrozenModel):
    started_at: datetime
    completed_at: datetime

    @field_validator("started_at", "completed_at")
    @classmethod
    def validate_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() != UTC.utcoffset(value):
            raise ValueError("record timestamps must be UTC")
        return value

    @model_validator(mode="after")
    def validate_order(self) -> TimestampedRecord:
        if self.completed_at < self.started_at:
            raise ValueError("completed_at cannot precede started_at")
        return self


class ProviderRecord(TimestampedRecord):
    provider_record_id: str
    provider_id: str
    operation: str
    model_id: str | None = None
    routing_decision_id: str | None = Field(default=None, pattern=r"^route-[0-9a-f]{20}$")
    model_task: ModelTask | None = None
    base_model_tier: ModelTier | None = None
    selected_model_tier: ModelTier | None = None
    model_escalation_reasons: tuple[EscalationReason, ...] = ()
    input_hashes: tuple[str, ...] = ()
    output_hashes: tuple[str, ...] = ()
    cost_minor_units: int | None = Field(default=None, ge=0)
    currency: str | None = None
    warnings: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_model_routing(self) -> ProviderRecord:
        identity = (
            self.routing_decision_id,
            self.model_task,
            self.base_model_tier,
            self.selected_model_tier,
        )
        has_routing = any(value is not None for value in identity) or bool(
            self.model_escalation_reasons
        )
        if not has_routing:
            return self
        if any(value is None for value in identity):
            raise ValueError("routing metadata must be supplied together")
        if self.model_id is None:
            raise ValueError("routed model calls must record model_id")

        assert self.model_task is not None
        assert self.base_model_tier is not None
        assert self.selected_model_tier is not None
        expected_base = model_task_base_tier(self.model_task)
        if expected_base is ModelTier.DETERMINISTIC:
            raise ValueError("deterministic tasks cannot be recorded as model calls")
        if self.base_model_tier is not expected_base:
            raise ValueError("base model tier must match the model task")

        tier_order = (
            ModelTier.DETERMINISTIC,
            ModelTier.ECONOMY,
            ModelTier.BALANCED,
            ModelTier.FRONTIER,
        )
        base_rank = tier_order.index(self.base_model_tier)
        selected_rank = tier_order.index(self.selected_model_tier)
        if selected_rank < base_rank:
            raise ValueError("selected model tier cannot be below base tier")
        if selected_rank > base_rank and not self.model_escalation_reasons:
            raise ValueError("tier escalation requires at least one reason")
        return self


class StrategyRecord(TimestampedRecord):
    strategy_record_id: str
    strategy_id: str
    strategy_version: str
    strategy_role: StrategyRole
    distribution_name: str
    distribution_version: str
    config_hash: str = Field(pattern=SHA256_PATTERN)
    input_hashes: tuple[str, ...] = ()
    output_hashes: tuple[str, ...] = ()
    provider_record_refs: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    provenance_ref: str
