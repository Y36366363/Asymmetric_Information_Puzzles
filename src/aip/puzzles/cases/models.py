from __future__ import annotations

from dataclasses import dataclass


STANDARD_PRIZES = (
    0.01, 1, 5, 10, 25, 50, 75, 100, 200, 300, 400, 500, 750,
    1_000, 5_000, 10_000, 25_000, 50_000, 75_000, 100_000, 200_000,
    300_000, 400_000, 500_000, 750_000, 1_000_000,
)


@dataclass(frozen=True, slots=True)
class CaseGameRules:
    prizes: tuple[float, ...] = STANDARD_PRIZES
    cases_opened_per_round: tuple[int, ...] = (6, 5, 4, 3, 2, 1, 1, 1, 1, 1)

    def __post_init__(self) -> None:
        if len(self.prizes) < 2 or len(set(self.prizes)) != len(self.prizes):
            raise ValueError("prizes must contain at least two distinct values")
        if any(value < 0 for value in self.prizes):
            raise ValueError("prizes cannot be negative")
        if any(count < 1 for count in self.cases_opened_per_round):
            raise ValueError("each round must open at least one case")
        if sum(self.cases_opened_per_round) != len(self.prizes) - 1:
            raise ValueError("opening schedule must reveal every case except the player's")


@dataclass(frozen=True, slots=True)
class BankerProfile:
    name: str
    offer_multipliers: tuple[float, ...]
    noise_fraction: float = 0.0

    def __post_init__(self) -> None:
        if not self.name or not self.offer_multipliers:
            raise ValueError("banker profile needs a name and offer multipliers")
        if any(multiplier < 0 for multiplier in self.offer_multipliers):
            raise ValueError("offer multipliers cannot be negative")
        if self.noise_fraction < 0:
            raise ValueError("noise_fraction cannot be negative")

    def multiplier(self, round_index: int) -> float:
        return self.offer_multipliers[min(round_index, len(self.offer_multipliers) - 1)]


CLASSROOM_BANKER = BankerProfile(
    "classroom",
    (0.50, 0.50, 0.60, 0.60, 0.70, 0.70, 0.80, 0.90, 0.99, 0.99),
)


@dataclass(frozen=True, slots=True)
class RiskPreferences:
    """CARA preferences; ``None`` means risk-neutral expected-value maximization."""

    risk_tolerance: float | None = None

    def __post_init__(self) -> None:
        if self.risk_tolerance is not None and self.risk_tolerance <= 0:
            raise ValueError("risk_tolerance must be positive")


@dataclass(frozen=True, slots=True)
class BankerHypothesis:
    profile: BankerProfile


@dataclass(frozen=True, slots=True)
class OfferAnalysis:
    remaining_prizes: tuple[float, ...]
    offer: float
    expected_value: float
    standard_deviation: float
    certainty_equivalent: float
    risk_premium: float
    offer_to_expected_value: float
    probability_case_beats_offer: float
    reservation_recommendation: str


@dataclass(frozen=True, slots=True)
class NextOfferProjection:
    outcomes: int
    expected_offer: float
    minimum_offer: float
    maximum_offer: float
    probability_next_offer_beats_current: float


@dataclass(frozen=True, slots=True)
class CaseRound:
    round_number: int
    revealed: tuple[float, ...]
    remaining: tuple[float, ...]
    offer: float
    analysis: OfferAnalysis
    accepted: bool


@dataclass(frozen=True, slots=True)
class CaseGameResult:
    player_case_value: float
    payout: float
    accepted_round: int | None
    rounds: tuple[CaseRound, ...]


@dataclass(frozen=True, slots=True)
class CaseSimulationSummary:
    trials: int
    mean_payout: float
    mean_case_value: float
    deal_rate: float
    mean_accepted_round: float | None
