from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from universal_cutup.schema import export_schemas


def test_schema_export_is_deterministic(tmp_path: Path) -> None:
    first_manifest = export_schemas(tmp_path)
    first_bytes = {
        path.name: path.read_bytes() for path in tmp_path.iterdir() if path.suffix == ".json"
    }
    second_manifest = export_schemas(tmp_path)
    second_bytes = {
        path.name: path.read_bytes() for path in tmp_path.iterdir() if path.suffix == ".json"
    }
    assert first_manifest == second_manifest
    assert first_bytes == second_bytes
    parsed = json.loads((tmp_path / "cut-plan.schema.json").read_text())
    assert parsed["title"] == "CutPlan"
    assert "educational-task-request.schema.json" in first_manifest
    assert "educational-selection-result.schema.json" in first_manifest
    assert "sports-observation-bundle.schema.json" in first_manifest
    assert "sports-task-request.schema.json" in first_manifest
    assert "sports-selection-result.schema.json" in first_manifest
    assert "four-track-evaluation-manifest.schema.json" in first_manifest
    assert "four-track-evaluation-report.schema.json" in first_manifest
    assert "blind-run-input.schema.json" in first_manifest
    assert "blind-run-manifest.schema.json" in first_manifest
    assert "model-routing-decision.schema.json" in first_manifest
    routing_schema = json.loads(
        (tmp_path / "model-routing-decision.schema.json").read_text(encoding="utf-8")
    )
    assert routing_schema["title"] == "ModelRoutingDecision"


def test_schema_export_cli_honors_explicit_output_directory(tmp_path: Path) -> None:
    project_root = Path(__file__).parents[2]
    output = tmp_path / "schema-freeze"

    subprocess.run(
        [sys.executable, str(project_root / "scripts/export_schemas.py"), str(output)],
        cwd=project_root,
        check=True,
    )

    assert (output / "manifest.json").is_file()
    assert (output / "cut-plan.schema.json").is_file()
