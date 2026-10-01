"""Exact and regret-minimization cross-check for the tiny adaptive duel."""

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
    AdaptiveGuessWhoGame,
    DEFAULT_QUESTIONS,
    DEFAULT_ROSTER,
)


CHECKPOINTS = (100, 1_000, 10_000)


def _secret_marginals(policy, player, roster):
    distribution = policy[(player, "select_secret")]
    return {character.name: distribution[index] for index, character in enumerate(roster)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output", type=Path,
        default=Path("research/results/adaptive_guess_who_audit_2026-10-01.json"),
    )
    args = parser.parse_args()
    roster = (DEFAULT_ROSTER[0], DEFAULT_ROSTER[6], DEFAULT_ROSTER[12])
    questions = DEFAULT_QUESTIONS[:3]
    game = AdaptiveGuessWhoGame(roster, questions)
    form = compile_sequence_form(
        game, game_properties=CFRGameProperties(2, True, True, True)
    )
    exact = solve_sequence_form(form)
    evaluator = FullTreeBestResponseEvaluator(
        game, evaluator_id="adaptive_guess_who_v1"
    )
    exact_report = run_independent_evaluation(
        evaluator, exact.policy, maximum_exploitability=1e-10
    )
    four_roster = tuple(DEFAULT_ROSTER[index * 6] for index in range(4))
    four_game = AdaptiveGuessWhoGame(four_roster, DEFAULT_QUESTIONS[:4])
    four_form = compile_sequence_form(
        four_game,
        game_properties=CFRGameProperties(2, True, True, True),
        maximum_histories=10_000,
        sparse=True,
    )
    four_exact = solve_sequence_form(four_form, backend="scipy_highs")
    four_report = run_independent_evaluation(
        FullTreeBestResponseEvaluator(
            four_game,
            evaluator_id="adaptive_guess_who_four_character_v1",
            maximum_histories=10_000,
        ),
        four_exact.policy,
        maximum_exploitability=1e-10,
    )
    algorithms = {}
    for algorithm_id in ("vanilla_cfr", "cfr_plus", "dcfr"):
        trainer = create_regret_minimization_trainer(game, algorithm_id)
        previous = 0
        trace = []
        for checkpoint in CHECKPOINTS:
            result = trainer.train(checkpoint - previous)
            evaluation = run_independent_evaluation(
                evaluator, result.policy, maximum_exploitability=1.0
            )
            trace.append({
                "iteration": checkpoint,
                "expected_value_to_player_0": evaluation.expected_value_to_player_0,
                "nash_conv": evaluation.nash_conv,
                "exploitability": evaluation.exploitability,
            })
            previous = checkpoint
        algorithms[algorithm_id] = {
            "algorithm": result.algorithm.to_artifact(),
            "information_sets": len(result.policy),
            "trace": trace,
            "final_passes_cross_check_gate": trace[-1]["exploitability"] < 0.001,
        }
    undertrained = create_regret_minimization_trainer(game, "vanilla_cfr").train(10)
    negative = run_independent_evaluation(
        evaluator, undertrained.policy, maximum_exploitability=0.001
    )
    artifact = {
        "model": "three-character adaptive simultaneous-round Guess Who duel",
        "scope": "research subgame only; no runtime epsilon-GTO label",
        "solver_router": "sequence_form_lp_primary_regret_minimization_cross_check",
        "characters": [character.name for character in roster],
        "questions": [question.id for question in questions],
        "tree_audit": form.audit.to_artifact(),
        "sequence_form": {
            "player_0_sequences": len(form.player_sequences[0]),
            "player_1_sequences": len(form.player_sequences[1]),
            "player_0_information_sets": len(form.information_sets[0]),
            "player_1_information_sets": len(form.information_sets[1]),
            "value_to_player_0": exact.value_to_player_0,
            "maximum_flow_residual": exact.maximum_flow_residual,
            "primal_dual_gap": exact.primal_dual_gap,
            "backend": exact.backend,
            "independent_evaluation": exact_report.to_artifact(),
            "player_0_secret_marginals": _secret_marginals(exact.policy, 0, roster),
            "player_1_secret_marginals": _secret_marginals(exact.policy, 1, roster),
        },
        "regret_minimization_cross_check": algorithms,
        "four_character_scaling_probe": {
            "dependency": "optional scipy>=1.13,<2 using HiGHS",
            "tree_audit": four_form.audit.to_artifact(),
            "player_0_sequences": len(four_form.player_sequences[0]),
            "player_1_sequences": len(four_form.player_sequences[1]),
            "payoff_shape": list(four_form.payoff_matrix.shape),
            "payoff_nonzeros": len(four_form.payoff_matrix.entries),
            "backend": four_exact.backend,
            "value_to_player_0": four_exact.value_to_player_0,
            "independent_evaluation": four_report.to_artifact(),
            "runtime_epsilon_gto_allowed": False,
        },
        "undertrained_negative_control": {
            "iterations": 10,
            "exploitability": negative.exploitability,
            "passed_gate": negative.passed,
        },
    }
    artifact["checks"] = {
        "tree_audit": form.audit.passed,
        "exact_independent_gate": exact_report.passed,
        "four_character_exact_independent_gate": four_report.passed,
        "zero_symmetric_value": abs(exact.value_to_player_0) < 1e-10,
        "all_cfr_cross_checks": all(
            value["final_passes_cross_check_gate"] for value in algorithms.values()
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
