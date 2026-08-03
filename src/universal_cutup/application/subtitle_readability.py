from __future__ import annotations

import math
import re

from universal_cutup.domain.subtitles import (
    ISOLATED_CHINESE_FUNCTION_WORDS,
    SubtitleDisplayUnit,
    SubtitleReadabilityCode,
    SubtitleReadabilityFinding,
    SubtitleReadabilityReport,
)

CJK_CONTENT_PATTERN = re.compile(r"[\u3400-\u9fff]")


def assess_subtitle_readability(
    units: tuple[SubtitleDisplayUnit, ...],
    *,
    max_characters_per_second: float,
    max_characters_per_line: int,
    max_lines: int,
) -> SubtitleReadabilityReport:
    if max_characters_per_second <= 0:
        raise ValueError("max_characters_per_second must be positive")
    if max_characters_per_line <= 0:
        raise ValueError("max_characters_per_line must be positive")
    if max_lines <= 0:
        raise ValueError("max_lines must be positive")
    findings: list[SubtitleReadabilityFinding] = []
    maximum_characters_per_second = 0.0
    for unit in units:
        duration_seconds = (unit.end_ms - unit.start_ms) / 1000
        for language, text in (
            (unit.source_language, unit.source_text),
            (unit.translation_language, unit.translated_text),
        ):
            character_count = len("".join(text.split()))
            characters_per_second = character_count / duration_seconds
            maximum_characters_per_second = max(
                maximum_characters_per_second,
                characters_per_second,
            )
            if characters_per_second > max_characters_per_second:
                findings.append(
                    SubtitleReadabilityFinding(
                        finding_id=(f"{unit.display_unit_id}-{language}-characters-per-second"),
                        code=SubtitleReadabilityCode.CHARACTERS_PER_SECOND,
                        display_unit_id=unit.display_unit_id,
                        language=language,
                        observed=characters_per_second,
                        limit=max_characters_per_second,
                    )
                )
            visual_lines = math.ceil(character_count / max_characters_per_line)
            if visual_lines > max_lines:
                findings.append(
                    SubtitleReadabilityFinding(
                        finding_id=f"{unit.display_unit_id}-{language}-visual-line-limit",
                        code=SubtitleReadabilityCode.VISUAL_LINE_LIMIT,
                        display_unit_id=unit.display_unit_id,
                        language=language,
                        observed=float(visual_lines),
                        limit=float(max_lines),
                    )
                )
            cjk_characters = tuple(CJK_CONTENT_PATTERN.findall(text))
            is_semantic_fragment = bool(
                cjk_characters
                and unit.semantic_level == "phrase"
                and (
                    len(cjk_characters) <= 2
                    or cjk_characters[0] in ISOLATED_CHINESE_FUNCTION_WORDS
                    or cjk_characters[-1] in ISOLATED_CHINESE_FUNCTION_WORDS
                )
            )
            if is_semantic_fragment:
                findings.append(
                    SubtitleReadabilityFinding(
                        finding_id=f"{unit.display_unit_id}-{language}-semantic-fragment",
                        code=SubtitleReadabilityCode.SEMANTIC_FRAGMENT,
                        display_unit_id=unit.display_unit_id,
                        language=language,
                        observed=float(len(cjk_characters)),
                        limit=3,
                    )
                )
    return SubtitleReadabilityReport(
        passed=not findings,
        unit_count=len(units),
        maximum_characters_per_second=maximum_characters_per_second,
        findings=tuple(findings),
    )
