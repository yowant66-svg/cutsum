from __future__ import annotations

from pathlib import Path

import yaml


def test_ci_covers_supported_platforms_and_python_versions_without_publish_permissions() -> None:
    workflow_path = Path(__file__).parents[2] / ".github/workflows/ci.yml"
    workflow = yaml.load(workflow_path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)

    assert workflow["permissions"] == {"contents": "read"}
    jobs = workflow["jobs"]
    assert jobs["platform"]["strategy"]["matrix"]["os"] == [
        "ubuntu-latest",
        "macos-latest",
        "windows-latest",
    ]
    assert jobs["python-compatibility"]["strategy"]["matrix"]["python-version"] == [
        "3.12",
        "3.13",
    ]
    coverage_job = jobs["coverage"]
    assert coverage_job["runs-on"] == "ubuntu-latest"
    coverage_steps = coverage_job["steps"]
    setup_step = next(
        step for step in coverage_steps if step.get("name") == "Install uv and Python"
    )
    assert setup_step["with"]["python-version"] == "3.12"
    coverage_step = next(
        step for step in coverage_steps if step.get("name") == "Enforce branch coverage"
    )
    coverage_command = coverage_step["run"]
    for required_argument in (
        "--cov=universal_cutup",
        "--cov-branch",
        "--cov-report=xml",
        "--cov-fail-under=85",
    ):
        assert required_argument in coverage_command
    workflow_text = workflow_path.read_text(encoding="utf-8")
    assert "uv publish" not in workflow_text
    assert "release" not in jobs
    for action_reference in (
        "actions/checkout@d23441a48e516b6c34aea4fa41551a30e30af803",
        "astral-sh/setup-uv@08807647e7069bb48b6ef5acd8ec9567f424441b",
    ):
        assert action_reference in workflow_text


def test_pull_requests_require_dco_signoff_without_write_permissions() -> None:
    workflow_path = Path(__file__).parents[2] / ".github/workflows/dco.yml"
    workflow = yaml.load(workflow_path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)

    assert workflow["permissions"] == {"contents": "read"}
    assert "pull_request" in workflow["on"]
    signoff_job = workflow["jobs"]["signoff"]
    assert signoff_job["name"] == "DCO sign-off"
    workflow_text = workflow_path.read_text(encoding="utf-8")
    assert "fetch-depth: 0" in workflow_text
    assert 'python scripts/check_dco.py "$BASE_SHA" "$HEAD_SHA"' in workflow_text
