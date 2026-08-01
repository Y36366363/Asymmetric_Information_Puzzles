"""Public-price leadership and convention selection."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class LeadershipCandidate:
    player_id: int
    commitment_bid: int
    proposed_price: int


@dataclass(frozen=True, slots=True)
class PriceVote:
    price: int
    first_choice_support: int
    expected_payoff_per_supporter: float
    group_surplus: float
    economically_viable: bool


@dataclass(frozen=True, slots=True)
class CoordinationOutcome:
    prize_value: int
    raw_high_bid_leader: int
    raw_high_bid: int
    raw_leader_bid_is_rational: bool
    maximum_rational_leadership_bid: float
    majority_recognized_leader: int | None
    equilibrium_price: int
    median_ideal_price: float
    votes: tuple[PriceVote, ...]
    leadership_contest_cost: int
    explanation: str


class PublicPriceCoordinationSolver:
    """Separate dominance by costly bidding from legitimacy by public support.

    Candidate identities and bids are public. Each candidate proposes a future
    common bid. Participants have single-peaked preferences over that convention
    and support the closest proposal; pairwise majority comparison selects the
    Condorcet price. This is a governance model, not a one-shot auction Nash
    equilibrium.
    """

    def solve(
        self,
        candidates: tuple[LeadershipCandidate, ...],
        ideal_prices: tuple[int, ...],
        *,
        prize_value: int = 100,
        remaining_rounds: int = 10,
        discount_factor: float = 0.9,
        leadership_bonus_per_round: float = 0.0,
    ) -> CoordinationOutcome:
        self._validate(
            candidates,
            ideal_prices,
            prize_value,
            remaining_rounds,
            discount_factor,
            leadership_bonus_per_round,
        )
        high_candidate = max(
            candidates, key=lambda candidate: (candidate.commitment_bid, -candidate.player_id)
        )
        leadership_value = leadership_bonus_per_round * sum(
            discount_factor**period for period in range(1, remaining_rounds + 1)
        )
        rational_cap = prize_value + leadership_value

        proposal_prices = tuple(sorted({candidate.proposed_price for candidate in candidates}))
        support = {price: 0 for price in proposal_prices}
        for ideal in ideal_prices:
            choice = min(proposal_prices, key=lambda price: (abs(price - ideal), price))
            support[choice] += 1

        equilibrium_price = self._condorcet_price(proposal_prices, ideal_prices)
        equilibrium_candidates = tuple(
            candidate for candidate in candidates if candidate.proposed_price == equilibrium_price
        )
        recognized = max(
            equilibrium_candidates,
            key=lambda candidate: (candidate.commitment_bid, -candidate.player_id),
        )
        strict_majority = support[equilibrium_price] > len(ideal_prices) / 2
        # A Condorcet winner can emerge only after pairwise runoff even when
        # fragmented first choices give nobody an immediate absolute majority.
        recognized_id = recognized.player_id

        votes = tuple(
            PriceVote(
                price,
                support[price],
                prize_value / len(ideal_prices) - price,
                prize_value - len(ideal_prices) * price,
                price < prize_value / len(ideal_prices),
            )
            for price in proposal_prices
        )
        explanation = (
            f"Player {high_candidate.player_id} wins raw price dominance with "
            f"{high_candidate.commitment_bid}, but player {recognized_id}'s proposed "
            f"price {equilibrium_price} is the pairwise-majority convention. "
            + (
                "It already has a strict first-choice majority."
                if strict_majority
                else "It requires a public pairwise runoff because first choices split."
            )
        )
        return CoordinationOutcome(
            prize_value,
            high_candidate.player_id,
            high_candidate.commitment_bid,
            high_candidate.commitment_bid <= rational_cap,
            rational_cap,
            recognized_id,
            equilibrium_price,
            self._median(ideal_prices),
            votes,
            sum(candidate.commitment_bid for candidate in candidates),
            explanation,
        )

    @staticmethod
    def _condorcet_price(prices: tuple[int, ...], ideals: tuple[int, ...]) -> int:
        for candidate in prices:
            beats_every_other = True
            for opponent in prices:
                if candidate == opponent:
                    continue
                candidate_votes = sum(
                    abs(candidate - ideal) < abs(opponent - ideal) for ideal in ideals
                )
                opponent_votes = sum(
                    abs(opponent - ideal) < abs(candidate - ideal) for ideal in ideals
                )
                if candidate_votes < opponent_votes:
                    beats_every_other = False
                    break
            if beats_every_other:
                return candidate
        # With single-peaked preferences a weak Condorcet winner exists; this
        # fallback is deterministic for even populations and exact-distance ties.
        median = PublicPriceCoordinationSolver._median(ideals)
        return min(prices, key=lambda price: (abs(price - median), price))

    @staticmethod
    def _median(values: tuple[int, ...]) -> float:
        ordered = sorted(values)
        middle = len(ordered) // 2
        if len(ordered) % 2:
            return float(ordered[middle])
        return (ordered[middle - 1] + ordered[middle]) / 2

    @staticmethod
    def _validate(
        candidates: tuple[LeadershipCandidate, ...],
        ideals: tuple[int, ...],
        prize: int,
        rounds: int,
        discount: float,
        bonus: float,
    ) -> None:
        if not candidates or not ideals:
            raise ValueError("at least one candidate and voter are required")
        if prize < 1 or rounds < 0 or not 0 <= discount <= 1 or bonus < 0:
            raise ValueError("invalid prize, horizon, discount, or leadership bonus")
        ids = [candidate.player_id for candidate in candidates]
        if len(ids) != len(set(ids)):
            raise ValueError("candidate player ids must be unique")
        if any(candidate.commitment_bid <= prize for candidate in candidates):
            raise ValueError("every leadership commitment must exceed the prize")
        if any(candidate.proposed_price < 1 for candidate in candidates):
            raise ValueError("proposed convention prices must be positive")
        if any(ideal < 1 for ideal in ideals):
            raise ValueError("ideal prices must be positive")
