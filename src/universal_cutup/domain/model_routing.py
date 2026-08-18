from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from types import MappingProxyType

from pydantic import Field, model_validator

from .common import FrozenModel


class ModelTier(StrEnum):
    DETERMINISTIC = "deterministic"
    ECONOMY = "economy"
    BALANCED = "balanced"
    FRONTIER = "frontier"


class ModelTask(StrEnum):
    PROTOCOL_VALIDATION = "protocol_validation"
    HASHING_AND_PROVENANCE = "hashing_and_provenance"
    SELECTION_ARITHMETIC = "selection_arithmetic"
    SUBTITLE_LAYOUT = "subtitle_layout"
    MEDIA_EXECUTION = "media_execution"
    TRANSCRIPT_CLEANUP = "transcript_cleanup"
    LANGUAGE_SEGMENTATION = "language_segmentation"
    KEYWORD_EXTRACTION = "keyword_extraction"
    CANDIDATE_PREFILTER = "candidate_prefilter"
    TITLE_DRAFT = "title_draft"
    CONTENT_PROFILE = "content_profile"
    INTENT_INTERPRETATION = "intent_interpretation"
    CANDIDATE_PROPOSAL = "candidate_proposal"
    DIMENSION_ASSESSMENT = "dimension_assessment"
    SEMANTIC_SUBTITLE_GROUPING = "semantic_subtitle_grouping"
    CONTEXTUAL_TRANSLATION = "contextual_translation"
    EDITORIAL_SELECTION_REVIEW = "editorial_selection_review"
    AMBIGUITY_RESOLUTION = "ambiguity_resolution"
    SPECIALIST_TRANSLATION_REVIEW = "specialist_translation_review"
    FINAL_QUALITY_REVIEW = "final_quality_review"


class EscalationReason(StrEnum):
    LOW_CONFIDENCE = "low_confidence"
    CLOSE_CANDIDATE_MARGIN = "close_candidate_margin"
    CROSS_SEGMENT_AMBIGUITY = "cross_segment_ambiguity"
    SEMANTIC_CONFLICT = "semantic_conflict"
    DIRECTED_CONSTRAINT_AMBIGUITY = "directed_constraint_ambiguity"
    SPECIALIST_TERMINOLOGY = "specialist_terminology"
    FINAL_QUALITY_GATE = "final_quality_gate"


class RoutingStatus(StrEnum):
    SELECTED = "selected"
    BLOCKED = "blocked"


_BASE_TIERS = MappingProxyType(
    {
        ModelTask.PROTOCOL_VALIDATION: ModelTier.DETERMINISTIC,
        ModelTask.HASHING_AND_PROVENANCE: ModelTier.DETERMINISTIC,
        ModelTask.SELECTION_ARITHMETIC: ModelTier.DETERMINISTIC,
        ModelTask.SUBTITLE_LAYOUT: ModelTier.DETERMINISTIC,
        ModelTask.MEDIA_EXECUTION: ModelTier.DETERMINISTIC,
        ModelTask.TRANSCRIPT_CLEANUP: ModelTier.ECONOMY,
        ModelTask.LANGUAGE_SEGMENTATION: ModelTier.ECONOMY,
        ModelTask.KEYWORD_EXTRACTION: ModelTier.ECONOMY,
        ModelTask.CANDIDATE_PREFILTER: ModelTier.ECONOMY,
        ModelTask.TITLE_DRAFT: ModelTier.ECONOMY,
        ModelTask.CONTENT_PROFILE: ModelTier.BALANCED,
        ModelTask.INTENT_INTERPRETATION: ModelTier.BALANCED,
        ModelTask.CANDIDATE_PROPOSAL: ModelTier.BALANCED,
        ModelTask.DIMENSION_ASSESSMENT: ModelTier.BALANCED,
        ModelTask.SEMANTIC_SUBTITLE_GROUPING: ModelTier.BALANCED,
        ModelTask.CONTEXTUAL_TRANSLATION: ModelTier.BALANCED,
        ModelTask.EDITORIAL_SELECTION_REVIEW: ModelTier.FRONTIER,
        ModelTask.AMBIGUITY_RESOLUTION: ModelTier.FRONTIER,
        ModelTask.SPECIALIST_TRANSLATION_REVIEW: ModelTier.FRONTIER,
        ModelTask.FINAL_QUALITY_REVIEW: ModelTier.FRONTIER,
    }
)

