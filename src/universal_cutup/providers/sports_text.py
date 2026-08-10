from __future__ import annotations

import hashlib
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

from universal_cutup.domain.records import ProviderRecord
from universal_cutup.domain.sports import (
    SportsEventType,
    SportsModality,
    SportsNarrativeCue,
    SportsObservation,
    SportsObservationBundle,
    SportsObservationType,
    SportsTemporalRole,
)
from universal_cutup.domain.transcript import TranscriptArtifact, TranscriptSegment
from universal_cutup.hashing import document_sha256

TRANSCRIPT_ONLY_WARNING = (
    "deterministic transcript-only sports detection; no audio, video, or OCR confirmation"
)


class SportsTextProfile(StrEnum):
    FOOTBALL = "football"
    AMERICAN_FOOTBALL = "american_football"
    RUGBY = "rugby"
    BASKETBALL = "basketball"
    TENNIS = "tennis"
    CRICKET = "cricket"
    GENERIC = "generic"


class _CurrentSegmentResultAssertion(StrEnum):
    EXPLICIT_RESULT = "explicit_result"
    NOMINAL_REFERENCE = "nominal_reference"
    ATTEMPT_OR_FUTURE = "attempt_or_future"
    NEGATED = "negated"
    CANCELLED = "cancelled"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class SportsTextDetection:
    segment_id: str
    start_ms: int
    end_ms: int
    event_type: SportsEventType
    signal: str
    confidence: float
    strong_outcome: bool
    normalized_text: str
    narrative_cues: tuple[SportsNarrativeCue, ...] = ()


@dataclass(frozen=True, slots=True)
class DetectedSportsObservations:
    artifact: SportsObservationBundle
    provider_record: ProviderRecord
    input_sha256: str
    output_sha256: str


@dataclass(frozen=True, slots=True)
class _Rule:
    signal: str
    pattern: re.Pattern[str]
    event_type: SportsEventType
    strong_outcome: bool = True
    confidence: float = 0.88
    narrative_cues: tuple[SportsNarrativeCue, ...] = ()


def _rule(
    signal: str,
    pattern: str,
    event_type: SportsEventType,
    *,
    strong_outcome: bool = True,
    confidence: float = 0.88,
    narrative_cues: tuple[SportsNarrativeCue, ...] = (),
) -> _Rule:
    return _Rule(
        signal=signal,
        pattern=re.compile(pattern, re.IGNORECASE),
        event_type=event_type,
        strong_outcome=strong_outcome,
        confidence=confidence,
        narrative_cues=narrative_cues,
    )


