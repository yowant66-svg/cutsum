from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from universal_cutup.domain.model_routing import (
    EscalationReason,
    ModelTask,
    ModelTier,
)
from universal_cutup.domain.records import ProviderRecord, StrategyRecord, StrategyRole

FIXED_TIME = datetime(2026, 7, 30, 12, 0, tzinfo=UTC)


def test_strategy_record_complete_round_trip() -> None:
    record = StrategyRecord(
        strategy_record_id="strategy-record-1",
        strategy_id="deterministic",
        strategy_version="0.1.0",
        strategy_role=StrategyRole.PROPOSAL,
        distribution_name="cutsum",
        distribution_version="0.1.0a1",
        config_hash="a" * 64,
        input_hashes=("b" * 64,),
        output_hashes=("c" * 64,),
        provider_record_refs=("provider-record-1",),
        started_at=FIXED_TIME,
        completed_at=FIXED_TIME,
        warnings=(),
        provenance_ref="new-original",
    )
    assert StrategyRecord.model_validate_json(record.model_dump_json()) == record


def test_provider_record_schema_has_no_secret_or_raw_response_fields() -> None:
    fields = ProviderRecord.model_fields
    assert "api_key" not in fields
    assert "token" not in fields
    assert "cookie" not in fields
    assert "raw_response" not in fields


def test_provider_record_preserves_complete_model_routing_provenance() -> None:
    record = ProviderRecord(
        provider_record_id="provider-record-model-1",
        provider_id="host-openai",
        operation="candidate_proposal",
        model_id="configured-balanced-model",
        routing_decision_id="route-" + "a" * 20,
        model_task=ModelTask.CANDIDATE_PROPOSAL,
        base_model_tier=ModelTier.BALANCED,
        selected_model_tier=ModelTier.FRONTIER,
        model_escalation_reasons=(EscalationReason.LOW_CONFIDENCE,),
        cost_minor_units=12,
        currency="USD",
        started_at=FIXED_TIME,
        completed_at=FIXED_TIME,
    )

    restored = ProviderRecord.model_validate_json(record.model_dump_json())

    assert restored == record
    assert restored.selected_model_tier is ModelTier.FRONTIER


def test_provider_record_remains_backward_compatible_without_routing_metadata() -> None:
    record = ProviderRecord(
        provider_record_id="provider-record-legacy",
        provider_id="fixture-provider",
        operation="fixture_import",
        started_at=FIXED_TIME,
        completed_at=FIXED_TIME,
    )

    assert record.routing_decision_id is None
    assert record.model_escalation_reasons == ()


@pytest.mark.parametrize(
    "partial_update",
    [
        {"routing_decision_id": "route-" + "b" * 20},
        {"model_task": ModelTask.CONTENT_PROFILE},
        {"base_model_tier": ModelTier.BALANCED},
        {"selected_model_tier": ModelTier.FRONTIER},
        {"model_escalation_reasons": (EscalationReason.LOW_CONFIDENCE,)},
    ],
)
def test_provider_record_rejects_partial_routing_metadata(
    partial_update: dict[str, object],
) -> None:
    with pytest.raises(ValidationError, match="routing metadata must be supplied together"):
        ProviderRecord(
            provider_record_id="provider-record-partial",
            provider_id="host-provider",
            operation="content_profile",
            started_at=FIXED_TIME,
            completed_at=FIXED_TIME,
            **partial_update,
        )


def test_provider_record_rejects_selected_tier_below_base_tier() -> None:
    with pytest.raises(ValidationError, match="selected model tier cannot be below base tier"):
        ProviderRecord(
            provider_record_id="provider-record-downgrade",
            provider_id="host-provider",
            operation="content_profile",
            model_id="configured-model",
            routing_decision_id="route-" + "c" * 20,
            model_task=ModelTask.CONTENT_PROFILE,
            base_model_tier=ModelTier.BALANCED,
            selected_model_tier=ModelTier.ECONOMY,
            started_at=FIXED_TIME,
            completed_at=FIXED_TIME,
        )


def test_provider_record_requires_reason_when_selected_tier_exceeds_base() -> None:
    with pytest.raises(ValidationError, match="tier escalation requires at least one reason"):
        ProviderRecord(
            provider_record_id="provider-record-unexplained",
            provider_id="host-provider",
            operation="content_profile",
            model_id="configured-model",
            routing_decision_id="route-" + "d" * 20,
            model_task=ModelTask.CONTENT_PROFILE,
            base_model_tier=ModelTier.BALANCED,
            selected_model_tier=ModelTier.FRONTIER,
            started_at=FIXED_TIME,
            completed_at=FIXED_TIME,
        )
