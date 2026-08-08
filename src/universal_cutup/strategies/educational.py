from __future__ import annotations

import re
from collections.abc import Iterable
from itertools import pairwise

from universal_cutup.domain.candidates import CutCandidate
from universal_cutup.domain.education import (
    STRUCTURAL_EDUCATION_SIGNAL_TYPES,
    EducationalCandidateProfile,
    EducationalQualification,
    EducationalSelectionResult,
    EducationContextRole,
    EducationSignal,
    EducationSignalType,
)

SIGNAL_PATTERNS: dict[EducationSignalType, tuple[str, ...]] = {
    EducationSignalType.DEFINITION: (
        r"\bdefinition of.{0,80}\bis\b",
        (
            r"\b(?:algorithm|problem|function|recurrence|theorem|rule|formula|"
            r"concept|term)\s+is\s+(?:an?|the)\b"
        ),
        r"\b[A-Za-z][A-Za-z -]{1,60},?\s+which\s+is\s+the\s+study\s+of\b",
        r"\b[A-Za-z][A-Za-z -]{1,60}\s+is\s+the\s+study\s+of\b",
        r"\b(?:it|this|that|[A-Za-z][A-Za-z -]{1,60})\s+refers\s+to\b",
        r"\bby\s+[A-Za-z][A-Za-z -]{1,40}\s+(?:we|I)\s+mean\b",
        r"定义",
        r"是指",
    ),
    EducationSignalType.THEOREM_OR_RULE: (
        r"\btheorem\b",
        r"\bprinciple\b",
        r"\brule\b",
        r"定理",
        r"规律",
        r"公式",
    ),
    EducationSignalType.REASONING_CHAIN: (
        r"\bassume\b",
        r"\btherefore\b",
        r"\bby induction\b",
        r"因此",
        r"所以",
        r"归纳",
    ),
    EducationSignalType.WORKED_EXAMPLE: (
        r"\bfor example\b",
        r"\bsuppose\b",
        r"\blet'?s say\b",
        r"例如",
        r"例题",
    ),
    EducationSignalType.PROCEDURE_OR_STEP: (
        r"\bfirst(?:,|\s+(?:we|you|take|compute|do|find|set|choose)\b)",
        r"\bnext(?:,|\s+(?:we|you|take|compute|do|find|set|choose)\b)",
        r"\bstep\b",
        r"第一步",
        r"接下来",
    ),
    EducationSignalType.SUMMARY: (
        r"\bin summary\b",
        r"\bto summarize\b",
        r"总结",
        r"总之",
    ),
    EducationSignalType.COMMON_MISTAKE: (
        r"\bcommon mistake\b",
        r"\bdon'?t confuse\b",
        r"常见错误",
        r"不要混淆",
    ),
    EducationSignalType.DIFFICULT_POINT: (
        r"\bdifficult part\b",
        r"\btricky\b",
        r"难点",
        r"比较难",
    ),
    EducationSignalType.TEACHER_EMPHASIS: (
        r"\bformal definition\b",
        r"\bthe key point\b",
        r"\bpay attention\b",
        r"\bthis is important\b",
        r"\bremember\b",
        r"\blet me emphasize\b",
        r"这是重点",
        r"大家注意",
        r"这里很重要",
        r"记住",
    ),
    EducationSignalType.EXAM_RELEVANCE: (
        r"\bon the exam\b",
        r"\bexam will\b",
        r"考试会考",
        r"考点",
    ),
}

KNOWN_EDUCATION_TERMS = (
    "algorithm",
    "function",
    "input",
    "output",
    "problem",
    "binary relation",
    "recurrence",
    "theorem",
    "rule",
    "formula",
    "definition",
    "example",
    "算法",
    "函数",
    "输入",
    "输出",
    "问题",
    "二元关系",
    "递推",
    "定理",
    "规则",
    "公式",
    "定义",
    "例题",
)
PREVIOUS_CONTEXT_PATTERN = re.compile(
    (
        r"^\s*(?:(?:and\s+)?(?:then|similarly|likewise|therefore|thus)|"
        r"but|however|instead|also|because of this|so(?!\s+let'?s say)|"
        r"this|that|these|those|然后|接着|同样|类似地|但是|不过|因此|所以|由此)\b"
    ),
    flags=re.IGNORECASE,
)
FOLLOWING_CONTEXT_PATTERN = re.compile(
    r"(?:\bbecause|\bif|\bwhen|\bwhich|\bthat|因为|如果|当|也就是说)\s*[,:，：]?\s*$",  # noqa: RUF001
    flags=re.IGNORECASE,
)
DEPENDENT_TOPIC_CONTEXT_PATTERN = re.compile(
    r"^\s*(?:because|therefore|thus|so\b|this\b|that\b|because of this|因此|所以|因为)",
    flags=re.IGNORECASE,
)
TOKEN_PATTERN = re.compile(r"[A-Za-z0-9]+(?:-[A-Za-z]+)?")


