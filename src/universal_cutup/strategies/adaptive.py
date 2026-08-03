from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from uuid import uuid4

from universal_cutup.domain.assessments import (
    AdaptiveSelectionDecision,
    AdaptiveSelectionResult,
    AssessmentBundle,
    CandidateAggregate,
    CandidateAssessment,
)
from universal_cutup.domain.candidates import CutCandidate
from universal_cutup.domain.errors import CutupError, ErrorCode
from universal_cutup.domain.intelligence import (
    DimensionApplicability,
    DimensionKey,
    ResolvedTaskProfile,
)
from universal_cutup.hashing import document_sha256

CALCULATION_VERSION = "adaptive-highlight14/0.2.0-gate-i"


def _candidate_evidence_ids(candidate: CutCandidate) -> set[str]:
    return {evidence.evidence_id for evidence in candidate.evidence_refs}


def aggregate_candidate(
    candidate: CutCandidate,
    assessment: CandidateAssessment,
    task_profile: ResolvedTaskProfile,
) -> CandidateAggregate:
    if assessment.candidate_id != candidate.candidate_id:
        raise CutupError(
            ErrorCode.ASSESSMENT_INVALID,
            "assessment candidate_id does not match candidate",
        )
    assessments = {item.dimension: item for item in assessment.dimensions}
    policies = {item.dimension: item for item in task_profile.dimension_policies}
    if set(assessments) != set(policies):
        raise CutupError(
            ErrorCode.ASSESSMENT_INVALID,
            "assessment must contain each registered dimension exactly once",
        )
    evidence_ids = _candidate_evidence_ids(candidate)
    for dimension_assessment in assessment.dimensions:
        if not set(dimension_assessment.evidence_refs) <= evidence_ids:
            raise CutupError(
                ErrorCode.ASSESSMENT_INVALID,
                f"{dimension_assessment.dimension.value} references unknown evidence",
            )

    participating: dict[DimensionKey, tuple[float, float]] = {}
    advisory: dict[DimensionKey, float] = {}
    exclusions: list[str] = []
    for dimension, policy in policies.items():
        dimension_assessment = assessments[dimension]
        if policy.applicability is DimensionApplicability.NOT_APPLICABLE:
            continue
        if dimension_assessment.score is None:
            if policy.applicability is DimensionApplicability.REQUIRED:
                exclusions.append(f"{dimension.value}:unavailable")
            continue
        score = dimension_assessment.score
        if policy.applicability is DimensionApplicability.ADVISORY:
            advisory[dimension] = score
        if policy.applicability is DimensionApplicability.REQUIRED:
            if policy.minimum is not None and score < policy.minimum:
                exclusions.append(f"{dimension.value}:below_minimum")
            if policy.weight is not None:
                participating[dimension] = (score, policy.weight)
        elif policy.applicability is DimensionApplicability.WEIGHTED:
            participating[dimension] = (score, policy.weight or 0)

    total_weight = sum(weight for _, weight in participating.values())
    normalized = (
        {dimension: weight / total_weight for dimension, (_, weight) in participating.items()}
        if total_weight > 0
        else {}
    )
    overall = (
        sum(participating[dimension][0] * weight for dimension, weight in normalized.items())
        if normalized
        else None
    )
    input_hash = document_sha256(
        {
            "candidate": candidate.model_dump(mode="json"),
            "assessment": assessment.model_dump(mode="json"),
            "task_profile": task_profile.model_dump(mode="json"),
            "calculation_version": CALCULATION_VERSION,
        }
    )
    return CandidateAggregate(
        candidate_id=candidate.candidate_id,
        overall=overall,
        normalized_weights=normalized,
        required_passed=not exclusions,
        exclusion_reasons=tuple(exclusions),
        advisory_scores=advisory,
        calculation_version=CALCULATION_VERSION,
        input_sha256=input_hash,
        model_reported_overall_ignored=assessment.model_reported_overall,
    )


def aggregate_bundle(
    candidates: tuple[CutCandidate, ...],
    bundle: AssessmentBundle,
    task_profile: ResolvedTaskProfile,
) -> tuple[CandidateAggregate, ...]:
    candidates_by_id = {candidate.candidate_id: candidate for candidate in candidates}
    assessment_ids = {assessment.candidate_id for assessment in bundle.candidates}
    if assessment_ids != set(candidates_by_id):
        raise CutupError(
            ErrorCode.ASSESSMENT_INVALID,
            "assessment bundle must cover every candidate exactly once",
        )
    return tuple(
        aggregate_candidate(
            candidates_by_id[assessment.candidate_id],
            assessment,
            task_profile,
        )
        for assessment in bundle.candidates
    )