_TIER_RANK = MappingProxyType(
    {
        ModelTier.DETERMINISTIC: 0,
        ModelTier.ECONOMY: 1,
        ModelTier.BALANCED: 2,
        ModelTier.FRONTIER: 3,
    }
)
_NEXT_TIER = MappingProxyType(
    {
        ModelTier.ECONOMY: ModelTier.BALANCED,
        ModelTier.BALANCED: ModelTier.FRONTIER,
        ModelTier.FRONTIER: ModelTier.FRONTIER,
    }
)
_MANDATORY_FRONTIER_REASONS = frozenset(
    {
        EscalationReason.CROSS_SEGMENT_AMBIGUITY,
        EscalationReason.SEMANTIC_CONFLICT,
        EscalationReason.DIRECTED_CONSTRAINT_AMBIGUITY,
        EscalationReason.FINAL_QUALITY_GATE,
    }
)


class ModelRoutingRequest(FrozenModel):
    task: ModelTask
    escalation_reasons: tuple[EscalationReason, ...] = ()
    maximum_tier: ModelTier = ModelTier.FRONTIER
    frontier_calls_remaining: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_deterministic_task(self) -> ModelRoutingRequest:
        if _BASE_TIERS[self.task] is ModelTier.DETERMINISTIC and self.escalation_reasons:
            raise ValueError("deterministic tasks cannot request model escalation")
        return self


class ModelRoutingDecision(FrozenModel):
    routing_decision_id: str
    task: ModelTask
    base_tier: ModelTier
    required_tier: ModelTier
    selected_tier: ModelTier | None
    status: RoutingStatus
    escalation_reasons: tuple[EscalationReason, ...] = ()
    explanation: str


def _required_tier(
    base_tier: ModelTier,
    reasons: tuple[EscalationReason, ...],
) -> ModelTier:
    if base_tier is ModelTier.DETERMINISTIC or not reasons:
        return base_tier
    if _MANDATORY_FRONTIER_REASONS.intersection(reasons):
        return ModelTier.FRONTIER
    return _NEXT_TIER[base_tier]


def model_task_base_tier(task: ModelTask) -> ModelTier:
    return _BASE_TIERS[task]


def _decision_id(
    request: ModelRoutingRequest,
    reasons: tuple[EscalationReason, ...],
) -> str:
    payload = {
        "task": request.task.value,
        "escalation_reasons": sorted(reason.value for reason in reasons),
        "maximum_tier": request.maximum_tier.value,
        "frontier_calls_remaining": request.frontier_calls_remaining,
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return f"route-{digest[:20]}"


def route_model_task(request: ModelRoutingRequest) -> ModelRoutingDecision:
    reasons = tuple(dict.fromkeys(request.escalation_reasons))
    base_tier = model_task_base_tier(request.task)
    required_tier = _required_tier(base_tier, reasons)
    decision_id = _decision_id(request, reasons)

    if _TIER_RANK[required_tier] > _TIER_RANK[request.maximum_tier]:
        return ModelRoutingDecision(
            routing_decision_id=decision_id,
            task=request.task,
            base_tier=base_tier,
            required_tier=required_tier,
            selected_tier=None,
            status=RoutingStatus.BLOCKED,
            escalation_reasons=reasons,
            explanation=(
                f"required tier {required_tier.value} exceeds host maximum tier "
                f"{request.maximum_tier.value}"
            ),
        )

    if required_tier is ModelTier.FRONTIER and request.frontier_calls_remaining == 0:
        return ModelRoutingDecision(
            routing_decision_id=decision_id,
            task=request.task,
            base_tier=base_tier,
            required_tier=required_tier,
            selected_tier=None,
            status=RoutingStatus.BLOCKED,
            escalation_reasons=reasons,
            explanation="required frontier tier exceeds the remaining frontier-call budget",
        )

    return ModelRoutingDecision(
        routing_decision_id=decision_id,
        task=request.task,
        base_tier=base_tier,
        required_tier=required_tier,
        selected_tier=required_tier,
        status=RoutingStatus.SELECTED,
        escalation_reasons=reasons,
        explanation=f"selected {required_tier.value} tier for {request.task.value}",
    )
