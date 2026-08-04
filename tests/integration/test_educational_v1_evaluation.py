from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from universal_cutup.application.educational import (
    create_educational_plan,
    propose_educational_candidates,
    resolve_educational_request,
    select_educational_for_request,
)
from universal_cutup.domain.intelligence import ControlMode
from universal_cutup.domain.sources import MediaSource, RightsAttestation
from universal_cutup.domain.transcript import TranscriptArtifact, TranscriptSegment

CASES_PATH = Path(__file__).parents[2] / "evaluation" / "educational-v1-cases.json"


def _transcript(payload: dict[str, object]) -> TranscriptArtifact:
    transcript_rows = cast(list[dict[str, object]], payload["transcript"])
    segments = tuple(
        TranscriptSegment(
            segment_id=f"segment-{index:02d}",
            source_id="source-education-eval",
            start_ms=cast(int, segment["start_ms"]),
            end_ms=cast(int, segment["end_ms"]),
            text=cast(str, segment["text"]),
            text_sha256=hashlib.sha256(cast(str, segment["text"]).encode()).hexdigest(),
        )
        for index, segment in enumerate(transcript_rows, start=1)
    )
    return TranscriptArtifact(
        document_type="transcript_artifact",
        created_at=datetime(2026, 7, 31, tzinfo=UTC),
        created_by="educational-v1-evaluation",
        transcript_id="transcript-education-eval",
        source_id="source-education-eval",
        language="en",
        segments=segments,
    )


def test_auto_and_natural_language_directed_runs_start_from_raw_transcript() -> None:
    payload = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    candidates = propose_educational_candidates(_transcript(payload))

    assert candidates
    assert all(candidate.end_ms - candidate.start_ms >= 15_000 for candidate in candidates)
    proposed_types = {
        signal.signal_type.value
        for candidate in candidates
        for signal in candidate.education_signals
    }
    assert set(cast(list[str], payload["expected_proposed_types"])) <= proposed_types
    unqualified_summaries = {
        candidate.summary
        for candidate in candidates
        if candidate.educational_profile is not None and not candidate.educational_profile.qualified
    }
    assert set(cast(list[str], payload["expected_unqualified_summaries"])) <= unqualified_summaries
    runs = cast(list[dict[str, object]], payload["runs"])
    for run in runs:
        request = resolve_educational_request(
            ControlMode(cast(str, run["mode"])),
            cast(str, run["instruction"]),
        )
        result = select_educational_for_request(candidates, request)
        selected = tuple(
            candidate
            for candidate in candidates
            if candidate.candidate_id in result.selected_candidate_ids
        )
        selected_types = {
            signal.signal_type.value
            for candidate in selected
            for signal in candidate.education_signals
        }
        assert set(cast(list[str], run["expected_selected_types"])) <= selected_types
        assert not set(cast(list[str], run["forbidden_selected_types"])) & selected_types
        assert all(
            candidate.candidate_id not in cast(str, run["instruction"]) for candidate in candidates
        )


def test_educational_plan_is_portable_and_covers_every_proposed_candidate() -> None:
    payload = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    transcript = _transcript(payload)
    request = resolve_educational_request(ControlMode.AUTO, "")
    source = MediaSource(
        source_id=transcript.source_id,
        media_id="media-education-eval",
        kind="video",
        sha256="a" * 64,
        basename_hint="fixture.mp4",
        rights_attestation=RightsAttestation.AUTHORIZED_OTHER,
        duration_ms=135_000,
    )

    plan = create_educational_plan(source, transcript, request)

    assert plan.selection_result.selected_candidate_ids
    assert {decision.candidate_id for decision in plan.selection_result.decisions} == {
        candidate.candidate_id for candidate in plan.candidates
    }
    assert plan.evidence_artifacts[0].artifact_id == transcript.transcript_id
