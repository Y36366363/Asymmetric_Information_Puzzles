"""Run the frozen v2 private-question-cost signaling experiment."""

from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path

from aip.core import (
    CFRGameProperties,
    compile_sequence_form,
    create_regret_minimization_trainer,
    run_independent_evaluation,
    solve_sequence_form,
)
from aip.core.tree_evaluation import FullTreeBestResponseEvaluator
from aip.puzzles.guess_who import (
    DEFAULT_QUESTIONS,
    DEFAULT_ROSTER,
    PrivateCostStrategicGuessWhoGame,
)
from audit_guess_who_signaling import compact_evaluation, root_policy_l1
from audit_strategic_guess_who import behavior_summary


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PREREGISTRATION = (
    ROOT / "configs/guess_who_private_cost_signaling_preregistration_2026-10-04.json"
)
DEFAULT_RULES = ROOT / "configs/strategic_guess_who_private_cost_rules_v2.json"
DEFAULT_OUTPUT = (
    ROOT / "research/results/guess_who_private_cost_signaling_2026-10-04.json"
)


def expected_costs(game, policy):
    result = defaultdict(float)

    def traverse(state, reach):
        if game.is_terminal(state):
            return
        player = game.current_player(state)
        key = (player, game.information_set(state))
        for action, probability in policy[key].items():
            if not probability:
                continue
            child_reach = reach * probability
            if state.stage == "player_1_action":
                action_zero = state.pending_player_0_action
                if action_zero is None or state.secrets[0] is None or state.secrets[1] is None:
                    raise AssertionError("private-cost round lacks committed state")
                if action_zero[0] == "ask":
                    result["player_0"] += child_reach * game.question_costs[
                        state.secrets[0]
                    ][action_zero[1]]
                if action[0] == "ask":
                    result["player_1"] += child_reach * game.question_costs[
                        state.secrets[1]
                    ][action[1]]
            traverse(game.next_state(state, action), child_reach)

    traverse(game.initial_state(), 1.0)
    return dict(result)


def build_game(preregistration, *, reverse=False):
    indices = tuple(preregistration["target"]["roster_indices"])
    roster = tuple(DEFAULT_ROSTER[index] for index in indices)
    by_id = {question.id: question for question in DEFAULT_QUESTIONS}
    questions = tuple(
        by_id[question_id]
        for question_id in preregistration["target"]["question_ids"]
    )
    costs = tuple(
        tuple(float(value) for value in row)
        for row in preregistration["private_question_costs"]
        ["matrix_by_roster_and_question_order"]
    )
    if reverse:
        roster = roster[::-1]
        questions = questions[::-1]
        costs = tuple(tuple(reversed(row)) for row in reversed(costs))
    return PrivateCostStrategicGuessWhoGame(roster, questions, costs)


