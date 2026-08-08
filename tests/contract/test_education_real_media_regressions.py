from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from universal_cutup.application.educational import (
    prepare_educational_candidate,
    propose_educational_candidates,
    resolve_educational_request,
    select_educational_for_request,
)
from universal_cutup.domain.candidates import CutCandidate, EvidenceRef
from universal_cutup.domain.intelligence import ControlMode
from universal_cutup.domain.transcript import (
    SubtitleCue,
    TranscriptArtifact,
    TranscriptSegment,
)


def _candidate(
    candidate_id: str,
    text: str,
    start_ms: int,
    *,
    duration_ms: int = 20_000,
) -> CutCandidate:
    evidence = EvidenceRef(
        evidence_id=f"evidence-{candidate_id}",
        artifact_id="transcript-real-regression",
        segment_ids=(f"segment-{candidate_id}",),
        start_ms=start_ms,
        end_ms=start_ms + duration_ms,
        text_sha256=hashlib.sha256(text.encode()).hexdigest(),
        snapshot=text,
    )
    return prepare_educational_candidate(
        CutCandidate(
            candidate_id=candidate_id,
            source_id="source-real-regression",
            start_ms=start_ms,
            end_ms=start_ms + duration_ms,
            summary=text,
            evidence_refs=(evidence,),
            subtitle_cues=(
                SubtitleCue(
                    cue_id=f"cue-{candidate_id}",
                    source_id="source-real-regression",
                    start_ms=start_ms,
                    end_ms=start_ms + duration_ms,
                    text=text,
                    language="en",
                    source_segment_ids=(f"segment-{candidate_id}",),
                ),
            ),
        )
    )


def _transcript(
    texts: tuple[str, ...],
    *,
    segment_duration_ms: int = 4_000,
) -> TranscriptArtifact:
    segments = tuple(
        TranscriptSegment(
            segment_id=f"segment-{index:04d}",
            source_id="source-real-regression",
            start_ms=(index - 1) * segment_duration_ms,
            end_ms=index * segment_duration_ms,
            text=text,
            text_sha256=hashlib.sha256(text.encode()).hexdigest(),
        )
        for index, text in enumerate(texts, start=1)
    )
    return TranscriptArtifact(
        document_type="transcript_artifact",
        created_at=datetime(2026, 8, 7, tzinfo=UTC),
        created_by="real-media-regression",
        transcript_id="transcript-real-regression",
        source_id="source-real-regression",
        language="en",
        segments=segments,
    )


def test_directed_topic_groups_filter_structurally_similar_but_irrelevant_content() -> None:
    candidates = (
        _candidate(
            "course-challenge",
            "The course is difficult; therefore, putting in time creates higher returns.",
            0,
        ),
        _candidate(
            "binary",
            "We use base two; therefore, each finger has two states to represent information.",
            30_000,
        ),
    )
    request = resolve_educational_request(
        ControlMode.DIRECTED,
        "只保留一个能独立解释二进制如何表示信息并包含完整推理链的片段。",
        required_topic_groups=(("binary", "base two", "zeros and ones"),),
    )

    result = select_educational_for_request(candidates, request)

    assert result.selected_candidate_ids == ("binary",)
    assert result.unsatisfied_requirements == ()


def test_topic_specific_directed_request_fails_closed_without_host_resolution() -> None:
    candidate = _candidate(
        "irrelevant",
        "The course is difficult and therefore practice improves the final result.",
        0,
    )
    request = resolve_educational_request(
        ControlMode.DIRECTED,
        "只保留一个能解释二进制如何表示信息的推理片段。",
    )

    result = select_educational_for_request((candidate,), request)

    assert request.unresolved_semantic_instruction is True
    assert result.selected_candidate_ids == ()
    assert "educational_topic_constraints_unresolved" in result.unsatisfied_requirements


def test_structural_only_directed_request_needs_no_topic_resolution() -> None:
    request = resolve_educational_request(
        ControlMode.DIRECTED,
        "只要两个例题，不要定义。",  # noqa: RUF001
    )

    assert request.unresolved_semantic_instruction is False


