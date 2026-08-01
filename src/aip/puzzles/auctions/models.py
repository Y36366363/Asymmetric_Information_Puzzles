from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class AuctionMode(str, Enum):
    NAIVE = "naive"
    CAUTIOUS = "cautious"
    EQUILIBRIUM = "equilibrium"
    COOPERATIVE = "cooperative"


@dataclass(frozen=True, slots=True)
class AuctionRules:
    player_count: int = 5
    rounds: int = 10
    prize_value: int = 100
    initial_budget: int = 100

    def __post_init__(self) -> None:
        if self.player_count < 2:
            raise ValueError("player_count must be at least 2")
        if self.rounds < 1 or self.prize_value < 1 or self.initial_budget < 0:
            raise ValueError("rounds and prize must be positive; budget cannot be negative")


@dataclass(frozen=True, slots=True)
class AuctionRound:
    number: int
    budgets_before: tuple[int, ...]
    bids: tuple[int, ...]
    winner: int | None
    budgets_after: tuple[int, ...]
    auctioneer_revenue: int

    @property
    def bidder_group_gain(self) -> int:
        return sum(self.budgets_after) - sum(self.budgets_before)


@dataclass(frozen=True, slots=True)
class AuctionRun:
    rules: AuctionRules
    mode: AuctionMode
    rounds: tuple[AuctionRound, ...]
    final_budgets: tuple[int, ...]
    auctioneer_revenue: int


@dataclass(frozen=True, slots=True)
class EquilibriumBenchmark:
    player_count: int
    prize_value: float
    expected_bid_per_player: float
    expected_total_bids: float
    expected_winning_bid: float
    expected_payoff_per_player: float
    bid_cdf: str


@dataclass(frozen=True, slots=True)
class ScenarioSummary:
    mode: AuctionMode
    trials: int
    mean_auctioneer_revenue: float
    mean_final_group_wealth: float
    mean_richest_share: float
    mean_bankrupt_players: float


@dataclass(frozen=True, slots=True)
class AuctionAnalysis:
    rules: AuctionRules
    benchmark: EquilibriumBenchmark
    scenarios: tuple[ScenarioSummary, ...]
    sample_runs: tuple[AuctionRun, ...]
