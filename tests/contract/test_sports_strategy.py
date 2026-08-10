from __future__ import annotations

from datetime import UTC, datetime
from typing import cast

import pytest

from universal_cutup.application.sports import (
    create_sports_plan,
    propose_sports_candidates,
    resolve_sports_request,
    select_sports_for_request,
)
from universal_cutup.domain.errors import CutupError, ErrorCode
from universal_cutup.domain.intelligence import ControlMode
from universal_cutup.domain.records import ProviderRecord
from universal_cutup.domain.sources import MediaSource, RightsAttestation
from universal_cutup.domain.sports import (
    SportsEvent,
    SportsEventType,
    SportsModality,
    SportsNarrativeCue,
    SportsObservation,
    SportsObservationBundle,
    SportsObservationType,
    SportsTemporalRole,
)
from universal_cutup.strategies.sports import aggregate_sports_events

FIXED_TIME = datetime(2026, 7, 31, tzinfo=UTC)


def _observation(
    observation_id: str,
    observation_type: SportsObservationType,
    modality: SportsModality,
    role: SportsTemporalRole,
    start_ms: int,
    end_ms: int,
    *,
    correlation_key: str,
    event_type: SportsEventType | None,
    replay_of: str | None = None,
    confidence: float = 0.9,
) -> SportsObservation:
    return SportsObservation(
        observation_id=observation_id,
        source_id="source-sports",
        observation_type=observation_type,
        modality=modality,
        temporal_role=role,
        start_ms=start_ms,
        end_ms=end_ms,
        confidence=confidence,
        label=observation_id,
        event_type_hint=event_type,
        correlation_key=correlation_key,
        replay_of_correlation_key=replay_of,
        provider_record_ref="provider-sports",
    )


def _bundle() -> SportsObservationBundle:
    return SportsObservationBundle(
        document_type="sports_observation_bundle",
        created_at=FIXED_TIME,
        created_by="test",
        bundle_id="bundle-sports",
        source_id="source-sports",
        provider_kind="fixture",
        provider_record_refs=("provider-sports",),
        observations=(
            _observation(
                "score-motion",
                SportsObservationType.MOTION_BURST,
                SportsModality.VIDEO,
                SportsTemporalRole.ACTION,
                10_000,
                12_000,
                correlation_key="score-1",
                event_type=SportsEventType.SCORE,
            ),
            _observation(
                "score-board",
                SportsObservationType.SCOREBOARD_CHANGE,
                SportsModality.OCR,
                SportsTemporalRole.OUTCOME,
                12_000,
                13_000,
                correlation_key="score-1",
                event_type=SportsEventType.SCORE,
            ),
            _observation(
                "score-crowd",
                SportsObservationType.AUDIO_PEAK,
                SportsModality.AUDIO,
                SportsTemporalRole.REACTION,
                12_500,
                14_000,
                correlation_key="score-1",
                event_type=SportsEventType.SCORE,
            ),
            _observation(
                "noise-only",
                SportsObservationType.AUDIO_PEAK,
                SportsModality.AUDIO,
                SportsTemporalRole.REACTION,
                20_000,
                21_000,
                correlation_key="noise-1",
                event_type=None,
            ),
            _observation(
                "save-motion",
                SportsObservationType.MOTION_BURST,
                SportsModality.VIDEO,
                SportsTemporalRole.ACTION,
                30_000,
                32_000,
                correlation_key="save-1",
                event_type=SportsEventType.SAVE,
            ),
            _observation(
                "save-commentary",
                SportsObservationType.COMMENTATOR_EMPHASIS,
                SportsModality.TEXT,
                SportsTemporalRole.OUTCOME,
                31_000,
                33_000,
                correlation_key="save-1",
                event_type=SportsEventType.SAVE,
            ),
            _observation(
                "replay-start",
                SportsObservationType.REPLAY_START,
                SportsModality.VIDEO,
                SportsTemporalRole.REPLAY,
                40_000,
                41_000,
                correlation_key="replay-score-1",
                event_type=SportsEventType.SCORE,
                replay_of="score-1",
            ),
            _observation(
                "replay-end",
                SportsObservationType.REPLAY_END,
                SportsModality.VIDEO,
                SportsTemporalRole.REPLAY,
                46_000,
                47_000,
                correlation_key="replay-score-1",
                event_type=SportsEventType.SCORE,
                replay_of="score-1",
            ),
        ),
    )


