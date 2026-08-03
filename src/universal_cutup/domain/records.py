from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import Field, field_validator, model_validator

from .common import SHA256_PATTERN, FrozenModel


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
    input_hashes: tuple[str, ...] = ()
    output_hashes: tuple[str, ...] = ()
    cost_minor_units: int | None = Field(default=None, ge=0)
    currency: str | None = None
    warnings: tuple[str, ...] = ()


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
