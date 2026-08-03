from __future__ import annotations

from universal_cutup.application.educational import prepare_educational_candidate
from universal_cutup.domain.candidates import CutCandidate, EvidenceRef
from universal_cutup.domain.education import (
    EducationContextRole,
    EducationSignalType,
    EducationVisualDependency,
    EducationVisualDependencyType,
)
from universal_cutup.domain.subtitles import (
    SubtitleSemanticLevel,
    SubtitleSemanticSpan,
    SubtitleTimingPrecision,
)
from universal_cutup.domain.transcript import SubtitleCue
from universal_cutup.strategies.educational import qualify_educational_candidate


def _candidate(text: str) -> CutCandidate:
    evidence = EvidenceRef(
        evidence_id="evidence-1",
        artifact_id="transcript-1",
        segment_ids=("segment-1",),
        start_ms=0,
        end_ms=20_000,
        text_sha256="a" * 64,
    )
    span = SubtitleSemanticSpan(
        semantic_span_id="semantic-1",
        source_id="source-1",
        start_ms=0,
        end_ms=20_000,
        source_cue_ids=("cue-1",),
        text=text,
        language="en",
        semantic_level=SubtitleSemanticLevel.SENTENCE,
        timing_precision=SubtitleTimingPrecision.EXACT,
    )
    cue = SubtitleCue(
        cue_id="cue-1",
        source_id="source-1",
        start_ms=0,
        end_ms=20_000,
        text=text,
        language="en",
        source_segment_ids=("segment-1",),
    )
    return CutCandidate(
        candidate_id="candidate-1",
        source_id="source-1",
        start_ms=0,
        end_ms=20_000,
        summary=text,
        evidence_refs=(evidence,),
        subtitle_cues=(cue,),
        subtitle_semantic_spans=(span,),
    )


def test_definition_extracts_key_terms_from_semantic_span() -> None:
    candidate = prepare_educational_candidate(
        _candidate("An algorithm is a function that maps inputs to outputs.")
    )

    definition = next(
        signal
        for signal in candidate.education_signals
        if signal.signal_type is EducationSignalType.DEFINITION
    )
    assert {"algorithm", "function", "input", "output"} <= set(definition.key_terms)
    assert definition.context_roles == (EducationContextRole.SELF_CONTAINED,)
    assert candidate.educational_profile is not None
    assert candidate.educational_profile.qualified


def test_reasoning_without_premise_is_not_auto_qualified() -> None:
    candidate = prepare_educational_candidate(_candidate("Therefore, this output is correct."))
    qualification = qualify_educational_candidate(
        candidate,
        required_types=(EducationSignalType.REASONING_CHAIN,),
    )

    assert not qualification.qualified
    assert "requires_previous_context" in qualification.reasons
    assert candidate.educational_profile is not None
    assert EducationContextRole.REQUIRES_PREVIOUS in (candidate.educational_profile.context_roles)


def test_definition_that_only_points_backward_is_not_standalone() -> None:
    candidate = prepare_educational_candidate(
        _candidate("That problem is a binary relation between inputs and outputs.")
    )

    assert candidate.educational_profile is not None
    assert not candidate.educational_profile.qualified
    assert EducationContextRole.REQUIRES_PREVIOUS in candidate.educational_profile.context_roles


def test_named_principle_without_explanation_is_not_complete_knowledge() -> None:
    candidate = prepare_educational_candidate(_candidate("Pigeonhole principle, right?"))
    qualification = qualify_educational_candidate(
        candidate,
        required_types=(EducationSignalType.THEOREM_OR_RULE,),
    )

    assert not qualification.qualified
    assert "insufficient_educational_statement" in qualification.reasons


def test_incomplete_explanation_requires_following_context() -> None:
    candidate = prepare_educational_candidate(_candidate("The recurrence works because"))

    assert candidate.educational_profile is not None
    assert EducationContextRole.REQUIRES_FOLLOWING in (candidate.educational_profile.context_roles)
    assert not candidate.educational_profile.qualified


def test_visual_dependency_is_disclosed_without_disqualifying_complete_definition() -> None:
    candidate = _candidate("A recurrence is a rule that defines later values.")
    dependency = EducationVisualDependency(
        dependency_id="visual-formula",
        dependency_type=EducationVisualDependencyType.FORMULA,
        start_ms=0,
        end_ms=20_000,
        description="The exact recurrence is visible on the blackboard.",
        confidence=0.9,
        evidence_refs=("evidence-1",),
    )
    prepared = prepare_educational_candidate(
        candidate.model_copy(update={"education_visual_dependencies": (dependency,)})
    )

    assert prepared.educational_profile is not None
    assert prepared.educational_profile.qualified
    assert EducationContextRole.REQUIRES_VISUAL in prepared.educational_profile.context_roles
    assert prepared.educational_profile.visual_dependency_types == (
        EducationVisualDependencyType.FORMULA,
    )