def _transcript_reliability(text: str) -> float:
    tokens = [token.casefold() for token in TOKEN_PATTERN.findall(text)]
    if not tokens:
        return 0.0
    penalty = 0.0
    for first, second in pairwise(tokens):
        if first == second or second.startswith(f"{first}-"):
            penalty += 0.25
    penalty += 0.05 * sum(token in {"uh", "um"} for token in tokens)
    return max(0.0, 1.0 - penalty)


def extract_education_signals(candidate: CutCandidate) -> tuple[EducationSignal, ...]:
    evidence_refs = tuple(evidence.evidence_id for evidence in candidate.evidence_refs)
    signals: list[EducationSignal] = []
    seen_types: set[EducationSignalType] = set()
    semantic_spans = tuple(
        (span.text, span.language, span.start_ms, span.end_ms)
        for span in candidate.subtitle_semantic_spans
    )
    display_spans = tuple(
        (unit.source_text, unit.source_language, unit.start_ms, unit.end_ms)
        for unit in candidate.subtitle_display_units
    )
    source_spans = tuple(
        (cue.text, cue.language or "und", cue.start_ms, cue.end_ms)
        for cue in candidate.subtitle_cues
    )
    spans = semantic_spans or display_spans or source_spans
    for text, language, start_ms, end_ms in spans:
        for signal_type, patterns in SIGNAL_PATTERNS.items():
            if signal_type in seen_types:
                continue
            match = _first_match(text, patterns)
            if match is None:
                continue
            signals.append(
                EducationSignal(
                    signal_id=f"education-{candidate.candidate_id}-{signal_type.value}",
                    signal_type=signal_type,
                    matched_text=match,
                    key_terms=_key_terms(text),
                    context_roles=_context_roles(
                        text,
                        signal_type=signal_type,
                        candidate=candidate,
                        start_ms=start_ms,
                        end_ms=end_ms,
                    ),
                    language=language,
                    start_ms=start_ms,
                    end_ms=end_ms,
                    confidence=0.9 if signal_type is EducationSignalType.DEFINITION else 0.8,
                    evidence_refs=evidence_refs,
                )
            )
            seen_types.add(signal_type)
    return tuple(signals)


def _first_match(text: str, patterns: Iterable[str]) -> str | None:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match is not None:
            return match.group(0)
    return None


def _key_terms(text: str) -> tuple[str, ...]:
    normalized = text.casefold()
    terms = []
    for term in KNOWN_EDUCATION_TERMS:
        if term.casefold() not in normalized:
            continue
        canonical = {
            "inputs": "input",
            "outputs": "output",
        }.get(term, term)
        if canonical not in terms:
            terms.append(canonical)
    return tuple(terms)


def _context_roles(
    text: str,
    *,
    signal_type: EducationSignalType,
    candidate: CutCandidate,
    start_ms: int,
    end_ms: int,
) -> tuple[EducationContextRole, ...]:
    roles: list[EducationContextRole] = []
    if PREVIOUS_CONTEXT_PATTERN.search(text):
        roles.append(EducationContextRole.REQUIRES_PREVIOUS)
    if FOLLOWING_CONTEXT_PATTERN.search(text):
        roles.append(EducationContextRole.REQUIRES_FOLLOWING)
    if any(
        dependency.end_ms > start_ms and dependency.start_ms < end_ms
        for dependency in candidate.education_visual_dependencies
    ):
        roles.append(EducationContextRole.REQUIRES_VISUAL)
    if not roles:
        roles.append(EducationContextRole.SELF_CONTAINED)
    return tuple(roles)


