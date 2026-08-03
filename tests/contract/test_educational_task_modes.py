from __future__ import annotations

from universal_cutup.application.educational import (
    prepare_educational_candidate,
    prepare_educational_duration,
    resolve_educational_request,
    select_educational_for_request,
)
from universal_cutup.domain.candidates import CutCandidate, EvidenceRef
from universal_cutup.domain.education import (
    EducationSignalType,
    EducationVisualDependency,
    EducationVisualDependencyType,
)
from universal_cutup.domain.intelligence import ControlMode
from universal_cutup.domain.transcript import SubtitleCue


def _candidate(candidate_id: str, text: str, start_ms: int, end_ms: int) -> CutCandidate:
    cue_duration = (end_ms - start_ms) // 3
    cues = tuple(
        SubtitleCue(
            cue_id=f"{candidate_id}-cue-{index}",
            source_id="source-1",
            start_ms=start_ms + ((index - 1) * cue_duration),
            end_ms=(end_ms if index == 3 else start_ms + (index * cue_duration)),
            text=text,
            language="en",
            source_segment_ids=(f"{candidate_id}-segment-{index}",),
        )
        for index in range(1, 4)
    )
    evidence = EvidenceRef(
        evidence_id=f"{candidate_id}-evidence",
        artifact_id="transcript-1",
        segment_ids=tuple(segment_id for cue in cues for segment_id in cue.source_segment_ids),
        start_ms=start_ms,
        end_ms=end_ms,
        text_sha256="a" * 64,
    )
    return prepare_educational_candidate(
        CutCandidate(
            candidate_id=candidate_id,
            source_id="source-1",
            start_ms=start_ms,
            end_ms=end_ms,
            summary=text,
            evidence_refs=(evidence,),
            subtitle_cues=cues,
        )
    )


def test_auto_selects_structural_knowledge_without_highlight14() -> None:
    candidates = (
        _candidate("definition", "An algorithm is a function.", 0, 20_000),
        _candidate("example", "For example, search for five in this array.", 30_000, 50_000),
        _candidate("filler", "Welcome back to the lecture.", 60_000, 80_000),
    )
    request = resolve_educational_request(ControlMode.AUTO, "")

    result = select_educational_for_request(candidates, request)

    assert set(result.selected_candidate_ids) == {"definition", "example"}
    assert "filler" not in result.selected_candidate_ids


def test_directed_natural_language_selects_examples_and_excludes_definitions() -> None:
    candidates = (
        _candidate("definition", "An algorithm is a function.", 0, 20_000),
        _candidate("example-1", "For example, find five in the array.", 30_000, 50_000),
        _candidate("example-2", "Suppose the array has two fives.", 60_000, 80_000),
    )
    request = resolve_educational_request(
        ControlMode.DIRECTED,
        "只要两个例题，不要定义。",  # noqa: RUF001
    )

    result = select_educational_for_request(candidates, request)

    assert request.required_types == (EducationSignalType.WORKED_EXAMPLE,)
    assert request.forbidden_types == (EducationSignalType.DEFINITION,)
    assert request.target_count == 2
    assert set(result.selected_candidate_ids) == {"example-1", "example-2"}


def test_auto_prefers_clean_transcript_when_education_type_is_equal() -> None:
    candidates = (
        _candidate(
            "garbled-reasoning",
            "Assume K and turn turn-ed by induction.",
            0,
            20_000,
        ),
        _candidate(
            "clean-reasoning",
            "Assume the inductive hypothesis is true for K.",
            30_000,
            50_000,
        ),
    )
    request = resolve_educational_request(ControlMode.AUTO, "一个")

    result = select_educational_for_request(candidates, request)

    assert result.selected_candidate_ids == ("clean-reasoning",)


def test_educational_context_extension_is_disclosed_between_60_and_120_seconds() -> None:
    candidate = _candidate(
        "long-definition",
        "A recurrence is a rule that defines later values.",
        0,
        90_000,
    )

    prepared = prepare_educational_duration(candidate)

    assert len(prepared) == 1
    assert prepared[0].extension_reason == "educational_context_requires_over_60_seconds"


def test_educational_candidate_over_120_seconds_splits_and_reprofiles_parts() -> None:
    candidate = _candidate(
        "very-long-definition",
        "A recurrence is a rule that defines later values.",
        0,
        150_000,
    )

    visual_dependency = EducationVisualDependency(
        dependency_id="visual-formula",
        dependency_type=EducationVisualDependencyType.FORMULA,
        start_ms=20_000,
        end_ms=130_000,
        description="The recurrence remains visible on the board.",
        confidence=0.8,
        evidence_refs=(candidate.evidence_refs[0].evidence_id,),
    )
    parts = prepare_educational_duration(
        candidate.model_copy(update={"education_visual_dependencies": (visual_dependency,)})
    )

    assert len(parts) == 3
    assert all(part.end_ms - part.start_ms <= 120_000 for part in parts)
    assert tuple(part.series_index for part in parts) == (1, 2, 3)
    assert all(part.educational_profile is not None for part in parts)
    assert all(
        part.educational_profile.candidate_id == part.candidate_id
        for part in parts
        if part.educational_profile is not None
    )
    assert all(CutCandidate.model_validate(part.model_dump()) == part for part in parts)
    assert all(
        set(dependency.evidence_refs) == {part.evidence_refs[0].evidence_id}
        for part in parts
        for dependency in part.education_visual_dependencies
    )