def test_event_aggregation_links_replay_and_keeps_noise_separate() -> None:
    events = aggregate_sports_events(_bundle())

    assert len(events) == 4
    primary_score = next(
        event
        for event in events
        if event.event_type is SportsEventType.SCORE and event.replay_of_event_id is None
    )
    replay = next(event for event in events if event.replay_of_event_id is not None)
    noise = next(event for event in events if event.event_type is SportsEventType.UNKNOWN)
    assert replay.replay_of_event_id == primary_score.event_id
    assert noise.modalities == (SportsModality.AUDIO,)


def test_auto_requires_multimodal_confirmation_and_deduplicates_replay() -> None:
    candidates = propose_sports_candidates(_bundle(), media_duration_ms=60_000)
    request = resolve_sports_request(ControlMode.AUTO, "")

    result = select_sports_for_request(candidates, request)
    selected = {
        candidate.candidate_id: candidate
        for candidate in candidates
        if candidate.candidate_id in result.selected_candidate_ids
    }

    assert {
        cast(SportsEvent, candidate.sports_event).event_type for candidate in selected.values()
    } == {
        SportsEventType.SCORE,
        SportsEventType.SAVE,
    }
    assert all(
        candidate.sports_profile is not None and not candidate.sports_profile.replay_only
        for candidate in selected.values()
    )


def test_directed_natural_language_selects_one_save_without_replay() -> None:
    candidates = propose_sports_candidates(_bundle(), media_duration_ms=60_000)
    request = resolve_sports_request(
        ControlMode.DIRECTED,
        "只要一个扑救，不要回放。",  # noqa: RUF001
    )

    result = select_sports_for_request(candidates, request)
    selected = next(
        candidate
        for candidate in candidates
        if candidate.candidate_id in result.selected_candidate_ids
    )

    assert request.required_event_types == (SportsEventType.SAVE,)
    assert request.target_count == 1
    assert not request.include_replays
    assert selected.sports_event is not None
    assert selected.sports_event.event_type is SportsEventType.SAVE


def test_directed_word_count_is_not_reused_as_a_sports_event() -> None:
    request = resolve_sports_request(ControlMode.DIRECTED, "Give me six saves")

    assert request.required_event_types == (SportsEventType.SAVE,)
    assert request.target_count == 6

    result = select_sports_for_request(
        propose_sports_candidates(_bundle(), media_duration_ms=60_000),
        request,
    )
    assert len(result.selected_candidate_ids) == 1
    assert result.unsatisfied_requirements == ("sports_required_count:6",)


def test_directed_multi_digit_count_is_parsed_as_a_whole_number() -> None:
    request = resolve_sports_request(ControlMode.DIRECTED, "Top 10 saves")

    assert request.required_event_types == (SportsEventType.SAVE,)
    assert request.target_count == 10


def test_directed_compound_chinese_count_is_parsed_as_a_whole_number() -> None:
    request = resolve_sports_request(ControlMode.DIRECTED, "只要十一个进球。")

    assert request.required_event_types == (SportsEventType.SCORE,)
    assert request.target_count == 11


def test_directed_mixed_score_subtype_requirements_fail_closed() -> None:
    with pytest.raises(CutupError) as raised:
        resolve_sports_request(
            ControlMode.DIRECTED,
            "goals but exclude three-pointers",
        )

    assert raised.value.code is ErrorCode.HOST_INTENT_CONFLICT
    assert raised.value.details["event_type"] == SportsEventType.SCORE.value


def test_directed_score_subtype_exclusion_fails_closed_without_overblocking() -> None:
    with pytest.raises(CutupError) as raised:
        resolve_sports_request(
            ControlMode.DIRECTED,
            "exclude three-pointers",
        )

    assert raised.value.code is ErrorCode.HOST_INTENT_CONFLICT
    assert raised.value.details["forbidden_markers"] == ("three-pointer",)


def test_existing_chinese_two_count_remains_supported() -> None:
    request = resolve_sports_request(ControlMode.DIRECTED, "只要两个扑救。")

    assert request.required_event_types == (SportsEventType.SAVE,)
    assert request.target_count == 2


def test_cricket_six_remains_a_score_event_when_not_used_as_a_count() -> None:
    request = resolve_sports_request(ControlMode.DIRECTED, "Show me the six")

    assert request.required_event_types == (SportsEventType.SCORE,)
    assert request.target_count is None