def build_educational_profile(candidate: CutCandidate) -> EducationalCandidateProfile:
    signal_types = tuple(
        dict.fromkeys(signal.signal_type for signal in candidate.education_signals)
    )
    context_roles = tuple(
        dict.fromkeys(
            role for signal in candidate.education_signals for role in signal.context_roles
        )
    )
    visual_types = tuple(
        dict.fromkeys(
            dependency.dependency_type for dependency in candidate.education_visual_dependencies
        )
    )
    if visual_types and EducationContextRole.REQUIRES_VISUAL not in context_roles:
        context_roles = (*context_roles, EducationContextRole.REQUIRES_VISUAL)
    candidate_texts = (
        tuple(span.text for span in candidate.subtitle_semantic_spans)
        or tuple(unit.source_text for unit in candidate.subtitle_display_units)
        or tuple(cue.text for cue in candidate.subtitle_cues)
    )
    if any(FOLLOWING_CONTEXT_PATTERN.search(text) for text in candidate_texts):
        context_roles = (*context_roles, EducationContextRole.REQUIRES_FOLLOWING)
    if any(text.rstrip().endswith((",", ";", ":", "，", "；", "：")) for text in candidate_texts):  # noqa: RUF001
        context_roles = (*context_roles, EducationContextRole.REQUIRES_FOLLOWING)
    if EducationSignalType.DEFINITION not in signal_types and any(
        PREVIOUS_CONTEXT_PATTERN.search(text) for text in candidate_texts
    ):
        context_roles = (*context_roles, EducationContextRole.REQUIRES_PREVIOUS)
    context_roles = tuple(
        role
        for role in dict.fromkeys(context_roles)
        if role is not EducationContextRole.SELF_CONTAINED or len(context_roles) == 1
    )
    if not context_roles:
        context_roles = (EducationContextRole.SELF_CONTAINED,)
    key_terms = tuple(
        dict.fromkeys(
            key_term for signal in candidate.education_signals for key_term in signal.key_terms
        )
    )
    context_incomplete = bool(
        set(context_roles)
        & {
            EducationContextRole.REQUIRES_PREVIOUS,
            EducationContextRole.REQUIRES_FOLLOWING,
        }
    )
    has_structural_signal = bool(set(signal_types) & STRUCTURAL_EDUCATION_SIGNAL_TYPES)
    has_sufficient_statement = len(TOKEN_PATTERN.findall(candidate.summary)) >= 5
    completeness_confidence = (
        0.55
        if context_incomplete
        else (
            0.45
            if not has_sufficient_statement
            else (0.8 if EducationContextRole.REQUIRES_VISUAL in context_roles else 0.95)
        )
    )
    return EducationalCandidateProfile(
        candidate_id=candidate.candidate_id,
        qualified=(has_structural_signal and has_sufficient_statement and not context_incomplete),
        signal_types=signal_types,
        context_roles=context_roles,
        key_terms=key_terms,
        visual_dependency_types=visual_types,
        completeness_confidence=completeness_confidence,
    )


def attach_education_signals(candidate: CutCandidate) -> CutCandidate:
    with_signals = candidate.model_copy(
        update={"education_signals": extract_education_signals(candidate)}
    )
    return with_signals.model_copy(
        update={"educational_profile": build_educational_profile(with_signals)}
    )


