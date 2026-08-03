from __future__ import annotations

from pathlib import Path

import yaml

SKILL_ROOT = Path(__file__).parents[2] / ".agents" / "skills" / "cutsum-intelligence"


def test_repo_skill_has_valid_identity_and_core_authority_boundary() -> None:
    content = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
    frontmatter = content.split("---", maxsplit=2)[1]
    metadata = yaml.safe_load(frontmatter)
    assert metadata["name"] == "cutsum-intelligence"
    assert set(metadata) == {"name", "description"}
    assert "only authority" in content
    assert "Do not embed a second scoring or ranking formula" in content


def test_repo_skill_supports_all_required_modes_and_protocol_schemas() -> None:
    skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
    reference = (SKILL_ROOT / "references/protocol-workflow.md").read_text(encoding="utf-8")
    for mode in ("AUTO", "GUIDED", "DIRECTED", "PLAN ONLY", "EXECUTE EXISTING PLAN"):
        assert mode in skill
    for schema in (
        "host-intent.schema.json",
        "content-profile.schema.json",
        "resolved-task-profile.schema.json",
        "candidate-proposal-bundle.schema.json",
        "assessment-bundle.schema.json",
    ):
        assert schema in reference


def test_repo_skill_routes_education_and_semantic_subtitle_display() -> None:
    skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
    reference = (SKILL_ROOT / "references/protocol-workflow.md").read_text(encoding="utf-8")
    assert "educational_distillation" in skill
    assert "SubtitleDisplayUnit" in skill
    assert "Layout wrapping must never create new timeline cues" in skill
    assert "contextual_translation_records" in reference
    assert "Teacher emphasis is supporting evidence" in reference
    assert "cutsum subtitle-capabilities" in skill
    assert "characters per second" in skill
    assert "subtitle_semantic_spans" in reference
    assert "propose_educational_candidates" in skill
    assert "candidate IDs or reference timestamps" in skill
    assert "educational-task-request.schema.json" in reference
    assert "15–60 seconds" in reference  # noqa: RUF001


def test_repo_skill_discloses_sports_observation_boundary() -> None:
    skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
    reference = (SKILL_ROOT / "references/protocol-workflow.md").read_text(encoding="utf-8")

    assert "SportsObservationBundle" in skill
    assert "single audio peak or shot change is not a highlight" in skill
    assert "Do not claim" in skill
    assert "sports-observation-bundle.schema.json" in reference
    assert "provider_kind=fixture" in reference


def test_repo_skill_preserves_evaluation_claim_boundary() -> None:
    skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
    reference = (SKILL_ROOT / "references/protocol-workflow.md").read_text(encoding="utf-8")

    assert "pass@1" in skill
    assert "never convert" in skill
    assert "content-quality claim" in skill
    assert "four-track-evaluation-report.schema.json" in reference
    assert "real_local" in reference
    assert "suite, case, and track identity must match" in reference


def test_repo_skill_uses_public_sdk_cli_and_structured_capability_boundary() -> None:
    skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
    reference = (SKILL_ROOT / "references/protocol-workflow.md").read_text(encoding="utf-8")

    assert "universal_cutup.sdk" in skill
    assert "cutsum capabilities" in skill
    assert "cutsum education-plan" in skill
    assert "cutsum sports-plan" in skill
    assert "provider_required" in skill
    assert "CutupError.as_dict()" in reference
