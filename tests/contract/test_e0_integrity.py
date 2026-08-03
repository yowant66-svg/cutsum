from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from universal_cutup.domain.common import DocumentHeader
from universal_cutup.domain.errors import CutupError, ErrorCode

from .test_plans import make_plan

FIXED_TIME = datetime(2026, 7, 30, 12, 0, tzinfo=UTC)


def test_duplicate_required_extensions_fail() -> None:
    with pytest.raises(ValidationError):
        DocumentHeader(
            document_type="test",
            created_at=FIXED_TIME,
            created_by="test-suite",
            extensions={"org.universal-cutup.core": {"version": "1"}},
            required_extensions=(
                "org.universal-cutup.core",
                "org.universal-cutup.core",
            ),
        )


def test_unsupported_schema_version_has_stable_error() -> None:
    with pytest.raises(CutupError) as caught:
        DocumentHeader(
            schema_version="9.0.0",
            document_type="test",
            created_at=FIXED_TIME,
            created_by="test-suite",
        )
    assert caught.value.code is ErrorCode.PROTOCOL_VERSION_UNSUPPORTED


def test_duplicate_candidate_ids_fail() -> None:
    plan = make_plan(plan_id="plan-1", created_at=FIXED_TIME)
    payload = plan.model_dump()
    payload["candidates"] = (plan.candidates[0],) * 2
    with pytest.raises(ValidationError):
        type(plan).model_validate(payload)


def test_broken_selection_reference_fails() -> None:
    plan = make_plan(plan_id="plan-1", created_at=FIXED_TIME)
    broken_decision = plan.selection_result.decisions[0].model_copy(
        update={"candidate_id": "missing-candidate"}
    )
    payload = plan.model_dump()
    payload["selection_result"] = plan.selection_result.model_copy(
        update={"decisions": (broken_decision,)}
    )
    with pytest.raises(ValidationError):
        type(plan).model_validate(payload)
