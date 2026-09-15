"""Compile audited adapters into realization-plan LPs without game knowledge."""

from dataclasses import dataclass
from math import fsum, isfinite

from aip.core.cfr import CFRGameProperties, ExtensiveFormGame
from aip.core.linear_program import maximize_linear_program
from aip.core.tree_evaluation import audit_small_extensive_form


@dataclass(frozen=True)
class SequenceForm:
    player_sequences: tuple
    information_sets: tuple
    flow_matrices: tuple
    flow_rhs: tuple
    payoff_matrix: tuple
    audit: object

    def to_artifact(self):
        """Sparse export; indices refer to the accompanying canonical sequences."""
        return {
            "schema_version": "sequence_form_v1",
            "sequences": [[repr(s) for s in seqs] for seqs in self.player_sequences],
            "flow_rhs": self.flow_rhs,
            "flow_entries": [
                [[i, j, v] for i, row in enumerate(matrix)
                 for j, v in enumerate(row) if v]
                for matrix in self.flow_matrices
            ],
            "payoff_shape": list(map(len, self.player_sequences)),
            "payoff_entries": [[i, j, v]
                               for i, row in enumerate(self.payoff_matrix)
                               for j, v in enumerate(row) if v],
            "tree_audit": self.audit.to_artifact(),
        }


def compile_sequence_form(
    game: ExtensiveFormGame, *, game_properties: CFRGameProperties,
    maximum_histories=100_000, maximum_matrix_cells=250_000,
):
    """Require declared two-player zero sum and audited perfect recall.

    Each sequence is the player's complete information/action history. Chance
    reach is included only in terminal payoff entries, never realization flow.
    """
    if (game_properties.players != 2 or not game_properties.finite
        or not game_properties.zero_sum_or_constant_sum
        or not game_properties.perfect_recall):
        raise ValueError("sequence form requires finite two-player zero-sum perfect recall")
    if maximum_matrix_cells <= 0:
        raise ValueError("matrix budget must be positive")
    audit = audit_small_extensive_form(game, maximum_histories=maximum_histories)
    if not audit.passed:
        raise ValueError("adapter audit failed: " + ", ".join(audit.failures))
    tables = ({}, {})
    sequences = ({()}, {()})
    terminals = {}

    def traverse(state, history, chance):
        if game.is_terminal(state):
            key = history
            terminals.setdefault(key, []).append(chance * game.utility_player_zero(state))
            return
        player = game.current_player(state)
        if player is None:
            for action, probability in game.chance_outcomes(state):
                traverse(game.next_state(state, action), history, chance * probability)
            return
        info = game.information_set(state)
        actions = game.legal_actions(state)
        tables[player][info] = (history[player], actions)
        for action in actions:
            child = history[player] + ((info, action),)
            sequences[player].add(child)
            updated = list(history)
            updated[player] = child
            traverse(game.next_state(state, action), tuple(updated), chance)

    traverse(game.initial_state(), ((), ()), 1.0)
    ordered = tuple(tuple(sorted(s, key=lambda x: (len(x), repr(x)))) for s in sequences)
    if len(ordered[0]) * len(ordered[1]) > maximum_matrix_cells:
        raise OverflowError("sequence payoff matrix exceeds declared cell budget")
    indices = tuple({s: i for i, s in enumerate(seqs)} for seqs in ordered)
    flows, rhs, definitions = [], [], []
    for player in (0, 1):
        rows = []
        root = [0.0] * len(ordered[player])
        root[0] = 1.0
        rows.append(tuple(root))
        infos = tuple(sorted(tables[player], key=repr))
        definitions.append(tuple((info, *tables[player][info]) for info in infos))
        for info in infos:
            parent, actions = tables[player][info]
            row = [0.0] * len(ordered[player])
            row[indices[player][parent]] = -1.0
            for action in actions:
                row[indices[player][parent + ((info, action),)]] = 1.0
            rows.append(tuple(row))
        flows.append(tuple(rows))
        rhs.append((1.0,) + (0.0,) * len(infos))
    payoff = [[0.0] * len(ordered[1]) for _ in ordered[0]]
    for (zero, one), contributions in terminals.items():
        payoff[indices[0][zero]][indices[1][one]] = fsum(contributions)
    return SequenceForm(ordered, tuple(definitions), tuple(flows), tuple(rhs),
                        tuple(map(tuple, payoff)), audit)


def _maximize_plan(payoff, row_flow, row_rhs, column_flow, column_rhs):
    n, m = len(payoff), len(column_flow)
    inequalities, bounds = [], []
    for flow, rhs in zip(row_flow, row_rhs):
        row = tuple(flow) + (0.0,) * (2 * m)
        inequalities.extend((row, tuple(-v for v in row)))
        bounds.extend((rhs, -rhs))
    for j in range(len(payoff[0])):
        inequalities.append(tuple(-payoff[i][j] for i in range(n))
                            + tuple(row[j] for row in column_flow)
                            + tuple(-row[j] for row in column_flow))
        bounds.append(0.0)
    objective = (0.0,) * n + tuple(column_rhs) + tuple(-v for v in column_rhs)
    result = maximize_linear_program(objective, tuple(inequalities), tuple(bounds))
    return result.objective, tuple(max(0.0, v) for v in result.variables[:n])


@dataclass(frozen=True)
class SequenceFormSolution:
    value_to_player_0: float
    realization_plans: tuple
    policy: dict
    maximum_flow_residual: float
    primal_dual_gap: float


def solve_sequence_form(form: SequenceForm, *, tolerance=1e-8):
    """Solve both seats' LPs; refuse infeasible flow or primal-dual disagreement."""
    if not isfinite(tolerance) or tolerance <= 0:
        raise ValueError("LP tolerance must be finite and positive")
    values, plans = [], []
    for player in (0, 1):
        payoff = form.payoff_matrix if player == 0 else tuple(
            tuple(-form.payoff_matrix[i][j] for i in range(len(form.payoff_matrix)))
            for j in range(len(form.payoff_matrix[0])))
        value, plan = _maximize_plan(payoff, form.flow_matrices[player],
                                    form.flow_rhs[player], form.flow_matrices[1-player],
                                    form.flow_rhs[1-player])
        values.append(value)
        plans.append(plan)
    residual = max(abs(fsum(a*b for a, b in zip(row, plans[p])) - target)
                   for p in (0, 1)
                   for row, target in zip(form.flow_matrices[p], form.flow_rhs[p]))
    gap = abs(fsum(values))
    if residual > tolerance or gap > tolerance:
        raise ValueError("sequence-form LP failed flow or primal-dual gate")
    policy = {}
    for p in (0, 1):
        index = {s: i for i, s in enumerate(form.player_sequences[p])}
        for info, parent, actions in form.information_sets[p]:
            weights = [plans[p][index[parent + ((info, a),)]] for a in actions]
            total = fsum(weights)
            policy[(p, info)] = dict(zip(actions, (
                [w / total for w in weights] if total > 1e-12
                else [1 / len(actions)] * len(actions))))
    return SequenceFormSolution(values[0], tuple(
        dict(zip(form.player_sequences[p], plans[p])) for p in (0, 1)),
        policy, residual, gap)
