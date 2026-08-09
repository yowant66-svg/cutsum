from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime

from universal_cutup import __version__
from universal_cutup.domain.candidates import (
    CutCandidate,
    EvidenceArtifactIdentity,
    EvidenceRef,
)
from universal_cutup.domain.intelligence import ControlMode
from universal_cutup.domain.plans import CutPlan
from universal_cutup.domain.records import ProviderRecord, StrategyRecord, StrategyRole
from universal_cutup.domain.selection import (
    SelectionDecision,
    SelectionResult,
    SelectionStatus,
)
from universal_cutup.domain.sources import MediaSource
from universal_cutup.domain.specs import OutputSpec
from universal_cutup.domain.sports import (
    SportsEventType,
    SportsModality,
    SportsNarrativeCue,
    SportsObservationBundle,
    SportsSelectionResult,
    SportsTaskRequest,
)
from universal_cutup.hashing import document_sha256
from universal_cutup.strategies.sports import (
    aggregate_sports_events,
    build_sports_profile,
    select_sports_candidates,
)

EVENT_MARKERS: dict[SportsEventType, tuple[str, ...]] = {
    SportsEventType.SCORE: (
        "score",
        "goal",
        "touchdown",
        "buzzer beater",
        "game winner",
        "ace",
        "six",
        "three-pointer",
        "得分",
        "进球",
        "扣篮",
        "达阵",
        "绝杀",
        "压哨",
        "三分",
        "六分球",
    ),
    SportsEventType.ATTEMPT: ("attempt", "shot", "射门", "尝试"),
    SportsEventType.SAVE: ("save", "扑救"),
    SportsEventType.BLOCK: ("block", "盖帽", "封堵"),
    SportsEventType.OVERTAKE: ("overtake", "pass for position", "超越"),
    SportsEventType.FINISH: ("finish", "final whistle", "wicket", "终场", "冲线", "出局"),
    SportsEventType.CELEBRATION: ("celebration", "庆祝"),
    SportsEventType.CONTROVERSY: ("controversy", "penalty call", "争议", "判罚"),
}
COUNT_WORD_VALUES = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "一": 1,
    "二": 2,
    "两": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
    "十": 10,
}
ENGLISH_COUNTED_EVENT_PATTERN = re.compile(
    r"(?<![\w-])(?P<count>[1-9]\d*|one|two|three|four|five|six|seven|eight|nine|ten)"
    r"(?![\w-])(?=\s+(?:scores?|goals?|touchdowns?|aces?|sixes|three-pointers?|"
    r"attempts?|shots?|saves?|blocks?|overtakes?|finishes?|wickets?|celebrations?|"
    r"controvers(?:y|ies)|penalty calls?)(?![\w-]))"
)
CHINESE_COUNTED_EVENT_PATTERN = re.compile(
    r"(?P<count>[1-9]\d*|一|二|两|三|四|五|六|七|八|九|十)(?:个)?"
    r"(?=\s*(?:得分|进球|扣篮|达阵|绝杀|压哨|三分|六分球|射门|尝试|扑救|盖帽|"
    r"封堵|超越|终场|冲线|出局|庆祝|争议|判罚))"
)
NARRATIVE_CUE_MARKERS: dict[SportsNarrativeCue, tuple[str, ...]] = {
    SportsNarrativeCue.DECISIVE_SCORE: (
        "buzzer beater",
        "game winner",
        "绝杀",
        "压哨",
    ),
}


def _extract_target_count(normalized: str) -> tuple[int | None, str]:
    for pattern in (ENGLISH_COUNTED_EVENT_PATTERN, CHINESE_COUNTED_EVENT_PATTERN):
        match = pattern.search(normalized)
        if match is None:
            continue
        marker = match.group("count")
        count = int(marker) if marker.isascii() and marker.isdigit() else COUNT_WORD_VALUES[marker]
        event_instruction = (
            normalized[: match.start()]
            + " " * (match.end() - match.start())
            + normalized[match.end() :]
        )
        return count, event_instruction
    return None, normalized


