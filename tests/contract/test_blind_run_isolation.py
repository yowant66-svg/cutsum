from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from universal_cutup.application.blind_runs import (
    FREEZE_MANIFEST_NAME,
    freeze_blind_run,
    load_blind_run_input,
    load_reference_after_freeze,
    verify_frozen_blind_run,
)
from universal_cutup.domain.blind_runs import BlindRunInput

FIXED_TIME = datetime(2026, 7, 30, tzinfo=UTC)


def _payload(root: Path) -> dict[str, object]:
    transcript = root / "raw.vtt"
    transcript.write_text("WEBVTT\n", encoding="utf-8")
    return {
        "schema_version": "0.1.0",
        "document_type": "blind_run_input",
        "created_at": FIXED_TIME.isoformat(),
        "created_by": "test-suite",
        "blind_run_id": "blind-1",
        "sample_id": "sample-1",
        "source_id": "source-1",
        "transcript_path": str(transcript),
        "tasks": [
            {"task_id": "auto", "control_mode": "auto", "raw_instruction": ""},
            {
                "task_id": "directed-a",
                "control_mode": "directed",
                "raw_instruction": "找一个立即可用的领导力钩子",
            },
            {
                "task_id": "directed-b",
                "control_mode": "directed",
                "raw_instruction": "保留一个完整的第一性原理论述",
            },
        ],
    }


def test_blind_input_accepts_only_one_auto_and_two_natural_language_tasks(
    tmp_path: Path,
) -> None:
    payload = _payload(tmp_path)
    validated = BlindRunInput.model_validate(payload)
    assert [task.control_mode.value for task in validated.tasks] == [
        "auto",
        "directed",
        "directed",
    ]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("hard_include_candidate_ids", ["known-candidate"]),
        ("hard_exclude_candidate_ids", ["known-candidate"]),
        ("start_ms", 42_000),
        ("score", 9.5),
    ],
)
def test_blind_input_rejects_curated_answer_fields(
    tmp_path: Path,
    field: str,
    value: object,
) -> None:
    payload = _payload(tmp_path)
    payload["tasks"][1][field] = value  # type: ignore[index]
    with pytest.raises(ValidationError):
        BlindRunInput.model_validate(payload)


@pytest.mark.parametrize(
    "instruction",
    ["Use candidate ID c4", "从 12:34 开始", "选择候选编号 2"],
)
def test_blind_input_rejects_reference_answers_in_natural_language(
    tmp_path: Path,
    instruction: str,
) -> None:
    payload = _payload(tmp_path)
    payload["tasks"][1]["raw_instruction"] = instruction  # type: ignore[index]
    with pytest.raises(ValidationError):
        BlindRunInput.model_validate(payload)


def test_loader_rejects_curated_and_gate_g_paths(tmp_path: Path) -> None:
    blind_root = tmp_path / "blind-input"
    blind_root.mkdir()
    payload = _payload(blind_root)
    input_path = blind_root / "input.json"
    input_path.write_text(json.dumps(payload), encoding="utf-8")
    assert load_blind_run_input(input_path, blind_input_root=blind_root).blind_run_id == "blind-1"

    curated = blind_root / "curated-inputs.json"
    curated.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="forbidden"):
        load_blind_run_input(curated, blind_input_root=blind_root)

    gate_g_root = tmp_path / "universal-cutup-gate-g-work"
    gate_g_root.mkdir()
    gate_g_input = gate_g_root / "input.json"
    gate_g_input.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError):
        load_blind_run_input(gate_g_input, blind_input_root=blind_root)


def test_reference_is_unavailable_until_freeze_and_mutation_is_detected(
    tmp_path: Path,
) -> None:
    result_root = tmp_path / "results"
    result_root.mkdir()
    result = result_root / "selection.json"
    result.write_text('{"selected": ["fresh"]}', encoding="utf-8")
    reference = tmp_path / "curated-inputs.json"
    reference.write_text('{"hidden": true}', encoding="utf-8")
    missing_manifest = result_root / FREEZE_MANIFEST_NAME

    with pytest.raises(FileNotFoundError):
        load_reference_after_freeze(reference, manifest_path=missing_manifest)

    manifest = freeze_blind_run(
        result_root,
        blind_run_id="blind-1",
        created_at=FIXED_TIME,
    )
    assert manifest.artifacts[0].relative_path == "selection.json"
    loaded = load_reference_after_freeze(reference, manifest_path=missing_manifest)
    assert loaded == {"hidden": True}

    result.write_text('{"selected": ["tampered"]}', encoding="utf-8")
    with pytest.raises(ValueError, match="changed after freeze"):
        verify_frozen_blind_run(missing_manifest)


def test_four_track_reference_requires_frozen_matching_identity(tmp_path: Path) -> None:
    blind_root = tmp_path / "blind-input"
    blind_root.mkdir()
    payload = _payload(blind_root)
    payload.update(
        {
            "suite_id": "four-track-v1",
            "case_id": "sports-case",
            "track": "sports",
        }
    )
    blind_input = BlindRunInput.model_validate(payload)
    result_root = tmp_path / "results"
    result_root.mkdir()
    (result_root / "selection.json").write_text(
        '{"selected": ["fresh"]}',
        encoding="utf-8",
    )
    manifest = freeze_blind_run(
        result_root,
        blind_run_id=blind_input.blind_run_id,
        blind_input=blind_input,
        created_at=FIXED_TIME,
    )
    assert manifest.track == "sports"
    reference = tmp_path / "sports-reference.json"
    reference.write_text(
        json.dumps(
            {
                "suite_id": "four-track-v1",
                "case_id": "sports-case",
                "track": "sports",
                "expected": ["score"],
            }
        ),
        encoding="utf-8",
    )

    loaded = load_reference_after_freeze(
        reference,
        manifest_path=result_root / FREEZE_MANIFEST_NAME,
    )

    assert loaded["expected"] == ["score"]  # type: ignore[index]
    reference.write_text(
        json.dumps(
            {
                "suite_id": "four-track-v1",
                "case_id": "education-case",
                "track": "education",
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="identity"):
        load_reference_after_freeze(
            reference,
            manifest_path=result_root / FREEZE_MANIFEST_NAME,
        )


def test_blind_reference_rejects_undeclared_filename(tmp_path: Path) -> None:
    result_root = tmp_path / "results"
    result_root.mkdir()
    (result_root / "selection.json").write_text("{}", encoding="utf-8")
    freeze_blind_run(
        result_root,
        blind_run_id="blind-1",
        created_at=FIXED_TIME,
    )
    reference = tmp_path / "answers.json"
    reference.write_text("{}", encoding="utf-8")

    with pytest.raises(ValueError, match="declared reference"):
        load_reference_after_freeze(
            reference,
            manifest_path=result_root / FREEZE_MANIFEST_NAME,
        )
