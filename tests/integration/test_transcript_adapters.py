from __future__ import annotations

import json
from datetime import UTC, datetime

from universal_cutup.adapters.transcripts import (
    TranscriptParseContext,
    parse_json_transcript,
    parse_srt,
    parse_vtt,
)
from universal_cutup.hashing import semantic_fingerprint

FIXED_TIME = datetime(2026, 7, 30, 12, 0, tzinfo=UTC)
CONTEXT = TranscriptParseContext(
    transcript_id="transcript-1",
    source_id="source-1",
    created_at=FIXED_TIME,
    created_by="test-suite",
)
SRT = """1
00:00:00,000 --> 00:00:01,250
你好世界

2
00:00:01,250 --> 00:00:03,000
No spaces are required.
"""
VTT = """WEBVTT

00:00:00.000 --> 00:00:01.250
你好世界

00:00:01.250 --> 00:00:03.000
No spaces are required.
"""
JSON_TRANSCRIPT = json.dumps(
    {
        "segments": [
            {"start_ms": 0, "end_ms": 1250, "text": "你好世界"},
            {
                "start_ms": 1250,
                "end_ms": 3000,
                "text": "No spaces are required.",
            },
        ]
    }
)


def test_equivalent_srt_vtt_and_json_produce_equivalent_artifacts() -> None:
    artifacts = (
        parse_srt(SRT, context=CONTEXT),
        parse_vtt(VTT, context=CONTEXT),
        parse_json_transcript(JSON_TRANSCRIPT, context=CONTEXT),
    )
    assert artifacts[0] == artifacts[1] == artifacts[2]
    assert len({semantic_fingerprint(artifact) for artifact in artifacts}) == 1
