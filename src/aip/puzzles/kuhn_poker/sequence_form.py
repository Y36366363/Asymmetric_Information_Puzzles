"""Independent sequence-form LP oracle for canonical Kuhn poker."""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Hashable, Mapping

from aip.core.evaluation import ActionValueReport, StrategyProfile
from aip.core.linear_program import maximize_linear_program
from aip.puzzles.kuhn_poker.cfr import KuhnCFRGame
from aip.puzzles.kuhn_poker.solver import (
    CARDS,
    KuhnPolicy,
    best_response_value,
    policy_value,
)


EMPTY_SEQUENCE = ("empty",)
Sequence = tuple[Hashable, ...]


@dataclass(frozen=True, slots=True)
class SequenceFormRepresentation:
    player_sequences: tuple[tuple[Sequence, ...], tuple[Sequence, ...]]
    flow_matrices: tuple[
        tuple[tuple[float, ...], ...], tuple[tuple[float, ...], ...]
    ]
    flow_rhs: tuple[tuple[float, ...], tuple[float, ...]]
    payoff_matrix: tuple[tuple[float, ...], ...]


@dataclass(frozen=True, slots=True)
class KuhnSequenceFormSolution:
    value_to_player_0: float
    realization_plans: tuple[Mapping[Sequence, float], Mapping[Sequence, float]]
    policy: StrategyProfile
    maximum_flow_residual: float
    primal_dual_gap: float


def _sequence(card: str, history: str, action: str) -> Sequence:
    return card, history, action


def _player_definition(player: int):
    if player == 0:
        infosets = tuple((card, history) for card in CARDS for history in ("", "cb"))
        actions = {
            (card, ""): ("check", "bet") for card in CARDS
        } | {
            (card, "cb"): ("fold", "call") for card in CARDS
        }
        parents = {
            (card, ""): EMPTY_SEQUENCE for card in CARDS
        } | {
            (card, "cb"): _sequence(card, "", "check") for card in CARDS
        }
    else:
        infosets = tuple((card, history) for card in CARDS for history in ("c", "b"))
        actions = {
            (card, "c"): ("check", "bet") for card in CARDS
        } | {
            (card, "b"): ("fold", "call") for card in CARDS
        }
        parents = {infoset: EMPTY_SEQUENCE for infoset in infosets}
    sequences = (EMPTY_SEQUENCE,) + tuple(
        _sequence(card, history, action)
        for card, history in infosets
        for action in actions[(card, history)]
    )
    index = {sequence: position for position, sequence in enumerate(sequences)}
    rows = []
    root = [0.0] * len(sequences)
    root[index[EMPTY_SEQUENCE]] = 1.0
    rows.append(tuple(root))
    for infoset in infosets:
        card, history = infoset
        row = [0.0] * len(sequences)
        row[index[parents[infoset]]] = -1.0
        for action in actions[infoset]:
            row[index[_sequence(card, history, action)]] = 1.0
        rows.append(tuple(row))
    return sequences, tuple(rows), (1.0,) + (0.0,) * len(infosets)


def build_kuhn_sequence_form() -> SequenceFormRepresentation:
    """Build realization-plan flow constraints and the chance-weighted payoff."""

    sequences_zero, flow_zero, rhs_zero = _player_definition(0)
    sequences_one, flow_one, rhs_one = _player_definition(1)
    index_zero = {sequence: index for index, sequence in enumerate(sequences_zero)}
    index_one = {sequence: index for index, sequence in enumerate(sequences_one)}
    payoff = [
        [0.0] * len(sequences_one) for _ in range(len(sequences_zero))
    ]
    terminals = {
        "cc": ("check", "c", "check"),
        "bc": ("bet", "b", "call"),
        "bf": ("bet", "b", "fold"),
        "cbc": ("call", "c", "bet"),
        "cbf": ("fold", "c", "bet"),
    }
    game = KuhnCFRGame()
    for first in CARDS:
        for second in CARDS:
            if first == second:
                continue
            for history, (zero_action, one_history, one_action) in terminals.items():
                zero_history = "cb" if history.startswith("cb") else ""
                zero_sequence = _sequence(first, zero_history, zero_action)
                one_sequence = _sequence(second, one_history, one_action)
                terminal_state = game.initial_state()
                terminal_state = game.next_state(terminal_state, (first, second))
                transitions = {
                    "cc": ("check", "check"),
                    "bc": ("bet", "call"),
                    "bf": ("bet", "fold"),
                    "cbc": ("check", "bet", "call"),
                    "cbf": ("check", "bet", "fold"),
                }
                for action in transitions[history]:
                    terminal_state = game.next_state(terminal_state, action)
                payoff[index_zero[zero_sequence]][index_one[one_sequence]] += (
                    game.utility_player_zero(terminal_state) / 6.0
                )
    return SequenceFormRepresentation(
        player_sequences=(sequences_zero, sequences_one),
        flow_matrices=(flow_zero, flow_one),
        flow_rhs=(rhs_zero, rhs_one),
        payoff_matrix=tuple(tuple(row) for row in payoff),
    )


