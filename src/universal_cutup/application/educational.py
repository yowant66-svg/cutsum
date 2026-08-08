from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime

from universal_cutup.application.duration import (
    ABSOLUTE_PART_DURATION_MS,
    DEFAULT_PART_DURATION_MS,
    split_candidate,
)
from universal_cutup.application.subtitle_display import semantic_source_spans
from universal_cutup.domain.candidates import (
    CutCandidate,
    EvidenceArtifactIdentity,
    EvidenceRef,
)
from universal_cutup.domain.education import (
    STRUCTURAL_EDUCATION_SIGNAL_TYPES,
    EducationalSelectionResult,
    EducationalTaskRequest,
    EducationSignalType,
)
from universal_cutup.domain.intelligence import ControlMode
from universal_cutup.domain.plans import CutPlan
from universal_cutup.domain.selection import (
    SelectionDecision,
    SelectionResult,
    SelectionStatus,
)
from universal_cutup.domain.sources import MediaSource
from universal_cutup.domain.specs import OutputSpec
from universal_cutup.domain.subtitles import SubtitleSemanticSpan
from universal_cutup.domain.transcript import SubtitleCue, TranscriptArtifact
from universal_cutup.strategies.educational import (
    attach_education_signals,
    build_educational_profile,
    extract_education_signals,
    select_educational_candidates,
)

EDUCATIONAL_INTENT_MARKERS: dict[EducationSignalType, tuple[str, ...]] = {
    EducationSignalType.DEFINITION: ("definition", "定义"),
    EducationSignalType.THEOREM_OR_RULE: ("theorem", "rule", "formula", "定理", "规则", "公式"),
    EducationSignalType.REASONING_CHAIN: ("reasoning", "proof", "推理", "证明"),
    EducationSignalType.WORKED_EXAMPLE: ("example", "worked example", "例题", "例子"),
    EducationSignalType.PROCEDURE_OR_STEP: ("step", "procedure", "步骤", "操作"),
    EducationSignalType.SUMMARY: ("summary", "总结"),
    EducationSignalType.COMMON_MISTAKE: ("mistake", "error", "常见错误", "易错"),
    EducationSignalType.DIFFICULT_POINT: ("difficult", "hard part", "难点"),
    EducationSignalType.TEACHER_EMPHASIS: ("emphasis", "important", "重点", "强调"),
    EducationSignalType.EXAM_RELEVANCE: ("exam", "test point", "考试", "考点"),
}
COUNT_MARKERS = {
    "1": 1,
    "one": 1,
    "一个": 1,
    "2": 2,
    "two": 2,
    "两个": 2,
    "3": 3,
    "three": 3,
    "三个": 3,
    "4": 4,
    "four": 4,
    "四个": 4,
    "5": 5,
    "five": 5,
    "五个": 5,
}
MINIMUM_EDUCATIONAL_CANDIDATE_DURATION_MS = 15_000
MAXIMUM_DURATION_PATTERN = re.compile(
    r"(?:最多|最长|不超过)\s*(\d+)\s*(秒|分钟)|"
    r"(?:at most|maximum|max|no more than)\s*(\d+)\s*(seconds?|minutes?)",
    flags=re.IGNORECASE,
)
DEPENDENT_SEMANTIC_START_PATTERN = re.compile(
    (
        r"^\s*(?:(?:and\s+)?(?:then|similarly|likewise|therefore|thus|so)|"
        r"but|however|instead|also|because of this|this|that|these|those|"
        r"assume\s+(?:the\s+)?(?:inductive\s+)?hypothesis|"
        r"然后|接着|同样|类似地|但是|不过|因此|所以|由此)\b"
    ),
    flags=re.IGNORECASE,
)
REFERENTIAL_SEMANTIC_PATTERN = re.compile(
    (
        r"\b(?:this|that|these|those)\s+(?:one|ones|guy|guys|edge|edges|"
        r"input|inputs|output|outputs|thing|things)\b"
    ),
    flags=re.IGNORECASE,
)
DIRECTED_CONTROL_MARKERS = (
    "只保留",
    "只要",
    "不要",
    "不需要",
    "排除",
    "保留",
    "提取",
    "选择",
    "完整",
    "连续",
    "独立",
    "知识片段",
    "片段",
    "能够",
    "能",
    "包含",
    "并",
    "的",
    "only",
    "keep",
    "select",
    "extract",
    "exclude",
    "without",
    "not",
    "complete",
    "self-contained",
    "clip",
    "segment",
    "and",
)


