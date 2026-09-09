"""Kuhn Poker adapter and independent certification for the shared CFR engine."""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Hashable

from aip.core.cfr import (
    CFRCertificationGate,
    CFRGateReport,
    CFRGameProperties,
    CFRResult,
    CFRThresholds,
    CFRTrainer,
)
from aip.puzzles.kuhn_poker.solver import CARDS, KuhnPolicy, audit_policy


@dataclass(frozen=True, slots=True)
class KuhnCFRState:
    cards: tuple[str, str] | None = None
    history: str = ""


class KuhnCFRGame:
    """Canonical three-card Kuhn tree; utilities are net chips for first seat."""

    TERMINALS = frozenset({"cc", "bc", "bf", "cbc", "cbf"})

    def initial_state(self) -> KuhnCFRState:
        return KuhnCFRState()

    def is_terminal(self, state: KuhnCFRState) -> bool:
        return state.cards is not None and state.history in self.TERMINALS

    def utility_player_zero(self, state: KuhnCFRState) -> float:
        if not self.is_terminal(state) or state.cards is None:
            raise ValueError("utility is defined only at terminal Kuhn states")
        if state.history == "bf":
            return 1.0
        if state.history == "cbf":
            return -1.0
        stakes = 2 if state.history in {"bc", "cbc"} else 1
        first_wins = CARDS.index(state.cards[0]) > CARDS.index(state.cards[1])
        return float(stakes if first_wins else -stakes)

    def current_player(self, state: KuhnCFRState) -> int | None:
        if state.cards is None:
            return None
        return {"": 0, "b": 1, "c": 1, "cb": 0}.get(state.history)

    def chance_outcomes(
        self, state: KuhnCFRState
    ) -> tuple[tuple[Hashable, float], ...]:
        if state.cards is not None:
            return ()
        deals = tuple(
            (first, second)
            for first in CARDS
            for second in CARDS
            if first != second
        )
        return tuple((deal, 1 / len(deals)) for deal in deals)

    def legal_actions(self, state: KuhnCFRState) -> tuple[Hashable, ...]:
        if state.history in {"", "c"}:
            return ("check", "bet")
        if state.history in {"b", "cb"}:
            return ("fold", "call")
        return ()

    def information_set(self, state: KuhnCFRState) -> Hashable:
        player = self.current_player(state)
        if player is None or state.cards is None:
            raise ValueError("chance and terminal states have no player information set")
        return state.cards[player], state.history

    def next_state(self, state: KuhnCFRState, action: Hashable) -> KuhnCFRState:
        if state.cards is None:
            if not isinstance(action, tuple) or len(action) != 2:
                raise ValueError("Kuhn chance action must be a two-card deal")
            return KuhnCFRState((str(action[0]), str(action[1])))
        transitions = {
            ("", "check"): "c",
            ("", "bet"): "b",
            ("c", "check"): "cc",
            ("c", "bet"): "cb",
            ("b", "fold"): "bf",
            ("b", "call"): "bc",
            ("cb", "fold"): "cbf",
            ("cb", "call"): "cbc",
        }
        try:
            history = transitions[(state.history, action)]
        except KeyError as error:
            raise ValueError(f"illegal Kuhn transition: {state.history!r}, {action!r}") from error
        return KuhnCFRState(state.cards, history)


def _probability(
    result: CFRResult, player: int, card: str, history: str, action: str
) -> Fraction:
    probability = result.policy[(player, (card, history))][action]
    return Fraction(float(probability)).limit_denominator(1_000_000)


def kuhn_policy_from_cfr(result: CFRResult) -> KuhnPolicy:
    """Translate the shared policy shape into the local audited policy contract."""

    return KuhnPolicy(
        first_open_bet={
            card: _probability(result, 0, card, "", "bet") for card in CARDS
        },
        first_call_after_check_bet={
            card: _probability(result, 0, card, "cb", "call") for card in CARDS
        },
        second_bet_after_check={
            card: _probability(result, 1, card, "c", "bet") for card in CARDS
        },
        second_call_open_bet={
            card: _probability(result, 1, card, "b", "call") for card in CARDS
        },
    )


def train_kuhn_cfr(iterations: int = 50_000) -> CFRResult:
    return CFRTrainer(KuhnCFRGame()).train(iterations)


def certify_kuhn_cfr(
    result: CFRResult,
    thresholds: CFRThresholds | None = None,
) -> CFRGateReport:
    """Gate CFR output using Kuhn's independent exhaustive best-response oracle."""

    policy = kuhn_policy_from_cfr(result)
    exploitability = float(audit_policy(policy).maximum_exploitability)
    gate = CFRCertificationGate(
        thresholds
        or CFRThresholds(
            min_iterations=50_000,
            min_information_sets=12,
            min_visits_per_information_set=50_000,
            max_average_positive_regret=0.01,
            max_exploitability=0.01,
        )
    )
    required_information_sets = frozenset(
        {
            (0, (card, history))
            for card in CARDS
            for history in ("", "cb")
        }
        | {
            (1, (card, history))
            for card in CARDS
            for history in ("c", "b")
        }
    )
    return gate.evaluate(
        result,
        exploitability=exploitability,
        required_information_sets=required_information_sets,
        exact_information_sets=True,
        game_properties=CFRGameProperties(
            players=2,
            finite=True,
            zero_sum_or_constant_sum=True,
            perfect_recall=True,
        ),
    )