def test_directed_topic_groups_fail_closed_when_no_candidate_covers_every_concept() -> None:
    candidates = (
        _candidate("algorithm", "An algorithm is a function from inputs to outputs.", 0),
        _candidate(
            "efficiency",
            "Therefore, efficiency controls how long computation takes.",
            30_000,
        ),
    )
    request = resolve_educational_request(
        ControlMode.DIRECTED,
        "解释算法、正确性与效率。",
        required_topic_groups=(
            ("algorithm",),
            ("correct", "correctness"),
            ("efficient", "efficiency"),
        ),
    )

    result = select_educational_for_request(candidates, request)

    assert result.selected_candidate_ids == ()
    assert "educational_required_count:1" in result.unsatisfied_requirements
    assert any(
        reason.startswith("missing_topic_group:")
        for qualification in result.qualifications
        for reason in qualification.reasons
    )


def test_directed_maximum_duration_is_a_hard_qualification() -> None:
    candidate = _candidate(
        "long-binary",
        "Therefore, binary representation uses two possible states to encode information.",
        0,
        duration_ms=70_000,
    )
    request = resolve_educational_request(
        ControlMode.DIRECTED,
        "只保留一个二进制推理片段，最多60秒。",  # noqa: RUF001
        required_topic_groups=(("binary",),),
    )

    result = select_educational_for_request((candidate,), request)

    assert request.maximum_duration_ms == 60_000
    assert result.selected_candidate_ids == ()
    assert result.qualifications[0].reasons[-1] == "exceeds_maximum_duration_ms:60000"


def test_general_psychology_definitions_are_valid_education_signals() -> None:
    candidates = propose_educational_candidates(
        _transcript(
            (
                "Psychology is often broken into five sub-areas.",
                "Neuroscience is the study of the mind by looking at the brain.",
                "Developmental psychology studies how people grow and learn.",
                "Cognitive psychology refers to a computational approach to the mind.",
                "Clinical psychology is the study of mental health and mental illness.",
            )
        )
    )

    assert candidates
    assert any(
        candidate.evidence_refs[0].snapshot is not None
        and "Neuroscience" in candidate.evidence_refs[0].snapshot
        for candidate in candidates
    )


def test_candidate_expansion_uses_complete_semantic_boundaries() -> None:
    candidates = propose_educational_candidates(
        _transcript(
            (
                "algorithm. Similarly, this mapping rejects an invalid output.",
                "And so, generally, an algorithm is a function.",
                "The function maps each input to one valid output.",
                "This complete sentence provides closing context.",
            )
        )
    )
    definition = next(
        candidate
        for candidate in candidates
        if "algorithm is a function" in candidate.summary.casefold()
    )

    snapshot = definition.evidence_refs[0].snapshot
    assert snapshot is not None
    assert not snapshot.startswith("algorithm.")
    assert snapshot.rstrip().endswith(".")
    assert definition.end_ms - definition.start_ms >= 15_000


def test_candidate_expansion_does_not_start_on_a_dependent_context_sentence() -> None:
    candidates = propose_educational_candidates(
        _transcript(
            (
                "This complete sentence establishes the surrounding lesson context.",
                "Similarly, this comparison",
                "still depends on",
                "the preceding statement.",
                "For example, binary search halves the remaining search space.",
                "This complete sentence closes the worked example.",
            )
        )
    )
    example = next(
        candidate
        for candidate in candidates
        if "binary search" in candidate.summary.casefold()
    )

    snapshot = example.evidence_refs[0].snapshot
    assert snapshot is not None
    assert snapshot.startswith("This complete sentence establishes")
    assert example.end_ms - example.start_ms >= 15_000


def test_long_dependent_core_still_expands_to_an_independent_start() -> None:
    candidates = propose_educational_candidates(
        _transcript(
            (
                "This complete sentence establishes the preceding algorithm context.",
                "And then, an algorithm is a function from inputs to valid outputs.",
                "This complete sentence closes the definition.",
            ),
            segment_duration_ms=16_000,
        )
    )
    definition = next(
        candidate
        for candidate in candidates
        if "algorithm is a function" in candidate.summary.casefold()
    )

    snapshot = definition.evidence_refs[0].snapshot
    assert snapshot is not None
    assert snapshot.startswith("This complete sentence establishes")


