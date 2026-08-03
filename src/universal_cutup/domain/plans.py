from __future__ import annotations

from datetime import datetime

from pydantic import model_validator

from .candidates import CutCandidate, EvidenceArtifactIdentity
from .common import DocumentHeader
from .records import ProviderRecord, StrategyRecord
from .selection import SelectionResult
from .sources import MediaBinding, MediaSource
from .specs import OutputSpec


class CutRequest(DocumentHeader):
    request_id: str
    source: MediaSource
    binding: MediaBinding | None = None
    strategy_id: str = "deterministic"
    output_spec: OutputSpec = OutputSpec()


class CutPlan(DocumentHeader):
    plan_id: str
    derived_from_plan_id: str | None = None
    source: MediaSource
    evidence_artifacts: tuple[EvidenceArtifactIdentity, ...]
    candidates: tuple[CutCandidate, ...]
    selection_result: SelectionResult
    provider_records: tuple[ProviderRecord, ...] = ()
    strategy_records: tuple[StrategyRecord, ...] = ()
    output_spec: OutputSpec = OutputSpec()

    @model_validator(mode="after")
    def validate_selection_references(self) -> CutPlan:
        candidate_id_list = [candidate.candidate_id for candidate in self.candidates]
        candidate_ids = set(candidate_id_list)
        if len(candidate_id_list) != len(candidate_ids):
            raise ValueError("candidate IDs must be unique")
        decision_ids = {decision.candidate_id for decision in self.selection_result.decisions}
        if decision_ids != candidate_ids:
            raise ValueError("selection decisions must cover every candidate exactly once")
        evidence_ids = [
            evidence.evidence_id
            for candidate in self.candidates
            for evidence in candidate.evidence_refs
        ]
        if len(evidence_ids) != len(set(evidence_ids)):
            raise ValueError("evidence IDs must be unique across a CutPlan")
        artifact_ids = [artifact.artifact_id for artifact in self.evidence_artifacts]
        if len(artifact_ids) != len(set(artifact_ids)):
            raise ValueError("evidence artifact IDs must be unique")
        artifacts_by_id = {artifact.artifact_id: artifact for artifact in self.evidence_artifacts}
        for candidate in self.candidates:
            if candidate.source_id != self.source.source_id:
                raise ValueError("candidate source_id must match CutPlan source_id")
            for evidence in candidate.evidence_refs:
                artifact = artifacts_by_id.get(evidence.artifact_id)
                if artifact is None:
                    raise ValueError("EvidenceRef references an unknown evidence artifact")
                if artifact.source_id != candidate.source_id:
                    raise ValueError("evidence artifact source_id must match candidate source_id")
                if not set(evidence.segment_ids) <= set(artifact.segment_ids):
                    raise ValueError("EvidenceRef references an unknown segment")
        evidence_id_set = set(evidence_ids)
        decision_evidence_refs = {
            evidence_ref
            for decision in self.selection_result.decisions
            for evidence_ref in decision.evidence_refs
        }
        if not decision_evidence_refs <= evidence_id_set:
            raise ValueError("selection decision references unknown evidence")
        dimension_evidence_refs = {
            evidence_ref
            for candidate in self.candidates
            for score in candidate.strategy_scores
            for dimension in score.dimensions
            for evidence_ref in dimension.evidence_refs
        }
        if not dimension_evidence_refs <= evidence_id_set:
            raise ValueError("strategy score references unknown evidence")
        provider_record_ids = [record.provider_record_id for record in self.provider_records]
        if len(provider_record_ids) != len(set(provider_record_ids)):
            raise ValueError("ProviderRecord IDs must be unique")
        strategy_record_ids = [record.strategy_record_id for record in self.strategy_records]
        if len(strategy_record_ids) != len(set(strategy_record_ids)):
            raise ValueError("StrategyRecord IDs must be unique")
        strategy_record_id_set = set(strategy_record_ids)
        score_record_refs = {
            score.strategy_record_ref
            for candidate in self.candidates
            for score in candidate.strategy_scores
        }
        if None in score_record_refs:
            raise ValueError("every StrategyScore must reference a StrategyRecord")
        if not score_record_refs <= strategy_record_id_set:
            raise ValueError("StrategyScore references an unknown StrategyRecord")
        selection_record_ref = self.selection_result.strategy_record_ref
        if selection_record_ref is not None and selection_record_ref not in strategy_record_id_set:
            raise ValueError("SelectionResult references an unknown StrategyRecord")
        provider_record_id_set = set(provider_record_ids)
        translation_provider_refs = {
            record.provider_record_ref
            for candidate in self.candidates
            for record in candidate.contextual_translation_records
        }
        if not translation_provider_refs <= provider_record_id_set:
            raise ValueError("contextual translation references an unknown ProviderRecord")
        provider_refs = {
            provider_ref
            for record in self.strategy_records
            for provider_ref in record.provider_record_refs
        } | set(self.selection_result.provider_record_refs)
        if not provider_refs <= provider_record_id_set:
            raise ValueError("strategy or selection references an unknown ProviderRecord")
        return self


def derive_plan(
    original: CutPlan,
    *,
    plan_id: str,
    created_at: datetime,
    selection_result: SelectionResult,
) -> CutPlan:
    return original.model_copy(
        update={
            "plan_id": plan_id,
            "derived_from_plan_id": original.plan_id,
            "created_at": created_at,
            "selection_result": selection_result,
        }
    )