PROFILE_RULES: dict[SportsTextProfile, tuple[_Rule, ...]] = {
    SportsTextProfile.FOOTBALL: (
        _rule("save", r"\b(?:what a |great |brilliant )?save\b|扑救", SportsEventType.SAVE),
        _rule(
            "decisive_score",
            r"\bgame winner\b|绝杀",
            SportsEventType.SCORE,
            narrative_cues=(SportsNarrativeCue.DECISIVE_SCORE,),
        ),
        _rule(
            "score",
            r"\b(?:goal|scor(?:es|ed)|equalizer|it(?:'s| is) in)\b"
            r"|进球|破门|球进了|打进了",
            SportsEventType.SCORE,
        ),
        _rule(
            "attempt",
            r"\b(?:shot|header|hits? the post|wide)\b|射门|中柱|偏出",
            SportsEventType.ATTEMPT,
            strong_outcome=False,
            confidence=0.72,
        ),
        _rule(
            "controversy",
            r"\b(?:var|red card|penalty call)\b|红牌|争议判罚",
            SportsEventType.CONTROVERSY,
        ),
    ),
    SportsTextProfile.AMERICAN_FOOTBALL: (
        _rule(
            "score",
            r"\b(?:touchdown|field goal|two[- ]point conversion)\b|达阵",
            SportsEventType.SCORE,
        ),
        _rule(
            "overtake",
            r"\b(?:interception|pick[- ]six|fumble recovery)\b",
            SportsEventType.OVERTAKE,
        ),
        _rule("block", r"\b(?:sack|blocked kick)\b", SportsEventType.BLOCK),
    ),
    SportsTextProfile.RUGBY: (
        _rule(
            "score",
            r"\b(?:(?:a|the|another|penalty) try|try (?:awarded|confirmed|scored)"
            r"|conversion|drop goal)\b|达阵得分",
            SportsEventType.SCORE,
        ),
        _rule(
            "overtake", r"\b(?:turnover|intercept(?:ion|ed))\b|夺回球权", SportsEventType.OVERTAKE
        ),
        _rule(
            "attempt",
            r"\b(?:tackle|scrum|lineout)\b|擒抱|争边球",
            SportsEventType.ATTEMPT,
            strong_outcome=False,
            confidence=0.70,
        ),
    ),
    SportsTextProfile.BASKETBALL: (
        _rule(
            "decisive_score",
            r"\b(?:buzzer beater|game winner)\b|压哨|绝杀",
            SportsEventType.SCORE,
            narrative_cues=(SportsNarrativeCue.DECISIVE_SCORE,),
        ),
        _rule(
            "score",
            r"\b(?:three[- ]pointer|slam dunk|dunks?|scores)\b|三分|扣篮",
            SportsEventType.SCORE,
        ),
        _rule("block", r"\b(?:block(?:ed)?|rejection)\b|盖帽|封盖", SportsEventType.BLOCK),
        _rule("overtake", r"\b(?:steal|turnover forced)\b|抢断", SportsEventType.OVERTAKE),
        _rule(
            "attempt",
            r"\b(?:missed shot|at the rim)\b|投篮不中",
            SportsEventType.ATTEMPT,
            strong_outcome=False,
            confidence=0.72,
        ),
    ),
    SportsTextProfile.TENNIS: (
        _rule(
            "score",
            r"\b(?:ace|winner|break point won|match point converted"
            r"|championship point converted)\b|发球直接得分|制胜分|破发成功",
            SportsEventType.SCORE,
        ),
        _rule(
            "finish",
            r"\b(?:wins? the match|champion|takes? the title)\b|赢得比赛|夺冠",
            SportsEventType.FINISH,
        ),
        _rule(
            "attempt",
            r"\b(?:break point|set point|match point|double fault)\b|破发点|盘点|赛点|双误",
            SportsEventType.ATTEMPT,
            strong_outcome=False,
            confidence=0.74,
        ),
        _rule(
            "controversy",
            r"\b(?:challenge|hawkeye|line call overturned)\b|鹰眼挑战|司线争议",
            SportsEventType.CONTROVERSY,
        ),
    ),
    SportsTextProfile.CRICKET: (
        _rule(
            "finish",
            r"\b(?:wicket|run out|clean bowled|stumped)\b|三柱门|出局",
            SportsEventType.FINISH,
        ),
        _rule(
            "score",
            r"\b(?:(?:hits?|smashes?|launches?) (?:it )?for (?:six|four)"
            r"|six runs?|four runs?|maximum|boundary|century|six[!.]|four[!.])"
            r"|六分球|四分球|边界球|百分",
            SportsEventType.SCORE,
        ),
        _rule(
            "controversy",
            r"\b(?:drs review|no ball controversy)\b|裁判复核",
            SportsEventType.CONTROVERSY,
        ),
    ),
    SportsTextProfile.GENERIC: (
        _rule(
            "score",
            r"\b(?:goal|score|touchdown|buzzer beater|ace|wicket)\b|进球|得分|绝杀",
            SportsEventType.SCORE,
        ),
        _rule("save", r"\b(?:save|block)\b|扑救|封盖", SportsEventType.SAVE),
        _rule(
            "finish",
            r"\b(?:finish|final whistle|wins? the match)\b|终场|冲线|赢得比赛",
            SportsEventType.FINISH,
        ),
    ),
}