def resolve_sports_request(
    control_mode: ControlMode,
    raw_instruction: str,
) -> SportsTaskRequest:
    normalized = raw_instruction.casefold()
    target_count, event_instruction = _extract_target_count(normalized)
    required: list[SportsEventType] = []
    forbidden: list[SportsEventType] = []
    for event_type, markers in EVENT_MARKERS.items():
        matching = tuple(marker for marker in markers if marker in event_instruction)
        if not matching:
            continue
        negated = any(
            re.search(
                rf"(?:不要|排除|不需要|exclude|without|not)\s*.{{0,6}}{re.escape(marker)}",
                event_instruction,
            )
            for marker in matching
        )
        (forbidden if negated else required).append(event_type)
    include_replays = bool(
        re.search(r"(?:include|with|包含|要|保留)\s*.{0,6}(?:replay|回放)", normalized)
    ) and not bool(re.search(r"(?:不要|排除|without|exclude)\s*.{0,6}(?:replay|回放)", normalized))
    required_narrative_cues = tuple(
        cue
        for cue, markers in NARRATIVE_CUE_MARKERS.items()
        if any(marker in normalized for marker in markers)
    )
    return SportsTaskRequest(
        control_mode=control_mode,
        raw_instruction=raw_instruction,
        required_event_types=tuple(dict.fromkeys(required)),
        forbidden_event_types=tuple(dict.fromkeys(forbidden)),
        required_narrative_cues=required_narrative_cues,
        include_replays=include_replays,
        target_count=target_count,
    )


