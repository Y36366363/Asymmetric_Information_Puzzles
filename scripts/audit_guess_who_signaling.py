"""Run the frozen asymmetric-roster Guess Who signaling experiment."""

from __future__ import annotations

import argparse
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
    StrategicGuessWhoGame,
)
from audit_strategic_guess_who import behavior_summary


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PREREGISTRATION = (
    ROOT / "configs/guess_who_signaling_preregistration_2026-10-03.json"
)
DEFAULT_RULES = ROOT / "configs/strategic_guess_who_rules_v1.json"
DEFAULT_OUTPUT = ROOT / "research/results/guess_who_signaling_2026-10-03.json"


def root_policy_l1(policy, roster_size):
    by_player = {}
    maximum = 0.0
    for player in (0, 1):
        distributions = [
            policy[(player, ("act", secret, ()))]
            for secret in range(roster_size)
        ]
        player_maximum = max(
            sum(abs(first[action] - second[action]) for action in first)
            for first in distributions
            for second in distributions
        )
        by_player[str(player)] = player_maximum
        maximum = max(maximum, player_maximum)
    return maximum, by_player


def compact_evaluation(report):
    """Keep independent metrics and coverage without duplicating large value tables."""

    artifact = report.to_artifact()
    artifact["action_value_information_sets"] = len(artifact.pop("action_values"))
    return artifact


def compile_and_solve(game, evaluator_id):
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
    if frozen_rules != StrategicGuessWhoGame.rules_contract():
        raise ValueError("implementation no longer matches frozen Guess Who rules")
    if preregistration["rules_id"] != StrategicGuessWhoGame.RULES_ID:
        raise ValueError("preregistration is not bound to the frozen rules")
    indices = tuple(preregistration["target"]["roster_indices"])
    roster = tuple(DEFAULT_ROSTER[index] for index in indices)
    if [character.name for character in roster] != preregistration["target"]["roster_names"]:
        raise ValueError("preregistered roster names and indices disagree")
    question_ids = tuple(preregistration["target"]["question_ids"])
    question_by_id = {question.id: question for question in DEFAULT_QUESTIONS}
    questions = tuple(question_by_id[question_id] for question_id in question_ids)

    game = StrategicGuessWhoGame(roster, questions)
    form, solution, independent = compile_and_solve(
        game, "guess_who_asymmetric_signaling_v1"
    )
    endpoint, endpoint_by_player = root_policy_l1(solution.policy, len(roster))
    behavior = behavior_summary(game, solution.policy)
    threshold = preregistration["primary_endpoint"]
    if endpoint >= threshold["positive_signal_threshold"]:
        classification = "positive_signal"
    elif endpoint <= threshold["null_result_threshold"]:
        classification = "zero_result"
    else:
        classification = "ambiguous"

    reversed_game = StrategicGuessWhoGame(roster[::-1], questions[::-1])
    _, reversed_solution, reversed_independent = compile_and_solve(
        reversed_game, "guess_who_asymmetric_signaling_reversed_v1"
    )
    reversed_endpoint, _ = root_policy_l1(reversed_solution.policy, len(roster))

    algorithms = {}
    iterations = int(preregistration["solver"]["cfr_iterations"])
    cfr_gate = float(preregistration["solver"]["cfr_maximum_exploitability"])
    evaluator = FullTreeBestResponseEvaluator(
        game, evaluator_id="guess_who_asymmetric_signaling_cfr_v1",
        maximum_histories=100_000,
    )
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

    artifact = {
        "experiment_id": preregistration["experiment_id"],
        "preregistration": str(args.preregistration.relative_to(ROOT)),
        "frozen_rules": frozen_rules,
        "target": preregistration["target"],
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
            "scope_warning": "one canonical equilibrium and its reversed enumeration do not characterize every equilibrium when equilibria are nonunique",
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
        "frozen_rules_match": frozen_rules == StrategicGuessWhoGame.rules_contract(),
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
