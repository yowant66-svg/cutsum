from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pydantic import BaseModel

from .domain.assessments import (
    AdaptiveSelectionResult,
    AggregateBundle,
    AssessmentBundle,
    CandidateProposalBundle,
)
from .domain.benchmarks import BenchmarkManifest
from .domain.blind_runs import BlindRunInput, BlindRunManifest
from .domain.education import EducationalSelectionResult, EducationalTaskRequest
from .domain.execution import ExecutionRecord, RunManifest
from .domain.intelligence import ContentProfile, HostIntent, ResolvedTaskProfile
from .domain.plans import CutPlan, CutRequest
from .domain.sports import (
    SportsObservationBundle,
    SportsSelectionResult,
    SportsTaskRequest,
)
from .domain.transcript import TranscriptArtifact
from .evaluation.models import FourTrackEvaluationManifest, FourTrackEvaluationReport

SCHEMA_MODELS: dict[str, type[BaseModel]] = {
    "cut-plan.schema.json": CutPlan,
    "cut-request.schema.json": CutRequest,
    "execution-record.schema.json": ExecutionRecord,
    "four-track-evaluation-manifest.schema.json": FourTrackEvaluationManifest,
    "four-track-evaluation-report.schema.json": FourTrackEvaluationReport,
    "educational-selection-result.schema.json": EducationalSelectionResult,
    "educational-task-request.schema.json": EducationalTaskRequest,
    "host-intent.schema.json": HostIntent,
    "content-profile.schema.json": ContentProfile,
    "assessment-bundle.schema.json": AssessmentBundle,
    "candidate-proposal-bundle.schema.json": CandidateProposalBundle,
    "adaptive-selection-result.schema.json": AdaptiveSelectionResult,
    "aggregate-bundle.schema.json": AggregateBundle,
    "resolved-task-profile.schema.json": ResolvedTaskProfile,
    "run-manifest.schema.json": RunManifest,
    "sports-observation-bundle.schema.json": SportsObservationBundle,
    "sports-selection-result.schema.json": SportsSelectionResult,
    "sports-task-request.schema.json": SportsTaskRequest,
    "transcript-artifact.schema.json": TranscriptArtifact,
    "benchmark-manifest.schema.json": BenchmarkManifest,
    "blind-run-input.schema.json": BlindRunInput,
    "blind-run-manifest.schema.json": BlindRunManifest,
}


def export_schemas(output_directory: Path) -> dict[str, str]:
    output_directory.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, str] = {}
    for filename, model in sorted(SCHEMA_MODELS.items()):
        schema_bytes = (
            json.dumps(
                model.model_json_schema(),
                ensure_ascii=False,
                sort_keys=True,
                indent=2,
            )
            + "\n"
        ).encode()
        (output_directory / filename).write_bytes(schema_bytes)
        manifest[filename] = hashlib.sha256(schema_bytes).hexdigest()
    return manifest
