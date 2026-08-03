from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from universal_cutup.domain.intelligence import ControlMode
from universal_cutup.domain.sources import MediaSource, RightsAttestation
from universal_cutup.domain.transcript import TranscriptArtifact, TranscriptSegment
from universal_cutup.sdk import (
    load_sports_observations,
    load_transcript,
    plan_educational_content,
    plan_sports_content,
)

EDUCATION_CASES = Path(__file__).parents[2] / "evaluation" / "educational-v1-cases.json"
SPORTS_CASES = Path(__file__).parents[2] / "evaluation" / "sports-alpha-observations.json"


def _educational_transcript() -> TranscriptArtifact:
    payload = json.loads(EDUCATION_CASES.read_text(encoding="utf-8"))
    rows = cast(list[dict[str, object]], payload["transcript"])
    return TranscriptArtifact(
        document_type="transcript_artifact",
        created_at=datetime(2026, 7, 31, tzinfo=UTC),
        created_by="sdk-strategy-test",
        transcript_id="transcript-sdk-education",
        source_id="source-sdk-education",
        language="en",
        segments=tuple(
            TranscriptSegment(
                segment_id=f"segment-{index:02d}",
                source_id="source-sdk-education",
                start_ms=cast(int, row["start_ms"]),
                end_ms=cast(int, row["end_ms"]),
                text=cast(str, row["text"]),
                text_sha256=hashlib.sha256(cast(str, row["text"]).encode()).hexdigest(),
            )
            for index, row in enumerate(rows, start=1)
        ),
    )


def test_transcript_loader_is_public_and_format_neutral(tmp_path: Path) -> None:
    paths = {
        "srt": "1\n00:00:00,000 --> 00:00:01,000\nA definition.\n",
        "vtt": "WEBVTT\n\n00:00.000 --> 00:01.000\nA definition.\n",
        "json": json.dumps(
            {"segments": [{"start_ms": 0, "end_ms": 1000, "text": "A definition."}]}
        ),
    }
    artifacts = []
    for suffix, content in paths.items():
        path = tmp_path / f"transcript.{suffix}"
        path.write_text(content, encoding="utf-8")
        artifacts.append(
            load_transcript(
                path,
                source_id="source-loader",
                created_at=datetime(2026, 7, 31, tzinfo=UTC),
            )
        )

    assert all(artifact.source_id == "source-loader" for artifact in artifacts)
    assert [artifact.segments[0].text for artifact in artifacts] == ["A definition."] * 3


def test_education_sdk_returns_one_coherent_planning_result() -> None:
    transcript = _educational_transcript()
    source = MediaSource(
        source_id=transcript.source_id,
        media_id="media-sdk-education",
        kind="video",
        sha256="a" * 64,
        basename_hint="education.mp4",
        rights_attestation=RightsAttestation.AUTHORIZED_OTHER,
        duration_ms=135_000,
    )

    result = plan_educational_content(
        source,
        transcript,
        control_mode=ControlMode.DIRECTED,
        raw_instruction="只要一个例题，不要定义。",  # noqa: RUF001
    )

    assert result.request.control_mode is ControlMode.DIRECTED
    assert result.candidates
    assert len(result.selection.selected_candidate_ids) == 1
    assert tuple(candidate.candidate_id for candidate in result.candidates) == tuple(
        candidate.candidate_id for candidate in result.plan.candidates
    )
    assert result.plan.selection_result.selected_candidate_ids == (
        result.selection.selected_candidate_ids
    )


def test_sports_sdk_preserves_file_provider_provenance() -> None:
    imported = load_sports_observations(SPORTS_CASES, provider_kind="fixture")
    source = MediaSource(
        source_id=imported.artifact.source_id,
        media_id="media-sdk-sports",
        kind="video",
        sha256="b" * 64,
        basename_hint="sports.mp4",
        rights_attestation=RightsAttestation.AUTHORIZED_OTHER,
        duration_ms=60_000,
    )

    result = plan_sports_content(
        source,
        imported.artifact,
        control_mode=ControlMode.DIRECTED,
        raw_instruction="只要一个进球，不要回放。",  # noqa: RUF001
        provider_records=(imported.provider_record,),
    )

    assert len(result.selection.selected_candidate_ids) == 1
    assert tuple(candidate.candidate_id for candidate in result.candidates) == tuple(
        candidate.candidate_id for candidate in result.plan.candidates
    )
    assert result.plan.provider_records == (imported.provider_record,)
    assert result.plan.selection_result.provider_record_refs == (
        imported.provider_record.provider_record_id,
    )
