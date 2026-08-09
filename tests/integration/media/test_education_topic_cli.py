from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from universal_cutup.cli import app


def test_cli_accepts_host_resolved_topic_groups_for_directed_education(
    synthetic_media: Path,
    tmp_path: Path,
) -> None:
    transcript = tmp_path / "topic-directed.srt"
    transcript.write_text(
        (
            "1\n00:00:00,200 --> 00:00:01,200\n"
            "The course is difficult and therefore practice improves the result.\n\n"
            "2\n00:00:01,200 --> 00:00:02,200\n"
            "We use base two and therefore each bit has two possible states.\n"
        ),
        encoding="utf-8",
    )

    result = CliRunner().invoke(
        app,
        [
            "education-plan",
            str(synthetic_media),
            str(transcript),
            "--mode",
            "directed",
            "--instruction",
            "只保留一个二进制推理片段。",
            "--topic-group",
            "binary|base two|zeros and ones",
        ],
    )

    assert result.exit_code == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["request"]["required_topic_groups"] == [["binary", "base two", "zeros and ones"]]
    selected_ids = set(payload["selection"]["selected_candidate_ids"])
    selected = [
        candidate
        for candidate in payload["candidates"]
        if candidate["candidate_id"] in selected_ids
    ]
    assert len(selected) == 1
    assert "base two" in selected[0]["summary"].casefold()
