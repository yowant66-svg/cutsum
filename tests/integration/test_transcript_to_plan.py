from __future__ import annotations

from datetime import UTC, datetime

from pytest import MonkeyPatch

from universal_cutup.adapters.transcripts import TranscriptParseContext, parse_srt
from universal_cutup.application.services import ApplicationContext, transcript_to_plan
from universal_cutup.domain.selection import SelectionStatus
from universal_cutup.domain.sources import MediaSource
from universal_cutup.domain.transcript import TranscriptArtifact
from universal_cutup.hashing import canonical_json_bytes, document_sha256, semantic_fingerprint
from universal_cutup.strategies.base import StrategyRegistry
from universal_cutup.strategies.deterministic import (
    DeterministicProposalStrategy,
    DeterministicScoringStrategy,
    DeterministicSelectionStrategy,
)

FIXED_TIME = datetime(2026, 7, 30, 12, 0, tzinfo=UTC)
SRT = """1
00:00:00,000 --> 00:00:02,000
这是一个无需空格分词的完整观点。

2
00:00:02,000 --> 00:00:05,000
This is a second complete thought with evidence.
"""


def make_context() -> ApplicationContext:
    registry = StrategyRegistry()
    registry.register_proposal(DeterministicProposalStrategy())
    registry.register_scoring(DeterministicScoringStrategy())
    registry.register_selection(DeterministicSelectionStrategy())
    return ApplicationContext(
        strategy_registry=registry,
        clock=lambda: FIXED_TIME,
        plan_id_factory=lambda: "plan-fixed",
    )


def make_inputs() -> tuple[MediaSource, TranscriptArtifact]:
    source = MediaSource(
        source_id="source-1",
        media_id="media-1",
        kind="transcript",
        sha256="a" * 64,
        basename_hint="lesson.srt",
    )
    transcript = parse_srt(
        SRT,
        context=TranscriptParseContext(
            transcript_id="transcript-1",
            source_id=source.source_id,
            created_at=FIXED_TIME,
            created_by="test-suite",
        ),
    )
    return source, transcript


def test_proposal_scoring_selection_are_separate_and_traceable() -> None:
    source, transcript = make_inputs()
    plan = transcript_to_plan(source, transcript, context=make_context())
    assert plan.selection_result.selection_strategy_id == "deterministic"
    assert all(candidate.evidence_refs for candidate in plan.candidates)
    assert all(candidate.strategy_scores for candidate in plan.candidates)
    assert all(
        decision.status in set(SelectionStatus) for decision in plan.selection_result.decisions
    )
    assert "这是一个" in plan.candidates[0].summary
    assert [record.strategy_role.value for record in plan.strategy_records] == [
        "proposal",
        "scoring",
        "selection",
    ]
    record_ids = {record.strategy_record_id for record in plan.strategy_records}
    assert plan.selection_result.strategy_record_ref in record_ids
    assert all(
        score.strategy_record_ref in record_ids
        for candidate in plan.candidates
        for score in candidate.strategy_scores
    )


def test_fixed_clock_and_id_produce_identical_canonical_bytes() -> None:
    source, transcript = make_inputs()
    first = transcript_to_plan(source, transcript, context=make_context())
    second = transcript_to_plan(source, transcript, context=make_context())
    assert canonical_json_bytes(first) == canonical_json_bytes(second)


def test_varying_document_identity_changes_hash_but_not_semantics() -> None:
    source, transcript = make_inputs()
    first_context = ApplicationContext.default()
    second_context = ApplicationContext.default()
    first = transcript_to_plan(source, transcript, context=first_context)
    second = transcript_to_plan(source, transcript, context=second_context)
    assert document_sha256(first) != document_sha256(second)
    assert semantic_fingerprint(first) == semantic_fingerprint(second)


def test_complete_path_needs_no_provider_or_api_key(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    source, transcript = make_inputs()
    plan = transcript_to_plan(source, transcript, context=make_context())
    assert plan.selection_result.selected_candidate_ids
