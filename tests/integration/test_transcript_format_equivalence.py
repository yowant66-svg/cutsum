from __future__ import annotations

import json
from datetime import UTC, datetime

from universal_cutup.adapters.transcripts import (
    TranscriptParseContext,
    parse_json_transcript,
    parse_srt,
    parse_vtt,
)


def test_srt_vtt_and_json_have_equivalent_timeline_semantics() -> None:
    context = TranscriptParseContext(
        transcript_id="transcript-formats",
        source_id="source-formats",
        created_at=datetime(2026, 7, 30, tzinfo=UTC),
        created_by="test-suite",
    )
    artifacts = (
        parse_srt(
            "1\r\n00:00:00,500 --> 00:00:01,500\r\nEquivalent text\r\n",
            context=context,
        ),
        parse_vtt(
            "\ufeffWEBVTT\n\ncue-a\n00:00.500 --> 00:01.500 align:start\nEquivalent text\n",
            context=context,
        ),
        parse_json_transcript(
            json.dumps(
                {
                    "segments": [
                        {
                            "start_ms": 500,
                            "end_ms": 1500,
                            "text": "Equivalent text",
                        }
                    ]
                }
            ),
            context=context,
        ),
    )
    semantics = [
        [
            (segment.start_ms, segment.end_ms, segment.text, segment.text_sha256)
            for segment in artifact.segments
        ]
        for artifact in artifacts
    ]
    assert semantics[0] == semantics[1] == semantics[2]
