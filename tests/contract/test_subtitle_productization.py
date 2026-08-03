from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from universal_cutup.application.subtitle_readability import assess_subtitle_readability
from universal_cutup.domain.candidates import CutCandidate, EvidenceRef
from universal_cutup.domain.specs import SubtitleMode, SubtitleSidecarFormat, SubtitleSpec
from universal_cutup.domain.subtitles import (
    SubtitleDisplayUnit,
    SubtitleSemanticLevel,
    SubtitleSemanticSpan,
    SubtitleTimingPrecision,
    SubtitleWordTiming,
)
from universal_cutup.domain.transcript import SubtitleCue
from universal_cutup.media.subtitles import clip_semantic_spans_to_candidate

FIXED_TIME = datetime(2026, 7, 31, tzinfo=UTC)


def _cue() -> SubtitleCue:
    return SubtitleCue(
        cue_id="cue-1",
        source_id="source-1",
        start_ms=1_000,
        end_ms=3_000,
        text="An algorithm is a function.",
        language="en",
        source_segment_ids=("segment-1",),
    )


def _evidence() -> EvidenceRef:
    return EvidenceRef(
        evidence_id="evidence-1",
        artifact_id="transcript-1",
        segment_ids=("segment-1",),
        start_ms=1_000,
        end_ms=3_000,
        text_sha256="a" * 64,
    )


def _display_unit(
    translated_text: str,
    *,
    start_ms: int = 1_000,
    end_ms: int = 3_000,
) -> SubtitleDisplayUnit:
    return SubtitleDisplayUnit(
        display_unit_id="display-1",
        source_id="source-1",
        start_ms=start_ms,
        end_ms=end_ms,
        source_cue_ids=("cue-1",),
        source_text="Algorithm.",
        translated_text=translated_text,
        source_language="en",
        translation_language="zh-CN",
        semantic_level=SubtitleSemanticLevel.SENTENCE,
        timing_precision=SubtitleTimingPrecision.EXACT,
        segmentation_reason="terminal punctuation",
        translation_record_ref="translation-1",
    )


def test_word_timing_must_stay_inside_referenced_source_cue() -> None:
    cue = _cue()
    outside = SubtitleWordTiming(
        word_timing_id="word-1",
        source_id="source-1",
        start_ms=900,
        end_ms=1_300,
        text="algorithm",
        source_cue_ids=("cue-1",),
        timing_precision=SubtitleTimingPrecision.EXACT,
    )

    with pytest.raises(ValidationError, match="word timing must stay within covered source cues"):
        CutCandidate(
            candidate_id="candidate-1",
            source_id="source-1",
            start_ms=1_000,
            end_ms=3_000,
            summary="Algorithm definition",
            evidence_refs=(_evidence(),),
            subtitle_cues=(cue,),
            subtitle_word_timings=(outside,),
        )


def test_estimated_word_timing_is_explicit_and_candidate_valid() -> None:
    word = SubtitleWordTiming(
        word_timing_id="word-1",
        source_id="source-1",
        start_ms=1_000,
        end_ms=1_500,
        text="algorithm",
        source_cue_ids=("cue-1",),
        timing_precision=SubtitleTimingPrecision.ESTIMATED,
    )
    candidate = CutCandidate(
        candidate_id="candidate-1",
        source_id="source-1",
        start_ms=1_000,
        end_ms=3_000,
        summary="Algorithm definition",
        evidence_refs=(_evidence(),),
        subtitle_cues=(_cue(),),
        subtitle_word_timings=(word,),
    )

    assert candidate.subtitle_word_timings[0].timing_precision == "estimated"


def test_candidate_preserves_estimated_semantic_span_mapping() -> None:
    span = SubtitleSemanticSpan(
        semantic_span_id="semantic-1",
        source_id="source-1",
        start_ms=1_000,
        end_ms=2_100,
        source_cue_ids=("cue-1",),
        text="An algorithm is a function.",
        language="en",
        semantic_level=SubtitleSemanticLevel.SENTENCE,
        timing_precision=SubtitleTimingPrecision.ESTIMATED,
    )
    candidate = CutCandidate(
        candidate_id="candidate-1",
        source_id="source-1",
        start_ms=1_000,
        end_ms=3_000,
        summary="Algorithm definition",
        evidence_refs=(_evidence(),),
        subtitle_cues=(_cue(),),
        subtitle_semantic_spans=(span,),
    )

    assert candidate.subtitle_semantic_spans == (span,)


def test_semantic_spans_become_source_timeline_cues_without_micro_fragments() -> None:
    span = SubtitleSemanticSpan(
        semantic_span_id="semantic-1",
        source_id="source-1",
        start_ms=1_000,
        end_ms=5_000,
        source_cue_ids=("cue-1", "cue-2"),
        text="An algorithm maps every input to a correct output.",
        language="en",
        semantic_level=SubtitleSemanticLevel.SENTENCE,
        timing_precision=SubtitleTimingPrecision.ESTIMATED,
    )

    clipped = clip_semantic_spans_to_candidate(
        (span,),
        candidate_start_ms=500,
        candidate_end_ms=5_500,
    )

    assert tuple(cue.text for cue in clipped) == (
        "An algorithm maps every input to a correct output.",
    )
    assert (clipped[0].start_ms, clipped[0].end_ms) == (500, 4_500)


def test_readability_report_flags_speed_and_visual_line_pressure() -> None:
    unit = _display_unit(
        "算法是一种函数，它把输入映射为输出，而且输出必须满足问题定义的正确性要求。",  # noqa: RUF001
        end_ms=2_000,
    )

    report = assess_subtitle_readability(
        (unit,),
        max_characters_per_second=12,
        max_characters_per_line=16,
        max_lines=2,
    )

    assert not report.passed
    assert {finding.code for finding in report.findings} == {
        "characters_per_second",
        "visual_line_limit",
    }
    assert report.maximum_characters_per_second > 12


def test_readability_report_accepts_complete_two_line_sentence() -> None:
    unit = _display_unit("算法是把输入映射为输出的函数。", end_ms=5_000)

    report = assess_subtitle_readability(
        (unit,),
        max_characters_per_second=12,
        max_characters_per_line=10,
        max_lines=2,
    )

    assert report.passed
    assert report.findings == ()
    assert report.unit_count == 1


def test_bilingual_sidecar_and_format_are_explicit_protocol_values() -> None:
    spec = SubtitleSpec(
        mode=SubtitleMode.BILINGUAL_SIDECAR,
        sidecar_format=SubtitleSidecarFormat.VTT,
        language="en",
        translation_language="zh-CN",
    )

    assert spec.mode == "bilingual_sidecar"
    assert spec.sidecar_format == "vtt"
