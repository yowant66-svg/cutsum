from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from universal_cutup.domain.assessments import (
    AssessmentBundle,
    CandidateAssessment,
    DimensionAssessment,
)
from universal_cutup.domain.errors import CutupError, ErrorCode
from universal_cutup.domain.intelligence import (
    ContentDensity,
    ContentProfile,
    DependencyProfile,
    DimensionKey,
)
from universal_cutup.hashing import document_sha256
from universal_cutup.providers.files import FileContentIntelligenceProvider

FIXED_TIME = datetime(2026, 7, 30, tzinfo=UTC)


def test_fixture_profile_import_has_strict_provenance(tmp_path: Path) -> None:
    profile = ContentProfile(
        document_type="content_profile",
        created_at=FIXED_TIME,
        created_by="synthetic-fixture",
        profile_id="profile-1",
        source_id="source-1",
        content_types=("lecture",),
        primary_topic="Synthetic lecture",
        structure_types=("definition_example_conclusion",),
        density=ContentDensity(
            narrative=0.1,
            knowledge=0.9,
            procedural=0.2,
            opinion=0.2,
            emotion=0.1,
        ),
        dependencies=DependencyProfile(visual=0.2, audio=0.9, subtitle=0.8),
        confidence=0.9,
        supporting_evidence_refs=("evidence-1",),
        provider_record_ref="provider-profile-1",
    )
    path = tmp_path / "content-profile.json"
    path.write_text(profile.model_dump_json(), encoding="utf-8")
    imported = FileContentIntelligenceProvider(
        provider_kind="fixture",
        clock=lambda: FIXED_TIME,
    ).import_content_profile(path)
    assert imported.artifact == profile
    assert imported.canonical_sha256 == document_sha256(profile)
    assert imported.provider_record.provider_id == "fixture-provider"
    assert "not a real AI" in imported.provider_record.warnings[0]


def test_fixture_assessment_cannot_claim_real_provider(tmp_path: Path) -> None:
    dimensions = tuple(
        DimensionAssessment(
            dimension=dimension,
            score=5,
            evidence_refs=("evidence-1",),
            explanation="Synthetic score",
        )
        for dimension in DimensionKey
    )
    bundle = {
        "schema_version": "0.1.0",
        "document_type": "assessment_bundle",
        "created_at": FIXED_TIME.isoformat().replace("+00:00", "Z"),
        "created_by": "synthetic-fixture",
        "assessment_bundle_id": "bundle-1",
        "source_id": "source-1",
        "provider_record_ref": "provider-assessment-1",
        "provider_kind": "openai",
        "is_fixture": True,
        "candidates": [
            CandidateAssessment(
                candidate_id="candidate-1",
                dimensions=dimensions,
            ).model_dump(mode="json")
        ],
        "input_document_sha256": "a" * 64,
    }
    path = tmp_path / "assessment.json"
    path.write_text(json.dumps(bundle), encoding="utf-8")
    with pytest.raises(CutupError) as caught:
        FileContentIntelligenceProvider(provider_kind="fixture").import_assessments(path)
    assert caught.value.code is ErrorCode.ASSESSMENT_INVALID


def test_missing_evidence_is_rejected_before_import(tmp_path: Path) -> None:
    invalid = {
        "dimension": "insight",
        "score": 8,
        "evidence_refs": [],
        "explanation": "Unsupported score",
    }
    with pytest.raises(ValidationError):
        DimensionAssessment.model_validate(invalid)


def test_assessment_bundle_schema_is_strict() -> None:
    with pytest.raises(ValidationError):
        AssessmentBundle.model_validate({"unexpected": True})
