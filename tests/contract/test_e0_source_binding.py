from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from universal_cutup.domain.sources import MediaBinding, MediaSource
from universal_cutup.serialization import (
    SerializationProfile,
    load_portable_plan,
    serialize_document,
    serialize_runtime_plan,
)

from .test_plans import make_plan


def test_media_source_is_portable_identity_only() -> None:
    assert "local_path" not in MediaSource.model_fields
    assert "uri" not in MediaSource.model_fields
    assert "credential_ref" not in MediaSource.model_fields


def test_media_binding_requires_exactly_one_runtime_location(tmp_path: Path) -> None:
    with pytest.raises(ValidationError):
        MediaBinding(source_id="source-1")
    with pytest.raises(ValidationError):
        MediaBinding(
            source_id="source-1",
            local_path=str(tmp_path / "input.mp4"),
            uri="file:///input.mp4",
        )


def test_media_binding_is_not_a_cut_plan_field() -> None:
    from universal_cutup.domain.plans import CutPlan

    assert "binding" not in CutPlan.model_fields


def test_portable_cut_plan_round_trips_without_runtime_binding(tmp_path: Path) -> None:
    plan = make_plan(
        plan_id="plan-portable",
        created_at=datetime(2026, 7, 30, 12, 0, tzinfo=UTC),
    )
    portable = serialize_document(plan, profile=SerializationProfile.PORTABLE)
    loaded = load_portable_plan(portable)
    assert loaded == plan
    assert str(tmp_path) not in portable
    runtime = serialize_runtime_plan(
        plan,
        MediaBinding(
            source_id=plan.source.source_id,
            local_path=str(tmp_path / "same-content.mp4"),
        ),
    )
    runtime_payload = json.loads(runtime)
    assert runtime_payload["binding"]["local_path"] == str(tmp_path / "same-content.mp4")
