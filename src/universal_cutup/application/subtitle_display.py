from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

from universal_cutup.domain.subtitles import (
    ContextualTranslationRecord,
    SubtitleDisplayUnit,
    SubtitleSemanticLevel,
    SubtitleSemanticSpan,
    SubtitleTimingPrecision,
)
from universal_cutup.domain.transcript import SubtitleCue

SENTENCE_ENDINGS = (".", "?", "!", "。", "？", "！")  # noqa: RUF001
CLAUSE_ENDINGS = (",", ";", ":", "，", "；", "：")  # noqa: RUF001
SEMANTIC_FRAGMENT_PATTERN = re.compile(
    r"[^.!?。！？,;:，；：]+(?:[.!?。！？,;:，；：]|$)"  # noqa: RUF001
)
CJK_PATTERN = re.compile(r"[\u3400-\u9fff]")
CJK_PUNCTUATION = frozenset("。！？；：，、")  # noqa: RUF001


@dataclass(frozen=True, slots=True)
class _TimedFragment:
    text: str
    start_ms: int
    end_ms: int
    source_cue_id: str
    boundary_level: SubtitleSemanticLevel
    timing_precision: SubtitleTimingPrecision


def semantic_source_spans(
    cues: tuple[SubtitleCue, ...],
    *,
    maximum_display_duration_ms: int = 12_000,
    maximum_gap_ms: int = 900,
) -> tuple[SubtitleSemanticSpan, ...]:
    if maximum_display_duration_ms <= 0:
        raise ValueError("maximum_display_duration_ms must be positive")
    if maximum_gap_ms < 0:
        raise ValueError("maximum_gap_ms cannot be negative")
    spans: list[SubtitleSemanticSpan] = []
    current: list[_TimedFragment] = []

    def flush(level: SubtitleSemanticLevel) -> None:
        if not current:
            return
        cue_ids = tuple(dict.fromkeys(fragment.source_cue_id for fragment in current))
        spans.append(
            SubtitleSemanticSpan(
                semantic_span_id=f"semantic-{len(spans) + 1:04d}",
                source_id=cues_by_id[cue_ids[0]].source_id,
                start_ms=current[0].start_ms,
                end_ms=current[-1].end_ms,
                source_cue_ids=cue_ids,
                text=_join_fragments(tuple(fragment.text for fragment in current)),
                language=cues_by_id[cue_ids[0]].language or "und",
                semantic_level=level,
                timing_precision=(
                    SubtitleTimingPrecision.EXACT
                    if all(
                        fragment.timing_precision is SubtitleTimingPrecision.EXACT
                        for fragment in current
                    )
                    else SubtitleTimingPrecision.ESTIMATED
                ),
            )
        )
        current.clear()

    cues_by_id = {cue.cue_id: cue for cue in cues}
    previous_cue: SubtitleCue | None = None
    for cue in cues:
        if previous_cue is not None and current:
            gap_ms = cue.start_ms - previous_cue.end_ms
            speaker_changed = (
                cue.speaker is not None
                and previous_cue.speaker is not None
                and cue.speaker != previous_cue.speaker
            )
            if gap_ms > maximum_gap_ms or speaker_changed:
                flush(SubtitleSemanticLevel.PHRASE)
        for fragment in _cue_fragments(cue):
            if (
                current
                and fragment.end_ms - current[0].start_ms > maximum_display_duration_ms
                and current[-1].boundary_level is SubtitleSemanticLevel.CLAUSE
            ):
                flush(SubtitleSemanticLevel.CLAUSE)
            current.append(fragment)
            if fragment.boundary_level is SubtitleSemanticLevel.SENTENCE:
                flush(SubtitleSemanticLevel.SENTENCE)
        previous_cue = cue
    flush(SubtitleSemanticLevel.PHRASE)
    return tuple(spans)


def _cue_fragments(cue: SubtitleCue) -> tuple[_TimedFragment, ...]:
    matches = tuple(
        match for match in SEMANTIC_FRAGMENT_PATTERN.finditer(cue.text) if match.group().strip()
    )
    if not matches:
        return ()
    cue_duration_ms = cue.end_ms - cue.start_ms
    fragments = []
    for match in matches:
        text = match.group().strip()
        start_ms = cue.start_ms + round(cue_duration_ms * match.start() / len(cue.text))
        end_ms = cue.start_ms + round(cue_duration_ms * match.end() / len(cue.text))
        last_character = text[-1]
        if last_character in SENTENCE_ENDINGS:
            boundary_level = SubtitleSemanticLevel.SENTENCE
        elif last_character in CLAUSE_ENDINGS:
            boundary_level = SubtitleSemanticLevel.CLAUSE
        else:
            boundary_level = SubtitleSemanticLevel.PHRASE
        fragments.append(
            _TimedFragment(
                text=text,
                start_ms=start_ms,
                end_ms=end_ms,
                source_cue_id=cue.cue_id,
                boundary_level=boundary_level,
                timing_precision=(
                    SubtitleTimingPrecision.EXACT
                    if len(matches) == 1
                    else SubtitleTimingPrecision.ESTIMATED
                ),
            )
        )
    return tuple(fragments)


