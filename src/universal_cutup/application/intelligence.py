from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from pydantic import BaseModel

from universal_cutup import __version__
from universal_cutup.application.duration import prepare_candidates_for_task
from universal_cutup.application.resolution import resolve_task_profile
from universal_cutup.domain.assessments import (
    AdaptiveSelectionResult,
    AggregateBundle,
    AssessmentBundle,
    CandidateProposalBundle,
)
from universal_cutup.domain.candidates import EvidenceArtifactIdentity
from universal_cutup.domain.intelligence import (
    CapabilityProfile,
    ContentProfile,
    HostIntent,
    ResolvedTaskProfile,
    TaskPreset,
)
from universal_cutup.domain.plans import CutPlan
from universal_cutup.domain.records import ProviderRecord, StrategyRecord, StrategyRole
from universal_cutup.domain.selection import (
    SelectionDecision,
    SelectionResult,
    SelectionStatus,
)
from universal_cutup.domain.sources import MediaSource
from universal_cutup.domain.specs import OutputSpec
from universal_cutup.hashing import document_sha256
from universal_cutup.strategies.adaptive import (
    CALCULATION_VERSION,
    aggregate_bundle,
    select_adaptive,
)

INTELLIGENCE_MODELS: dict[str, type[BaseModel]] = {
    "host-intent": HostIntent,
    "content-profile": ContentProfile,
    "resolved-task": ResolvedTaskProfile,
    "proposals": CandidateProposalBundle,
    "assessments": AssessmentBundle,
    "aggregates": AggregateBundle,
    "selection": AdaptiveSelectionResult,
}


def validate_intelligence_document(kind: str, payload: object) -> BaseModel:
    try:
        model = INTELLIGENCE_MODELS[kind]
    except KeyError as error:
        raise ValueError(f"unsupported intelligence document kind: {kind}") from error
    return model.model_validate(payload)


def resolve_intelligence_task(
    host_intent: HostIntent,
    content_profile: ContentProfile | None,
    *,
    preset: TaskPreset | None = None,
    capability_profile: CapabilityProfile | None = None,
    created_at: datetime | None = None,
) -> ResolvedTaskProfile:
    return resolve_task_profile(
        host_intent,
        content_profile,
        preset=preset,
        capability_profile=capability_profile,
        created_at=created_at,
    )


def aggregate_intelligence(
    proposals: CandidateProposalBundle,
    assessments: AssessmentBundle,
    task_profile: ResolvedTaskProfile,
    *,
    created_at: datetime | None = None,
) -> AggregateBundle:
    if proposals.source_id != assessments.source_id:
        raise ValueError("proposal and assessment source IDs must match")
    proposals, assessments = prepare_candidates_for_task(
        proposals,
        assessments,
        task_profile,
    )
    aggregates = aggregate_bundle(proposals.candidates, assessments, task_profile)
    input_hash = document_sha256(
        {
            "proposals": proposals.model_dump(mode="json"),
            "assessments": assessments.model_dump(mode="json"),
            "task_profile": task_profile.model_dump(mode="json"),
        }
    )
    return AggregateBundle(
        document_type="aggregate_bundle",
        created_at=created_at or datetime.now(UTC),
        created_by="universal-cutup",
        aggregate_bundle_id=str(uuid4()),
        source_id=proposals.source_id,
        resolved_task_id=task_profile.resolved_task_id,
        aggregates=aggregates,
        input_document_sha256=input_hash,
    )


def select_intelligence(
    proposals: CandidateProposalBundle,
    assessments: AssessmentBundle,
    aggregates: AggregateBundle,
    task_profile: ResolvedTaskProfile,
    *,
    created_at: datetime | None = None,
) -> AdaptiveSelectionResult:
    proposals, assessments = prepare_candidates_for_task(
        proposals,
        assessments,
        task_profile,
    )
    return select_adaptive(
        proposals.candidates,
        assessments.candidates,
        aggregates.aggregates,
        task_profile,
        created_at=created_at,
    )


def _evidence_artifacts(
    proposals: CandidateProposalBundle,
) -> tuple[EvidenceArtifactIdentity, ...]:
    artifact_segments: dict[str, set[str]] = {}
    for candidate in proposals.candidates:
        for evidence in candidate.evidence_refs:
            artifact_segments.setdefault(evidence.artifact_id, set()).update(evidence.segment_ids)
    return tuple(
        EvidenceArtifactIdentity(
            artifact_id=artifact_id,
            source_id=proposals.source_id,
            segment_ids=tuple(sorted(segment_ids)),
        )
        for artifact_id, segment_ids in sorted(artifact_segments.items())
    )


def create_adaptive_plan(
    source: MediaSource,
    proposals: CandidateProposalBundle,
    assessments: AssessmentBundle,
    task_profile: ResolvedTaskProfile,
    selection: AdaptiveSelectionResult,
    *,
    provider_records: tuple[ProviderRecord, ...] = (),
    output_spec: OutputSpec | None = None,
    created_at: datetime | None = None,
) -> CutPlan:
    proposals, assessments = prepare_candidates_for_task(
        proposals,
        assessments,
        task_profile,
    )
    if source.source_id != proposals.source_id:
        raise ValueError("source and proposal source IDs must match")
    occurred_at = created_at or datetime.now(UTC)
    selected_ids = set(selection.selected_candidate_ids)
    decisions = tuple(
        SelectionDecision(
            candidate_id=candidate.candidate_id,
            status=(
                SelectionStatus.SELECTED
                if candidate.candidate_id in selected_ids
                else SelectionStatus.REJECTED
            ),
            reason=";".join(
                next(
                    decision.reasons
                    for decision in selection.decisions
                    if decision.candidate_id == candidate.candidate_id
                )
            ),
            evidence_refs=tuple(evidence.evidence_id for evidence in candidate.evidence_refs),
        )
        for candidate in proposals.candidates
    )
    strategy_record_id = f"strategy-record-adaptive-{selection.input_sha256[:16]}"
    strategy_record = StrategyRecord(
        strategy_record_id=strategy_record_id,
        strategy_id="adaptive-highlight14",
        strategy_version=CALCULATION_VERSION,
        strategy_role=StrategyRole.SELECTION,
        distribution_name="cutsum",
        distribution_version=__version__,
        config_hash=document_sha256(task_profile),
        input_hashes=(
            document_sha256(proposals),
            document_sha256(assessments),
            document_sha256(task_profile),
        ),
        output_hashes=(document_sha256(selection),),
        provider_record_refs=tuple(record.provider_record_id for record in provider_records),
        started_at=occurred_at,
        completed_at=occurred_at,
        provenance_ref="new-original:adaptive-highlight14-alpha",
    )
    return CutPlan(
        document_type="cut_plan",
        created_at=occurred_at,
        created_by="universal-cutup",
        plan_id=str(uuid4()),
        source=source,
        evidence_artifacts=_evidence_artifacts(proposals),
        candidates=proposals.candidates,
        selection_result=SelectionResult(
            selection_id=selection.selection_id,
            selection_strategy_id="adaptive-highlight14",
            selection_strategy_version=CALCULATION_VERSION,
            decisions=decisions,
            strategy_record_ref=strategy_record_id,
        ),
        provider_records=provider_records,
        strategy_records=(strategy_record,),
        output_spec=output_spec or OutputSpec(),
    )