def _maximize_realization_plan(
    payoff: tuple[tuple[float, ...], ...],
    row_flow: tuple[tuple[float, ...], ...],
    row_rhs: tuple[float, ...],
    column_flow: tuple[tuple[float, ...], ...],
    column_rhs: tuple[float, ...],
) -> tuple[float, tuple[float, ...]]:
    row_sequences = len(payoff)
    dual_rows = len(column_flow)
    variable_count = row_sequences + 2 * dual_rows
    inequalities = []
    bounds = []
    for flow_row, rhs in zip(row_flow, row_rhs):
        row = list(flow_row) + [0.0] * (2 * dual_rows)
        inequalities.append(tuple(row))
        bounds.append(rhs)
        inequalities.append(tuple(-value for value in row))
        bounds.append(-rhs)
    for column in range(len(payoff[0])):
        row = [-payoff[index][column] for index in range(row_sequences)]
        row.extend(column_flow[index][column] for index in range(dual_rows))
        row.extend(-column_flow[index][column] for index in range(dual_rows))
        inequalities.append(tuple(row))
        bounds.append(0.0)
    objective = [0.0] * variable_count
    for index, rhs in enumerate(column_rhs):
        objective[row_sequences + index] = rhs
        objective[row_sequences + dual_rows + index] = -rhs
    solution = maximize_linear_program(
        tuple(objective), tuple(inequalities), tuple(bounds)
    )
    realization = tuple(max(0.0, value) for value in solution.variables[:row_sequences])
    return solution.objective, realization


def _behavior_from_realization(
    player: int,
    sequences: tuple[Sequence, ...],
    realization: tuple[float, ...],
) -> dict[tuple[int, Hashable], dict[Hashable, float]]:
    index = {sequence: position for position, sequence in enumerate(sequences)}
    histories = ("", "cb") if player == 0 else ("c", "b")
    policy = {}
    for card in CARDS:
        for history in histories:
            actions = (
                ("check", "bet")
                if history in ("", "c")
                else ("fold", "call")
            )
            parent = (
                _sequence(card, "", "check")
                if player == 0 and history == "cb"
                else EMPTY_SEQUENCE
            )
            denominator = realization[index[parent]]
            weights = [
                realization[index[_sequence(card, history, action)]]
                for action in actions
            ]
            total = sum(weights)
            if denominator <= 1e-12 or total <= 1e-12:
                probabilities = (0.5, 0.5)
            else:
                probabilities = tuple(max(0.0, value / denominator) for value in weights)
                normalizer = sum(probabilities)
                probabilities = tuple(value / normalizer for value in probabilities)
            policy[(player, (card, history))] = dict(zip(actions, probabilities))
    return policy