def _overlap_ratio(first: CutCandidate, second: CutCandidate) -> float:
    overlap = max(0, min(first.end_ms, second.end_ms) - max(first.start_ms, second.start_ms))
    shorter = min(first.end_ms - first.start_ms, second.end_ms - second.start_ms)
    return overlap / shorter if shorter else 0


def _token_similarity(first: str, second: str) -> float:
    first_tokens = set(first.casefold().split())
    second_tokens = set(second.casefold().split())
    union = first_tokens | second_tokens
    return len(first_tokens & second_tokens) / len(union) if union else 1


def _same_series(first: CutCandidate, second: CutCandidate) -> bool:
    return first.series_group_id is not None and first.series_group_id == second.series_group_id


def _within_duration(candidate: CutCandidate, task_profile: ResolvedTaskProfile) -> bool:
    duration = candidate.end_ms - candidate.start_ms
    constraints = task_profile.hard_constraints
    if constraints.minimum_duration_ms is not None and duration < constraints.minimum_duration_ms:
        return False
    if constraints.maximum_duration_ms is not None and duration > constraints.maximum_duration_ms:
        return False
    return not (
        constraints.default_max_duration_ms is not None
        and duration > constraints.default_max_duration_ms
        and constraints.host_requested_duration_ms is None
        and not candidate.extension_reason
    )


def _missing_semantic_qualifications(
    candidate: CutCandidate,
    task_profile: ResolvedTaskProfile,
) -> tuple[str, ...]:
    requirements = task_profile.semantic_requirements
    if requirements is None:
        return ()
    missing: list[str] = []
    if (
        requirements.semantic_type is not None
        and requirements.semantic_type not in candidate.semantic_types
    ):
        missing.append(f"semantic_type:{requirements.semantic_type.value}")
    if requirements.required_count == 1 and candidate.series_group_id is None:
        absent_structure = set(requirements.required_structure) - set(candidate.semantic_structure)
        missing.extend(f"structure:{item}" for item in sorted(absent_structure))
    forbidden = set(requirements.forbidden_types) & set(candidate.semantic_types)
    missing.extend(f"forbidden_type:{item.value}" for item in sorted(forbidden))
    if requirements.topic_constraint is not None:
        topic = requirements.topic_constraint.casefold()
        candidate_topics = " ".join((*candidate.topics, candidate.summary)).casefold()
        if topic not in candidate_topics:
            missing.append(f"topic:{requirements.topic_constraint}")
    if (
        requirements.speaker_constraint is not None
        and requirements.speaker_constraint.casefold()
        not in {speaker.casefold() for speaker in candidate.speakers}
    ):
        missing.append(f"speaker:{requirements.speaker_constraint}")
    if requirements.sequence_constraint is not None and candidate.series_group_id is None:
        sequence = requirements.sequence_constraint.casefold()
        if sequence not in {item.casefold() for item in candidate.semantic_structure}:
            missing.append(f"sequence:{requirements.sequence_constraint}")
    return tuple(missing)


def _ranked_candidates(
    candidates: Iterable[CutCandidate],
    aggregates: dict[str, CandidateAggregate],
    task_profile: ResolvedTaskProfile,
) -> list[CutCandidate]:
    preferred = task_profile.hard_constraints.preferred_duration_ms
    return sorted(
        candidates,
        key=lambda candidate: (
            (preferred is None or candidate.end_ms - candidate.start_ms <= preferred),
            aggregates[candidate.candidate_id].overall is not None,
            aggregates[candidate.candidate_id].overall or 0,
            -candidate.start_ms,
        ),
        reverse=True,
    )


def _prefer_new_tracks(
    candidates: list[CutCandidate],
    assessments: dict[str, CandidateAssessment],
) -> list[CutCandidate]:
    """Move the best first representative of each track ahead without rejecting anything."""
    preferred: list[CutCandidate] = []
    remaining: list[CutCandidate] = []
    seen_tracks: set[str] = set()
    for candidate in candidates:
        candidate_tracks = set(assessments[candidate.candidate_id].content_track_ids)
        if candidate_tracks - seen_tracks:
            preferred.append(candidate)
            seen_tracks.update(candidate_tracks)
        else:
            remaining.append(candidate)
    return [*preferred, *remaining]


