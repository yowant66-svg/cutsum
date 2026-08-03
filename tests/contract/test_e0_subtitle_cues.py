from __future__ import annotations

import pytest
from pydantic import ValidationError

from universal_cutup.domain.candidates import CutCandidate, EvidenceRef
from universal_cutup.domain.transcript import SubtitleCue


def make_evidence() -> EvidenceRef:
    return EvidenceRef(
        evidence_id="evidence-1",
        artifact_id="transcript-1",
        segment_ids=("segment-1",),
        start_ms=1000,
        end_ms=3000,
        text_sha256="a" * 64,
    )


def test_candidate_accepts_overlapping_source_timeline_cue() -> None:
    cue = SubtitleCue(
        cue_id="cue-1",
        source_id="source-1",
        start_ms=500,
        end_ms=1500,
        text="真实字幕",
        source_segment_ids=("segment-1",),
    )
    candidate = CutCandidate(
        candidate_id="candidate-1",
        source_id="source-1",
        start_ms=1000,
        end_ms=3000,
        summary="摘要与字幕不同",
        evidence_refs=(make_evidence(),),
        subtitle_cues=(cue,),
    )
    assert candidate.subtitle_cues == (cue,)


def test_candidate_rejects_non_overlapping_cue() -> None:
    cue = SubtitleCue(
        cue_id="cue-1",
        source_id="source-1",
        start_ms=0,
        end_ms=500,
        text="outside",
        source_segment_ids=("segment-1",),
    )
    with pytest.raises(ValidationError):
        CutCandidate(
            candidate_id="candidate-1",
            source_id="source-1",
            start_ms=1000,
            end_ms=3000,
            summary="summary",
            evidence_refs=(make_evidence(),),
            subtitle_cues=(cue,),
        )


def test_candidate_rejects_duplicate_cue_ids() -> None:
    cue = SubtitleCue(
        cue_id="cue-1",
        source_id="source-1",
        start_ms=1000,
        end_ms=1500,
        text="cue",
        source_segment_ids=("segment-1",),
    )
    with pytest.raises(ValidationError):
        CutCandidate(
            candidate_id="candidate-1",
            source_id="source-1",
            start_ms=1000,
            end_ms=3000,
            summary="summary",
            evidence_refs=(make_evidence(),),
            subtitle_cues=(cue, cue),
        )