HYPOTHETICAL_PATTERN = re.compile(
    r"\b(?:if|would|could|needs? to|might|may)\b.{0,50}"
    r"\b(?:scor(?:e|es|ed)|goal|equalizer|win)\b|如果|要是|可能会",
    re.IGNORECASE,
)
INHERITED_HYPOTHETICAL_PATTERN = re.compile(
    r"\bif\b.{0,50}\b(?:score|goal|win|goes? in|do (?:it|this))\b"
    r"|\bneeds?\b.{0,20}\b(?:score|goal|win)\b"
    r"|(?:如果|要是).{0,30}(?:进球|得分|获胜|赢|做到|打进)"
    r"|(?:需要|必须).{0,15}(?:进球|得分|获胜|赢)",
    re.IGNORECASE,
)
RETROSPECTIVE_PATTERN = re.compile(
    r"\b(?:replay|earlier|previously|highlights? of)\b|回放|此前|刚才的|精彩回顾",
    re.IGNORECASE,
)
CANCELLED_PATTERN = re.compile(
    r"\b(?:no goal|(?:goal|score|try|touchdown|wicket|point) (?:is )?"
    r"(?:disallowed|ruled out|overturned|does not count)"
    r"|(?:disallowed|ruled out|overturned) (?:the )?"
    r"(?:goal|score|try|touchdown|wicket|point)"
    r"|no[- ]ball.{0,30}(?:wicket|out|dismissal))\b"
    r"|进球无效|取消进球|(?:进球|得分).{0,12}改判|改判.{0,12}(?:进球|得分)",
    re.IGNORECASE,
)
FAILED_PATTERN = re.compile(
    r"\b(?:missed|misses|wide|off the post|no good)\b|没进|偏出|不中",
    re.IGNORECASE,
)
BROAD_HYPOTHETICAL_CONTEXT_PATTERN = re.compile(
    r"\b(?:if|could|might|may|would|needs?)\b|如果|要是|可能|也许|需要",
    re.IGNORECASE,
)
EXPLICIT_RESULT_PATTERN = re.compile(
    r"\bgoal\s*!|\bscor(?:es|ed)\b"
    r"|\bit(?:'s| is) in\b|球进了|打进了|进球了|破门了",
    re.IGNORECASE,
)
ATTEMPT_OR_FUTURE_PATTERN = re.compile(
    r"\b(?:to score|going to score|about to score|needs? to score)\b"
    r"|\b(?:if|could|might|may|would|needs?)\b.{0,50}"
    r"\b(?:scor(?:e|es|ed)|goal|equalizer|win)\b"
    r"|准备进球|试图进球|可能进球|需要进球",
    re.IGNORECASE,
)
NEGATED_RESULT_PATTERN = re.compile(
    r"\b(?:did not|didn't|has not|hasn't|have not|haven't) score\b"
    r"|\bnot (?:a )?goal\b|\b(?:it is|it's) not in\b|没有进球|并未进球|球没进",
    re.IGNORECASE,
)
NOMINAL_RESULT_PATTERN = re.compile(
    r"\b(?:goal|equalizer|score)\b|进球|得分|扳平球",
    re.IGNORECASE,
)
CONTEXT_MAX_GAP_MS = 1_500
CANCELLATION_LOOKBACK_MS = 15_000
ROLLING_DUPLICATE_MAX_GAP_MS = 1_500


def _has_open_context(text: str) -> bool:
    stripped = text.rstrip()
    return bool(stripped) and not stripped.endswith((".", "!", "?", "。", "\uff01", "\uff1f"))


def _classify_current_segment_result_assertion(
    text: str,
) -> _CurrentSegmentResultAssertion:
    normalized = " ".join(text.casefold().split())
    if CANCELLED_PATTERN.search(normalized):
        return _CurrentSegmentResultAssertion.CANCELLED
    if NEGATED_RESULT_PATTERN.search(normalized):
        return _CurrentSegmentResultAssertion.NEGATED
    if ATTEMPT_OR_FUTURE_PATTERN.search(normalized):
        return _CurrentSegmentResultAssertion.ATTEMPT_OR_FUTURE
    if EXPLICIT_RESULT_PATTERN.search(normalized):
        return _CurrentSegmentResultAssertion.EXPLICIT_RESULT
    if NOMINAL_RESULT_PATTERN.search(normalized):
        return _CurrentSegmentResultAssertion.NOMINAL_REFERENCE
    return _CurrentSegmentResultAssertion.UNKNOWN