def _validate_hard_selection_requirements(
    candidates: tuple[CutCandidate, ...],
    task_profile: ResolvedTaskProfile,
    assessments: dict[str, CandidateAssessment],
) -> None:
    hard_include = set(task_profile.hard_include_candidate_ids)
    candidates_by_id = {candidate.candidate_id: candidate for candidate in candidates}
    maximum_count = task_profile.hard_constraints.maximum_count
    if maximum_count is not None and len(hard_include) > maximum_count:
        raise CutupError(
            ErrorCode.HOST_INTENT_CONFLICT,
            "hard-included candidates exceed maximum_count",
            details={
                "hard_include_candidate_ids": sorted(hard_include),
                "maximum_count": maximum_count,
            },
        )
    duration_conflicts = sorted(
        candidate_id
        for candidate_id in hard_include
        if not _within_duration(candidates_by_id[candidate_id], task_profile)
    )
    if duration_conflicts:
        raise CutupError(
            ErrorCode.HOST_INTENT_CONFLICT,
            "hard-included candidates conflict with hard duration constraints",
            details={"candidate_ids": duration_conflicts},
        )
    if task_profile.selection_policy.require_track_diversity:
        used_tracks: set[str] = set()
        duplicate_track_candidates: list[str] = []
        for candidate_id in sorted(hard_include):
            candidate_tracks = set(assessments[candidate_id].content_track_ids)
            if used_tracks and candidate_tracks <= used_tracks:
                duplicate_track_candidates.append(candidate_id)
            used_tracks.update(candidate_tracks)
        if duplicate_track_candidates:
            raise CutupError(
                ErrorCode.HOST_INTENT_CONFLICT,
                "hard-included candidates conflict with required track diversity",
                details={"candidate_ids": duplicate_track_candidates},
            )