def _has_unresolved_directed_semantics(
    control_mode: ControlMode,
    normalized_instruction: str,
    *,
    required_topic_groups: tuple[tuple[str, ...], ...],
) -> bool:
    if (
        control_mode is not ControlMode.DIRECTED
        or not normalized_instruction.strip()
        or required_topic_groups
    ):
        return False
    residual = MAXIMUM_DURATION_PATTERN.sub("", normalized_instruction)
    removable = {
        *COUNT_MARKERS,
        *DIRECTED_CONTROL_MARKERS,
        *(
            marker
            for markers in EDUCATIONAL_INTENT_MARKERS.values()
            for marker in markers
        ),
    }
    for marker in sorted(removable, key=len, reverse=True):
        residual = residual.replace(marker, "")
    residual = re.sub(r"[\W_\d]+", "", residual, flags=re.UNICODE)
    return bool(residual)


def _weak_semantic_boundary(span: SubtitleSemanticSpan) -> bool:
    return len(re.findall(r"[A-Za-z0-9\u3400-\u9fff]+", span.text)) < 3


def _dependent_semantic_boundary(span: SubtitleSemanticSpan) -> bool:
    return bool(
        DEPENDENT_SEMANTIC_START_PATTERN.search(span.text)
        or REFERENTIAL_SEMANTIC_PATTERN.search(span.text)
    )


def _unsafe_previous_boundary(span: SubtitleSemanticSpan) -> bool:
    return _weak_semantic_boundary(span) or _dependent_semantic_boundary(span)


def _expand_semantic_spans(
    spans: tuple[SubtitleSemanticSpan, ...],
    index: int,
) -> tuple[SubtitleSemanticSpan, ...]:
    first = last = index
    while (
        spans[last].end_ms - spans[first].start_ms
        < MINIMUM_EDUCATIONAL_CANDIDATE_DURATION_MS
    ) and (
        first > 0 or last < len(spans) - 1
    ):
        options: list[tuple[bool, int, str]] = []
        if first > 0:
            options.append(
                (
                    _unsafe_previous_boundary(spans[first - 1]),
                    max(0, spans[first].start_ms - spans[first - 1].end_ms),
                    "previous",
                )
            )
        if last < len(spans) - 1:
            options.append(
                (
                    False,
                    max(0, spans[last + 1].start_ms - spans[last].end_ms),
                    "following",
                )
            )
        direction = min(options, key=lambda item: item[:2])[2]
        if direction == "previous":
            first -= 1
        else:
            last += 1
    while first > 0 and _dependent_semantic_boundary(spans[first]):
        previous = first - 1
        while previous >= 0 and _weak_semantic_boundary(spans[previous]):
            previous -= 1
        if previous < 0:
            break
        first = previous
    while last < len(spans) - 1 and _weak_semantic_boundary(spans[last]):
        last += 1
    return spans[first : last + 1]


