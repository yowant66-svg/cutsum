from __future__ import annotations

import re
from pathlib import Path

import yaml

REPOSITORY_ROOT = Path(__file__).parents[2]
RELEASE_WORKFLOW = REPOSITORY_ROOT / ".github/workflows/release.yml"


def test_release_workflow_uses_one_artifact_and_job_scoped_oidc() -> None:
    workflow = yaml.safe_load(RELEASE_WORKFLOW.read_text(encoding="utf-8"))

    assert workflow[True] == {"push": {"tags": ["v*"]}, "workflow_dispatch": {}}
    jobs = workflow["jobs"]
    assert jobs["build"]["permissions"] == {"contents": "read"}
    assert jobs["publish-testpypi"]["permissions"] == {"id-token": "write"}
    assert jobs["publish-pypi"]["permissions"] == {"id-token": "write"}
    assert "startsWith(github.ref, 'refs/tags/v')" in jobs["publish-testpypi"]["if"]
    assert "startsWith(github.ref, 'refs/tags/v')" in jobs["publish-pypi"]["if"]
    assert jobs["publish-pypi"]["environment"] == "pypi"
    assert jobs["publish-testpypi"]["environment"] == "testpypi"
    assert "publish-testpypi" in jobs["publish-pypi"]["needs"]
    assert jobs["github-release"]["permissions"] == {"contents": "write"}


def test_release_actions_are_pinned_to_full_shas() -> None:
    text = RELEASE_WORKFLOW.read_text(encoding="utf-8")

    for uses in re.findall(r"uses:\s+([^\s]+)", text):
        assert re.search(r"@[0-9a-f]{40}$", uses), uses


def test_release_workflow_reuses_the_build_artifact() -> None:
    text = RELEASE_WORKFLOW.read_text(encoding="utf-8")

    assert text.count("uv build") == 1
    assert text.count("name: cutsum-release") >= 4
    assert "packages-dir: publish-dist" in text
