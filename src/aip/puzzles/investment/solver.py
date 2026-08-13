from __future__ import annotations

import random
from dataclasses import dataclass


def kelly_fraction(probability: float, net_odds: float) -> float:
    """Log-growth-optimal fraction for a binary bet, clipped to [0, 1]."""
    if not 0 < probability < 1 or net_odds <= 0:
        raise ValueError("probability and net odds must be positive and valid")
    return max(0.0, min(1.0, (net_odds * probability - (1 - probability)) / net_odds))


@dataclass(frozen=True, slots=True)
class Opportunity:
    id: str
    net_odds: float
    probability: float

    @property
    def expected_return(self) -> float:
        return self.probability * self.net_odds - (1 - self.probability)

    @property
    def kelly(self) -> float:
        return kelly_fraction(self.probability, self.net_odds)


@dataclass(slots=True)
class Contestant:
    id: str
    name: str
    skill: str
    bankroll: float = 1000.0
    alive: bool = True


class InvestmentTournament:
    """Virtual-money tournament with private skill models and public rankings."""

    max_rounds = 12
    elimination_rounds = (4, 7, 10)

    def __init__(self, rng: random.Random | None = None) -> None:
        self.rng = rng or random.Random()
        self.round_number = 1
        self.phase = "decision"
        self.history: list[dict[str, object]] = []
        self.contestants = [
            Contestant("player", "You", "odds_analyst"),
            Contestant("kelly", "Kelly", "full_kelly"),
            Contestant("shield", "Shield", "half_kelly"),
            Contestant("chaser", "Chaser", "rank_chaser"),
            Contestant("rocket", "Rocket", "longshot"),
            Contestant("anchor", "Anchor", "capital_preserver"),
        ]
        self.offers = self._make_offers()

    def _make_offers(self) -> list[Opportunity]:
        offers = [Opportunity("A", 1.0, 0.5)]
        odds = self.rng.sample([0.75, 1.5, 2.0, 3.0, 5.0], 2)
        edges = self.rng.sample([-0.05, 0.02, 0.06, 0.10], 2)
        offers.extend(
            Opportunity(chr(66 + index), value, min(0.82, max(0.08, (1 + edge) / (value + 1))))
            for index, (value, edge) in enumerate(zip(odds, edges))
        )
        return offers

    def _contestant(self, contestant_id: str) -> Contestant:
        return next(item for item in self.contestants if item.id == contestant_id)

    def _ai_choice(self, contestant: Contestant) -> tuple[Opportunity, float]:
        positive = [offer for offer in self.offers if offer.expected_return > 0]
        pool = positive or self.offers
        if contestant.skill == "longshot":
            return max(self.offers, key=lambda item: item.net_odds), 0.45
        best = max(pool, key=lambda item: (item.expected_return, item.kelly))
        if contestant.skill == "half_kelly":
            return best, min(0.35, best.kelly * 0.5)
        if contestant.skill == "capital_preserver":
            return best, min(0.12, best.kelly * 0.35)
        if contestant.skill == "rank_chaser":
            living = sorted((item.bankroll for item in self.contestants if item.alive))
            median = living[len(living) // 2]
            return best, min(0.65, best.kelly * (1.8 if contestant.bankroll < median else 0.8))
        return best, min(0.6, best.kelly)

    def invest(self, offer_id: str, fraction: float) -> None:
        if self.phase != "decision":
            raise ValueError("the tournament is not awaiting an investment")
        if fraction < 0 or fraction > 0.75:
            raise ValueError("stake fraction must be between 0 and 0.75")
        try:
            player_offer = next(item for item in self.offers if item.id == offer_id)
        except StopIteration as error:
            raise ValueError("unknown opportunity") from error
        choices: dict[str, tuple[Opportunity, float]] = {"player": (player_offer, fraction)}
        for contestant in self.contestants:
            if contestant.alive and contestant.id != "player":
                choices[contestant.id] = self._ai_choice(contestant)
        results = []
        for contestant in self.contestants:
            if not contestant.alive:
                continue
            offer, stake_fraction = choices[contestant.id]
            before = contestant.bankroll
            stake = before * stake_fraction
            won = self.rng.random() < offer.probability
            contestant.bankroll = before + (stake * offer.net_odds if won else -stake)
            results.append({
                "id": contestant.id, "offer": offer.id, "fraction": stake_fraction,
                "won": won, "before": before, "after": contestant.bankroll,
            })
        eliminated = None
        if self.round_number in self.elimination_rounds:
            loser = min((item for item in self.contestants if item.alive), key=lambda item: (item.bankroll, item.id))
            loser.alive = False
            eliminated = loser.id
        self.history.append({"round": self.round_number, "results": results, "eliminated": eliminated})
        if not self._contestant("player").alive or self.round_number >= self.max_rounds:
            self.phase = "finished"
            return
        self.round_number += 1
        self.offers = self._make_offers()

    @property
    def rankings(self) -> list[Contestant]:
        return sorted(self.contestants, key=lambda item: (item.alive, item.bankroll), reverse=True)

    @property
    def winner(self) -> str | None:
        if self.phase != "finished" or self.round_number < self.max_rounds:
            return None
        return max(
            (item for item in self.contestants if item.alive),
            key=lambda item: item.bankroll,
        ).id