def propose_educational_candidates(
    transcript: TranscriptArtifact,
) -> tuple[CutCandidate, ...]:
    """Create traceable education candidates from transcript semantics alone."""
    cues = tuple(
        SubtitleCue(
            cue_id=f"cue-{segment.segment_id}",
            source_id=segment.source_id,
            start_ms=segment.start_ms,
            end_ms=segment.end_ms,
            text=segment.text,
            language=transcript.language,
            speaker=segment.speaker,
            source_segment_ids=(segment.segment_id,),
        )
        for segment in transcript.segments
    )
    transcript_semantic_spans = semantic_source_spans(
        cues,
        maximum_display_duration_ms=30_000,
    )
    candidates: list[CutCandidate] = []
    cues_by_id = {cue.cue_id: cue for cue in cues}
    for span_index, span in enumerate(transcript_semantic_spans):
        context_semantic_spans = _expand_semantic_spans(
            transcript_semantic_spans,
            span_index,
        )
        covered_cue_ids = tuple(
            dict.fromkeys(
                cue_id
                for semantic_span in context_semantic_spans
                for cue_id in semantic_span.source_cue_ids
            )
        )
        covered_cues = tuple(cues_by_id[cue_id] for cue_id in covered_cue_ids)
        segment_ids = tuple(
            dict.fromkeys(
                segment_id for cue in covered_cues for segment_id in cue.source_segment_ids
            )
        )
        evidence_text = " ".join(item.text.strip() for item in context_semantic_spans)
        evidence_hash = hashlib.sha256(evidence_text.encode()).hexdigest()
        candidate = CutCandidate(
            candidate_id=f"education-{span.semantic_span_id}",
            source_id=transcript.source_id,
            start_ms=context_semantic_spans[0].start_ms,
            end_ms=context_semantic_spans[-1].end_ms,
            summary=span.text,
            evidence_refs=(
                EvidenceRef(
                    evidence_id=(f"evidence-{span.semantic_span_id}-{evidence_hash[:8]}"),
                    artifact_id=transcript.transcript_id,
                    segment_ids=segment_ids,
                    start_ms=context_semantic_spans[0].start_ms,
                    end_ms=context_semantic_spans[-1].end_ms,
                    text_sha256=evidence_hash,
                    snapshot=evidence_text,
                ),
            ),
            subtitle_cues=covered_cues,
            subtitle_semantic_spans=context_semantic_spans,
            tags=("education", "semantic-proposal"),
        )
        signal_source = candidate.model_copy(
            update={"subtitle_semantic_spans": (span,)}
        )
        candidate = candidate.model_copy(
            update={"education_signals": extract_education_signals(signal_source)}
        )
        candidate = candidate.model_copy(
            update={"educational_profile": build_educational_profile(candidate)}
        )
        profile = candidate.educational_profile
        if profile is not None and (set(profile.signal_types) & STRUCTURAL_EDUCATION_SIGNAL_TYPES):
            candidates.append(candidate)
    return tuple(candidates)


def prepare_educational_candidate(candidate: CutCandidate) -> CutCandidate:
    return attach_education_signals(candidate)


def resolve_educational_request(
    control_mode: ControlMode,
    raw_instruction: str,
    *,
    required_topic_groups: tuple[tuple[str, ...], ...] = (),
) -> EducationalTaskRequest:
    normalized = raw_instruction.casefold()
    required: list[EducationSignalType] = []
    forbidden: list[EducationSignalType] = []
    for signal_type, markers in EDUCATIONAL_INTENT_MARKERS.items():
        matching_markers = tuple(marker for marker in markers if marker in normalized)
        if not matching_markers:
            continue
        negated = any(
            re.search(
                rf"(?:不要|排除|不需要|exclude|without|not)\s*.{{0,6}}{re.escape(marker)}",
                normalized,
            )
            for marker in matching_markers
        )
        target = forbidden if negated else required
        target.append(signal_type)
    target_count = next(
        (count for marker, count in COUNT_MARKERS.items() if marker in normalized),
        None,
    )
    duration_match = MAXIMUM_DURATION_PATTERN.search(normalized)
    maximum_duration_ms = None
    if duration_match is not None:
        value = int(duration_match.group(1) or duration_match.group(3))
        unit = duration_match.group(2) or duration_match.group(4)
        maximum_duration_ms = value * (60_000 if unit in {"分钟", "minute", "minutes"} else 1000)
    return EducationalTaskRequest(
        control_mode=control_mode,
        raw_instruction=raw_instruction,
        required_types=tuple(dict.fromkeys(required)),
        forbidden_types=tuple(dict.fromkeys(forbidden)),
        target_count=target_count,
        required_topic_groups=required_topic_groups,
        maximum_duration_ms=maximum_duration_ms,
        unresolved_semantic_instruction=_has_unresolved_directed_semantics(
            control_mode,
            normalized,
            required_topic_groups=required_topic_groups,
        ),
    )


