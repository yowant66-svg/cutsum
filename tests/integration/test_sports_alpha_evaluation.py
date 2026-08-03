from __future__ import annotations

from pathlib import Path
from typing import cast

from universal_cutup.application.sports import (
    propose_sports_candidates,
    resolve_sports_request,
    select_sports_for_request,
)
from universal_cutup.domain.intelligence import ControlMode
from universal_cutup.domain.sports import (
    SportsCandidateProfile,
    SportsEventType,
    SportsObservationBundle,
)

CASES_PATH = Path(__file__).parents[2] / "evaluation" / "sports-alpha-observations.json"


def _bundle() -> SportsObservationBundle:
    return SportsObservationBundle.model_validate_json(CASES_PATH.read_text(encoding="utf-8"))


def test_sports_auto_uses_observations_without_output_candidate_ids() -> None:
    candidates = propose_sports_candidates(_bundle(), media_duration_ms=60_000)
    request = resolve_sports_request(ControlMode.AUTO, "")
    result = select_sports_for_request(candidates, request)
    selected = tuple(
        candidate
        for candidate in candidates
        if candidate.candidate_id in result.selected_candidate_ids
    )

    assert len(candidates) == 4
    assert {
        cast(SportsCandidateProfile, candidate.sports_profile).event_type for candidate in selected
    } == {
        SportsEventType.SCORE,
        SportsEventType.SAVE,
    }
    assert all(
        candidate.sports_profile is not None and not candidate.sports_profile.replay_only
        for candidate in selected
    )
    assert all(8_000 <= candidate.end_ms - candidate.start_ms <= 60_000 for candidate in candidates)


def test_sports_directed_is_pure_natural_language_and_excludes_replay() -> None:
    candidates = propose_sports_candidates(_bundle(), media_duration_ms=60_000)
    instruction = "只要一个进球，不要回放。"  # noqa: RUF001
    request = resolve_sports_request(ControlMode.DIRECTED, instruction)
    result = select_sports_for_request(candidates, request)
    selected = tuple(
        candidate
        for candidate in candidates
        if candidate.candidate_id in result.selected_candidate_ids
    )

    assert len(selected) == 1
    assert selected[0].sports_event is not None
    assert selected[0].sports_event.event_type is SportsEventType.SCORE
    assert all(candidate.candidate_id not in instruction for candidate in candidates)
