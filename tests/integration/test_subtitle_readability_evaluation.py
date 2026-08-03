from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from universal_cutup.application.subtitle_readability import assess_subtitle_readability
from universal_cutup.domain.subtitles import SubtitleDisplayUnit

CASES_PATH = Path(__file__).parents[2] / "evaluation" / "subtitle-readability-cases.json"


def _unit(case_id: str, index: int, payload: dict[str, Any]) -> SubtitleDisplayUnit:
    return SubtitleDisplayUnit(
        display_unit_id=f"{case_id}-display-{index}",
        source_id=f"{case_id}-source",
        start_ms=payload["start_ms"],
        end_ms=payload["end_ms"],
        source_cue_ids=(f"{case_id}-cue-{index}",),
        source_text=payload["source_text"],
        translated_text=payload["translated_text"],
        source_language="en",
        translation_language="zh-CN",
        semantic_level=payload["semantic_level"],
        segmentation_reason="evaluation fixture",
        translation_record_ref=f"{case_id}-translation-{index}",
    )


def test_subtitle_readability_cases_match_expected_human_failure_classes() -> None:
    payload = json.loads(CASES_PATH.read_text())

    for case in payload["cases"]:
        units = tuple(
            _unit(case["case_id"], index, unit) for index, unit in enumerate(case["units"], start=1)
        )
        report = assess_subtitle_readability(
            units,
            max_characters_per_second=20,
            max_characters_per_line=34,
            max_lines=2,
        )
        assert report.passed is case["expected_pass"], case["case_id"]
        assert set(case["expected_codes"]) <= {finding.code.value for finding in report.findings}
