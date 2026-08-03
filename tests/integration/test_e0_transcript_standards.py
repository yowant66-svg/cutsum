from __future__ import annotations

import json
from datetime import UTC, datetime

from universal_cutup.adapters.transcripts import (
    TranscriptParseContext,
    parse_json_transcript,
    parse_vtt,
)

CONTEXT = TranscriptParseContext(
    transcript_id="transcript-standard",
    source_id="source-1",
    created_at=datetime(2026, 7, 30, 12, 0, tzinfo=UTC),
    created_by="test-suite",
)


def test_vtt_supports_bom_identifiers_short_time_settings_and_metadata() -> None:
    vtt = """\ufeffWEBVTT

STYLE
::cue { color: lime; }

REGION
id:fred

NOTE ignored metadata
still ignored

cue-alpha
00:01.000 --> 00:03.000 align:start position:10%
<v Alice>First &amp; overlapping</v>

cue-beta
00:02.500 --> 00:04.000 line:90%
Second cue
"""
    artifact = parse_vtt(vtt, context=CONTEXT)
    assert [(segment.start_ms, segment.end_ms) for segment in artifact.segments] == [
        (1000, 3000),
        (2500, 4000),
    ]
    assert artifact.segments[0].text == "First & overlapping"
    assert artifact.segments[0].cue_identifier == "cue-alpha"


def test_json_preserves_speaker_and_confidence() -> None:
    content = json.dumps(
        {
            "segments": [
                {
                    "start_ms": 0,
                    "end_ms": 1000,
                    "text": "hello",
                    "speaker": "Alice",
                    "confidence": 0.91,
                }
            ]
        }
    )
    artifact = parse_json_transcript(content, context=CONTEXT)
    assert artifact.segments[0].speaker == "Alice"
    assert artifact.segments[0].confidence == 0.91
