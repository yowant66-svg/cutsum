from __future__ import annotations

import pytest
from pydantic import ValidationError

from universal_cutup.domain.candidates import CutCandidate, EvidenceRef
from universal_cutup.domain.education import (
    EducationalCandidateProfile,
    EducationContextRole,
    EducationSignal,
    EducationSignalType,
    EducationVisualDependency,
    EducationVisualDependencyType,
)


def _evidence() -> EvidenceRef:
    return EvidenceRef(
        evidence_id="evidence-1",
        artifact_id="transcript-1",
        segment_ids=("segment-1",),
        start_ms=0,
        end_ms=20_000,
        text_sha256="a" * 64,
    )


def test_education_signal_records_key_terms_and_context_roles() -> None:
    signal = EducationSignal(
        signal_id="signal-definition",
        signal_type=EducationSignalType.DEFINITION,
        matched_text="algorithm is a function",
        key_terms=("algorithm", "function"),
        context_roles=(EducationContextRole.SELF_CONTAINED,),
        language="en",
        start_ms=0,
        end_ms=4_000,
        confidence=0.9,
        evidence_refs=("evidence-1",),
    )

    assert signal.key_terms == ("algorithm", "function")
    assert signal.context_roles == ("self_contained",)


def test_visual_dependency_is_typed_and_candidate_evidence_backed() -> None:
    dependency = EducationVisualDependency(
        dependency_id="visual-formula-1",
        dependency_type=EducationVisualDependencyType.FORMULA,
        start_ms=2_000,
        end_ms=6_000,
        description="The formula is written on the board and not spoken in full.",
        confidence=0.8,
        evidence_refs=("evidence-1",),
    )
    candidate = CutCandidate(
        candidate_id="candidate-1",
        source_id="source-1",
        start_ms=0,
        end_ms=20_000,
        summary="Formula explanation",
        evidence_refs=(_evidence(),),
        education_visual_dependencies=(dependency,),
    )

    assert candidate.education_visual_dependencies == (dependency,)


def test_candidate_rejects_unknown_visual_evidence() -> None:
    dependency = EducationVisualDependency(
        dependency_id="visual-slide-1",
        dependency_type=EducationVisualDependencyType.SLIDE,
        start_ms=0,
        end_ms=5_000,
        description="Definition appears only on the slide.",
        confidence=0.7,
        evidence_refs=("missing-evidence",),
    )

    with pytest.raises(ValidationError, match="visual dependency references unknown"):
        CutCandidate(
            candidate_id="candidate-1",
            source_id="source-1",
            start_ms=0,
            end_ms=20_000,
            summary="Slide definition",
            evidence_refs=(_evidence(),),
            education_visual_dependencies=(dependency,),
        )


def test_qualified_profile_requires_structural_education_signal() -> None:
    with pytest.raises(ValidationError, match="qualified educational profile"):
        EducationalCandidateProfile(
            candidate_id="candidate-1",
            qualified=True,
            signal_types=(EducationSignalType.TEACHER_EMPHASIS,),
            context_roles=(EducationContextRole.SELF_CONTAINED,),
            key_terms=("remember",),
            visual_dependency_types=(),
            completeness_confidence=0.8,
        )


def test_profile_deduplicates_are_rejected() -> None:
    with pytest.raises(ValidationError, match="key terms must be unique"):
        EducationalCandidateProfile(
            candidate_id="candidate-1",
            qualified=True,
            signal_types=(EducationSignalType.DEFINITION,),
            context_roles=(EducationContextRole.SELF_CONTAINED,),
            key_terms=("algorithm", "algorithm"),
            visual_dependency_types=(),
            completeness_confidence=0.9,
        )