def _should_inherit_context(
    previous_text: str,
    current_assertion: _CurrentSegmentResultAssertion,
) -> bool:
    normalized = " ".join(previous_text.casefold().split())
    if RETROSPECTIVE_PATTERN.search(normalized) or INHERITED_HYPOTHETICAL_PATTERN.search(
        normalized
    ):
        return True
    return bool(
        current_assertion is not _CurrentSegmentResultAssertion.EXPLICIT_RESULT
        and BROAD_HYPOTHETICAL_CONTEXT_PATTERN.search(normalized)
    )


class LocalSportsTextProvider:
    def __init__(
        self,
        *,
        profile: SportsTextProfile,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.profile = profile
        self.provider_id = f"sports-text-{profile.value}"
        self._clock = clock or (lambda: datetime.now(UTC))

    def detect(self, transcript: TranscriptArtifact) -> DetectedSportsObservations:
        occurred_at = self._clock()
        input_hash = document_sha256(transcript)
        detection_fingerprint = hashlib.sha256(
            f"{input_hash}\0{self.profile.value}".encode()
        ).hexdigest()
        detections = self._detect_segments(transcript.segments)
        provider_record_id = f"provider-sports-text-{detection_fingerprint[:16]}"
        observations = tuple(
            self._observation(detection, transcript.source_id, provider_record_id)
            for detection in detections
        )
        artifact = SportsObservationBundle(
            document_type="sports_observation_bundle",
            created_at=occurred_at,
            created_by=self.provider_id,
            bundle_id=f"bundle-sports-text-{detection_fingerprint[:16]}",
            source_id=transcript.source_id,
            provider_kind="local_detector",
            provider_record_refs=(provider_record_id,),
            observations=observations,
        )
        output_hash = document_sha256(artifact)
        record = ProviderRecord(
            provider_record_id=provider_record_id,
            provider_id=self.provider_id,
            operation="detect_sports_from_transcript",
            started_at=occurred_at,
            completed_at=occurred_at,
            input_hashes=(input_hash,),
            output_hashes=(output_hash,),
            warnings=(TRANSCRIPT_ONLY_WARNING,),
        )
        return DetectedSportsObservations(
            artifact=artifact,
            provider_record=record,
            input_sha256=input_hash,
            output_sha256=output_hash,
        )

    def _detect_segments(
        self,
        segments: tuple[TranscriptSegment, ...],
    ) -> tuple[SportsTextDetection, ...]:
        detections: list[SportsTextDetection] = []
        previous_segment: TranscriptSegment | None = None
        for segment in segments:
            context_text = segment.text
            current_assertion = _classify_current_segment_result_assertion(segment.text)
            if (
                previous_segment is not None
                and segment.start_ms - previous_segment.end_ms <= CONTEXT_MAX_GAP_MS
                and _has_open_context(previous_segment.text)
                and _should_inherit_context(previous_segment.text, current_assertion)
            ):
                context_text = f"{previous_segment.text} {segment.text}"
            current = self._detect_segment(
                segment,
                context_text=context_text,
                result_assertion=current_assertion,
            )
            if any(item.signal == "cancelled_score" for item in current):
                for index in range(len(detections) - 1, -1, -1):
                    previous_detection = detections[index]
                    if (
                        previous_detection.event_type
                        in {SportsEventType.SCORE, SportsEventType.FINISH}
                        and 0
                        <= segment.start_ms - previous_detection.end_ms
                        <= CANCELLATION_LOOKBACK_MS
                    ):
                        del detections[index]
                        break
            for detection in current:
                if not self._is_rolling_duplicate(detection, detections):
                    detections.append(detection)
            previous_segment = segment
        return tuple(detections)

    def _detect_segment(
        self,
        segment: TranscriptSegment,
        *,
        context_text: str | None = None,
        result_assertion: _CurrentSegmentResultAssertion | None = None,
    ) -> tuple[SportsTextDetection, ...]:
        normalized = " ".join(segment.text.casefold().split())
        normalized_context = " ".join((context_text or segment.text).casefold().split())
        assertion = result_assertion or _classify_current_segment_result_assertion(segment.text)
        if RETROSPECTIVE_PATTERN.search(normalized_context):
            return ()
        if assertion is _CurrentSegmentResultAssertion.CANCELLED:
            return (
                self._detection(
                    segment,
                    normalized,
                    SportsEventType.CONTROVERSY,
                    "cancelled_score",
                    0.92,
                    True,
                ),
            )
        if assertion in {
            _CurrentSegmentResultAssertion.ATTEMPT_OR_FUTURE,
            _CurrentSegmentResultAssertion.NEGATED,
        } or HYPOTHETICAL_PATTERN.search(normalized_context):
            return ()
        detections: list[SportsTextDetection] = []
        emitted_event_types: set[SportsEventType] = set()
        for rule in PROFILE_RULES[self.profile]:
            if not rule.pattern.search(normalized):
                continue
            event_type = (
                SportsEventType.ATTEMPT
                if rule.event_type is SportsEventType.SCORE and FAILED_PATTERN.search(normalized)
                else rule.event_type
            )
            if event_type in emitted_event_types:
                continue
            detections.append(
                self._detection(
                    segment,
                    normalized,
                    event_type,
                    rule.signal,
                    rule.confidence,
                    rule.strong_outcome and event_type is not SportsEventType.ATTEMPT,
                    narrative_cues=(
                        rule.narrative_cues if event_type is not SportsEventType.ATTEMPT else ()
                    ),
                )
            )
            emitted_event_types.add(event_type)
        return tuple(detections)

    @staticmethod
    def _detection(
        segment: TranscriptSegment,
        normalized_text: str,
        event_type: SportsEventType,
        signal: str,
        confidence: float,
        strong_outcome: bool,
        narrative_cues: tuple[SportsNarrativeCue, ...] = (),
    ) -> SportsTextDetection:
        return SportsTextDetection(
            segment_id=segment.segment_id,
            start_ms=segment.start_ms,
            end_ms=segment.end_ms,
            event_type=event_type,
            signal=signal,
            confidence=confidence,
            strong_outcome=strong_outcome,
            normalized_text=normalized_text,
            narrative_cues=narrative_cues,
        )

    @staticmethod
    def _is_rolling_duplicate(
        current: SportsTextDetection,
        previous: list[SportsTextDetection],
    ) -> bool:
        for item in reversed(previous[-3:]):
            overlaps = current.start_ms < item.end_ms and current.end_ms > item.start_ms
            gap_ms = current.start_ms - item.end_ms
            current_words = set(re.findall(r"\w+", current.normalized_text))
            previous_words = set(re.findall(r"\w+", item.normalized_text))
            shared_words = current_words & previous_words
            similarity = len(shared_words) / max(1, min(len(current_words), len(previous_words)))
            same_event = current.event_type is item.event_type and current.signal == item.signal
            if (
                same_event
                and (overlaps or 0 <= gap_ms <= ROLLING_DUPLICATE_MAX_GAP_MS)
                and similarity >= 0.8
            ):
                return True
        return False

    def _observation(
        self,
        detection: SportsTextDetection,
        source_id: str,
        provider_record_id: str,
    ) -> SportsObservation:
        correlation_key = hashlib.sha256(
            (
                f"{source_id}\0{self.profile.value}\0{detection.segment_id}\0"
                f"{detection.event_type.value}\0{detection.signal}"
            ).encode()
        ).hexdigest()[:16]
        return SportsObservation(
            observation_id=f"sports-text-classification-{correlation_key}",
            source_id=source_id,
            observation_type=SportsObservationType.EVENT_CLASSIFICATION,
            modality=SportsModality.TEXT,
            temporal_role=(
                SportsTemporalRole.OUTCOME
                if detection.strong_outcome
                else SportsTemporalRole.ACTION
            ),
            start_ms=detection.start_ms,
            end_ms=detection.end_ms,
            confidence=detection.confidence,
            label=f"{self.profile.value}:{detection.signal}",
            value=detection.normalized_text[:500],
            event_type_hint=detection.event_type,
            narrative_cues=detection.narrative_cues,
            correlation_key=correlation_key,
            provider_record_ref=provider_record_id,
        )
