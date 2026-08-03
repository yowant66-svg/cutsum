from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from universal_cutup.application import skill_materialization
from universal_cutup.application.sdk import SourceInspection
from universal_cutup.domain.sources import (
    MediaBinding,
    MediaSource,
    RightsAttestation,
)

FIXED_TIME = datetime(2026, 7, 30, tzinfo=UTC)
SHA256 = "a" * 64


def _blind_input(root: Path) -> Path:
    transcript = root / "transcript.json"
    transcript.write_text(
        json.dumps(
            {
                "segments": [
                    {
                        "start_ms": index * 10_000,
                        "end_ms": (index + 1) * 10_000,
                        "text": f"Original segment {index}",
                    }
                    for index in range(10)
                ]
            }
        ),
        encoding="utf-8",
    )
    media = root / "media.mp4"
    media.write_bytes(b"test-media")
    payload = {
        "document_type": "blind_run_input",
        "created_at": FIXED_TIME.isoformat(),
        "created_by": "test-suite",
        "blind_run_id": "blind-test",
        "sample_id": "sample-test",
        "source_id": "source-test",
        "transcript_path": str(transcript),
        "media_path": str(media),
        "tasks": [
            {"task_id": "auto", "control_mode": "auto", "raw_instruction": ""},
            {
                "task_id": "directed-a",
                "control_mode": "directed",
                "raw_instruction": "Find a clear definition",
            },
            {
                "task_id": "directed-b",
                "control_mode": "directed",
                "raw_instruction": "Preserve the reasoning",
            },
        ],
    }
    path = root / "blind-input.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _skill_output(root: Path) -> Path:
    payload = {
        "content_profile": {
            "content_types": ["lecture"],
            "primary_topic": "Synthetic original material",
            "structure_types": ["exposition"],
            "value_sources": ["definitions", "reasoning"],
            "density": {
                "narrative": 0.1,
                "knowledge": 0.9,
                "procedural": 0.4,
                "opinion": 0.1,
                "emotion": 0.1,
            },
            "dependencies": {"visual": 0.2, "audio": 0.8, "subtitle": 0.9},
            "confidence": 0.9,
            "auto_objectives": ["representative knowledge"],
            "auto_clip_constraints": {
                "minimum_count": 2,
                "maximum_count": 2,
                "target_count": 2,
            },
        },
        "candidates": [
            {
                "candidate_id": f"fresh-{index}",
                "initial_start_ms": index * 10_000,
                "initial_end_ms": (index + 1) * 10_000,
                "start_ms": index * 10_000,
                "end_ms": (index + 1) * 10_000,
                "summary": f"Original candidate {index}",
                "scores": [float((index + offset) % 11) for offset in range(14)],
                "track_ids": [],
                "semantic_types": ["definition"] if index == 0 else [],
                "semantic_structure": ["term", "meaning"] if index == 0 else [],
                "translations": [f"原始片段 {index}"] if index == 0 else [],
            }
            for index in range(10)
        ],
        "task_interpretations": [
            {"task_id": "auto"},
            {
                "task_id": "directed-a",
                "desired_outcomes": ["definition"],
                "clip_constraints": {"target_count": 1},
            },
            {
                "task_id": "directed-b",
                "desired_outcomes": ["reasoning"],
                "clip_constraints": {"target_count": 1},
            },
        ],
    }
    path = root / "skill-output.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _inspection(path: Path) -> SourceInspection:
    return SourceInspection(
        source=MediaSource(
            source_id="source-test",
            media_id="media-test",
            kind="video",
            sha256=SHA256,
            basename_hint=path.name,
            rights_attestation=RightsAttestation.AUTHORIZED_OTHER,
            duration_ms=100_000,
        ),
        binding=MediaBinding(source_id="source-test", local_path=str(path)),
        has_video=True,
        has_audio=True,
    )


def test_materializes_fresh_skill_output_into_strict_protocol_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    blind_input = _blind_input(tmp_path)
    skill_output = _skill_output(tmp_path)
    monkeypatch.setattr(
        skill_materialization,
        "inspect_source",
        lambda path, **_: _inspection(path),
    )
    output_root = tmp_path / "formal"
    result = skill_materialization.materialize_skill_output(
        blind_input,
        skill_output,
        output_root,
        rights_attestation=RightsAttestation.AUTHORIZED_OTHER,
    )
    assert result["candidate_count"] == 10
    proposals = json.loads((output_root / "proposals.json").read_text())
    assessments = json.loads((output_root / "assessments.json").read_text())
    assert len(proposals["candidates"]) == 10
    assert len(assessments["candidates"][0]["dimensions"]) == 14
    assert proposals["candidates"][0]["semantic_types"] == ["definition"]
    assert proposals["candidates"][0]["translated_subtitle_cues"][0]["language"] == "zh-CN"
    directed = json.loads((output_root / "host-intents/intent-directed-a.json").read_text())
    assert directed["raw_instruction"] == "Find a clear definition"
    assert directed["hard_include_candidate_ids"] == []


def test_rejects_candidate_answers_in_task_interpretation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    blind_input = _blind_input(tmp_path)
    skill_output = _skill_output(tmp_path)
    payload = json.loads(skill_output.read_text())
    payload["task_interpretations"][1]["candidate_ids"] = ["fresh-1"]
    skill_output.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(
        skill_materialization,
        "inspect_source",
        lambda path, **_: _inspection(path),
    )
    with pytest.raises(ValueError, match="forbidden answer fields"):
        skill_materialization.materialize_skill_output(
            blind_input,
            skill_output,
            tmp_path / "formal",
            rights_attestation=RightsAttestation.AUTHORIZED_OTHER,
        )
