from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from itertools import product
from typing import Mapping


CARDS = ("J", "Q", "K")
ProbabilityTable = Mapping[str, Fraction]


@dataclass(frozen=True, slots=True)
class KuhnPolicy:
    """Behavior strategy for both seats in the three-card Kuhn game.

    Each table stores the probability of the aggressive action: bet for the
    opening tables and call for the response tables.
    """

    first_open_bet: ProbabilityTable
    first_call_after_check_bet: ProbabilityTable
    second_bet_after_check: ProbabilityTable
    second_call_open_bet: ProbabilityTable


@dataclass(frozen=True, slots=True)
class PolicyAudit:
    first_seat_best_response: Fraction
    second_seat_best_response: Fraction
    first_seat_exploitability: Fraction
    second_seat_exploitability: Fraction

    @property
    def maximum_exploitability(self) -> Fraction:
        return max(self.first_seat_exploitability, self.second_seat_exploitability)


def equilibrium_policy() -> KuhnPolicy:
    """Return the alpha=1/3 member of Kuhn Poker's equilibrium family."""
    return KuhnPolicy(
        first_open_bet={"J": Fraction(1, 3), "Q": Fraction(0), "K": Fraction(1)},
        first_call_after_check_bet={
            "J": Fraction(0),
            "Q": Fraction(2, 3),
            "K": Fraction(1),
        },
        second_bet_after_check={
            "J": Fraction(1, 3),
            "Q": Fraction(0),
            "K": Fraction(1),
        },
        second_call_open_bet={
            "J": Fraction(0),
            "Q": Fraction(1, 3),
            "K": Fraction(1),
        },
    )


def legacy_policy() -> KuhnPolicy:
    """Return the pre-audit policy, retained as a regression comparison."""
    policy = equilibrium_policy()
    return KuhnPolicy(
        first_open_bet=policy.first_open_bet,
        first_call_after_check_bet={
            "J": Fraction(0),
            "Q": Fraction(1, 3),
            "K": Fraction(1),
        },
        second_bet_after_check=policy.second_bet_after_check,
        second_call_open_bet=policy.second_call_open_bet,
    )


def basic_policy() -> KuhnPolicy:
    """Return the intentionally exploitable policy used by the basic AI.

    The policy preserves Kuhn Poker's value bets and randomized bluffs, but it
    calls a bet with Q too rarely after checking.  A second-seat player can
    therefore earn more than the game's equilibrium seat value by adapting.
    """
    return legacy_policy()


def game_value(hero_first: bool) -> Fraction:
    """Zero-sum equilibrium value for the requested seat, including antes."""
    return Fraction(-1 if hero_first else 1, 18)


def policy_value(
    hero: KuhnPolicy, opponent: KuhnPolicy, *, hero_first: bool
) -> Fraction:
    """Return the exact expected value of one behavior policy against another."""
    total = Fraction(0)
    for hero_card in CARDS:
        for opponent_card in CARDS:
            if hero_card == opponent_card:
                continue
            if hero_first:
                open_probability = hero.first_open_bet[hero_card]
                opponent_call = opponent.second_call_open_bet[opponent_card]
                bet_value = opponent_call * _showdown(hero_card, opponent_card, 2)
                bet_value += (1 - opponent_call) * 1
                opponent_bet = opponent.second_bet_after_check[opponent_card]
                hero_call = hero.first_call_after_check_bet[hero_card]
                response_value = hero_call * _showdown(hero_card, opponent_card, 2)
                response_value += (1 - hero_call) * -1
                check_value = (1 - opponent_bet) * _showdown(
                    hero_card, opponent_card, 1
                )
                check_value += opponent_bet * response_value
                value = open_probability * bet_value + (1 - open_probability) * check_value
            else:
                opponent_open = opponent.first_open_bet[opponent_card]
                hero_call = hero.second_call_open_bet[hero_card]
                facing_bet = hero_call * _showdown(hero_card, opponent_card, 2)
                facing_bet += (1 - hero_call) * -1
                hero_bet = hero.second_bet_after_check[hero_card]
                opponent_call = opponent.first_call_after_check_bet[opponent_card]
                bet_value = opponent_call * _showdown(hero_card, opponent_card, 2)
                bet_value += (1 - opponent_call) * 1
                checked_to = hero_bet * bet_value
                checked_to += (1 - hero_bet) * _showdown(hero_card, opponent_card, 1)
                value = opponent_open * facing_bet + (1 - opponent_open) * checked_to
            total += value
    return total / 6


def _showdown(hero_card: str, opponent_card: str, stakes: int) -> Fraction:
    return Fraction(stakes if CARDS.index(hero_card) > CARDS.index(opponent_card) else -stakes)


def _pure_response_value(
    opponent: KuhnPolicy,
    *,
    hero_first: bool,
    aggressive: Mapping[str, bool],
    call: Mapping[str, bool],
) -> Fraction:
    total = Fraction(0)
    for hero_card in CARDS:
        for opponent_card in CARDS:
            if hero_card == opponent_card:
                continue
            if hero_first:
                if aggressive[hero_card]:
                    call_probability = opponent.second_call_open_bet[opponent_card]
                    value = call_probability * _showdown(hero_card, opponent_card, 2)
                    value += (1 - call_probability) * 1
                else:
                    bet_probability = opponent.second_bet_after_check[opponent_card]
                    response = (
                        _showdown(hero_card, opponent_card, 2)
                        if call[hero_card]
                        else Fraction(-1)
                    )
                    value = (1 - bet_probability) * _showdown(hero_card, opponent_card, 1)
                    value += bet_probability * response
            else:
                open_probability = opponent.first_open_bet[opponent_card]
                response = (
                    _showdown(hero_card, opponent_card, 2)
                    if call[hero_card]
                    else Fraction(-1)
                )
                value = open_probability * response
                if aggressive[hero_card]:
                    call_probability = opponent.first_call_after_check_bet[opponent_card]
                    checked_value = call_probability * _showdown(hero_card, opponent_card, 2)
                    checked_value += (1 - call_probability) * 1
                else:
                    checked_value = _showdown(hero_card, opponent_card, 1)
                value += (1 - open_probability) * checked_value
            total += value
    return total / 6


def best_response_value(opponent: KuhnPolicy, *, hero_first: bool) -> Fraction:
    """Exhaust all 64 pure behavioral responses and return the best value."""
    best: Fraction | None = None
    for choices in product((False, True), repeat=6):
        aggressive = dict(zip(CARDS, choices[:3]))
        call = dict(zip(CARDS, choices[3:]))
        value = _pure_response_value(
            opponent,
            hero_first=hero_first,
            aggressive=aggressive,
            call=call,
        )
        if best is None or value > best:
            best = value
    assert best is not None
    return best


def audit_policy(policy: KuhnPolicy) -> PolicyAudit:
    first = best_response_value(policy, hero_first=True)
    second = best_response_value(policy, hero_first=False)
    return PolicyAudit(
        first_seat_best_response=first,
        second_seat_best_response=second,
        first_seat_exploitability=first - game_value(True),
        second_seat_exploitability=second - game_value(False),
    )
