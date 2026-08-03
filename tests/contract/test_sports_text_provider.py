from __future__ import annotations

import hashlib
from datetime import UTC, datetime

import pytest

from universal_cutup.domain.sports import (
    SportsEventType,
    SportsObservationType,
)
from universal_cutup.domain.transcript import TranscriptArtifact, TranscriptSegment
from universal_cutup.providers.sports_text import (
    LocalSportsTextProvider,
    SportsTextProfile,
)

FIXED_TIME = datetime(2026, 8, 1, tzinfo=UTC)


def _transcript(*segments: tuple[int, int, str]) -> TranscriptArtifact:
    return TranscriptArtifact(
        document_type="transcript",
        created_at=FIXED_TIME,
        created_by="test",
        transcript_id="transcript-sports-text",
        source_id="source-sports-text",
        language="en",
        segments=tuple(
            TranscriptSegment(
                segment_id=f"segment-{index}",
                source_id="source-sports-text",
                start_ms=start_ms,
                end_ms=end_ms,
                text=text,
                text_sha256=hashlib.sha256(text.encode()).hexdigest(),
            )
            for index, (start_ms, end_ms, text) in enumerate(segments, start=1)
        ),
    )


def test_detector_emits_local_provider_provenance_without_merging_continuous_captions() -> None:
    transcript = _transcript(
        (0, 1_000, "The teams exchange possession."),
        (1_050, 2_000, "GOAL! A brilliant finish makes it two one."),
        (2_050, 3_000, "The crowd is still celebrating."),
        (3_050, 4_000, "What a save by the goalkeeper!"),
    )

    detected = LocalSportsTextProvider(
        profile=SportsTextProfile.FOOTBALL,
        clock=lambda: FIXED_TIME,
    ).detect(transcript)

    assert detected.artifact.provider_kind == "local_detector"
    assert detected.provider_record.operation == "detect_sports_from_transcript"
    assert {item.event_type_hint for item in detected.artifact.observations} == {
        SportsEventType.SCORE,
        SportsEventType.SAVE,
    }
    assert max(item.end_ms - item.start_ms for item in detected.artifact.observations) <= 1_000


def test_detector_filters_hypothetical_and_replay_mentions() -> None:
    transcript = _transcript(
        (0, 1_000, "If they score here they could win the match."),
        (2_000, 3_000, "Replay of the earlier goal from the first half."),
    )

    detected = LocalSportsTextProvider(
        profile=SportsTextProfile.FOOTBALL,
        clock=lambda: FIXED_TIME,
    ).detect(transcript)

    assert detected.artifact.observations == ()


def test_detector_turns_disallowed_score_into_controversy() -> None:
    transcript = _transcript((0, 1_000, "No goal! VAR has ruled it out for offside."))

    detected = LocalSportsTextProvider(
        profile=SportsTextProfile.FOOTBALL,
        clock=lambda: FIXED_TIME,
    ).detect(transcript)

    assert {item.event_type_hint for item in detected.artifact.observations} == {
        SportsEventType.CONTROVERSY
    }


def test_american_football_and_rugby_profiles_do_not_share_touchdown() -> None:
    transcript = _transcript((0, 1_000, "Touchdown! The receiver scores in the end zone."))

    american = LocalSportsTextProvider(
        profile=SportsTextProfile.AMERICAN_FOOTBALL,
        clock=lambda: FIXED_TIME,
    ).detect(transcript)
    rugby = LocalSportsTextProvider(
        profile=SportsTextProfile.RUGBY,
        clock=lambda: FIXED_TIME,
    ).detect(transcript)

    assert any(
        item.observation_type is SportsObservationType.EVENT_CLASSIFICATION
        for item in american.artifact.observations
    )
    assert rugby.artifact.observations == ()


@pytest.mark.parametrize(
    ("profile", "text"),
    (
        (SportsTextProfile.RUGBY, "They try to move the ball forward."),
        (SportsTextProfile.CRICKET, "Six overs remain in the innings."),
        (SportsTextProfile.FOOTBALL, "The score is still one nil."),
    ),
)
def test_detector_rejects_ambiguous_sports_nouns_and_verbs(
    profile: SportsTextProfile,
    text: str,
) -> None:
    detected = LocalSportsTextProvider(profile=profile, clock=lambda: FIXED_TIME).detect(
        _transcript((0, 1_000, text))
    )

    assert detected.artifact.observations == ()


def test_detector_carries_open_hypothetical_context_across_adjacent_cues() -> None:
    detected = LocalSportsTextProvider(
        profile=SportsTextProfile.FOOTBALL,
        clock=lambda: FIXED_TIME,
    ).detect(
        _transcript(
            (0, 1_000, "If they can do it here,"),
            (1_050, 2_000, "Goal! They win the match."),
        )
    )

    assert detected.artifact.observations == ()


