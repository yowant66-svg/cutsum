from __future__ import annotations

import hashlib
import unicodedata

from universal_cutup.domain.candidates import (
    CutCandidate,
    DimensionScore,
    EvidenceRef,
    StrategyScore,
)
from universal_cutup.domain.selection import (
    SelectionDecision,
    SelectionResult,
    SelectionStatus,
)
from universal_cutup.domain.transcript import SubtitleCue, TranscriptArtifact

STRATEGY_ID = "deterministic"
STRATEGY_VERSION = "0.1.0"
MIN_SELECTED_DURATION_MS = 500
TEXT_ENERGY_NORMALIZER = 80


def _stable_id(prefix: str, value: str) -> str:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}-{digest}"


def _informational_units(text: str) -> int:
    return sum(1 for character in text if unicodedata.category(character)[0] in {"L", "N"})


class DeterministicProposalStrategy:
    strategy_id = STRATEGY_ID
    strategy_version = STRATEGY_VERSION

    def propose(self, transcript: TranscriptArtifact) -> tuple[CutCandidate, ...]:
        candidates: list[CutCandidate] = []
        for segment in transcript.segments:
            evidence_id = _stable_id(
                "evidence",
                f"{transcript.transcript_id}:{segment.segment_id}:{segment.text_sha256}",
            )
            evidence = EvidenceRef(
                evidence_id=evidence_id,
                artifact_id=transcript.transcript_id,
                segment_ids=(segment.segment_id,),
                start_ms=segment.start_ms,
                end_ms=segment.end_ms,
                text_sha256=segment.text_sha256,
                snapshot=segment.text,
            )
            candidate_id = _stable_id(
                "candidate",
                f"{transcript.source_id}:{segment.start_ms}:{segment.end_ms}:{segment.text_sha256}",
            )
            subtitle_cue = SubtitleCue(
                cue_id=_stable_id("cue", segment.segment_id),
                source_id=transcript.source_id,
                start_ms=segment.start_ms,
                end_ms=segment.end_ms,
                text=segment.text,
                language=transcript.language,
                speaker=segment.speaker,
                source_segment_ids=(segment.segment_id,),
            )
            candidates.append(
                CutCandidate(
                    candidate_id=candidate_id,
                    source_id=transcript.source_id,
                    start_ms=segment.start_ms,
                    end_ms=segment.end_ms,
                    summary=segment.text,
                    evidence_refs=(evidence,),
                    subtitle_cues=(subtitle_cue,),
                    tags=("deterministic-segment",),
                )
            )
        return tuple(candidates)


class DeterministicScoringStrategy:
    strategy_id = STRATEGY_ID
    strategy_version = STRATEGY_VERSION

    def score(
        self,
        candidates: tuple[CutCandidate, ...],
        *,
        strategy_record_id: str,
    ) -> tuple[CutCandidate, ...]:
        scored: list[CutCandidate] = []
        for candidate in candidates:
            evidence_ids = tuple(evidence.evidence_id for evidence in candidate.evidence_refs)
            aggregate = min(
                1.0,
                _informational_units(candidate.summary) / TEXT_ENERGY_NORMALIZER,
            )
            strategy_score = StrategyScore(
                strategy_id=self.strategy_id,
                strategy_version=self.strategy_version,
                strategy_record_ref=strategy_record_id,
                dimensions=(
                    DimensionScore(
                        dimension_id="text_energy",
                        value=aggregate,
                        evidence_refs=evidence_ids,
                    ),
                ),
                aggregate=aggregate,
            )
            scored.append(
                candidate.model_copy(
                    update={"strategy_scores": (*candidate.strategy_scores, strategy_score)}
                )
            )
        return tuple(scored)


class DeterministicSelectionStrategy:
    strategy_id = STRATEGY_ID
    strategy_version = STRATEGY_VERSION

    def select(
        self,
        candidates: tuple[CutCandidate, ...],
        *,
        strategy_record_id: str,
    ) -> SelectionResult:
        decisions: list[SelectionDecision] = []
        for candidate in candidates:
            score = candidate.strategy_scores[-1].aggregate
            duration_ms = candidate.end_ms - candidate.start_ms
            selected = score is not None and score > 0 and duration_ms >= MIN_SELECTED_DURATION_MS
            decisions.append(
                SelectionDecision(
                    candidate_id=candidate.candidate_id,
                    status=(SelectionStatus.SELECTED if selected else SelectionStatus.REJECTED),
                    reason=(
                        "deterministic text evidence and duration accepted"
                        if selected
                        else "deterministic minimum not met"
                    ),
                    rule_ids=("text-energy-positive", "minimum-duration"),
                    evidence_refs=tuple(
                        evidence.evidence_id for evidence in candidate.evidence_refs
                    ),
                )
            )
        selection_key = "|".join(
            f"{decision.candidate_id}:{decision.status.value}" for decision in decisions
        )
        return SelectionResult(
            selection_id=_stable_id("selection", selection_key),
            selection_strategy_id=self.strategy_id,
            selection_strategy_version=self.strategy_version,
            decisions=tuple(decisions),
            strategy_record_ref=strategy_record_id,
        )
