from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from universal_cutup.domain.errors import CutupError, ErrorCode
from universal_cutup.domain.intelligence import (
    ALL_DIMENSION_KEYS,
    CandidateProposalPolicy,
    CapabilityProfile,
    ClipConstraints,
    ContentProfile,
    ControlMode,
    DecisionSource,
    DimensionApplicability,
    DimensionKey,
    DimensionPolicy,
    DurationSource,
    ExplanationPolicy,
    HostIntent,
    ResolutionTraceEntry,
    ResolvedTaskProfile,
    SelectionPolicy,
    SemanticRequirements,
    SemanticType,
    TaskPreset,
)

CONTENT_EMPHASIS: dict[str, tuple[DimensionKey, ...]] = {
    "lecture": (DimensionKey.INSIGHT, DimensionKey.CLARITY, DimensionKey.COMPLETION),
    "course": (DimensionKey.INSIGHT, DimensionKey.CLARITY, DimensionKey.COMPLETION),
    "knowledge": (DimensionKey.INSIGHT, DimensionKey.CLARITY, DimensionKey.COMPLETION),
    "story": (DimensionKey.EMOTION, DimensionKey.COMPLETION, DimensionKey.EDITABILITY),
    "drama": (DimensionKey.EMOTION, DimensionKey.COMPLETION, DimensionKey.EDITABILITY),
    "narrative": (DimensionKey.EMOTION, DimensionKey.COMPLETION, DimensionKey.EDITABILITY),
    "tutorial": (
        DimensionKey.CLARITY,
        DimensionKey.COMPLETION,
        DimensionKey.SUBTITLE_RELIABILITY,
    ),
    "manual": (
        DimensionKey.CLARITY,
        DimensionKey.COMPLETION,
        DimensionKey.SUBTITLE_RELIABILITY,
    ),
    "product_instruction": (
        DimensionKey.CLARITY,
        DimensionKey.COMPLETION,
        DimensionKey.SUBTITLE_RELIABILITY,
    ),
    "interview": (DimensionKey.INSIGHT, DimensionKey.QUOTABILITY, DimensionKey.STANDALONE),
    "podcast": (DimensionKey.INSIGHT, DimensionKey.QUOTABILITY, DimensionKey.STANDALONE),
}
NARRATIVE_TYPES = frozenset({"story", "drama", "narrative"})
HOOK_OBJECTIVES = frozenset({"hook", "three_second_hook", "viral_hook"})
DEFAULT_PREFERRED_DURATION_MS = 60_000
DEFAULT_MAX_DURATION_MS = 60_000
ABSOLUTE_AUTO_MAX_DURATION_MS = 120_000

SEMANTIC_OBJECTIVES: tuple[tuple[str, SemanticType, tuple[str, ...]], ...] = (
    ("definition", SemanticType.DEFINITION, ()),
    (
        "reasoning",
        SemanticType.REASONING_CHAIN,
        ("premise", "reasoning", "conclusion"),
    ),
    ("conflict", SemanticType.CONFLICT, ()),
    ("hook", SemanticType.HOOK, ()),
    ("step", SemanticType.STEP, ()),
    (
        "story_arc",
        SemanticType.STORY_ARC,
        ("setup", "development", "resolution"),
    ),
    (
        "sequence",
        SemanticType.STORY_ARC,
        ("setup", "development", "resolution"),
    ),
)


def _fallback_policy(dimension: DimensionKey) -> DimensionPolicy:
    return DimensionPolicy(
        dimension=dimension,
        applicability=DimensionApplicability.ADVISORY,
        rationale="Registered as advisory until task evidence makes it applicable",
        source=DecisionSource.FALLBACK,
    )


def _content_policies(
    content_profile: ContentProfile | None,
) -> dict[DimensionKey, DimensionPolicy]:
    policies = {dimension: _fallback_policy(dimension) for dimension in ALL_DIMENSION_KEYS}
    if content_profile is None:
        return policies
    emphasized: set[DimensionKey] = set()
    for content_type in content_profile.content_types:
        emphasized.update(CONTENT_EMPHASIS.get(content_type, ()))
    for dimension in emphasized:
        policies[dimension] = DimensionPolicy(
            dimension=dimension,
            applicability=DimensionApplicability.WEIGHTED,
            weight=1.0,
            rationale=(
                "Provisional alpha emphasis inferred from content labels; "
                "not a frozen production weight"
            ),
            source=DecisionSource.CONTENT_INFERENCE,
            confidence=content_profile.confidence,
        )
    if content_profile.dependencies.visual >= 0.8:
        policies[DimensionKey.VISUAL_INDEPENDENCE] = DimensionPolicy(
            dimension=DimensionKey.VISUAL_INDEPENDENCE,
            applicability=DimensionApplicability.NOT_APPLICABLE,
            rationale="The source is intentionally visual-dependent",
            source=DecisionSource.CONTENT_INFERENCE,
            confidence=content_profile.confidence,
        )
    return policies


