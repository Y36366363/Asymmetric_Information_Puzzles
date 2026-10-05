"""Run the frozen private-question-cost dose-response experiment."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from aip.core import create_regret_minimization_trainer, run_independent_evaluation
from aip.core.tree_evaluation import FullTreeBestResponseEvaluator
from aip.puzzles.guess_who import (
    DEFAULT_QUESTIONS,
    DEFAULT_ROSTER,
    PrivateCostStrategicGuessWhoGame,
)
from audit_guess_who_private_cost_signaling import expected_costs, solve_exact
from audit_guess_who_signaling import compact_evaluation, root_policy_l1
from audit_strategic_guess_who import behavior_summary


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PREREGISTRATION = (
    ROOT
    / "configs/guess_who_private_cost_dose_response_preregistration_2026-10-05.json"
)
DEFAULT_RULES = ROOT / "configs/strategic_guess_who_private_cost_rules_v2.json"
DEFAULT_OUTPUT = (
    ROOT / "research/results/guess_who_private_cost_dose_response_2026-10-05.json"
)


def _validate_design(preregistration):
    design = preregistration["private_question_cost_shape"]
    units = tuple(float(value) for value in design["unit_cost_levels"])
    maxima = tuple(
        float(value) for value in design["maximum_single_question_cost_by_level"]
    )
    shape = tuple(
        tuple(int(value) for value in row)
        for row in design["integer_matrix_by_roster_and_question_order"]
    )
    if not units or any(not math.isfinite(value) or value < 0 for value in units):
        raise ValueError("dose levels must be finite and nonnegative")
    if tuple(sorted(set(units))) != units:
        raise ValueError("dose levels must be unique and increasing")
    if len(shape) != len(preregistration["target"]["roster_indices"]):
        raise ValueError("cost-shape rows must match the roster")
    question_count = len(preregistration["target"]["question_ids"])
    if any(len(row) != question_count or any(value < 0 for value in row) for row in shape):
        raise ValueError("cost-shape columns must match questions and be nonnegative")
    expected_maxima = tuple(max(max(row) for row in shape) * unit for unit in units)
    if maxima != expected_maxima:
        raise ValueError("preregistered maximum costs disagree with shape and dose")
    if float(preregistration["solver"]["cfr_cross_check_unit_cost"]) not in units:
        raise ValueError("CFR cross-check dose must be in the frozen grid")
    return units, shape


def build_game(preregistration, unit_cost, *, reverse=False):
    units, shape = _validate_design(preregistration)
    if float(unit_cost) not in units:
        raise ValueError("unit cost is outside the preregistered grid")
    roster = tuple(
        DEFAULT_ROSTER[index]
        for index in preregistration["target"]["roster_indices"]
    )
    question_by_id = {question.id: question for question in DEFAULT_QUESTIONS}
    questions = tuple(
        question_by_id[question_id]
        for question_id in preregistration["target"]["question_ids"]
    )
    costs = tuple(
        tuple(float(unit_cost) * multiplier for multiplier in row)
        for row in shape
    )
    if reverse:
        roster = roster[::-1]
        questions = questions[::-1]
        costs = tuple(tuple(reversed(row)) for row in reversed(costs))
    return PrivateCostStrategicGuessWhoGame(roster, questions, costs)


def _classification(value, endpoint):
    if value >= float(endpoint["positive_signal_threshold"]):
        return "positive_signal"
    if value <= float(endpoint["null_result_threshold"]):
        return "zero_result"
    return "ambiguous"


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
    if not preregistration["frozen_before_outcome_evaluation"]:
        raise ValueError("dose-response design is not frozen")
    units, shape = _validate_design(preregistration)
    endpoint = preregistration["primary_endpoint"]
    exact_gate = float(preregistration["solver"]["maximum_exploitability"])

    levels = []
    all_exact_checks = True
    all_enumeration_checks = True
    for index, unit_cost in enumerate(units):
        game = build_game(preregistration, unit_cost)
        if [character.name for character in game.roster] != preregistration["target"][
            "roster_names"
        ]:
            raise ValueError("preregistered roster names and indices disagree")
        form, solution, independent = solve_exact(
            game, f"guess_who_private_cost_dose_{index}_v2"
        )
        root_l1, by_player = root_policy_l1(solution.policy, len(game.roster))

        reversed_game = build_game(preregistration, unit_cost, reverse=True)
        _, reversed_solution, reversed_independent = solve_exact(
            reversed_game, f"guess_who_private_cost_dose_{index}_reversed_v2"
        )
        reversed_l1, _ = root_policy_l1(
            reversed_solution.policy, len(reversed_game.roster)
        )
        enumeration_invariant = (
            abs(root_l1 - reversed_l1) < 1e-10
            and abs(solution.value_to_player_0 - reversed_solution.value_to_player_0)
            < 1e-10
        )
        exact_checks = (
            form.audit.passed
            and independent.passed
            and reversed_independent.passed
            and independent.exploitability <= exact_gate
            and reversed_independent.exploitability <= exact_gate
        )
        all_exact_checks = all_exact_checks and exact_checks
        all_enumeration_checks = all_enumeration_checks and enumeration_invariant
        behavior = behavior_summary(game, solution.policy)
        behavior["expected_question_cost_by_seat"] = expected_costs(
            game, solution.policy
        )
        levels.append(
            {
                "dose_index": index,
                "unit_cost": unit_cost,
                "maximum_single_question_cost": max(max(row) for row in shape)
                * unit_cost,
                "classification": _classification(root_l1, endpoint),
                "primary_endpoint": root_l1,
                "primary_endpoint_by_player": by_player,
                "reversed_enumeration_endpoint": reversed_l1,
                "value_to_player_0": solution.value_to_player_0,
                "reversed_value_to_player_0": reversed_solution.value_to_player_0,
                "tree_audit": form.audit.to_artifact(),
                "sequence_form": {
                    "player_0_sequences": len(form.player_sequences[0]),
                    "player_1_sequences": len(form.player_sequences[1]),
                    "payoff_shape": list(form.payoff_matrix.shape),
                    "payoff_nonzeros": len(form.payoff_matrix.entries),
                    "backend": solution.backend,
                    "maximum_flow_residual": solution.maximum_flow_residual,
                    "primal_dual_gap": solution.primal_dual_gap,
                },
                "independent_evaluation": compact_evaluation(independent),
                "reversed_independent_evaluation": compact_evaluation(
                    reversed_independent
                ),
                "equilibrium_behavior": behavior,
                "checks": {
                    "exact_certification": exact_checks,
                    "enumeration_invariance": enumeration_invariant,
                },
            }
        )

    positive_levels = [
        level for level in levels if level["classification"] == "positive_signal"
    ]
    first_positive = (
        positive_levels[0]["unit_cost"] if positive_levels else "none_in_grid"
    )

    cfr_unit = float(preregistration["solver"]["cfr_cross_check_unit_cost"])
    cfr_game = build_game(preregistration, cfr_unit)
    cfr_gate = float(preregistration["solver"]["cfr_maximum_exploitability"])
    iterations = int(preregistration["solver"]["cfr_iterations"])
    evaluator = FullTreeBestResponseEvaluator(
        cfr_game,
        evaluator_id="guess_who_private_cost_dose_response_cfr_v2",
        maximum_histories=100_000,
    )
    algorithms = {}
    for algorithm_id in preregistration["solver"]["cfr_cross_check_algorithms"]:
        result = create_regret_minimization_trainer(
            cfr_game, algorithm_id
        ).train(iterations)
        report = run_independent_evaluation(
            evaluator, result.policy, maximum_exploitability=cfr_gate
        )
        algorithms[algorithm_id] = {
            "algorithm": result.algorithm.to_artifact(),
            "iterations": iterations,
            "independent_evaluation": compact_evaluation(report),
        }
    negative_iterations = int(
        preregistration["solver"]["undertrained_negative_control_iterations"]
    )
    negative_result = create_regret_minimization_trainer(
        cfr_game, "vanilla_cfr"
    ).train(negative_iterations)
    negative = run_independent_evaluation(
        evaluator, negative_result.policy, maximum_exploitability=cfr_gate
    )

    artifact = {
        "experiment_id": preregistration["experiment_id"],
        "preregistration": str(args.preregistration.relative_to(ROOT)),
        "frozen_rules": frozen_rules,
        "target": preregistration["target"],
        "private_question_cost_shape": preregistration[
            "private_question_cost_shape"
        ],
        "primary_endpoint": {
            "name": endpoint["name"],
            "positive_signal_threshold": endpoint["positive_signal_threshold"],
            "null_result_threshold": endpoint["null_result_threshold"],
            "smallest_preregistered_unit_cost_with_positive_signal": first_positive,
            "scope_warning": "canonical and reversed LP solutions do not enumerate every equilibrium when the equilibrium set is nonunique",
        },
        "dose_response": levels,
        "regret_minimization_cross_check": {
            "unit_cost": cfr_unit,
            "algorithms": algorithms,
        },
        "undertrained_negative_control": {
            "unit_cost": cfr_unit,
            "iterations": negative_iterations,
            "exploitability": negative.exploitability,
            "passed_gate": negative.passed,
        },
        "runtime_epsilon_gto_allowed": False,
    }
    artifact["checks"] = {
        "frozen_rules_match": frozen_rules
        == PrivateCostStrategicGuessWhoGame.rules_contract(),
        "all_doses_exactly_certified": all_exact_checks,
        "all_doses_enumeration_invariant": all_enumeration_checks,
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
