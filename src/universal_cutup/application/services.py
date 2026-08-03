from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from pydantic import BaseModel

from universal_cutup import __version__
from universal_cutup.domain.candidates import EvidenceArtifactIdentity
from universal_cutup.domain.plans import CutPlan
from universal_cutup.domain.records import StrategyRecord, StrategyRole
from universal_cutup.domain.sources import MediaSource
from universal_cutup.domain.transcript import TranscriptArtifact
from universal_cutup.hashing import document_sha256
from universal_cutup.strategies.base import StrategyRegistry
from universal_cutup.strategies.deterministic import (
    DeterministicProposalStrategy,
    DeterministicScoringStrategy,
    DeterministicSelectionStrategy,
)


@dataclass(frozen=True, slots=True)
class ApplicationContext:
    strategy_registry: StrategyRegistry
    clock: Callable[[], datetime]
    plan_id_factory: Callable[[], str]

    @classmethod
    def default(cls) -> ApplicationContext:
        registry = StrategyRegistry()
        registry.register_proposal(DeterministicProposalStrategy())
        registry.register_scoring(DeterministicScoringStrategy())
        registry.register_selection(DeterministicSelectionStrategy())
        return cls(
            strategy_registry=registry,
            clock=lambda: datetime.now(UTC),
            plan_id_factory=lambda: str(uuid4()),
        )


def _strategy_record_id(role: StrategyRole, input_hash: str) -> str:
    return f"strategy-record-{role.value}-{input_hash[:16]}"


def _strategy_config_hash(strategy_id: str, strategy_version: str, role: StrategyRole) -> str:
    return document_sha256(
        {
            "strategy_id": strategy_id,
            "strategy_version": strategy_version,
            "strategy_role": role.value,
            "config": {},
        }
    )


def _items_hash(items: tuple[BaseModel, ...]) -> str:
    serialized_items = [item.model_dump(mode="json", exclude_none=True) for item in items]
    return document_sha256({"items": serialized_items})


def _strategy_record(
    *,
    record_id: str,
    role: StrategyRole,
    input_hash: str,
    output_hash: str,
    occurred_at: datetime,
) -> StrategyRecord:
    return StrategyRecord(
        strategy_record_id=record_id,
        strategy_id="deterministic",
        strategy_version="0.1.0",
        strategy_role=role,
        distribution_name="cutsum",
        distribution_version=__version__,
        config_hash=_strategy_config_hash("deterministic", "0.1.0", role),
        input_hashes=(input_hash,),
        output_hashes=(output_hash,),
        started_at=occurred_at,
        completed_at=occurred_at,
        provenance_ref="new-original:deterministic-v0.1.0",
    )


def transcript_to_plan(
    source: MediaSource,
    transcript: TranscriptArtifact,
    *,
    context: ApplicationContext,
    strategy_id: str = "deterministic",
) -> CutPlan:
    if transcript.source_id != source.source_id:
        raise ValueError("transcript and media source IDs must match")
    occurred_at = context.clock()
    transcript_hash = document_sha256(transcript)
    proposed = context.strategy_registry.proposal(strategy_id).propose(transcript)
    proposed_hash = _items_hash(proposed)
    proposal_record_id = _strategy_record_id(StrategyRole.PROPOSAL, transcript_hash)
    scoring_record_id = _strategy_record_id(StrategyRole.SCORING, proposed_hash)
    scored = context.strategy_registry.scoring(strategy_id).score(
        proposed,
        strategy_record_id=scoring_record_id,
    )
    scored_hash = _items_hash(scored)
    selection_record_id = _strategy_record_id(StrategyRole.SELECTION, scored_hash)
    selection_result = context.strategy_registry.selection(strategy_id).select(
        scored,
        strategy_record_id=selection_record_id,
    )
    selection_hash = document_sha256(selection_result.model_dump(mode="json"))
    strategy_records = (
        _strategy_record(
            record_id=proposal_record_id,
            role=StrategyRole.PROPOSAL,
            input_hash=transcript_hash,
            output_hash=proposed_hash,
            occurred_at=occurred_at,
        ),
        _strategy_record(
            record_id=scoring_record_id,
            role=StrategyRole.SCORING,
            input_hash=proposed_hash,
            output_hash=scored_hash,
            occurred_at=occurred_at,
        ),
        _strategy_record(
            record_id=selection_record_id,
            role=StrategyRole.SELECTION,
            input_hash=scored_hash,
            output_hash=selection_hash,
            occurred_at=occurred_at,
        ),
    )
    return CutPlan(
        document_type="cut_plan",
        created_at=occurred_at,
        created_by="universal-cutup",
        plan_id=context.plan_id_factory(),
        source=source,
        evidence_artifacts=(
            EvidenceArtifactIdentity(
                artifact_id=transcript.transcript_id,
                source_id=transcript.source_id,
                segment_ids=tuple(segment.segment_id for segment in transcript.segments),
            ),
        ),
        candidates=scored,
        selection_result=selection_result,
        strategy_records=strategy_records,
    )
