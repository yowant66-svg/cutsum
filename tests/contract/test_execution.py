from __future__ import annotations

from datetime import UTC, datetime

from universal_cutup.domain.execution import ExecutionRecord, RunManifest, StepResult
from universal_cutup.domain.records import ProviderRecord
from universal_cutup.hashing import document_sha256

from .test_plans import make_plan

FIXED_TIME = datetime(2026, 7, 30, 12, 0, tzinfo=UTC)


def test_execution_provider_records_do_not_change_saved_plan() -> None:
    plan = make_plan(plan_id="plan-1", created_at=FIXED_TIME)
    plan_hash = document_sha256(plan)
    rendering_record = ProviderRecord(
        provider_record_id="provider-record-render",
        provider_id="mock",
        operation="render",
        started_at=FIXED_TIME,
        completed_at=FIXED_TIME,
        input_hashes=(plan_hash,),
        output_hashes=("e" * 64,),
    )
    execution = ExecutionRecord(
        document_type="execution_record",
        created_at=FIXED_TIME,
        created_by="test-suite",
        execution_id="execution-1",
        plan_id=plan.plan_id,
        plan_document_sha256=plan_hash,
        started_at=FIXED_TIME,
        completed_at=FIXED_TIME,
        steps=(StepResult(step_id="validate", status="completed"),),
        provider_records=(rendering_record,),
    )
    manifest = RunManifest(
        document_type="run_manifest",
        created_at=FIXED_TIME,
        created_by="test-suite",
        run_id="run-1",
        plan_id=plan.plan_id,
        execution_ids=(execution.execution_id,),
        provider_records=(rendering_record,),
    )
    assert document_sha256(plan) == plan_hash
    assert execution.provider_records == (rendering_record,)
    assert manifest.provider_records == (rendering_record,)
