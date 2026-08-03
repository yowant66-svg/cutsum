from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from universal_cutup.application.sdk import plan_sports_transcript
from universal_cutup.domain.intelligence import ControlMode
from universal_cutup.domain.sources import MediaSource, RightsAttestation
from universal_cutup.domain.sports import SportsEventType, SportsNarrativeCue
from universal_cutup.domain.transcript import TranscriptArtifact, TranscriptSegment
from universal_cutup.providers.sports_text import SportsTextProfile

FIXED_TIME = datetime(2026, 8, 1, tzinfo=UTC)


def _source() -> MediaSource:
    return MediaSource(
        source_id="source-game",
        media_id="media-game",
        kind="video",
        sha256="a" * 64,
        basename_hint="game.mp4",
        rights_attestation=RightsAttestation.OWNED,
        duration_ms=180_000,
    )


def _transcript() -> TranscriptArtifact:
    score_text = "BUZZER BEATER! The game winner drops as time expires!"
    block_text = "What a block at the rim!"
    return TranscriptArtifact(
        document_type="transcript",
        created_at=FIXED_TIME,
        created_by="test",
        transcript_id="transcript-game",
        source_id="source-game",
        language="en",
        segments=(
            TranscriptSegment(
                segment_id="segment-score",
                source_id="source-game",
                start_ms=30_000,
                end_ms=33_000,
                text=score_text,
                text_sha256=hashlib.sha256(score_text.encode()).hexdigest(),
            ),
            TranscriptSegment(
                segment_id="segment-block",
                source_id="source-game",
                start_ms=90_000,
                end_ms=92_000,
                text=block_text,
                text_sha256=hashlib.sha256(block_text.encode()).hexdigest(),
            ),
        ),
    )


def test_transcript_provider_reaches_directed_cut_plan_with_bounded_clips() -> None:
    result = plan_sports_transcript(
        _source(),
        _transcript(),
        profile=SportsTextProfile.BASKETBALL,
        control_mode=ControlMode.DIRECTED,
        raw_instruction="只要一个绝杀。",
        clock=lambda: FIXED_TIME,
    )

    assert result.observations.provider_kind == "local_detector"
    assert result.selection.selected_candidate_ids
    selected = next(
        candidate
        for candidate in result.candidates
        if candidate.candidate_id in result.selection.selected_candidate_ids
    )
    assert selected.sports_event is not None
    assert selected.sports_event.event_type is SportsEventType.SCORE
    assert selected.end_ms - selected.start_ms <= 60_000
    assert "text-only-event" in selected.tags
    assert result.plan.provider_records[0].provider_id == "sports-text-basketball"
    snapshot = selected.evidence_refs[0].snapshot
    assert snapshot is not None
    assert "buzzer beater! the game winner drops as time expires!" in snapshot


def test_directed_decisive_request_rejects_ordinary_score_and_selects_game_winner() -> None:
    ordinary_text = "He scores with an easy layup."
    decisive_text = "BUZZER BEATER! The game winner drops as time expires!"
    transcript = TranscriptArtifact(
        document_type="transcript",
        created_at=FIXED_TIME,
        created_by="test",
        transcript_id="transcript-game",
        source_id="source-game",
        language="en",
        segments=(
            TranscriptSegment(
                segment_id="segment-ordinary",
                source_id="source-game",
                start_ms=10_000,
                end_ms=12_000,
                text=ordinary_text,
                text_sha256=hashlib.sha256(ordinary_text.encode()).hexdigest(),
            ),
            TranscriptSegment(
                segment_id="segment-decisive",
                source_id="source-game",
                start_ms=100_000,
                end_ms=102_000,
                text=decisive_text,
                text_sha256=hashlib.sha256(decisive_text.encode()).hexdigest(),
            ),
        ),
    )

    result = plan_sports_transcript(
        _source(),
        transcript,
        profile=SportsTextProfile.BASKETBALL,
        control_mode=ControlMode.DIRECTED,
        raw_instruction="只要一个绝杀。",
        clock=lambda: FIXED_TIME,
    )

    assert result.request.required_narrative_cues == (SportsNarrativeCue.DECISIVE_SCORE,)
    assert result.selection.selected_candidate_ids == (
        next(
            candidate.candidate_id
            for candidate in result.candidates
            if candidate.start_ms == 95_000
        ),
    )
    ordinary = next(candidate for candidate in result.candidates if candidate.start_ms == 5_000)
    ordinary_qualification = next(
        item
        for item in result.selection.qualifications
        if item.candidate_id == ordinary.candidate_id
    )
    assert "missing_required_sports_narrative_cue" in ordinary_qualification.reasons
