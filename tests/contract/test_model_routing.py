from __future__ import annotations

import pytest
from pydantic import ValidationError

from universal_cutup.domain.model_routing import (
    EscalationReason,
    ModelRoutingRequest,
    ModelTask,
    ModelTier,
    RoutingStatus,
    route_model_task,
)


@pytest.mark.parametrize(
    ("task", "expected_tier"),
    [
        (ModelTask.PROTOCOL_VALIDATION, ModelTier.DETERMINISTIC),
        (ModelTask.MEDIA_EXECUTION, ModelTier.DETERMINISTIC),
        (ModelTask.TRANSCRIPT_CLEANUP, ModelTier.ECONOMY),
        (ModelTask.CANDIDATE_PREFILTER, ModelTier.ECONOMY),
        (ModelTask.CONTENT_PROFILE, ModelTier.BALANCED),
        (ModelTask.DIMENSION_ASSESSMENT, ModelTier.BALANCED),
        (ModelTask.EDITORIAL_SELECTION_REVIEW, ModelTier.FRONTIER),
        (ModelTask.FINAL_QUALITY_REVIEW, ModelTier.FRONTIER),
    ],
)
def test_model_task_uses_stable_provider_neutral_base_tier(
    task: ModelTask,
    expected_tier: ModelTier,
) -> None:
    decision = route_model_task(ModelRoutingRequest(task=task))

    assert decision.base_tier is expected_tier
    assert decision.required_tier is expected_tier
    assert decision.selected_tier is expected_tier
    assert decision.status is RoutingStatus.SELECTED
    assert decision.routing_decision_id.startswith("route-")


@pytest.mark.parametrize(
    "reason",
    [EscalationReason.LOW_CONFIDENCE, EscalationReason.CLOSE_CANDIDATE_MARGIN],
)
def test_uncertainty_promotes_one_tier(reason: EscalationReason) -> None:
    economy = route_model_task(
        ModelRoutingRequest(task=ModelTask.CANDIDATE_PREFILTER, escalation_reasons=(reason,))
    )
    balanced = route_model_task(
        ModelRoutingRequest(task=ModelTask.CANDIDATE_PROPOSAL, escalation_reasons=(reason,))
    )

    assert economy.required_tier is ModelTier.BALANCED
    assert balanced.required_tier is ModelTier.FRONTIER


@pytest.mark.parametrize(
    "reason",
    [
        EscalationReason.CROSS_SEGMENT_AMBIGUITY,
        EscalationReason.SEMANTIC_CONFLICT,
        EscalationReason.FINAL_QUALITY_GATE,
    ],
)
def test_high_risk_reason_requires_frontier(reason: EscalationReason) -> None:
    decision = route_model_task(
        ModelRoutingRequest(
            task=ModelTask.CONTENT_PROFILE,
            escalation_reasons=(reason,),
        )
    )

    assert decision.required_tier is ModelTier.FRONTIER
    assert decision.selected_tier is ModelTier.FRONTIER


def test_tier_ceiling_blocks_instead_of_silently_downgrading() -> None:
    decision = route_model_task(
        ModelRoutingRequest(
            task=ModelTask.CONTENT_PROFILE,
            escalation_reasons=(EscalationReason.SEMANTIC_CONFLICT,),
            maximum_tier=ModelTier.BALANCED,
        )
    )

    assert decision.status is RoutingStatus.BLOCKED
    assert decision.required_tier is ModelTier.FRONTIER
    assert decision.selected_tier is None
    assert "maximum tier" in decision.explanation


def test_frontier_budget_blocks_required_frontier_call() -> None:
    decision = route_model_task(
        ModelRoutingRequest(
            task=ModelTask.FINAL_QUALITY_REVIEW,
            frontier_calls_remaining=0,
        )
    )

    assert decision.status is RoutingStatus.BLOCKED
    assert decision.selected_tier is None
    assert "frontier-call budget" in decision.explanation


def test_routing_deduplicates_repeated_reasons_deterministically() -> None:
    decision = route_model_task(
        ModelRoutingRequest(
            task=ModelTask.CONTEXTUAL_TRANSLATION,
            escalation_reasons=(
                EscalationReason.SPECIALIST_TERMINOLOGY,
                EscalationReason.SPECIALIST_TERMINOLOGY,
                EscalationReason.LOW_CONFIDENCE,
            ),
        )
    )

    assert decision.escalation_reasons == (
        EscalationReason.SPECIALIST_TERMINOLOGY,
        EscalationReason.LOW_CONFIDENCE,
    )


def test_deterministic_task_rejects_model_escalation() -> None:
    with pytest.raises(ValidationError, match="deterministic tasks cannot request model escalation"):
        ModelRoutingRequest(
            task=ModelTask.MEDIA_EXECUTION,
            escalation_reasons=(EscalationReason.LOW_CONFIDENCE,),
        )
