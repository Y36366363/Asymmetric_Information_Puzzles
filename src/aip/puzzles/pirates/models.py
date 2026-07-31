from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class VoteThreshold(str, Enum):
    """How many yes votes are needed for a proposal to pass."""

    HALF_OR_MORE = "half"       # ceil(n / 2), so an exact tie passes
    STRICT_MAJORITY = "majority"  # floor(n / 2) + 1


@dataclass(frozen=True, slots=True)
class PirateRules:
    """Configurable interpretation of the classic pirate puzzle."""

    threshold: VoteThreshold = VoteThreshold.HALF_OR_MORE
    proposer_votes: bool = True
    accept_equal_gold: bool = False

    def votes_required(self, pirate_count: int) -> int:
        if pirate_count < 1:
            raise ValueError("pirate_count must be positive")
        if self.threshold is VoteThreshold.HALF_OR_MORE:
            return (pirate_count + 1) // 2
        return pirate_count // 2 + 1


@dataclass(frozen=True, slots=True)
class PirateOutcome:
    alive: bool
    gold: int


@dataclass(frozen=True, slots=True)
class Vote:
    pirate: str
    offered_gold: int
    rejection_outcome: PirateOutcome
    supports: bool
    reason: str


@dataclass(frozen=True, slots=True)
class ProposalRound:
    pirate_count: int
    proposer: str
    allocation: tuple[int, ...]
    alive: tuple[bool, ...]
    votes: tuple[Vote, ...]
    votes_required: int
    passed: bool
    explanation: str

    @property
    def yes_votes(self) -> int:
        return sum(vote.supports for vote in self.votes)


@dataclass(frozen=True, slots=True)
class Solution:
    pirate_names: tuple[str, ...]
    total_gold: int
    rounds: tuple[ProposalRound, ...]

    @property
    def final_round(self) -> ProposalRound:
        return self.rounds[-1]

