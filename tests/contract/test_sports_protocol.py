from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from universal_cutup.domain.candidates import CutCandidate, EvidenceRef
from universal_cutup.domain.sports import (
    SportsCandidateProfile,
    SportsEvent,
    SportsEventType,
    SportsModality,
    SportsObservation,
    SportsObservationBundle,
    SportsObservationType,
    SportsTemporalRole,
)
from universal_cutup.providers.sports import FileSportsObservationProvider

FIXED_TIME = datetime(2026, 7, 31, tzinfo=UTC)


def _observation(
    observation_id: str,
    observation_type: SportsObservationType,
    modality: SportsModality,
    *,
    role: SportsTemporalRole,
    start_ms: int = 10_000,
    end_ms: int = 11_000,
    correlation_key: str | None = "event-score-1",
    replay_of_correlation_key: str | None = None,
) -> SportsObservation:
    return SportsObservation(
        observation_id=observation_id,
        source_id="source-sport",
        observation_type=observation_type,
        modality=modality,
        temporal_role=role,
        start_ms=start_ms,
        end_ms=end_ms,
        confidence=0.9,
        label=observation_type.value,
        event_type_hint=SportsEventType.SCORE,
        correlation_key=correlation_key,
        replay_of_correlation_key=replay_of_correlation_key,
        provider_record_ref="provider-sport-fixture",
    )


def test_observation_bundle_preserves_cross_modal_provenance() -> None:
    bundle = SportsObservationBundle(
        document_type="sports_observation_bundle",
        created_at=FIXED_TIME,
        created_by="test",
        bundle_id="bundle-1",
        source_id="source-sport",
        provider_kind="fixture",
        provider_record_refs=("provider-sport-fixture",),
        observations=(
            _observation(
                "audio-1",
                SportsObservationType.AUDIO_PEAK,
                SportsModality.AUDIO,
                role=SportsTemporalRole.REACTION,
            ),
            _observation(
                "scoreboard-1",
                SportsObservationType.SCOREBOARD_CHANGE,
                SportsModality.OCR,
                role=SportsTemporalRole.OUTCOME,
            ),
        ),
    )

    assert {item.modality for item in bundle.observations} == {
        SportsModality.AUDIO,
        SportsModality.OCR,
    }


def test_bundle_rejects_unknown_provider_record() -> None:
    with pytest.raises(ValidationError, match="unknown provider record"):
        SportsObservationBundle(
            document_type="sports_observation_bundle",
            created_at=FIXED_TIME,
            created_by="test",
            bundle_id="bundle-1",
            source_id="source-sport",
            provider_kind="fixture",
            provider_record_refs=("different-provider",),
            observations=(
                _observation(
                    "audio-1",
                    SportsObservationType.AUDIO_PEAK,
                    SportsModality.AUDIO,
                    role=SportsTemporalRole.REACTION,
                ),
            ),
        )


def test_replay_observation_requires_primary_event_correlation() -> None:
    with pytest.raises(ValidationError, match="replay observation requires"):
        _observation(
            "replay-1",
            SportsObservationType.REPLAY_START,
            SportsModality.VIDEO,
            role=SportsTemporalRole.REPLAY,
            correlation_key="replay-score-1",
        )


def test_bundle_rejects_replay_target_that_is_not_present() -> None:
    with pytest.raises(ValidationError, match="unknown primary correlation"):
        SportsObservationBundle(
            document_type="sports_observation_bundle",
            created_at=FIXED_TIME,
            created_by="test",
            bundle_id="bundle-1",
            source_id="source-sport",
            provider_kind="fixture",
            provider_record_refs=("provider-sport-fixture",),
            observations=(
                _observation(
                    "replay-1",
                    SportsObservationType.REPLAY_START,
                    SportsModality.VIDEO,
                    role=SportsTemporalRole.REPLAY,
                    correlation_key="replay-score-1",
                    replay_of_correlation_key="missing-primary",
                ),
            ),
        )


def test_candidate_validates_sports_event_and_profile_identity() -> None:
    event = SportsEvent(
        event_id="event-score-1",
        source_id="source-sport",
        event_type=SportsEventType.SCORE,
        start_ms=10_000,
        end_ms=14_000,
        observation_ids=("audio-1", "scoreboard-1"),
        temporal_roles=(SportsTemporalRole.ACTION, SportsTemporalRole.OUTCOME),
        modalities=(SportsModality.AUDIO, SportsModality.OCR),
        observation_types=(
            SportsObservationType.AUDIO_PEAK,
            SportsObservationType.SCOREBOARD_CHANGE,
        ),
        confidence=0.9,
    )
    profile = SportsCandidateProfile(
        candidate_id="candidate-score-1",
        event_id=event.event_id,
        qualified=True,
        event_type=event.event_type,
        temporal_roles=event.temporal_roles,
        modalities=event.modalities,
        observation_types=event.observation_types,
        cross_modal_confirmations=2,
        replay_only=False,
        completeness_confidence=0.9,
    )
    evidence = EvidenceRef(
        evidence_id="evidence-score-1",
        artifact_id="bundle-1",
        segment_ids=event.observation_ids,
        start_ms=10_000,
        end_ms=14_000,
        text_sha256="a" * 64,
    )

    candidate = CutCandidate(
        candidate_id="candidate-score-1",
        source_id="source-sport",
        start_ms=5_000,
        end_ms=19_000,
        summary="Synthetic score event",
        evidence_refs=(evidence,),
        sports_event=event,
        sports_profile=profile,
    )

    assert candidate.sports_event == event
    assert candidate.sports_profile == profile


def test_file_sports_provider_labels_fixture_and_validates_kind(tmp_path: Path) -> None:
    payload = SportsObservationBundle(
        document_type="sports_observation_bundle",
        created_at=FIXED_TIME,
        created_by="test",
        bundle_id="bundle-1",
        source_id="source-sport",
        provider_kind="fixture",
        provider_record_refs=("provider-sport-fixture",),
        observations=(
            _observation(
                "audio-1",
                SportsObservationType.AUDIO_PEAK,
                SportsModality.AUDIO,
                role=SportsTemporalRole.REACTION,
            ),
        ),
    )
    bundle_path = tmp_path / "sports-observations.json"
    bundle_path.write_text(json.dumps(payload.model_dump(mode="json")))
    provider = FileSportsObservationProvider(
        provider_kind="fixture",
        clock=lambda: FIXED_TIME,
    )

    imported = provider.import_observations(bundle_path)

    assert imported.artifact == payload
    assert imported.provider_record.provider_record_id == "provider-sport-fixture"
    assert imported.provider_record.warnings == (
        "fixture sports observations; not real detector output",
    )