def select_adaptive(
    candidates: tuple[CutCandidate, ...],
    assessments: tuple[CandidateAssessment, ...],
    aggregates: tuple[CandidateAggregate, ...],
    task_profile: ResolvedTaskProfile,
    *,
    created_at: datetime | None = None,
) -> AdaptiveSelectionResult:
    assessments_by_id = {assessment.candidate_id: assessment for assessment in assessments}
    aggregates_by_id = {aggregate.candidate_id: aggregate for aggregate in aggregates}
    candidate_ids = {candidate.candidate_id for candidate in candidates}
    if set(assessments_by_id) != candidate_ids or set(aggregates_by_id) != candidate_ids:
        raise CutupError(
            ErrorCode.ASSESSMENT_INVALID,
            "selection inputs must cover every candidate exactly once",
        )
    hard_include = set(task_profile.hard_include_candidate_ids)
    hard_exclude = set(task_profile.hard_exclude_candidate_ids)
    if not (hard_include | hard_exclude) <= candidate_ids:
        raise CutupError(
            ErrorCode.HOST_INTENT_CONFLICT,
            "hard include/exclude references unknown candidate",
        )
    _validate_hard_selection_requirements(candidates, task_profile, assessments_by_id)

    target = (
        task_profile.hard_constraints.target_count
        or task_profile.hard_constraints.maximum_count
        or len(candidates)
    )
    selected: list[CutCandidate] = []
    reasons: dict[str, list[str]] = {candidate.candidate_id: [] for candidate in candidates}
    ordered = _ranked_candidates(candidates, aggregates_by_id, task_profile)
    if task_profile.selection_policy.prefer_track_diversity:
        ordered = _prefer_new_tracks(ordered, assessments_by_id)
    ordered.sort(key=lambda candidate: candidate.candidate_id not in hard_include)
    for candidate in ordered:
        candidate_id = candidate.candidate_id
        aggregate = aggregates_by_id[candidate_id]
        if candidate_id in hard_exclude:
            reasons[candidate_id].append("host_hard_exclude")
            continue
        if candidate_id not in hard_include and not aggregate.required_passed:
            reasons[candidate_id].extend(aggregate.exclusion_reasons)
            continue
        missing_qualifications = _missing_semantic_qualifications(candidate, task_profile)
        if candidate_id not in hard_include and missing_qualifications:
            reasons[candidate_id].extend(
                f"semantic_qualification:{item}" for item in missing_qualifications
            )
            continue
        if candidate_id not in hard_include and not _within_duration(candidate, task_profile):
            reasons[candidate_id].append("duration_constraint")
            continue
        if len(selected) >= target and candidate_id not in hard_include:
            reasons[candidate_id].append("count_limit")
            continue
        if candidate_id not in hard_include and any(
            not _same_series(candidate, existing)
            and _overlap_ratio(candidate, existing)
            > task_profile.selection_policy.maximum_overlap_ratio
            for existing in selected
        ):
            reasons[candidate_id].append("overlap_limit")
            continue
        if candidate_id not in hard_include and any(
            not _same_series(candidate, existing)
            and _token_similarity(candidate.summary, existing.summary)
            >= task_profile.selection_policy.duplicate_similarity_threshold
            for existing in selected
        ):
            reasons[candidate_id].append("duplicate_content")
            continue
        if (
            candidate_id not in hard_include
            and task_profile.selection_policy.require_track_diversity
            and selected
        ):
            used_tracks = {
                track_id
                for existing in selected
                for track_id in assessments_by_id[existing.candidate_id].content_track_ids
            }
            if set(assessments_by_id[candidate_id].content_track_ids) <= used_tracks:
                reasons[candidate_id].append("track_diversity")
                continue
        reasons[candidate_id].append(
            "host_hard_include" if candidate_id in hard_include else "ranked_selection"
        )
        selected.append(candidate)

    if task_profile.selection_policy.preserve_time_order:
        selected.sort(key=lambda candidate: candidate.start_ms)
    unsatisfied: list[str] = []
    minimum = task_profile.hard_constraints.minimum_count
    if minimum is not None and len(selected) < minimum:
        unsatisfied.append(f"minimum_count:{minimum}")
    if not hard_include <= {candidate.candidate_id for candidate in selected}:
        unsatisfied.append("hard_include")
    semantic_required_count = (
        task_profile.semantic_requirements.required_count
        if task_profile.semantic_requirements is not None
        else None
    )
    if semantic_required_count is not None and len(selected) < semantic_required_count:
        unsatisfied.append(f"semantic_required_count:{semantic_required_count}")
    if task_profile.semantic_requirements is not None and selected:
        required_structure = set(task_profile.semantic_requirements.required_structure)
        selected_structure = {
            item for candidate in selected for item in candidate.semantic_structure
        }
        for missing_structure in sorted(required_structure - selected_structure):
            unsatisfied.append(f"semantic_structure:{missing_structure}")
        if task_profile.semantic_requirements.sequence_constraint == "chronological":
            indices = [candidate.series_index for candidate in selected]
            concrete_indices = [index for index in indices if index is not None]
            if len(concrete_indices) != len(indices) or concrete_indices != sorted(
                concrete_indices
            ):
                unsatisfied.append("sequence:chronological")
    nearest = sorted(
        (
            candidate
            for candidate in candidates
            if candidate.candidate_id not in {item.candidate_id for item in selected}
        ),
        key=lambda candidate: (
            len(_missing_semantic_qualifications(candidate, task_profile)),
            -(aggregates_by_id[candidate.candidate_id].overall or 0),
        ),
    )
    ranks = {candidate.candidate_id: rank for rank, candidate in enumerate(selected, start=1)}
    decisions = tuple(
        AdaptiveSelectionDecision(
            candidate_id=candidate.candidate_id,
            selected=candidate.candidate_id in ranks,
            rank=ranks.get(candidate.candidate_id),
            reasons=tuple(reasons[candidate.candidate_id]),
            overall=aggregates_by_id[candidate.candidate_id].overall,
            semantic_qualified=not _missing_semantic_qualifications(
                candidate,
                task_profile,
            ),
            missing_qualifications=_missing_semantic_qualifications(
                candidate,
                task_profile,
            ),
        )
        for candidate in candidates
    )
    input_hash = document_sha256(
        {
            "candidates": [candidate.model_dump(mode="json") for candidate in candidates],
            "assessments": [assessment.model_dump(mode="json") for assessment in assessments],
            "aggregates": [aggregate.model_dump(mode="json") for aggregate in aggregates],
            "task_profile": task_profile.model_dump(mode="json"),
            "calculation_version": CALCULATION_VERSION,
        }
    )
    return AdaptiveSelectionResult(
        document_type="adaptive_selection_result",
        created_at=created_at or datetime.now(UTC),
        created_by="universal-cutup",
        selection_id=str(uuid4()),
        decisions=decisions,
        selected_candidate_ids=tuple(candidate.candidate_id for candidate in selected),
        unsatisfied_constraints=tuple(unsatisfied),
        nearest_candidate_ids=tuple(
            candidate.candidate_id
            for candidate in nearest[:3]
            if _missing_semantic_qualifications(candidate, task_profile)
        ),
        calculation_version=CALCULATION_VERSION,
        input_sha256=input_hash,
    )
