from __future__ import annotations

import pytest

from universal_cutup.adapters.youtube_json3 import normalize_youtube_json3


def test_json3_normalization_removes_append_markers_and_clips_window() -> None:
    payload = {
        "events": [
            {"tStartMs": 0, "dDurationMs": 10_000, "id": 1},
            {
                "tStartMs": 1_000,
                "dDurationMs": 4_000,
                "segs": [{"utf8": "A"}, {"utf8": " clean"}, {"utf8": " sentence."}],
            },
            {"tStartMs": 2_900, "segs": [{"utf8": "\n"}]},
            {
                "tStartMs": 3_000,
                "dDurationMs": 4_000,
                "segs": [{"utf8": "Second"}, {"utf8": " thought."}],
            },
            {
                "tStartMs": 7_000,
                "dDurationMs": 2_000,
                "segs": [{"utf8": "Outside window"}],
            },
        ]
    }
    assert normalize_youtube_json3(payload, maximum_end_ms=6_000) == {
        "segments": [
            {"start_ms": 1_000, "end_ms": 3_000, "text": "A clean sentence."},
            {"start_ms": 3_000, "end_ms": 6_000, "text": "Second thought."},
        ]
    }


def test_json3_normalization_rejects_invalid_or_empty_payload() -> None:
    with pytest.raises(ValueError, match="events array"):
        normalize_youtube_json3({})
    with pytest.raises(ValueError, match="no usable"):
        normalize_youtube_json3({"events": [{"tStartMs": 0}]})