def qualify_educational_candidate(
    candidate: CutCandidate,
    *,
    required_types: tuple[EducationSignalType, ...],
    required_topic_groups: tuple[tuple[str, ...], ...] = (),
    maximum_duration_ms: int | None = None,
    semantic_constraints_resolved: bool = True,
) -> EducationalQualification:
    matched = tuple(dict.fromkeys(signal.signal_type for signal in candidate.education_signals))
    matched_set = set(matched)
    missing = tuple(signal_type for signal_type in required_types if signal_type not in matched_set)
    has_structural_signal = bool(matched_set & STRUCTURAL_EDUCATION_SIGNAL_TYPES)
    reasons = []
    if missing:
        reasons.append("missing_required_education_signal")
    if not has_structural_signal:
        reasons.append("teacher_emphasis_alone_is_not_selectable")
    if len(TOKEN_PATTERN.findall(candidate.summary)) < 5:
        reasons.append("insufficient_educational_statement")
    profile = candidate.educational_profile or build_educational_profile(candidate)
    if EducationContextRole.REQUIRES_PREVIOUS in profile.context_roles:
        reasons.append("requires_previous_context")
    if EducationContextRole.REQUIRES_FOLLOWING in profile.context_roles:
        reasons.append("requires_following_context")
    candidate_text = candidate.summary.casefold()
    if (
        DEPENDENT_TOPIC_CONTEXT_PATTERN.search(candidate.summary)
        and candidate.evidence_refs
        and candidate.evidence_refs[0].snapshot is not None
    ):
        candidate_text = candidate.evidence_refs[0].snapshot.casefold()
    for group in required_topic_groups:
        if not any(term.casefold() in candidate_text for term in group):
            reasons.append(f"missing_topic_group:{'|'.join(group)}")
    if (
        maximum_duration_ms is not None
        and candidate.end_ms - candidate.start_ms > maximum_duration_ms
    ):
        reasons.append(f"exceeds_maximum_duration_ms:{maximum_duration_ms}")
    if not semantic_constraints_resolved:
        reasons.append("topic_constraints_require_host_resolution")
    return EducationalQualification(
        candidate_id=candidate.candidate_id,
        qualified=not reasons and has_structural_signal and profile.qualified,
        matched_types=matched,
        missing_types=missing,
        reasons=tuple(reasons),
    )


def select_educational_candidates(
    candidates: tuple[CutCandidate, ...],
    *,
    required_types: tuple[EducationSignalType, ...],
    required_count: int,
    forbidden_types: tuple[EducationSignalType, ...] = (),
    required_topic_groups: tuple[tuple[str, ...], ...] = (),
    maximum_duration_ms: int | None = None,
    semantic_constraints_resolved: bool = True,
) -> EducationalSelectionResult:
    if required_count < 1:
        raise ValueError("required_count must be at least one")
    qualifications = []
    forbidden_set = set(forbidden_types)
    for candidate in candidates:
        qualification = qualify_educational_candidate(
            candidate,
            required_types=required_types,
            required_topic_groups=required_topic_groups,
            maximum_duration_ms=maximum_duration_ms,
            semantic_constraints_resolved=semantic_constraints_resolved,
        )
        matched_set = set(qualification.matched_types)
        if matched_set & forbidden_set:
            qualification = qualification.model_copy(
                update={
                    "qualified": False,
                    "reasons": (*qualification.reasons, "contains_forbidden_education_type"),
                }
            )
        qualifications.append(qualification)
    qualification_tuple = tuple(qualifications)
    qualified_ids = {
        qualification.candidate_id
        for qualification in qualification_tuple
        if qualification.qualified
    }
    ranked = sorted(
        (candidate for candidate in candidates if candidate.candidate_id in qualified_ids),
        key=lambda candidate: (
            EducationSignalType.TEACHER_EMPHASIS
            in {signal.signal_type for signal in candidate.education_signals},
            len(candidate.education_signals),
            _transcript_reliability(candidate.summary),
            -candidate.start_ms,
            -(candidate.end_ms - candidate.start_ms),
        ),
        reverse=True,
    )
    selected: list[CutCandidate] = []
    covered_structural_types: set[EducationSignalType] = set()
    for candidate in ranked:
        structural_types = {
            signal.signal_type
            for signal in candidate.education_signals
            if signal.signal_type in STRUCTURAL_EDUCATION_SIGNAL_TYPES
        }
        if structural_types - covered_structural_types:
            selected.append(candidate)
            covered_structural_types.update(structural_types)
        if len(selected) == required_count:
            break
    if len(selected) < required_count:
        selected_ids_so_far = {candidate.candidate_id for candidate in selected}
        selected.extend(
            candidate for candidate in ranked if candidate.candidate_id not in selected_ids_so_far
        )
    selected_ids = tuple(candidate.candidate_id for candidate in selected[:required_count])
    unsatisfied = (
        ()
        if len(selected_ids) == required_count
        else (f"educational_required_count:{required_count}",)
    )
    return EducationalSelectionResult(
        selected_candidate_ids=selected_ids,
        qualifications=qualification_tuple,
        unsatisfied_requirements=unsatisfied,
    )
