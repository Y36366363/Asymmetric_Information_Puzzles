"""Exact decision probes for the four-card Goofspiel horizontal benchmark."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from fractions import Fraction
from itertools import combinations
from typing import Mapping

from aip.benchmark.types import ActionSpec, AgentDecision, AgentInput
from aip.benchmark.value_decomposition import ValueDecomposition
from aip.puzzles.goofspiel import GoofspielSolver


RULES = (
    "Both players start with bid cards 1 through 4. A remaining prize is revealed, "
    "then both players secretly and simultaneously spend one remaining bid card. "
    "The higher bid wins the prize value, equal bids discard it, and spent cards do "
    "not return. Choose one supplied legal bid to maximize final score difference."
)


def _digest(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _action_id(card: int) -> str:
    return f"bid:{card}"


@dataclass(frozen=True, slots=True)
class GoofspielProbe:
    """One public Goofspiel state with an exact equilibrium-opponent oracle."""

    probe_id: str
    player_cards: tuple[int, ...]
    opponent_cards: tuple[int, ...]
    remaining_prizes: tuple[int, ...]
    current_prize: int
    exact_action_values: Mapping[str, Fraction]
    equilibrium_policy: Mapping[str, Fraction]
    opponent_bid_belief: Mapping[str, Fraction]

    def decision_input(self) -> AgentInput:
        return AgentInput(
            environment_id="goofspiel-four-card-held-out",
            episode_id="goofspiel-four-card:oracle-probe",
            step=4 - len(self.player_cards),
            observation={"kind": "simultaneous_bid", "currentPrize": self.current_prize},
            information_state={
                "remainingBidCards": list(self.player_cards),
                "opponentRemainingBidCards": list(self.opponent_cards),
                "remainingPrizesIncludingCurrent": list(self.remaining_prizes),
                "beliefTarget": "opponent_current_bid",
                "beliefStateLabels": [str(card) for card in self.opponent_cards],
            },
            legal_actions=tuple(
                ActionSpec(_action_id(card), f"Secretly spend bid card {card}.")
                for card in self.player_cards
            ),
            natural_language_rules=RULES,
        )

    def evaluate(self, decision: AgentDecision) -> dict[str, object]:
        if decision.action_id not in self.exact_action_values:
            raise ValueError("chosen action is not legal in this Goofspiel state")
        optimum = max(self.exact_action_values.values())
        regret = optimum - self.exact_action_values[decision.action_id]
        belief_brier = None
        if decision.belief is not None:
            if decision.belief.target != "opponent_current_bid":
                raise ValueError("belief target must be opponent_current_bid")
            belief_brier = sum(
                (
                    decision.belief.probabilities.get(label, 0.0)
                    - float(probability)
                ) ** 2
                for label, probability in self.opponent_bid_belief.items()
            )
        return {
            "actionRegret": float(regret),
            "optimalActionIds": sorted(
                action for action, value in self.exact_action_values.items()
                if value == optimum
            ),
            "optimalPolicyAgreement": regret == 0,
            "equilibriumActionProbability": float(
                self.equilibrium_policy[decision.action_id]
            ),
            "beliefBrierToEquilibriumOpponent": belief_brier,
        }

    def to_artifact(self) -> dict[str, object]:
        return {
            "id": self.probe_id,
            "playerCards": list(self.player_cards),
            "opponentCards": list(self.opponent_cards),
            "remainingPrizes": list(self.remaining_prizes),
            "currentPrize": self.current_prize,
            "exactActionValues": {
                action: float(value) for action, value in self.exact_action_values.items()
            },
            "equilibriumPolicy": {
                action: float(value) for action, value in self.equilibrium_policy.items()
            },
            "opponentBidBelief": {
                label: float(value) for label, value in self.opponent_bid_belief.items()
            },
            "oracle": "exact_backward_induction_plus_zero_sum_matrix",
            "objective": "expected_final_score_difference",
        }


def _probe(
    solver: GoofspielSolver,
    player_cards: tuple[int, ...],
    opponent_cards: tuple[int, ...],
    prizes: tuple[int, ...],
    current_prize: int,
) -> GoofspielProbe:
    solution = solver.round_solution(
        player_cards, opponent_cards, prizes, current_prize
    )
    next_prizes = tuple(prize for prize in prizes if prize != current_prize)
    values: dict[str, Fraction] = {}
    for row_index, player_bid in enumerate(player_cards):
        next_player = tuple(card for card in player_cards if card != player_bid)
        value = Fraction(0)
        for column_index, opponent_bid in enumerate(opponent_cards):
            next_opponent = tuple(
                card for card in opponent_cards if card != opponent_bid
            )
            immediate = current_prize * (
                (player_bid > opponent_bid) - (player_bid < opponent_bid)
            )
            value += solution.column_strategy[column_index] * (
                immediate
                + solver.state_value(next_player, next_opponent, next_prizes)
            )
        values[_action_id(player_bid)] = value
    identity = {
        "playerCards": player_cards,
        "opponentCards": opponent_cards,
        "prizes": prizes,
        "currentPrize": current_prize,
    }
    return GoofspielProbe(
        probe_id="goofspiel-probe-" + _digest(identity)[:12],
        player_cards=player_cards,
        opponent_cards=opponent_cards,
        remaining_prizes=prizes,
        current_prize=current_prize,
        exact_action_values=values,
        equilibrium_policy={
            _action_id(card): probability
            for card, probability in zip(player_cards, solution.row_strategy)
        },
        opponent_bid_belief={
            str(card): probability
            for card, probability in zip(opponent_cards, solution.column_strategy)
        },
    )


def candidate_goofspiel_probes() -> tuple[GoofspielProbe, ...]:
    """Enumerate every non-terminal four-card public decision state exactly."""

    solver = GoofspielSolver(4)
    cards = solver.cards
    probes = []
    for remaining in (4, 3, 2):
        for player_cards in combinations(cards, remaining):
            for opponent_cards in combinations(cards, remaining):
                for prizes in combinations(cards, remaining):
                    for current_prize in prizes:
                        probes.append(_probe(
                            solver,
                            player_cards,
                            opponent_cards,
                            prizes,
                            current_prize,
                        ))
    return tuple(probes)


def build_goofspiel_oracle_probes(count: int = 30) -> tuple[GoofspielProbe, ...]:
    """Select a deterministic stage-stratified exact panel for later experiments."""

    if count != 30:
        raise ValueError("the frozen Goofspiel v1 panel contains exactly 30 states")
    candidates = candidate_goofspiel_probes()
    by_remaining = {
        remaining: [
            probe for probe in candidates
            if len(probe.player_cards) == remaining
            and max(probe.exact_action_values.values())
            > min(probe.exact_action_values.values())
        ]
        for remaining in (4, 3, 2)
    }
    quotas = {4: 4, 3: 13, 2: 13}
    selected = []
    for remaining in (4, 3, 2):
        ranked = sorted(
            by_remaining[remaining],
            key=lambda probe: _digest({
                "seed": 20260923,
                "panel": "goofspiel_four_card_v1",
                "probe": probe.probe_id,
            }),
        )
        selected.extend(ranked[:quotas[remaining]])
    if len(selected) != count:
        raise ValueError("insufficient nontrivial Goofspiel states")
    return tuple(selected)


class GoofspielValueDecompositionOracle:
    """Exact opponent-bid posterior → immediate/future bid values → action."""

    oracle_id = "goofspiel_four_card_value_decomposition_v1"

    def __init__(self, solver: GoofspielSolver | None = None) -> None:
        self.solver = solver or GoofspielSolver(4)

    def decompose(self, probe: GoofspielProbe) -> ValueDecomposition:
        next_prizes = tuple(
            prize for prize in probe.remaining_prizes
            if prize != probe.current_prize
        )
        immediate = {}
        continuation = {}
        for player_bid in probe.player_cards:
            action = _action_id(player_bid)
            next_player = tuple(
                card for card in probe.player_cards if card != player_bid
            )
            immediate_value = Fraction(0)
            continuation_value = Fraction(0)
            for opponent_bid in probe.opponent_cards:
                probability = probe.opponent_bid_belief[str(opponent_bid)]
                next_opponent = tuple(
                    card for card in probe.opponent_cards if card != opponent_bid
                )
                immediate_value += probability * probe.current_prize * (
                    (player_bid > opponent_bid) - (player_bid < opponent_bid)
                )
                continuation_value += probability * self.solver.state_value(
                    next_player, next_opponent, next_prizes
                )
            immediate[action] = float(immediate_value)
            continuation[action] = float(continuation_value)
        total = {
            action: immediate[action] + continuation[action]
            for action in immediate
        }
        optimum = max(total.values())
        chosen = sorted(
            action for action, value in total.items()
            if abs(value - optimum) <= 1e-12
        )[0]
        return ValueDecomposition(
            posterior_target="opponent_current_bid",
            posterior={
                label: float(probability)
                for label, probability in probe.opponent_bid_belief.items()
            },
            immediate_action_values=immediate,
            continuation_action_values=continuation,
            total_action_values=total,
            chosen_action_id=chosen,
        )
