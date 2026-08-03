from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any

from pydantic import BaseModel

SEMANTIC_FINGERPRINT_VERSION = "1"
SEMANTIC_IDENTITY_FIELDS = frozenset(
    {
        "plan_id",
        "created_at",
        "created_by",
        "started_at",
        "completed_at",
        "document_sha256",
        "semantic_fingerprint",
    }
)


def canonical_data(document: BaseModel | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(document, BaseModel):
        return document.model_dump(mode="json", exclude_none=True)
    return dict(document)


def canonical_json_bytes(document: BaseModel | Mapping[str, Any]) -> bytes:
    return json.dumps(
        canonical_data(document),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def document_sha256(document: BaseModel | Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json_bytes(document)).hexdigest()


def _without_identity(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            key: _without_identity(item)
            for key, item in value.items()
            if key not in SEMANTIC_IDENTITY_FIELDS
        }
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_without_identity(item) for item in value]
    return value


def semantic_fingerprint(document: BaseModel | Mapping[str, Any]) -> str:
    semantic_document = {
        "fingerprint_version": SEMANTIC_FINGERPRINT_VERSION,
        "document": _without_identity(canonical_data(document)),
    }
    return hashlib.sha256(canonical_json_bytes(semantic_document)).hexdigest()
