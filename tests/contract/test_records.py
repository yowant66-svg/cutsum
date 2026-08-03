from __future__ import annotations

from datetime import UTC, datetime

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
