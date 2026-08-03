from __future__ import annotations

import hashlib
from collections import defaultdict

from universal_cutup.domain.candidates import CutCandidate
from universal_cutup.domain.sports import (
    SportsCandidateProfile,
    SportsEvent,
    SportsEventType,
    SportsModality,
    SportsObservation,
    SportsObservationBundle,
    SportsObservationType,
    SportsQualification,
    SportsSelectionResult,
    SportsTaskRequest,
    SportsTemporalRole,
)


def _event_id(correlation_key: str) -> str:
    digest = hashlib.sha256(correlation_key.encode()).hexdigest()[:12]
    return f"sports-event-{digest}"


def _event_type(observations: tuple[SportsObservation, ...]) -> SportsEventType:
    hinted = tuple(
        observation for observation in observations if observation.event_type_hint is not None
    )
    if not hinted:
        return SportsEventType.UNKNOWN
    return max(hinted, key=lambda observation: observation.confidence).event_type_hint or (
        SportsEventType.UNKNOWN
    )


def aggregate_sports_events(
    bundle: SportsObservationBundle,
) -> tuple[SportsEvent, ...]:
    grouped: dict[str, list[SportsObservation]] = defaultdict(list)
    cluster_index = 0
    previous_end_ms: int | None = None
    for observation in sorted(bundle.observations, key=lambda item: item.start_ms):
        if observation.correlation_key is not None:
            key = observation.correlation_key
        else:
            if previous_end_ms is None or observation.start_ms - previous_end_ms > 2_000:
                cluster_index += 1
            key = f"temporal-cluster-{cluster_index}"
        grouped[key].append(observation)
        previous_end_ms = max(previous_end_ms or 0, observation.end_ms)

    primary_ids_by_key = {
        key: _event_id(key)
        for key, observations in grouped.items()
        if not all(item.temporal_role is SportsTemporalRole.REPLAY for item in observations)
    }
    events = []
    for key, observation_list in grouped.items():
        observations = tuple(observation_list)
        replay_targets = {
            observation.replay_of_correlation_key
            for observation in observations
            if observation.replay_of_correlation_key is not None
        }
        replay_of_event_id = None
        if replay_targets:
            replay_target = sorted(replay_targets)[0]
            replay_of_event_id = primary_ids_by_key.get(replay_target)
        events.append(
            SportsEvent(
                event_id=_event_id(key),
                source_id=bundle.source_id,
                event_type=_event_type(observations),
                start_ms=min(item.start_ms for item in observations),
                end_ms=max(item.end_ms for item in observations),
                observation_ids=tuple(item.observation_id for item in observations),
                temporal_roles=tuple(dict.fromkeys(item.temporal_role for item in observations)),
                modalities=tuple(dict.fromkeys(item.modality for item in observations)),
                observation_types=tuple(
                    dict.fromkeys(item.observation_type for item in observations)
                ),
                confidence=sum(item.confidence for item in observations) / len(observations),
                narrative_cues=tuple(
                    dict.fromkeys(
                        cue for observation in observations for cue in observation.narrative_cues
                    )
                ),
                replay_of_event_id=replay_of_event_id,
            )
        )
    return tuple(sorted(events, key=lambda event: event.start_ms))


def build_sports_profile(candidate: CutCandidate) -> SportsCandidateProfile:
    if candidate.sports_event is None:
        raise ValueError("sports profile requires candidate.sports_event")
    event = candidate.sports_event
    replay_only = set(event.temporal_roles) == {SportsTemporalRole.REPLAY}
    cross_modal_confirmations = len(set(event.modalities))
    strong_scoreboard_outcome = (
        SportsObservationType.SCOREBOARD_CHANGE in event.observation_types
        and SportsTemporalRole.OUTCOME in event.temporal_roles
    )
    strong_textual_outcome = (
        event.observation_types == (SportsObservationType.EVENT_CLASSIFICATION,)
        and event.temporal_roles == (SportsTemporalRole.OUTCOME,)
        and event.modalities == (SportsModality.TEXT,)
        and event.confidence >= 0.85
    )
    has_core_role = bool(
        set(event.temporal_roles) & {SportsTemporalRole.ACTION, SportsTemporalRole.OUTCOME}
    )
    primary_qualified = (
        event.event_type is not SportsEventType.UNKNOWN
        and has_core_role
        and (cross_modal_confirmations >= 2 or strong_scoreboard_outcome or strong_textual_outcome)
    )
    replay_qualified = replay_only and event.replay_of_event_id is not None
    qualified = replay_qualified or primary_qualified
    completeness_confidence = (
        min(1.0, 0.45 + (0.15 * cross_modal_confirmations)) if qualified else 0.35
    )
    return SportsCandidateProfile(
        candidate_id=candidate.candidate_id,
        event_id=event.event_id,
        qualified=qualified,
        event_type=event.event_type,
        temporal_roles=event.temporal_roles,
        modalities=event.modalities,
        observation_types=event.observation_types,
        cross_modal_confirmations=cross_modal_confirmations,
        replay_only=replay_only,
        completeness_confidence=completeness_confidence,
        narrative_cues=event.narrative_cues,
    )


def qualify_sports_candidate(
    candidate: CutCandidate,
    request: SportsTaskRequest,
) -> SportsQualification:
    profile = candidate.sports_profile or build_sports_profile(candidate)
    reasons = []
    if not profile.qualified:
        reasons.append("insufficient_multimodal_event_evidence")
    if request.required_event_types and profile.event_type not in request.required_event_types:
        reasons.append("missing_required_sports_event_type")
    if request.required_narrative_cues and not set(request.required_narrative_cues) <= set(
        profile.narrative_cues
    ):
        reasons.append("missing_required_sports_narrative_cue")
    if profile.event_type in request.forbidden_event_types:
        reasons.append("contains_forbidden_sports_event_type")
    if profile.replay_only and not request.include_replays:
        reasons.append("replay_excluded_by_default")
    return SportsQualification(
        candidate_id=candidate.candidate_id,
        qualified=not reasons,
        reasons=tuple(reasons),
    )


def select_sports_candidates(
    candidates: tuple[CutCandidate, ...],
    request: SportsTaskRequest,
) -> SportsSelectionResult:
    qualifications = tuple(qualify_sports_candidate(candidate, request) for candidate in candidates)
    qualified_ids = {
        qualification.candidate_id for qualification in qualifications if qualification.qualified
    }

    def rank(candidate: CutCandidate) -> tuple[float, int, float, int]:
        if candidate.sports_profile is None or candidate.sports_event is None:
            raise ValueError("sports selection requires event and profile")
        return (
            candidate.sports_profile.completeness_confidence,
            candidate.sports_profile.cross_modal_confirmations,
            candidate.sports_event.confidence,
            -candidate.start_ms,
        )

    ranked = sorted(
        (
            candidate
            for candidate in candidates
            if candidate.candidate_id in qualified_ids
            and candidate.sports_event is not None
            and candidate.sports_profile is not None
        ),
        key=rank,
        reverse=True,
    )
    target_count = request.target_count or min(3, len(ranked))
    selected_ids = tuple(candidate.candidate_id for candidate in ranked[:target_count])
    unsatisfied = (
        () if len(selected_ids) == target_count else (f"sports_required_count:{target_count}",)
    )
    return SportsSelectionResult(
        selected_candidate_ids=selected_ids,
        qualifications=qualifications,
        unsatisfied_requirements=unsatisfied,
    )