def _apply_policy_layer(
    current: dict[DimensionKey, DimensionPolicy],
    incoming: tuple[DimensionPolicy, ...],
) -> None:
    for policy in incoming:
        current[policy.dimension] = policy


def _capability_conflicts(
    host_intent: HostIntent,
    capability_profile: CapabilityProfile,
) -> tuple[str, ...]:
    requested = {
        *host_intent.subtitle_requirements,
        *host_intent.visual_requirements,
    }
    conflicts = requested & set(capability_profile.unavailable_features)
    maximum = capability_profile.maximum_clip_duration_ms
    target = host_intent.clip_constraints.target_duration_ms
    if maximum is not None and target is not None and target > maximum:
        conflicts.add("target_duration_ms")
    return tuple(sorted(conflicts))


def _resolved_constraints(
    host_intent: HostIntent,
    content_profile: ContentProfile | None,
) -> tuple[ClipConstraints, DecisionSource]:
    host_values = host_intent.clip_constraints.model_dump(mode="json", exclude_none=True)
    inferred = (
        content_profile.auto_clip_constraints
        if content_profile is not None
        and host_intent.control_mode in {ControlMode.AUTO, ControlMode.GUIDED}
        else None
    )
    inferred_values = (
        inferred.model_dump(mode="json", exclude_none=True) if inferred is not None else {}
    )
    merged = {**inferred_values, **host_values}
    explicit_duration = any(
        key in host_values
        for key in ("minimum_duration_ms", "maximum_duration_ms", "target_duration_ms")
    )
    duration_source = (
        DurationSource.HOST_EXPLICIT
        if explicit_duration
        else (
            DurationSource.CONTENT_INFERENCE
            if any(
                key in inferred_values
                for key in ("minimum_duration_ms", "maximum_duration_ms", "target_duration_ms")
            )
            else DurationSource.DEFAULT_POLICY
        )
    )
    requested_duration = (
        host_values.get("target_duration_ms")
        or host_values.get("maximum_duration_ms")
        or host_values.get("minimum_duration_ms")
    )
    host_long_form_override = host_intent.control_mode is ControlMode.DIRECTED and explicit_duration
    if not host_long_form_override:
        inferred_maximum = merged.get("maximum_duration_ms")
        merged["maximum_duration_ms"] = min(
            inferred_maximum or ABSOLUTE_AUTO_MAX_DURATION_MS,
            ABSOLUTE_AUTO_MAX_DURATION_MS,
        )
    merged.update(
        preferred_duration_ms=merged.get("preferred_duration_ms", DEFAULT_PREFERRED_DURATION_MS),
        default_max_duration_ms=DEFAULT_MAX_DURATION_MS,
        absolute_auto_max_duration_ms=ABSOLUTE_AUTO_MAX_DURATION_MS,
        host_requested_duration_ms=requested_duration,
        duration_source=duration_source,
    )
    source = (
        DecisionSource.HOST_EXPLICIT
        if host_values
        else (DecisionSource.CONTENT_INFERENCE if inferred_values else DecisionSource.FALLBACK)
    )
    return ClipConstraints.model_validate(merged), source


def _semantic_requirements(
    host_intent: HostIntent,
    objectives: tuple[str, ...],
) -> SemanticRequirements | None:
    if host_intent.semantic_requirements is not None:
        return host_intent.semantic_requirements
    normalized = " ".join(objectives).casefold()
    for marker, semantic_type, structure in SEMANTIC_OBJECTIVES:
        if marker not in normalized:
            continue
        requested_count = (
            host_intent.clip_constraints.target_count
            or host_intent.clip_constraints.minimum_count
            or 1
        )
        return SemanticRequirements(
            semantic_type=semantic_type,
            required_count=requested_count,
            required_structure=structure,
            sequence_constraint=(
                "chronological" if semantic_type is SemanticType.STORY_ARC else None
            ),
        )
    return None