def solve_kuhn_sequence_form() -> KuhnSequenceFormSolution:
    """Solve both sequence-form LPs and return a behavioral equilibrium."""

    representation = build_kuhn_sequence_form()
    value_zero, realization_zero = _maximize_realization_plan(
        representation.payoff_matrix,
        representation.flow_matrices[0],
        representation.flow_rhs[0],
        representation.flow_matrices[1],
        representation.flow_rhs[1],
    )
    payoff_one = tuple(
        tuple(
            -representation.payoff_matrix[row][column]
            for row in range(len(representation.payoff_matrix))
        )
        for column in range(len(representation.payoff_matrix[0]))
    )
    value_one, realization_one = _maximize_realization_plan(
        payoff_one,
        representation.flow_matrices[1],
        representation.flow_rhs[1],
        representation.flow_matrices[0],
        representation.flow_rhs[0],
    )
    policy = {
        **_behavior_from_realization(
            0, representation.player_sequences[0], realization_zero
        ),
        **_behavior_from_realization(
            1, representation.player_sequences[1], realization_one
        ),
    }
    residuals = []
    for matrix, rhs, realization in zip(
        representation.flow_matrices,
        representation.flow_rhs,
        (realization_zero, realization_one),
    ):
        residuals.extend(
            abs(sum(coefficient * value for coefficient, value in zip(row, realization)) - target)
            for row, target in zip(matrix, rhs)
        )
    return KuhnSequenceFormSolution(
        value_to_player_0=value_zero,
        realization_plans=(
            dict(zip(representation.player_sequences[0], realization_zero)),
            dict(zip(representation.player_sequences[1], realization_one)),
        ),
        policy=policy,
        maximum_flow_residual=max(residuals),
        primal_dual_gap=abs(value_zero + value_one),
    )


def _profile_to_kuhn(profile: StrategyProfile) -> KuhnPolicy:
    def probability(player: int, card: str, history: str, action: str) -> Fraction:
        value = profile[(player, (card, history))][action]
        return Fraction(float(value)).limit_denominator(1_000_000_000)

    return KuhnPolicy(
        first_open_bet={card: probability(0, card, "", "bet") for card in CARDS},
        first_call_after_check_bet={
            card: probability(0, card, "cb", "call") for card in CARDS
        },
        second_bet_after_check={
            card: probability(1, card, "c", "bet") for card in CARDS
        },
        second_call_open_bet={
            card: probability(1, card, "b", "call") for card in CARDS
        },
    )


def kuhn_policy_profile(policy: KuhnPolicy) -> dict:
    """Translate the analytic policy contract into the generic evaluator shape."""

    profile = {}
    for card in CARDS:
        profile[(0, (card, ""))] = {
            "check": float(1 - policy.first_open_bet[card]),
            "bet": float(policy.first_open_bet[card]),
        }
        profile[(0, (card, "cb"))] = {
            "fold": float(1 - policy.first_call_after_check_bet[card]),
            "call": float(policy.first_call_after_check_bet[card]),
        }
        profile[(1, (card, "c"))] = {
            "check": float(1 - policy.second_bet_after_check[card]),
            "bet": float(policy.second_bet_after_check[card]),
        }
        profile[(1, (card, "b"))] = {
            "fold": float(1 - policy.second_call_open_bet[card]),
            "call": float(policy.second_call_open_bet[card]),
        }
    return profile


class KuhnIndependentEvaluator:
    """Exhaustive Kuhn evaluator independent of any regret-minimization state."""

    evaluator_id = "kuhn_exhaustive_best_response_v1"

    def expected_value(self, profile: StrategyProfile) -> float:
        policy = _profile_to_kuhn(profile)
        return float(policy_value(policy, policy, hero_first=True))

    def best_response(self, profile: StrategyProfile, player: int) -> float:
        if player not in (0, 1):
            raise ValueError("best-response player must be zero or one")
        return float(
            best_response_value(_profile_to_kuhn(profile), hero_first=player == 0)
        )

    def nash_conv(self, profile: StrategyProfile) -> float:
        return self.best_response(profile, 0) + self.best_response(profile, 1)

    def exploitability(self, profile: StrategyProfile) -> float:
        return self.nash_conv(profile) / 2.0

    def action_values(self, profile: StrategyProfile) -> ActionValueReport:
        values = {}
        for key, distribution in profile.items():
            player = key[0]
            action_returns = {}
            for action in distribution:
                changed = {
                    other_key: dict(other_distribution)
                    for other_key, other_distribution in profile.items()
                }
                changed[key] = {
                    candidate: float(candidate == action)
                    for candidate in distribution
                }
                root_value = self.expected_value(changed)
                action_returns[action] = root_value if player == 0 else -root_value
            values[key] = action_returns
        return values
