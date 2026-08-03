from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from universal_cutup.domain.common import DocumentHeader, TimeRange
from universal_cutup.domain.errors import CutupError, ErrorCode

FIXED_TIME = datetime(2026, 7, 30, 12, 0, tzinfo=UTC)


def test_document_header_requires_utc_created_at() -> None:
    with pytest.raises(ValidationError):
        DocumentHeader(
            document_type="test",
            created_at=datetime(2026, 7, 30, 12, 0),
            created_by="test-suite",
        )


def test_time_range_rejects_end_not_after_start() -> None:
    with pytest.raises(ValidationError):
        TimeRange(start_ms=1000, end_ms=1000)


def test_unknown_optional_extension_round_trips() -> None:
    header = DocumentHeader(
        document_type="test",
        created_at=FIXED_TIME,
        created_by="test-suite",
        extensions={"example.optional": {"value": 1}},
    )
    loaded = DocumentHeader.model_validate_json(header.model_dump_json())
    assert loaded.extensions == {"example.optional": {"value": 1}}


def test_required_extensions_must_be_extension_keys() -> None:
    with pytest.raises(ValidationError):
        DocumentHeader(
            document_type="test",
            created_at=FIXED_TIME,
            created_by="test-suite",
            extensions={},
            required_extensions=("example.missing",),
        )


def test_unknown_required_extension_has_stable_error() -> None:
    with pytest.raises(CutupError) as caught:
        DocumentHeader(
            document_type="test",
            created_at=FIXED_TIME,
            created_by="test-suite",
            extensions={"example.required": {"version": "1"}},
            required_extensions=("example.required",),
        )
    assert caught.value.code is ErrorCode.PROTOCOL_UNSUPPORTED_EXTENSION