def test_expansion_prefers_forward_context_over_a_dependent_previous_chain() -> None:
    candidates = propose_educational_candidates(
        _transcript(
            (
                "Similarly, this comparison",
                "still depends on",
                "the preceding statement.",
                "An algorithm is a function from inputs to valid outputs.",
                "Okay.",
                "The mapping rejects every invalid output.",
                "This complete sentence closes the explanation.",
            )
        )
    )
    definition = next(
        candidate
        for candidate in candidates
        if "algorithm is a function" in candidate.summary.casefold()
    )

    snapshot = definition.evidence_refs[0].snapshot
    assert snapshot is not None
    assert snapshot.startswith("An algorithm is a function")
    assert snapshot.endswith("explanation.")


def test_topic_qualification_uses_core_statement_not_neighboring_context() -> None:
    candidates = propose_educational_candidates(
        _transcript(
            (
                "The course is difficult and therefore steady practice improves the final result.",
                "We use base two and therefore each finger has two possible states.",
                "A complete sentence provides neutral closing context.",
                "Another complete sentence keeps the media window realistic.",
            )
        )
    )
    request = resolve_educational_request(
        ControlMode.DIRECTED,
        "只保留一个二进制推理片段。",
        required_topic_groups=(("binary", "base two"),),
    )

    result = select_educational_for_request(candidates, request)
    selected = next(
        candidate
        for candidate in candidates
        if candidate.candidate_id in result.selected_candidate_ids
    )

    assert "base two" in selected.summary.casefold()


def test_dependent_reasoning_statement_can_use_its_required_previous_topic_context() -> None:
    candidates = propose_educational_candidates(
        _transcript(
            (
                "We use base two rather than unary representation.",
                (
                    "Because each finger can be down or up, every finger therefore "
                    "has two possible states."
                ),
                "A complete sentence provides neutral closing context.",
                "Another complete sentence keeps the media window realistic.",
            )
        )
    )
    request = resolve_educational_request(
        ControlMode.DIRECTED,
        "只保留一个二进制推理片段。",
        required_topic_groups=(("binary", "base two"),),
    )

    result = select_educational_for_request(candidates, request)

    assert result.selected_candidate_ids
    selected = next(
        candidate
        for candidate in candidates
        if candidate.candidate_id in result.selected_candidate_ids
    )
    assert selected.summary.startswith("Because")
    snapshot = selected.evidence_refs[0].snapshot
    assert snapshot is not None
    assert "base two" in snapshot.casefold()


def test_internal_discourse_marker_does_not_make_complete_window_context_dependent() -> None:
    candidates = propose_educational_candidates(
        _transcript(
            (
                "Base two represents information with two possible states.",
                "But this complete transition remains inside the selected window.",
                "Because each bit has two states, it can therefore encode a binary choice.",
                "This complete sentence closes the explanation.",
            )
        )
    )
    request = resolve_educational_request(
        ControlMode.DIRECTED,
        "只保留一个二进制推理片段。",
        required_topic_groups=(("binary", "base two"),),
    )

    result = select_educational_for_request(candidates, request)

    assert result.selected_candidate_ids
    selected = next(
        candidate
        for candidate in candidates
        if candidate.candidate_id in result.selected_candidate_ids
    )
    assert selected.educational_profile is not None
    assert selected.educational_profile.qualified is True


def test_candidate_cannot_borrow_an_education_signal_from_neighboring_context() -> None:
    candidates = propose_educational_candidates(
        _transcript(
            (
                "A transition sentence introduces the next topic.",
                "For example, binary search halves the remaining search space.",
                "A complete sentence closes the worked example.",
                "Another complete sentence keeps the window realistic.",
            )
        )
    )

    assert all(
        candidate.summary != "A transition sentence introduces the next topic."
        for candidate in candidates
    )