def _join_fragments(values: tuple[str, ...]) -> str:
    result = ""
    for value in values:
        if not result:
            result = value
        elif CJK_PATTERN.match(value) and (
            CJK_PATTERN.match(result[-1]) or result[-1] in CJK_PUNCTUATION
        ):
            result += value
        else:
            result += f" {value}"
    return result


def semantic_source_groups(
    cues: tuple[SubtitleCue, ...],
    *,
    maximum_display_duration_ms: int = 12_000,
    maximum_gap_ms: int = 900,
) -> tuple[tuple[SubtitleCue, ...], ...]:
    if maximum_display_duration_ms <= 0:
        raise ValueError("maximum_display_duration_ms must be positive")
    if maximum_gap_ms < 0:
        raise ValueError("maximum_gap_ms cannot be negative")
    groups: list[tuple[SubtitleCue, ...]] = []
    current: list[SubtitleCue] = []
    for cue in cues:
        if current:
            gap_ms = cue.start_ms - current[-1].end_ms
            speaker_changed = (
                cue.speaker is not None
                and current[-1].speaker is not None
                and cue.speaker != current[-1].speaker
            )
            if gap_ms > maximum_gap_ms or speaker_changed:
                groups.append(tuple(current))
                current = []
        current.append(cue)
        duration_ms = current[-1].end_ms - current[0].start_ms
        if cue.text.rstrip().endswith(SENTENCE_ENDINGS):
            groups.append(tuple(current))
            current = []
        elif duration_ms >= maximum_display_duration_ms:
            split_index = _latest_clause_boundary(current)
            if split_index is not None:
                groups.append(tuple(current[:split_index]))
                current = current[split_index:]
    if current:
        groups.append(tuple(current))
    return tuple(groups)


def _latest_clause_boundary(cues: Sequence[SubtitleCue]) -> int | None:
    for index in range(len(cues) - 1, 0, -1):
        if cues[index - 1].text.rstrip().endswith(CLAUSE_ENDINGS):
            return index
    return None


def source_group_text(cues: Sequence[SubtitleCue]) -> str:
    return " ".join(cue.text.strip() for cue in cues)


def materialize_display_units(
    source_cues: tuple[SubtitleCue, ...],
    translation_records: tuple[ContextualTranslationRecord, ...],
    *,
    source_id: str,
    segmentation_reason: str = "semantic_sentence_with_context_translation",
) -> tuple[SubtitleDisplayUnit, ...]:
    cues_by_id = {cue.cue_id: cue for cue in source_cues}
    cue_positions = {cue.cue_id: index for index, cue in enumerate(source_cues)}
    units: list[SubtitleDisplayUnit] = []
    used_cue_ids: set[str] = set()
    for index, record in enumerate(translation_records, start=1):
        try:
            covered = tuple(cues_by_id[cue_id] for cue_id in record.source_cue_ids)
        except KeyError as error:
            raise ValueError(
                f"translation references unknown source cue: {error.args[0]}"
            ) from error
        positions = [cue_positions[cue.cue_id] for cue in covered]
        if positions != list(range(positions[0], positions[-1] + 1)):
            raise ValueError("translation source cues must form one contiguous timeline span")
        if used_cue_ids & set(record.source_cue_ids):
            raise ValueError("translation records cannot reuse source cues")
        derived_source_text = source_group_text(covered)
        if record.source_text != derived_source_text:
            raise ValueError("translation source_text must preserve the covered source cue text")
        used_cue_ids.update(record.source_cue_ids)
        units.append(
            SubtitleDisplayUnit(
                display_unit_id=f"display-{index:04d}-{record.translation_record_id}",
                source_id=source_id,
                start_ms=min(cue.start_ms for cue in covered),
                end_ms=max(cue.end_ms for cue in covered),
                source_cue_ids=record.source_cue_ids,
                source_text=record.source_text,
                translated_text=record.translated_text,
                source_language=record.source_language,
                translation_language=record.translation_language,
                segmentation_reason=segmentation_reason,
                translation_record_ref=record.translation_record_id,
            )
        )
    return tuple(sorted(units, key=lambda unit: unit.start_ms))
