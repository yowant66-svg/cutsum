from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from universal_cutup.domain.sources import MediaBinding, MediaSource, RightsAttestation
from universal_cutup.domain.transcript import TranscriptArtifact, TranscriptSegment
from universal_cutup.serialization import (
    SerializationProfile,
    serialize_document,
    validate_serialized_identity,
)

FIXED_TIME = datetime(2026, 7, 30, 12, 0, tzinfo=UTC)
SOURCE_HASH = "a" * 64
TEXT_HASH = "b" * 64


def test_media_binding_requires_local_path_or_uri_but_not_both() -> None:
    with pytest.raises(ValidationError):
        MediaBinding(source_id="source-1")


def test_transcript_segments_are_monotonic_and_hash_addressed() -> None:
    first = TranscriptSegment(
        segment_id="segment-1",
        source_id="source-1",
        start_ms=1000,
        end_ms=2000,
        text="Hello",
        text_sha256=TEXT_HASH,
    )
    second = first.model_copy(update={"segment_id": "segment-2", "start_ms": 500, "end_ms": 1500})
    with pytest.raises(ValidationError):
        TranscriptArtifact(
            document_type="transcript",
            created_at=FIXED_TIME,
            created_by="test-suite",
            transcript_id="transcript-1",
            source_id="source-1",
            segments=(first, second),
        )


def test_portable_source_keeps_identity_without_private_path() -> None:
    source = MediaSource(
        source_id="source-1",
        media_id="media-1",
        kind="video",
        sha256=SOURCE_HASH,
        basename_hint="input.mp4",
        rights_attestation=RightsAttestation.OWNED,
    )
    binding = MediaBinding(
        source_id=source.source_id,
        local_path="/private-home/alice/Videos/input.mp4",
    )
    portable = serialize_document(source, profile=SerializationProfile.PORTABLE)
    runtime = serialize_document(binding, profile=SerializationProfile.RUNTIME)
    assert "private-home" not in portable
    assert "source-1" in portable and SOURCE_HASH in portable
    assert "/private-home/alice/Videos/input.mp4" in runtime
    validate_serialized_identity(portable)