def select_educational_for_request(
    candidates: tuple[CutCandidate, ...],
    request: EducationalTaskRequest,
) -> EducationalSelectionResult:
    prepared = tuple(
        candidate
        if candidate.educational_profile is not None
        else prepare_educational_candidate(candidate)
        for candidate in candidates
    )
    if request.target_count is not None:
        required_count = request.target_count
    else:
        forbidden = set(request.forbidden_types)
        eligible_count = sum(
            bool(
                candidate.educational_profile is not None
                and candidate.educational_profile.qualified
                and set(candidate.educational_profile.signal_types)
                & STRUCTURAL_EDUCATION_SIGNAL_TYPES
                and not set(candidate.educational_profile.signal_types) & forbidden
            )
            for candidate in prepared
        )
        required_count = max(1, min(3, eligible_count))
    result = select_educational_candidates(
        prepared,
        required_types=request.required_types,
        forbidden_types=request.forbidden_types,
        required_count=required_count,
        required_topic_groups=request.required_topic_groups,
        maximum_duration_ms=request.maximum_duration_ms,
        semantic_constraints_resolved=not request.unresolved_semantic_instruction,
    )
    if not request.unresolved_semantic_instruction:
        return result
    return result.model_copy(
        update={
            "unsatisfied_requirements": tuple(
                dict.fromkeys(
                    (
                        *result.unsatisfied_requirements,
                        "educational_topic_constraints_unresolved",
                    )
                )
            )
        }
    )


def prepare_educational_duration(
    candidate: CutCandidate,
) -> tuple[CutCandidate, ...]:
    duration_ms = candidate.end_ms - candidate.start_ms
    if duration_ms <= DEFAULT_PART_DURATION_MS:
        return (candidate,)
    if duration_ms <= ABSOLUTE_PART_DURATION_MS:
        return (
            candidate.model_copy(
                update={"extension_reason": "educational_context_requires_over_60_seconds"}
            ),
        )
    return tuple(
        prepare_educational_candidate(part.model_copy(update={"educational_profile": None}))
        for part in split_candidate(candidate)
    )


def create_educational_plan(
    source: MediaSource,
    transcript: TranscriptArtifact,
    request: EducationalTaskRequest,
    *,
    output_spec: OutputSpec | None = None,
) -> CutPlan:
    candidates = tuple(
        prepared
        for candidate in propose_educational_candidates(transcript)
        for prepared in prepare_educational_duration(candidate)
    )
    selection = select_educational_for_request(candidates, request)
    return build_educational_plan(
        source,
        transcript,
        request,
        candidates,
        selection,
        output_spec=output_spec,
    )


def build_educational_plan(
    source: MediaSource,
    transcript: TranscriptArtifact,
    request: EducationalTaskRequest,
    candidates: tuple[CutCandidate, ...],
    selection: EducationalSelectionResult,
    *,
    output_spec: OutputSpec | None = None,
) -> CutPlan:
    if source.source_id != transcript.source_id:
        raise ValueError("source and transcript source_id must match")
    candidate_ids = {candidate.candidate_id for candidate in candidates}
    qualification_ids = {item.candidate_id for item in selection.qualifications}
    if qualification_ids != candidate_ids:
        raise ValueError("educational qualifications must cover every candidate")
    if not set(selection.selected_candidate_ids) <= candidate_ids:
        raise ValueError("educational selection references unknown candidate")
    selected_ids = set(selection.selected_candidate_ids)
    plan_fingerprint = hashlib.sha256(
        (
            f"{source.source_id}\0{transcript.transcript_id}\0"
            f"{request.control_mode.value}\0{request.raw_instruction}"
        ).encode()
    ).hexdigest()[:12]
    decisions = tuple(
        SelectionDecision(
            candidate_id=candidate.candidate_id,
            status=(
                SelectionStatus.SELECTED
                if candidate.candidate_id in selected_ids
                else SelectionStatus.REJECTED
            ),
            reason=(
                "educational_request_selected"
                if candidate.candidate_id in selected_ids
                else "educational_request_not_selected"
            ),
            evidence_refs=tuple(evidence.evidence_id for evidence in candidate.evidence_refs),
        )
        for candidate in candidates
    )
    return CutPlan(
        document_type="cut_plan",
        created_at=datetime.now(UTC),
        created_by="universal-cutup-educational-v1",
        plan_id=f"plan-education-{plan_fingerprint}",
        source=source,
        evidence_artifacts=(
            EvidenceArtifactIdentity(
                artifact_id=transcript.transcript_id,
                source_id=transcript.source_id,
                segment_ids=tuple(segment.segment_id for segment in transcript.segments),
            ),
        ),
        candidates=candidates,
        selection_result=SelectionResult(
            selection_id=f"selection-{selection.strategy_id}-{plan_fingerprint}",
            selection_strategy_id=selection.strategy_id,
            selection_strategy_version=selection.strategy_version,
            decisions=decisions,
            warnings=selection.unsatisfied_requirements,
        ),
        output_spec=output_spec or OutputSpec(),
    )