def _candidate_range(
    start_ms: int,
    end_ms: int,
    *,
    media_duration_ms: int,
) -> tuple[int, int]:
    candidate_start = max(0, start_ms - 5_000)
    candidate_end = min(media_duration_ms, end_ms + 5_000)
    missing = max(0, 8_000 - (candidate_end - candidate_start))
    candidate_start = max(0, candidate_start - (missing // 2))
    candidate_end = min(media_duration_ms, candidate_end + missing - (missing // 2))
    if candidate_end - candidate_start > 60_000:
        candidate_end = candidate_start + 60_000
    return candidate_start, candidate_end


def propose_sports_candidates(
    bundle: SportsObservationBundle,
    *,
    media_duration_ms: int,
) -> tuple[CutCandidate, ...]:
    observations_by_id = {
        observation.observation_id: observation for observation in bundle.observations
    }
    candidates = []
    for event in aggregate_sports_events(bundle):
        event_observations = tuple(
            observations_by_id[observation_id] for observation_id in event.observation_ids
        )
        snapshot = " | ".join(
            f"{observation.observation_type.value}:{observation.label}"
            for observation in event_observations
        )
        transcript_excerpts = tuple(
            str(observation.value)
            for observation in event_observations
            if observation.modality is SportsModality.TEXT and isinstance(observation.value, str)
        )
        if transcript_excerpts:
            snapshot = f"{snapshot} | transcript_excerpt:{' '.join(transcript_excerpts)}"
        snapshot = snapshot[:2048]
        evidence_hash = hashlib.sha256(snapshot.encode()).hexdigest()
        candidate_start, candidate_end = _candidate_range(
            event.start_ms,
            event.end_ms,
            media_duration_ms=media_duration_ms,
        )
        candidate = CutCandidate(
            candidate_id=f"candidate-{event.event_id}",
            source_id=bundle.source_id,
            start_ms=candidate_start,
            end_ms=candidate_end,
            summary=f"{event.event_type.value} event",
            evidence_refs=(
                EvidenceRef(
                    evidence_id=f"evidence-{event.event_id}",
                    artifact_id=bundle.bundle_id,
                    segment_ids=event.observation_ids,
                    start_ms=event.start_ms,
                    end_ms=event.end_ms,
                    text_sha256=evidence_hash,
                    snapshot=snapshot,
                ),
            ),
            sports_event=event,
            tags=(
                "sports",
                (
                    "text-only-event"
                    if event.modalities == (SportsModality.TEXT,)
                    else "multimodal-event"
                ),
            ),
        )
        candidates.append(
            candidate.model_copy(update={"sports_profile": build_sports_profile(candidate)})
        )
    return tuple(candidates)


def select_sports_for_request(
    candidates: tuple[CutCandidate, ...],
    request: SportsTaskRequest,
) -> SportsSelectionResult:
    return select_sports_candidates(candidates, request)


def create_sports_plan(
    source: MediaSource,
    bundle: SportsObservationBundle,
    request: SportsTaskRequest,
    *,
    provider_records: tuple[ProviderRecord, ...] = (),
    output_spec: OutputSpec | None = None,
) -> CutPlan:
    if source.duration_ms is None:
        raise ValueError("sports plan requires source duration_ms")
    candidates = propose_sports_candidates(
        bundle,
        media_duration_ms=source.duration_ms,
    )
    selection = select_sports_for_request(candidates, request)
    return build_sports_plan(
        source,
        bundle,
        request,
        candidates,
        selection,
        provider_records=provider_records,
        output_spec=output_spec,
    )


def build_sports_plan(
    source: MediaSource,
    bundle: SportsObservationBundle,
    request: SportsTaskRequest,
    candidates: tuple[CutCandidate, ...],
    selection: SportsSelectionResult,
    *,
    provider_records: tuple[ProviderRecord, ...] = (),
    output_spec: OutputSpec | None = None,
) -> CutPlan:
    if source.source_id != bundle.source_id:
        raise ValueError("source and sports bundle source_id must match")
    provider_record_ids = {record.provider_record_id for record in provider_records}
    if not set(bundle.provider_record_refs) <= provider_record_ids:
        raise ValueError("sports plan requires every observation provider record")
    candidate_ids = {candidate.candidate_id for candidate in candidates}
    qualification_ids = {item.candidate_id for item in selection.qualifications}
    if qualification_ids != candidate_ids:
        raise ValueError("sports qualifications must cover every candidate")
    if not set(selection.selected_candidate_ids) <= candidate_ids:
        raise ValueError("sports selection references unknown candidate")
    selected_ids = set(selection.selected_candidate_ids)
    qualifications = {item.candidate_id: item for item in selection.qualifications}
    fingerprint = hashlib.sha256(
        (
            f"{source.source_id}\0{bundle.bundle_id}\0"
            f"{request.control_mode.value}\0{request.raw_instruction}"
        ).encode()
    ).hexdigest()[:12]
    occurred_at = datetime.now(UTC)
    strategy_record_id = f"strategy-record-sports-{fingerprint}"
    strategy_record = StrategyRecord(
        strategy_record_id=strategy_record_id,
        strategy_id=selection.strategy_id,
        strategy_version=selection.strategy_version,
        strategy_role=StrategyRole.SELECTION,
        distribution_name="cutsum",
        distribution_version=__version__,
        config_hash=document_sha256(request),
        input_hashes=(
            document_sha256(bundle),
            document_sha256(
                {
                    "candidates": [
                        candidate.model_dump(mode="json", exclude_none=True)
                        for candidate in candidates
                    ]
                }
            ),
        ),
        output_hashes=(document_sha256(selection),),
        provider_record_refs=tuple(record.provider_record_id for record in provider_records),
        started_at=occurred_at,
        completed_at=occurred_at,
        provenance_ref="new-original:sports-highlight-alpha-0.2.0",
    )
    return CutPlan(
        document_type="cut_plan",
        created_at=occurred_at,
        created_by="universal-cutup-sports-alpha",
        plan_id=f"plan-sports-{fingerprint}",
        source=source,
        evidence_artifacts=(
            EvidenceArtifactIdentity(
                artifact_id=bundle.bundle_id,
                source_id=bundle.source_id,
                segment_ids=tuple(
                    observation.observation_id for observation in bundle.observations
                ),
            ),
        ),
        candidates=candidates,
        selection_result=SelectionResult(
            selection_id=f"selection-sports-{fingerprint}",
            selection_strategy_id=selection.strategy_id,
            selection_strategy_version=selection.strategy_version,
            decisions=tuple(
                SelectionDecision(
                    candidate_id=candidate.candidate_id,
                    status=(
                        SelectionStatus.SELECTED
                        if candidate.candidate_id in selected_ids
                        else SelectionStatus.REJECTED
                    ),
                    reason=(
                        "sports_request_selected"
                        if candidate.candidate_id in selected_ids
                        else ";".join(qualifications[candidate.candidate_id].reasons)
                        or "sports_request_not_selected"
                    ),
                    evidence_refs=tuple(
                        evidence.evidence_id for evidence in candidate.evidence_refs
                    ),
                )
                for candidate in candidates
            ),
            warnings=selection.unsatisfied_requirements,
            provider_record_refs=tuple(record.provider_record_id for record in provider_records),
            strategy_record_ref=strategy_record_id,
        ),
        provider_records=provider_records,
        strategy_records=(strategy_record,),
        output_spec=output_spec or OutputSpec(),
    )
