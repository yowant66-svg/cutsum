from __future__ import annotations

from universal_cutup.application.subtitle_display import semantic_source_spans
from universal_cutup.domain.subtitles import (
    SubtitleSemanticLevel,
    SubtitleTimingPrecision,
)
from universal_cutup.domain.transcript import SubtitleCue


def _cue(
    cue_id: str,
    text: str,
    start_ms: int,
    end_ms: int,
    *,
    speaker: str | None = None,
) -> SubtitleCue:
    return SubtitleCue(
        cue_id=cue_id,
        source_id="source-1",
        start_ms=start_ms,
        end_ms=end_ms,
        text=text,
        language="en",
        speaker=speaker,
        source_segment_ids=(f"segment-{cue_id}",),
    )


def test_punctuation_inside_one_source_cue_creates_two_estimated_sentences() -> None:
    cue = _cue(
        "cue-1",
        "A problem is a binary relation. Each input can have valid outputs.",
        0,
        8_000,
    )

    spans = semantic_source_spans((cue,))

    assert tuple(span.text for span in spans) == (
        "A problem is a binary relation.",
        "Each input can have valid outputs.",
    )
    assert spans[0].end_ms == spans[1].start_ms
    assert spans[0].source_cue_ids == ("cue-1",)
    assert spans[0].timing_precision is SubtitleTimingPrecision.ESTIMATED
    assert all(span.semantic_level is SubtitleSemanticLevel.SENTENCE for span in spans)


def test_sentence_can_cross_multiple_source_cues() -> None:
    cues = (
        _cue("cue-1", "An algorithm maps each", 0, 2_000),
        _cue("cue-2", "input to one correct output.", 2_000, 4_000),
    )

    spans = semantic_source_spans(cues)

    assert len(spans) == 1
    assert spans[0].text == "An algorithm maps each input to one correct output."
    assert spans[0].source_cue_ids == ("cue-1", "cue-2")
    assert spans[0].start_ms == 0
    assert spans[0].end_ms == 4_000
    assert spans[0].timing_precision is SubtitleTimingPrecision.EXACT


def test_speaker_change_and_large_gap_force_phrase_boundaries() -> None:
    cues = (
        _cue("cue-1", "First unfinished thought", 0, 2_000, speaker="teacher"),
        _cue("cue-2", "student interruption", 2_000, 3_000, speaker="student"),
        _cue("cue-3", "Later continuation", 4_500, 6_000, speaker="student"),
    )

    spans = semantic_source_spans(cues, maximum_gap_ms=900)

    assert tuple(span.text for span in spans) == (
        "First unfinished thought",
        "student interruption",
        "Later continuation",
    )
    assert all(span.semantic_level is SubtitleSemanticLevel.PHRASE for span in spans)


def test_long_sentence_splits_at_clause_boundary_without_fixed_width_cut() -> None:
    cue = _cue(
        "cue-1",
        "First we define the inputs, then we identify valid outputs, and finally we map them.",
        0,
        15_000,
    )

    spans = semantic_source_spans((cue,), maximum_display_duration_ms=7_000)

    assert tuple(span.text for span in spans) == (
        "First we define the inputs,",
        "then we identify valid outputs,",
        "and finally we map them.",
    )
    assert tuple(span.semantic_level for span in spans) == (
        SubtitleSemanticLevel.CLAUSE,
        SubtitleSemanticLevel.CLAUSE,
        SubtitleSemanticLevel.SENTENCE,
    )
    assert spans[0].end_ms == spans[1].start_ms
    assert spans[1].end_ms == spans[2].start_ms


def test_chinese_sentence_and_clause_boundaries_preserve_function_words() -> None:
    cue = _cue(
        "cue-1",
        "算法是一种函数，它把输入映射为输出。这个输出必须满足问题要求。",  # noqa: RUF001
        0,
        9_000,
    )

    spans = semantic_source_spans((cue,), maximum_display_duration_ms=6_000)

    assert tuple(span.text for span in spans) == (
        "算法是一种函数，它把输入映射为输出。",  # noqa: RUF001
        "这个输出必须满足问题要求。",
    )
    assert all(span.text not in {"的", "了", "是", "因", "此"} for span in spans)