def test_sports_plan_is_portable_and_carries_provider_provenance() -> None:
    bundle = _bundle()
    source = MediaSource(
        source_id=bundle.source_id,
        media_id="media-sports",
        kind="video",
        sha256="a" * 64,
        basename_hint="sports.mp4",
        rights_attestation=RightsAttestation.OWNED,
        duration_ms=60_000,
    )
    provider_record = ProviderRecord(
        provider_record_id="provider-sports",
        provider_id="sports-fixture-provider",
        operation="observe_sports_events",
        started_at=FIXED_TIME,
        completed_at=FIXED_TIME,
    )
    request = resolve_sports_request(ControlMode.AUTO, "")

    plan = create_sports_plan(
        source,
        bundle,
        request,
        provider_records=(provider_record,),
    )

    assert plan.provider_records == (provider_record,)
    assert plan.selection_result.selected_candidate_ids
    assert {decision.candidate_id for decision in plan.selection_result.decisions} == {
        candidate.candidate_id for candidate in plan.candidates
    }
    assert len(plan.strategy_records) == 1
    assert plan.selection_result.strategy_record_ref == plan.strategy_records[0].strategy_record_id


def test_sports_plan_represents_an_empty_detector_result_without_crashing() -> None:
    bundle = _bundle().model_copy(update={"observations": ()})
    source = MediaSource(
        source_id=bundle.source_id,
        media_id="media-sports-empty",
        kind="video",
        sha256="a" * 64,
        basename_hint="sports-empty.mp4",
        rights_attestation=RightsAttestation.OWNED,
        duration_ms=60_000,
    )
    provider_record = ProviderRecord(
        provider_record_id="provider-sports",
        provider_id="sports-fixture-provider",
        operation="observe_sports_events",
        started_at=FIXED_TIME,
        completed_at=FIXED_TIME,
    )

    plan = create_sports_plan(
        source,
        bundle,
        resolve_sports_request(ControlMode.AUTO, ""),
        provider_records=(provider_record,),
    )

    assert plan.evidence_artifacts == ()
    assert plan.candidates == ()
    assert plan.selection_result.decisions == ()
    assert plan.selection_result.warnings == ("sports_no_qualified_candidate",)


def test_plan_preserves_candidate_qualification_reasons() -> None:
    bundle = _bundle()
    source = MediaSource(
        source_id=bundle.source_id,
        media_id="media-sports",
        kind="video",
        sha256="a" * 64,
        basename_hint="sports.mp4",
        rights_attestation=RightsAttestation.OWNED,
        duration_ms=60_000,
    )
    provider_record = ProviderRecord(
        provider_record_id="provider-sports",
        provider_id="sports-fixture-provider",
        operation="observe_sports_events",
        started_at=FIXED_TIME,
        completed_at=FIXED_TIME,
    )

    plan = create_sports_plan(
        source,
        bundle,
        resolve_sports_request(ControlMode.DIRECTED, "只要一个扑救。"),
        provider_records=(provider_record,),
    )

    score_candidate_ids = {
        candidate.candidate_id
        for candidate in plan.candidates
        if candidate.sports_event is not None
        and candidate.sports_event.event_type is SportsEventType.SCORE
    }
    rejected_score = next(
        decision
        for decision in plan.selection_result.decisions
        if decision.status.value == "rejected" and decision.candidate_id in score_candidate_ids
    )
    assert rejected_score.reason == "missing_required_sports_event_type"


def test_auto_keeps_evidence_strength_ahead_of_unrequested_narrative_cues() -> None:
    candidates = propose_sports_candidates(_bundle(), media_duration_ms=60_000)
    score = next(
        candidate
        for candidate in candidates
        if candidate.sports_event is not None
        and candidate.sports_event.event_type is SportsEventType.SCORE
        and candidate.sports_event.replay_of_event_id is None
    )
    assert score.sports_profile is not None
    decisive_text_only = score.model_copy(
        update={
            "candidate_id": "candidate-text-decisive",
            "sports_profile": score.sports_profile.model_copy(
                update={
                    "candidate_id": "candidate-text-decisive",
                    "cross_modal_confirmations": 1,
                    "completeness_confidence": 0.6,
                    "narrative_cues": (SportsNarrativeCue.DECISIVE_SCORE,),
                }
            ),
        }
    )

    result = select_sports_for_request(
        (score, decisive_text_only),
        resolve_sports_request(ControlMode.AUTO, "一个得分"),
    )

    assert result.selected_candidate_ids[0] == score.candidate_id
