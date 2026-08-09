from __future__ import annotations

import re
import subprocess
import tomllib
from pathlib import Path

import pytest
import yaml

PROJECT_ROOT = Path(__file__).parents[1]
REQUIRED_GOVERNANCE_FILES = (
    "LICENSE",
    "NOTICE",
    "SECURITY.md",
    "CONTRIBUTING.md",
    "CHANGELOG.md",
    "CODE_OF_CONDUCT.md",
    "DCO",
    "docs/quickstart.md",
    "docs/trial-kit/README.md",
    ".github/ISSUE_TEMPLATE/trial_feedback.yml",
)
FORBIDDEN_PROJECT_PATHS = (
    "output",
    "fonts",
    ".env",
    "cookies.txt",
)
SECRET_PATTERNS = (
    re.compile(r"(?:AKIA|ASIA)[A-Z0-9]{16}"),
    re.compile(r"(?:ghp_|gho_|ghs_|github_pat_)[A-Za-z0-9_]{20,}"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
)
PRIVATE_HOME_PATTERNS = (
    re.compile(r"/Users/[^/\s]+/"),
    re.compile(r"/home/[^/\s]+/"),
    re.compile(r"[A-Za-z]:\\Users\\[^\\\s]+\\"),
)


def tracked_files() -> tuple[Path, ...]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
    )
    return tuple(PROJECT_ROOT / item.decode() for item in result.stdout.split(b"\0") if item)


def test_required_governance_files_exist() -> None:
    missing = [
        relative_path
        for relative_path in REQUIRED_GOVERNANCE_FILES
        if not (PROJECT_ROOT / relative_path).is_file()
    ]
    assert missing == []


def test_forbidden_private_paths_are_absent() -> None:
    present = [
        relative_path
        for relative_path in FORBIDDEN_PROJECT_PATHS
        if (PROJECT_ROOT / relative_path).exists()
    ]
    assert present == []


def test_provenance_ledger_has_versioned_records() -> None:
    ledger_path = PROJECT_ROOT / "provenance" / "ledger.yaml"
    ledger = yaml.safe_load(ledger_path.read_text(encoding="utf-8"))
    assert ledger["schema_version"] == "1.0"
    assert isinstance(ledger["records"], list)


@pytest.mark.parametrize("relative_path", FORBIDDEN_PROJECT_PATHS)
def test_gitignore_names_private_or_generated_paths(relative_path: str) -> None:
    gitignore = (PROJECT_ROOT / ".gitignore").read_text(encoding="utf-8")
    assert relative_path in gitignore


def test_tracked_files_do_not_contain_common_secret_material_or_private_home_paths() -> None:
    findings: list[str] = []
    for path in tracked_files():
        if path == Path(__file__):
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for pattern in (*SECRET_PATTERNS, *PRIVATE_HOME_PATTERNS):
            if pattern.search(content):
                findings.append(f"{path.relative_to(PROJECT_ROOT)}:{pattern.pattern}")
    assert findings == []


def test_sensitive_filename_classes_are_not_tracked() -> None:
    forbidden: list[str] = []
    for path in tracked_files():
        relative = path.relative_to(PROJECT_ROOT)
        lowered = path.name.casefold()
        if (
            lowered in {".env", "cookies.txt", "credentials", "id_rsa"}
            or lowered.endswith((".pem", ".key"))
            or lowered.startswith("secrets.")
        ):
            forbidden.append(str(relative))
    assert forbidden == []


def test_public_alpha_identity_and_version_are_consistent() -> None:
    from universal_cutup import __version__

    project = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    lock = tomllib.loads((PROJECT_ROOT / "uv.lock").read_text(encoding="utf-8"))
    locked_project = next(package for package in lock["package"] if package["name"] == "cutsum")

    assert project["project"]["name"] == "cutsum"
    assert project["project"]["authors"] == [{"name": "DXBATM", "email": "yowant66@gmail.com"}]
    assert project["project"]["scripts"] == {
        "cutup": "universal_cutup.cli:app",
        "cutsum": "universal_cutup.cli:app",
    }
    assert __version__ == "0.1.0a2"
    assert project["project"]["version"] == __version__
    assert locked_project["version"] == __version__


def test_trial_feedback_template_requires_real_run_and_privacy_confirmation() -> None:
    template = yaml.safe_load(
        (PROJECT_ROOT / ".github" / "ISSUE_TEMPLATE" / "trial_feedback.yml").read_text(
            encoding="utf-8"
        )
    )
    fields = {item.get("id"): item for item in template["body"] if "id" in item}

    assert template["labels"] == ["trial-feedback"]
    assert fields["result"]["validations"]["required"] is True
    assert fields["environment"]["validations"]["required"] is True
    confirmations = fields["confirmation"]["attributes"]["options"]
    assert all(option["required"] is True for option in confirmations)
