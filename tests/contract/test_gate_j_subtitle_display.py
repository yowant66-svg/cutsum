from __future__ import annotations

from datetime import UTC, datetime

import pytest

from universal_cutup.application.subtitle_display import (
    materialize_display_units,
    semantic_source_groups,
    source_group_text,
)
from universal_cutup.domain.candidates import CutCandidate, EvidenceRef
from universal_cutup.domain.subtitles import (
    ContextualTranslationRecord,
    SubtitleDisplayUnit,
    subtitle_text_sha256,
)
from universal_cutup.domain.transcript import SubtitleCue
from universal_cutup.media.subtitles import semantic_two_line_text

FIXED_TIME = datetime(2026, 7, 31, tzinfo=UTC)


def _cue(index: int, text: str) -> SubtitleCue:
    return SubtitleCue(
        cue_id=f"cue-{index}",
        source_id="mit-source",
        start_ms=(index - 1) * 2_000,
        end_ms=index * 2_000,
        text=text,
        language="en",
        source_segment_ids=(f"segment-{index}",),
    )


def _record(
    cues: tuple[SubtitleCue, ...],
    translated_text: str,
) -> ContextualTranslationRecord:
    source_text = source_group_text(cues)
    return ContextualTranslationRecord(
        translation_record_id="translation-1",
        provider_record_ref="provider-translation",
        source_language="en",
        translation_language="zh-CN",
        source_cue_ids=tuple(cue.cue_id for cue in cues),
        source_text=source_text,
        preceding_context="The lecturer is defining a computational problem.",
        following_context="The lecturer next explains when an algorithm solves the problem.",
        translated_text=translated_text,
        glossary={
            "algorithm": "算法",
            "function": "函数",
            "input": "输入",
            "output": "输出",
            "computational problem": "计算问题",
            "binary relation": "二元关系",
        },
        source_text_sha256=subtitle_text_sha256(source_text),
        translation_sha256=subtitle_text_sha256(translated_text),
    )


def _legacy_force_to_source_cue_widths(
    value: str,
    character_counts: tuple[int, ...],
) -> tuple[str, ...]:
    boundaries = []
    consumed = 0
    for character_count in character_counts:
        boundaries.append(value[consumed : consumed + character_count])
        consumed += character_count
    assert consumed == len(value)
    return tuple(boundaries)


def test_gate_i_equal_count_split_reproduces_chinese_word_fragments() -> None:
    fragments = _legacy_force_to_source_cue_widths(
        "算法是一套有限而明确的步骤。",
        (3, 4, 3, 2, 2),
    )
    assert fragments == ("算法是", "一套有限", "而明确", "的步", "骤。")


def test_multiple_source_cues_materialize_one_semantic_display_unit() -> None:
    cues = (
        _cue(1, "we want is a an algorithm is a function."),
        _cue(2, "It takes inputs to outputs."),
        _cue(3, "An algorithm is some kind of function,"),
        _cue(4, "that maps each input to a single output,"),
        _cue(5, "and that output must be correct."),
    )
    translation = "算法是一个函数：它把每个输入映射到一个满足问题要求的正确输出。"  # noqa: RUF001
    record = _record(cues, translation)
    units = materialize_display_units(
        cues,
        (record,),
        source_id="mit-source",
    )
    assert len(units) == 1
    assert units[0].source_cue_ids == tuple(cue.cue_id for cue in cues)
    assert units[0].start_ms == cues[0].start_ms
    assert units[0].end_ms == cues[-1].end_ms
    assert units[0].translated_text == translation


def test_semantic_grouping_uses_sentence_and_gap_boundaries_not_character_count() -> None:
    cues = (
        _cue(1, "An algorithm is a function."),
        _cue(2, "It maps inputs"),
        _cue(3, "to outputs."),
        _cue(4, "Next topic."),
    )
    groups = semantic_source_groups(cues)
    assert tuple(tuple(cue.cue_id for cue in group) for group in groups) == (
        ("cue-1",),
        ("cue-2", "cue-3"),
        ("cue-4",),
    )


def test_display_unit_rejects_isolated_chinese_function_word() -> None:
    with pytest.raises(ValueError, match="isolated function word"):
        SubtitleDisplayUnit(
            display_unit_id="display-1",
            source_id="mit-source",
            start_ms=0,
            end_ms=2_000,
            source_cue_ids=("cue-1",),
            source_text="is",
            translated_text="是",
            source_language="en",
            translation_language="zh-CN",
            segmentation_reason="semantic sentence",
            translation_record_ref="translation-1",
        )


def test_cjk_visual_wrap_uses_semantic_punctuation_without_splitting_input() -> None:
    text = (
        "计算问题是输入集合与输出集合之间的二元关系。"
        "对于每个输入，它规定哪些输出是正确的。"  # noqa: RUF001
    )

    wrapped = semantic_two_line_text(text)

    assert wrapped == (
        "计算问题是输入集合与输出集合之间的二元关系。\n对于每个输入，它规定哪些输出是正确的。"  # noqa: RUF001
    )
    assert "输\n入" not in wrapped


def test_candidate_preserves_source_cues_and_validates_display_mapping() -> None:
    cues = (_cue(1, "An algorithm is a function."), _cue(2, "It maps inputs to outputs."))
    record = _record(cues, "算法是一个把输入映射为输出的函数。")
    units = materialize_display_units(cues, (record,), source_id="mit-source")
    evidence = EvidenceRef(
        evidence_id="evidence-1",
        artifact_id="transcript-1",
        segment_ids=("segment-1", "segment-2"),
        start_ms=0,
        end_ms=4_000,
        text_sha256="a" * 64,
    )
    candidate = CutCandidate(
        candidate_id="candidate-1",
        source_id="mit-source",
        start_ms=0,
        end_ms=4_000,
        summary="Algorithm definition",
        evidence_refs=(evidence,),
        subtitle_cues=cues,
        subtitle_display_units=units,
        contextual_translation_records=(record,),
    )
    assert candidate.subtitle_cues == cues
    assert candidate.subtitle_display_units[0].source_cue_ids == ("cue-1", "cue-2")
