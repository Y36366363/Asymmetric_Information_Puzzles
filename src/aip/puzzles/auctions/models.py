from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class AuctionMode(str, Enum):
    NAIVE = "naive"
    CAUTIOUS = "cautious"
    EQUILIBRIUM = "equilibrium"
    COOPERATIVE = "cooperative"
    TACIT = "tacit"
    SOCIAL = "social"


@dataclass(frozen=True, slots=True)
class AuctionRules:
    player_count: int = 5
    rounds: int = 10
    prize_value: int = 100
    initial_budget: int = 100
    tacit_deviation_probability: float = 0.0
    social_supporters: int | None = None
    social_identity_observable: bool = True
    social_leader_bid: int = 101
    social_deviation_probability: float = 0.0

    def __post_init__(self) -> None:
        if self.player_count < 2:
            raise ValueError("player_count must be at least 2")
        if self.rounds < 1 or self.prize_value < 1 or self.initial_budget < 0:
            raise ValueError("rounds and prize must be positive; budget cannot be negative")
        if not 0 <= self.tacit_deviation_probability <= 1:
            raise ValueError("tacit_deviation_probability must be between 0 and 1")
        supporters = self.player_count if self.social_supporters is None else self.social_supporters
        if not 1 <= supporters <= self.player_count:
            raise ValueError("social_supporters must be between 1 and player_count")
        if self.social_leader_bid <= self.prize_value:
            raise ValueError("social_leader_bid must exceed the prize value")
        if not 0 <= self.social_deviation_probability <= 1:
            raise ValueError("social_deviation_probability must be between 0 and 1")

    @property
    def effective_social_supporters(self) -> int:
        return self.player_count if self.social_supporters is None else self.social_supporters


@dataclass(frozen=True, slots=True)
class AuctionRound:
    number: int
    budgets_before: tuple[int, ...]
    bids: tuple[int, ...]
    winner: int | None
    budgets_after: tuple[int, ...]
    auctioneer_revenue: int
    public_price: int
    coordination_active_before: bool
    coordination_active_after: bool
    active_players_before: tuple[int, ...]
    expelled_after: tuple[int, ...]

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
    coordination_break_round: int | None = None
    expelled_players: tuple[int, ...] = ()


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
    coordination_survival_rate: float | None = None
    mean_expelled_players: float = 0.0


@dataclass(frozen=True, slots=True)
class AuctionAnalysis:
    rules: AuctionRules
    benchmark: EquilibriumBenchmark
    scenarios: tuple[ScenarioSummary, ...]
    sample_runs: tuple[AuctionRun, ...]
    tacit_patience_threshold: float
    social_patience_threshold: float
    leadership_signal_net_cost: float
    cooperative_payoff_per_round: float
