from __future__ import annotations

import json
from enum import StrEnum
from typing import Any

from pydantic import BaseModel

from .domain.plans import CutPlan
from .domain.sources import MediaBinding
from .hashing import canonical_data


class SerializationProfile(StrEnum):
    RUNTIME = "local/runtime"
    PORTABLE = "portable/public"


def _portable(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _portable(item)
            for key, item in value.items()
            if key not in {"local_path", "font_path"}
        }
    if isinstance(value, list):
        return [_portable(item) for item in value]
    return value


def serialize_document(
    document: BaseModel,
    *,
    profile: SerializationProfile,
) -> str:
    data = canonical_data(document)
    if profile is SerializationProfile.PORTABLE:
        data = _portable(data)
    envelope = {"serialization_profile": profile.value, "document": data}
    return json.dumps(
        envelope,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def serialize_runtime_plan(plan: CutPlan, binding: MediaBinding) -> str:
    if binding.source_id != plan.source.source_id:
        raise ValueError("binding source_id must match CutPlan source_id")
    envelope = {
        "serialization_profile": SerializationProfile.RUNTIME.value,
        "document": canonical_data(plan),
        "binding": canonical_data(binding),
    }
    return json.dumps(
        envelope,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def load_portable_plan(serialized: str) -> CutPlan:
    envelope = json.loads(serialized)
    if envelope.get("serialization_profile") != SerializationProfile.PORTABLE.value:
        raise ValueError("expected portable/public serialization profile")
    return CutPlan.model_validate(envelope["document"])


def validate_serialized_identity(serialized: str) -> None:
    envelope = json.loads(serialized)
    document = envelope["document"]
    sources = [document.get("source", document)]
    for source in sources:
        if "source_id" not in source or "media_id" not in source or "sha256" not in source:
            raise ValueError("serialized source identity is incomplete")