@pytest.mark.parametrize(
    ("lead_in", "result"),
    (
        ("This could be the moment,", "GOAL! The striker scores."),
        ("If you look at the movement,", "GOAL! A brilliant finish."),
        ("They might have one final chance,", "GOAL!"),
    ),
)
def test_detector_keeps_explicit_result_after_broad_open_context(
    lead_in: str,
    result: str,
) -> None:
    detected = LocalSportsTextProvider(
        profile=SportsTextProfile.FOOTBALL,
        clock=lambda: FIXED_TIME,
    ).detect(
        _transcript(
            (0, 1_000, lead_in),
            (1_050, 2_000, result),
        )
    )

    assert tuple(item.event_type_hint for item in detected.artifact.observations) == (
        SportsEventType.SCORE,
    )


@pytest.mark.parametrize(
    ("lead_in", "result_reference"),
    (
        ("This could be the moment,", "for the winning goal."),
        ("They might have one final chance,", "to score."),
        ("If they create an opening,", "a chance for the equalizer."),
    ),
)
def test_detector_inherits_broad_context_for_non_asserted_results(
    lead_in: str,
    result_reference: str,
) -> None:
    detected = LocalSportsTextProvider(
        profile=SportsTextProfile.FOOTBALL,
        clock=lambda: FIXED_TIME,
    ).detect(
        _transcript(
            (0, 1_000, lead_in),
            (1_050, 2_000, result_reference),
        )
    )

    assert detected.artifact.observations == ()


def test_detector_emits_multiple_distinct_events_from_one_caption() -> None:
    detected = LocalSportsTextProvider(
        profile=SportsTextProfile.FOOTBALL,
        clock=lambda: FIXED_TIME,
    ).detect(_transcript((0, 1_000, "Goal! VAR checks a red card after the celebration.")))

    assert {item.event_type_hint for item in detected.artifact.observations} == {
        SportsEventType.SCORE,
        SportsEventType.CONTROVERSY,
    }


def test_detector_collapses_adjacent_rolling_caption_restatements() -> None:
    detected = LocalSportsTextProvider(
        profile=SportsTextProfile.FOOTBALL,
        clock=lambda: FIXED_TIME,
    ).detect(
        _transcript(
            (0, 1_000, "Goal! Smith scores for the home side."),
            (1_050, 2_000, "Smith scores for the home side!"),
        )
    )

    assert len(detected.artifact.observations) == 1


@pytest.mark.parametrize(
    ("profile", "text"),
    (
        (SportsTextProfile.RUGBY, "What a try! It is awarded after review."),
        (SportsTextProfile.CRICKET, "He launches it for six!"),
        (SportsTextProfile.FOOTBALL, "GOAL! The home side takes the lead."),
    ),
)
def test_detector_keeps_unambiguous_scoring_language(
    profile: SportsTextProfile,
    text: str,
) -> None:
    detected = LocalSportsTextProvider(profile=profile, clock=lambda: FIXED_TIME).detect(
        _transcript((0, 1_000, text))
    )

    assert tuple(item.event_type_hint for item in detected.artifact.observations) == (
        SportsEventType.SCORE,
    )


def test_detector_replaces_adjacent_score_with_cross_cue_cancellation() -> None:
    detected = LocalSportsTextProvider(
        profile=SportsTextProfile.FOOTBALL,
        clock=lambda: FIXED_TIME,
    ).detect(
        _transcript(
            (0, 1_000, "Goal! The striker celebrates."),
            (1_050, 2_000, "No goal, it was disallowed for offside."),
        )
    )

    assert tuple(item.event_type_hint for item in detected.artifact.observations) == (
        SportsEventType.CONTROVERSY,
    )


def test_detector_filters_replay_context_split_across_cues() -> None:
    detected = LocalSportsTextProvider(
        profile=SportsTextProfile.FOOTBALL,
        clock=lambda: FIXED_TIME,
    ).detect(
        _transcript(
            (0, 1_000, "Replay of the earlier"),
            (1_050, 2_000, "goal from the first half."),
        )
    )

    assert detected.artifact.observations == ()


def test_detector_does_not_carry_a_closed_hypothetical_sentence() -> None:
    detected = LocalSportsTextProvider(
        profile=SportsTextProfile.FOOTBALL,
        clock=lambda: FIXED_TIME,
    ).detect(
        _transcript(
            (0, 1_000, "If they score, they win the match."),
            (1_050, 2_000, "GOAL! The striker has done it."),
        )
    )

    assert tuple(item.event_type_hint for item in detected.artifact.observations) == (
        SportsEventType.SCORE,
    )


def test_overturned_red_card_does_not_cancel_an_adjacent_goal() -> None:
    detected = LocalSportsTextProvider(
        profile=SportsTextProfile.FOOTBALL,
        clock=lambda: FIXED_TIME,
    ).detect(
        _transcript(
            (0, 1_000, "GOAL! The home side takes the lead."),
            (1_050, 2_000, "The red card was overturned after VAR."),
        )
    )

    assert {item.event_type_hint for item in detected.artifact.observations} == {
        SportsEventType.SCORE,
        SportsEventType.CONTROVERSY,
    }