def solve_exact(game, evaluator_id):
    form = compile_sequence_form(
        game,
        game_properties=CFRGameProperties(2, True, True, True),
        maximum_histories=100_000,
        sparse=True,
    )
    solution = solve_sequence_form(form, backend="scipy_highs")
    report = run_independent_evaluation(
        FullTreeBestResponseEvaluator(
            game, evaluator_id=evaluator_id, maximum_histories=100_000
        ),
        solution.policy,
        maximum_exploitability=1e-10,
    )
    return form, solution, report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preregistration", type=Path, default=DEFAULT_PREREGISTRATION)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    preregistration = json.loads(args.preregistration.read_text(encoding="utf-8"))
    frozen_rules = json.loads(DEFAULT_RULES.read_text(encoding="utf-8"))
    if frozen_rules != PrivateCostStrategicGuessWhoGame.rules_contract():
        raise ValueError("implementation no longer matches frozen private-cost rules")
    if preregistration["rules_id"] != PrivateCostStrategicGuessWhoGame.RULES_ID:
        raise ValueError("preregistration is not bound to private-cost v2 rules")
    game = build_game(preregistration)
    expected_names = preregistration["target"]["roster_names"]
    if [character.name for character in game.roster] != expected_names:
        raise ValueError("preregistered roster names and indices disagree")

    form, solution, independent = solve_exact(
        game, "guess_who_private_cost_signaling_v2"
    )
    endpoint, endpoint_by_player = root_policy_l1(
        solution.policy, len(game.roster)
    )
    threshold = preregistration["primary_endpoint"]
    if endpoint >= threshold["positive_signal_threshold"]:
        classification = "positive_signal"
    elif endpoint <= threshold["null_result_threshold"]:
        classification = "zero_result"
    else:
        classification = "ambiguous"

    reversed_game = build_game(preregistration, reverse=True)
    _, reversed_solution, reversed_independent = solve_exact(
        reversed_game, "guess_who_private_cost_signaling_reversed_v2"
    )
    reversed_endpoint, _ = root_policy_l1(
        reversed_solution.policy, len(reversed_game.roster)
    )

    iterations = int(preregistration["solver"]["cfr_iterations"])
    cfr_gate = float(preregistration["solver"]["cfr_maximum_exploitability"])
    evaluator = FullTreeBestResponseEvaluator(
        game, evaluator_id="guess_who_private_cost_signaling_cfr_v2",
        maximum_histories=100_000,
    )
    algorithms = {}
    for algorithm_id in preregistration["solver"]["cfr_cross_check_algorithms"]:
        result = create_regret_minimization_trainer(game, algorithm_id).train(iterations)
        report = run_independent_evaluation(
            evaluator, result.policy, maximum_exploitability=cfr_gate
        )
        algorithms[algorithm_id] = {
            "algorithm": result.algorithm.to_artifact(),
            "iterations": iterations,
            "independent_evaluation": compact_evaluation(report),
        }
    negative_result = create_regret_minimization_trainer(
        game, "vanilla_cfr"
    ).train(10)
    negative = run_independent_evaluation(
        evaluator, negative_result.policy, maximum_exploitability=cfr_gate
    )

    behavior = behavior_summary(game, solution.policy)
    behavior["expected_question_cost_by_seat"] = expected_costs(
        game, solution.policy
    )
    artifact = {
        "experiment_id": preregistration["experiment_id"],
        "preregistration": str(args.preregistration.relative_to(ROOT)),
        "frozen_rules": frozen_rules,
        "target": preregistration["target"],
        "private_question_costs": preregistration["private_question_costs"],
        "tree_audit": form.audit.to_artifact(),
        "sequence_form": {
            "player_0_sequences": len(form.player_sequences[0]),
            "player_1_sequences": len(form.player_sequences[1]),
            "payoff_shape": list(form.payoff_matrix.shape),
            "payoff_nonzeros": len(form.payoff_matrix.entries),
            "value_to_player_0": solution.value_to_player_0,
            "backend": solution.backend,
            "maximum_flow_residual": solution.maximum_flow_residual,
            "primal_dual_gap": solution.primal_dual_gap,
            "independent_evaluation": compact_evaluation(independent),
        },
        "primary_endpoint": {
            "name": threshold["name"],
            "value": endpoint,
            "by_player": endpoint_by_player,
            "classification": classification,
            "positive_signal_threshold": threshold["positive_signal_threshold"],
            "null_result_threshold": threshold["null_result_threshold"],
            "reversed_enumeration_value": reversed_endpoint,
            "scope_warning": "canonical and reversed LP solutions do not enumerate every equilibrium when the equilibrium set is nonunique",
        },
        "equilibrium_behavior": behavior,
        "regret_minimization_cross_check": algorithms,
        "undertrained_negative_control": {
            "iterations": 10,
            "exploitability": negative.exploitability,
            "passed_gate": negative.passed,
        },
        "runtime_epsilon_gto_allowed": False,
    }
    artifact["checks"] = {
        "frozen_rules_match": frozen_rules == PrivateCostStrategicGuessWhoGame.rules_contract(),
        "tree_audit": form.audit.passed,
        "independent_exploitability_gate": independent.passed,
        "reversed_independent_exploitability_gate": reversed_independent.passed,
        "endpoint_enumeration_invariance": abs(endpoint - reversed_endpoint) < 1e-10,
        "all_cfr_cross_checks": all(
            record["independent_evaluation"]["passed"]
            for record in algorithms.values()
        ),
        "undertrained_negative_control_rejected": not negative.passed,
    }
    artifact["passed"] = all(artifact["checks"].values())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(artifact, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(args.output)
    return 0 if artifact["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