def resolve_task_profile(
    host_intent: HostIntent,
    content_profile: ContentProfile | None,
    *,
    preset: TaskPreset | None = None,
    capability_profile: CapabilityProfile | None = None,
    created_at: datetime | None = None,
    resolved_task_id: str | None = None,
) -> ResolvedTaskProfile:
    if host_intent.control_mode is ControlMode.AUTO and content_profile is None:
        raise CutupError(
            ErrorCode.PROVIDER_REQUIRED,
            "AUTO mode requires a ContentProfile or a configured content intelligence provider",
            category="provider",
            step="resolve_task",
            recoverable=True,
        )
    resolved_capabilities = capability_profile or CapabilityProfile()
    conflicts = _capability_conflicts(host_intent, resolved_capabilities)
    if conflicts:
        raise CutupError(
            ErrorCode.CAPABILITY_CONFLICT,
            "host requirements conflict with available capabilities",
            category="capability",
            step="resolve_task",
            details={"conflicts": list(conflicts)},
        )

    policies = _content_policies(content_profile)
    if preset is not None:
        _apply_policy_layer(policies, preset.dimension_policies)
    _apply_policy_layer(policies, host_intent.dimension_policies)

    if set(host_intent.desired_outcomes) & HOOK_OBJECTIVES:
        policies[DimensionKey.HOOK] = DimensionPolicy(
            dimension=DimensionKey.HOOK,
            applicability=DimensionApplicability.REQUIRED,
            minimum=0,
            rationale="Host explicitly requested a hook; alpha threshold remains non-exclusionary",
            source=DecisionSource.HOST_EXPLICIT,
        )
        if DimensionKey.COMPLETION not in {
            policy.dimension for policy in host_intent.dimension_policies
        }:
            policies[DimensionKey.COMPLETION] = DimensionPolicy(
                dimension=DimensionKey.COMPLETION,
                applicability=DimensionApplicability.ADVISORY,
                rationale="A short hook need not form a complete argument",
                source=DecisionSource.HOST_EXPLICIT,
            )

    objectives = host_intent.desired_outcomes
    objective_source = DecisionSource.HOST_EXPLICIT
    if not objectives and preset is not None and preset.objectives:
        objectives = preset.objectives
        objective_source = DecisionSource.HOST_PRESET
    if not objectives and content_profile is not None:
        objectives = (
            content_profile.auto_objectives
            or content_profile.value_sources
            or (f"extract_value_from_{content_profile.content_types[0]}",)
        )
        objective_source = DecisionSource.CONTENT_INFERENCE
    if not objectives:
        objectives = ("produce_explainable_candidates",)
        objective_source = DecisionSource.FALLBACK

    inferred_order = bool(
        content_profile and NARRATIVE_TYPES.intersection(content_profile.content_types)
    )
    preserve_order = inferred_order
    order_source = DecisionSource.CONTENT_INFERENCE
    if preset is not None and preset.preserve_time_order is not None:
        preserve_order = preset.preserve_time_order
        order_source = DecisionSource.HOST_PRESET
    if host_intent.preserve_time_order is not None:
        preserve_order = host_intent.preserve_time_order
        order_source = DecisionSource.HOST_EXPLICIT

    prefer_track_diversity = bool(content_profile and len(content_profile.tracks) > 1)
    require_track_diversity = False
    diversity_source = DecisionSource.FALLBACK
    if preset is not None and preset.require_track_diversity is not None:
        require_track_diversity = preset.require_track_diversity
        diversity_source = DecisionSource.HOST_PRESET
    if host_intent.require_track_diversity is not None:
        require_track_diversity = host_intent.require_track_diversity
        diversity_source = DecisionSource.HOST_EXPLICIT

    resolved_constraints, constraint_source = _resolved_constraints(host_intent, content_profile)
    semantic_requirements = _semantic_requirements(host_intent, objectives)
    trace = [
        ResolutionTraceEntry(
            decision_path="final_objectives",
            source=objective_source,
            value=list(objectives),
            rationale="Resolved using the frozen host-first priority order",
        ),
        ResolutionTraceEntry(
            decision_path="selection_policy.preserve_time_order",
            source=order_source,
            value=preserve_order,
            rationale="Explicit host choice overrides preset and content inference",
        ),
        ResolutionTraceEntry(
            decision_path="hard_constraints",
            source=constraint_source,
            value=resolved_constraints.model_dump(mode="json", exclude_none=True),
            rationale=(
                "Explicit host values override content-inferred AUTO/GUIDED recommendations"
            ),
        ),
        ResolutionTraceEntry(
            decision_path="prohibited_outcomes",
            source=DecisionSource.HOST_EXPLICIT,
            value=list(host_intent.prohibited_outcomes),
            rationale="Host prohibitions are never inferred away",
        ),
        ResolutionTraceEntry(
            decision_path="candidate_policy.allow_context_dependency",
            source=(
                DecisionSource.HOST_EXPLICIT
                if host_intent.allow_context_dependency is not None
                else DecisionSource.FALLBACK
            ),
            value=host_intent.allow_context_dependency or False,
            rationale="Use the host choice when present, otherwise the conservative fallback",
        ),
        ResolutionTraceEntry(
            decision_path="selection_policy.prefer_track_diversity",
            source=DecisionSource.CONTENT_INFERENCE,
            value=prefer_track_diversity,
            rationale="Multiple inferred content tracks create a soft ordering preference only",
        ),
        ResolutionTraceEntry(
            decision_path="selection_policy.require_track_diversity",
            source=diversity_source,
            value=require_track_diversity,
            rationale=(
                "Strong track coverage is enabled only by an explicit host or preset choice"
            ),
        ),
        ResolutionTraceEntry(
            decision_path="selection_policy.maximum_overlap_ratio",
            source=DecisionSource.FALLBACK,
            value=0.2,
            rationale="Alpha protocol fallback; not a frozen content-quality threshold",
        ),
        ResolutionTraceEntry(
            decision_path="selection_policy.duplicate_similarity_threshold",
            source=DecisionSource.FALLBACK,
            value=0.85,
            rationale="Alpha protocol fallback; not a frozen content-quality threshold",
        ),
        ResolutionTraceEntry(
            decision_path="capability_profile",
            source=DecisionSource.SYSTEM_CAPABILITY,
            value=resolved_capabilities.model_dump(mode="json", exclude_none=True),
            rationale="Capabilities may block execution but do not rewrite host goals",
        ),
        ResolutionTraceEntry(
            decision_path="semantic_requirements",
            source=DecisionSource.HOST_EXPLICIT,
            value=(
                semantic_requirements.model_dump(mode="json", exclude_none=True)
                if semantic_requirements is not None
                else {}
            ),
            rationale="Desired outcomes resolve to verifiable semantic eligibility before ranking",
        ),
    ]
    trace.extend(
        ResolutionTraceEntry(
            decision_path=f"dimension_policies.{dimension.value}",
            source=policy.source,
            value=policy.model_dump(mode="json", exclude_none=True),
            rationale=policy.rationale,
        )
        for dimension, policy in policies.items()
    )
    warnings: list[str] = []
    if host_intent.dimension_policies and content_profile is not None:
        warnings.append("host_explicit dimension policy overrides content inference")

    return ResolvedTaskProfile(
        document_type="resolved_task_profile",
        created_at=created_at or datetime.now(UTC),
        created_by="universal-cutup",
        resolved_task_id=resolved_task_id or str(uuid4()),
        host_intent_id=host_intent.intent_id,
        content_profile_id=content_profile.profile_id if content_profile else None,
        control_mode=host_intent.control_mode,
        final_objectives=objectives,
        prohibited_outcomes=host_intent.prohibited_outcomes,
        hard_constraints=resolved_constraints,
        hard_include_candidate_ids=host_intent.hard_include_candidate_ids,
        hard_exclude_candidate_ids=host_intent.hard_exclude_candidate_ids,
        dimension_policies=tuple(policies[dimension] for dimension in ALL_DIMENSION_KEYS),
        candidate_policy=CandidateProposalPolicy(
            allow_context_dependency=host_intent.allow_context_dependency or False,
            preferred_track_ids=(
                tuple(track.track_id for track in content_profile.tracks) if content_profile else ()
            ),
        ),
        selection_policy=SelectionPolicy(
            prefer_track_diversity=prefer_track_diversity,
            require_track_diversity=require_track_diversity,
            preserve_time_order=preserve_order,
        ),
        explanation_policy=ExplanationPolicy(),
        resolution_trace=tuple(trace),
        warnings=tuple(warnings),
        semantic_requirements=semantic_requirements,
    )
