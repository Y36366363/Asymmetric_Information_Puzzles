from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class BidderType(str, Enum):
    HONEST = "honest"
    BLUFFER = "bluffer"


@dataclass(frozen=True, slots=True)
class LiarsDiceRules:
    player_count: int = 4
    dice_per_player: int = 5
    sides: int = 6
    wild_ones: bool = True

    def __post_init__(self) -> None:
        if self.player_count < 2:
            raise ValueError("player_count must be at least 2")
        if self.dice_per_player < 1:
            raise ValueError("dice_per_player must be positive")
        if self.sides < 2:
            raise ValueError("sides must be at least 2")

    @property
    def total_dice(self) -> int:
        return self.player_count * self.dice_per_player


@dataclass(frozen=True, slots=True)
class DiceBid:
    quantity: int
    face: int

    def validate(self, rules: LiarsDiceRules) -> None:
        if self.quantity < 1 or self.quantity > rules.total_dice:
            raise ValueError("bid quantity must be between 1 and total dice")
        if self.face < 1 or self.face > rules.sides:
            raise ValueError("bid face is outside the die")


@dataclass(frozen=True, slots=True)
class BidAnalysis:
    bid: DiceBid
    own_matches: int
    hidden_dice: int
    hidden_match_probability: float
    matches_still_needed: int
    probability_bid_true: float
    probability_exactly_true: float
    challenge_expected_value: float
    challenge_threshold: float
    recommendation: str


@dataclass(frozen=True, slots=True)
class RaiseOption:
    bid: DiceBid
    probability_true: float


@dataclass(frozen=True, slots=True)
class ProbabilityCheck:
    trials: int
    exact_probability: float
    simulated_probability: float
    absolute_error: float


@dataclass(frozen=True, slots=True)
class BidderHypothesis:
    bidder_type: BidderType
