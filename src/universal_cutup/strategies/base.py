from __future__ import annotations

from dataclasses import dataclass, field
from importlib.metadata import entry_points
from typing import Protocol, TypeVar, cast

from universal_cutup.domain.candidates import CutCandidate
from universal_cutup.domain.selection import SelectionResult
from universal_cutup.domain.transcript import TranscriptArtifact

StrategyType = TypeVar("StrategyType")


class ProposalStrategy(Protocol):
    strategy_id: str
    strategy_version: str

    def propose(self, transcript: TranscriptArtifact) -> tuple[CutCandidate, ...]: ...


class ScoringStrategy(Protocol):
    strategy_id: str
    strategy_version: str

    def score(
        self,
        candidates: tuple[CutCandidate, ...],
        *,
        strategy_record_id: str,
    ) -> tuple[CutCandidate, ...]: ...


class SelectionStrategy(Protocol):
    strategy_id: str
    strategy_version: str

    def select(
        self,
        candidates: tuple[CutCandidate, ...],
        *,
        strategy_record_id: str,
    ) -> SelectionResult: ...


@dataclass(slots=True)
class StrategyRegistry:
    _proposal: dict[str, ProposalStrategy] = field(default_factory=dict)
    _scoring: dict[str, ScoringStrategy] = field(default_factory=dict)
    _selection: dict[str, SelectionStrategy] = field(default_factory=dict)

    def register_proposal(self, strategy: ProposalStrategy) -> None:
        self._register(self._proposal, strategy.strategy_id, strategy)

    def register_scoring(self, strategy: ScoringStrategy) -> None:
        self._register(self._scoring, strategy.strategy_id, strategy)

    def register_selection(self, strategy: SelectionStrategy) -> None:
        self._register(self._selection, strategy.strategy_id, strategy)

    def proposal(self, strategy_id: str) -> ProposalStrategy:
        return self._proposal[strategy_id]

    def scoring(self, strategy_id: str) -> ScoringStrategy:
        return self._scoring[strategy_id]

    def selection(self, strategy_id: str) -> SelectionStrategy:
        return self._selection[strategy_id]

    @staticmethod
    def _register(
        registry: dict[str, StrategyType],
        strategy_id: str,
        strategy: StrategyType,
    ) -> None:
        if strategy_id in registry:
            raise ValueError(f"duplicate strategy ID: {strategy_id}")
        registry[strategy_id] = strategy

    def load_distribution_entry_points(self) -> None:
        for entry_point in entry_points(group="universal_cutup.proposal"):
            proposal_strategy = cast(ProposalStrategy, entry_point.load()())
            self.register_proposal(proposal_strategy)
        for entry_point in entry_points(group="universal_cutup.scoring"):
            scoring_strategy = cast(ScoringStrategy, entry_point.load()())
            self.register_scoring(scoring_strategy)
        for entry_point in entry_points(group="universal_cutup.selection"):
            selection_strategy = cast(SelectionStrategy, entry_point.load()())
            self.register_selection(selection_strategy)
