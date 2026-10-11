"""Validate reach-weighted average-strategy estimation on exact small games."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from aip.core import (
    ExternalSamplingCFRTrainer,
    ReachWeightedExternalSamplingCFRTrainer,
    run_independent_evaluation,
    strategy_profile_fingerprint,
)
from aip.puzzles.kuhn_poker import KuhnCFRGame, evaluate_kuhn_cfr
from aip.puzzles.liars_dice import (
    OneDieLiarDiceCFRGame,
    OneDieLiarIndependentEvaluator,
    OneDieLiarState,
    required_one_die_information_sets,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PREREGISTRATION = (
    ROOT / "configs/average_strategy_estimator_validation_2026-10-11.json"
)
DEFAULT_OUTPUT = (
    ROOT / "research/results/average_strategy_estimator_validation_2026-10-11.json"
)


def _initialize_one_die(trainer) -> None:
    game = trainer.game
    for player, information_set in sorted(
        required_one_die_information_sets(), key=repr
    ):
        own_die, bids = information_set
        dice = (own_die, 1) if player == 0 else (1, own_die)
        actions = game.legal_actions(OneDieLiarState(dice, bids))
        trainer.initialize_information_set(player, information_set, actions)


def _coverage(result) -> tuple[int, float]:
    observed = sum(
        weight > 0
        for weight in result.average_strategy_observation_weight.values()
    )
    return observed, observed / len(result.policy)


def _normalized_complete(result, required: int) -> bool:
    return len(result.policy) == required and all(
        distribution
        and all(probability >= 0 for probability in distribution.values())
        and abs(sum(distribution.values()) - 1.0) <= 1e-9
        for distribution in result.policy.values()
    )


def _common_diagnostics(candidate, comparison) -> dict[str, object]:
    positive_weight, weight_coverage = _coverage(candidate)
    positive_count = sum(
        count > 0 for count in candidate.average_strategy_observations.values()
    )
    return {
        "information_sets": len(candidate.policy),
        "positive_observation_count_information_sets": positive_count,
        "average_strategy_observation_count_coverage": (
            positive_count / len(candidate.policy)
        ),
        "positive_observation_weight_information_sets": positive_weight,
        "average_strategy_observation_weight_coverage": weight_coverage,
        "total_average_strategy_observations": sum(
            candidate.average_strategy_observations.values()
        ),
        "total_average_strategy_observation_weight": sum(
            candidate.average_strategy_observation_weight.values()
        ),
        "regret_trace_parity_with_comparison": (
            candidate.average_positive_regret == comparison.average_positive_regret
        ),
        "visit_trace_parity_with_comparison": (
            candidate.information_set_visits == comparison.information_set_visits
        ),
        "candidate_profile_fingerprint": strategy_profile_fingerprint(
            candidate.policy
        ),
        "comparison_profile_fingerprint": strategy_profile_fingerprint(
            comparison.policy
        ),
    }


def _kuhn(plan: dict) -> dict[str, object]:
    seed = int(plan["seed"])
    iterations = int(plan["iterations"])
    candidate = ReachWeightedExternalSamplingCFRTrainer(
        KuhnCFRGame(), seed=seed
    ).train(iterations)
    repeated = ReachWeightedExternalSamplingCFRTrainer(
        KuhnCFRGame(), seed=seed
    ).train(iterations)
    comparison = ExternalSamplingCFRTrainer(
        KuhnCFRGame(), seed=seed
    ).train(iterations)
    candidate_evaluation = evaluate_kuhn_cfr(candidate)
    comparison_evaluation = evaluate_kuhn_cfr(comparison)
    diagnostics = _common_diagnostics(candidate, comparison)
    gates = {
        "fixed_seed_reproducible": candidate.policy == repeated.policy,
        "regret_trace_parity": diagnostics["regret_trace_parity_with_comparison"],
        "visit_trace_parity": diagnostics["visit_trace_parity_with_comparison"],
        "normalized_complete_policy": _normalized_complete(
            candidate, int(plan["required_information_sets"])
        ),
        "observation_coverage": diagnostics[
            "average_strategy_observation_weight_coverage"
        ]
        >= float(plan["minimum_average_strategy_observation_coverage"]),
        "independent_exploitability": (
            candidate_evaluation.exploitability
            <= float(plan["maximum_independent_exploitability"])
        ),
        "not_materially_worse_than_comparison": (
            candidate_evaluation.exploitability
            <= comparison_evaluation.exploitability
            + float(plan["maximum_exploitability_increase_vs_comparison"])
        ),
    }
    return {
        "seed": seed,
        "iterations": iterations,
        "candidate_algorithm": candidate.algorithm.to_artifact(),
        "comparison_algorithm": comparison.algorithm.to_artifact(),
        "diagnostics": diagnostics,
        "candidate_evaluation": candidate_evaluation.to_report(),
        "comparison_evaluation": comparison_evaluation.to_report(),
        "gates": gates,
        "passed": all(gates.values()),
    }


def _compact_independent(report) -> dict[str, object]:
    artifact = report.to_artifact()
    artifact.pop("action_values")
    artifact["action_value_information_sets"] = len(report.action_values)
    return artifact


def _one_die(plan: dict) -> dict[str, object]:
    seed = int(plan["seed"])
    iterations = int(plan["iterations"])
    candidate_trainer = ReachWeightedExternalSamplingCFRTrainer(
        OneDieLiarDiceCFRGame(), seed=seed
    )
    repeated_trainer = ReachWeightedExternalSamplingCFRTrainer(
        OneDieLiarDiceCFRGame(), seed=seed
    )
    comparison_trainer = ExternalSamplingCFRTrainer(
        OneDieLiarDiceCFRGame(), seed=seed
    )
    for trainer in (candidate_trainer, repeated_trainer, comparison_trainer):
        _initialize_one_die(trainer)
    candidate = candidate_trainer.train(iterations)
    repeated = repeated_trainer.train(iterations)
    comparison = comparison_trainer.train(iterations)
    threshold = float(plan["maximum_independent_exploitability"])
    candidate_evaluation = run_independent_evaluation(
        OneDieLiarIndependentEvaluator(),
        candidate.policy,
        maximum_exploitability=threshold,
    )
    comparison_evaluation = run_independent_evaluation(
        OneDieLiarIndependentEvaluator(),
        comparison.policy,
        maximum_exploitability=threshold,
    )
    diagnostics = _common_diagnostics(candidate, comparison)
    gates = {
        "fixed_seed_reproducible": candidate.policy == repeated.policy,
        "regret_trace_parity": diagnostics["regret_trace_parity_with_comparison"],
        "visit_trace_parity": diagnostics["visit_trace_parity_with_comparison"],
        "normalized_complete_policy": _normalized_complete(
            candidate, int(plan["required_information_sets"])
        ),
        "observation_coverage": diagnostics[
            "average_strategy_observation_weight_coverage"
        ]
        >= float(plan["minimum_average_strategy_observation_coverage"]),
        "independent_exploitability": candidate_evaluation.passed,
        "not_materially_worse_than_comparison": (
            candidate_evaluation.exploitability
            <= comparison_evaluation.exploitability
            + float(plan["maximum_exploitability_increase_vs_comparison"])
        ),
    }
    return {
        "seed": seed,
        "iterations": iterations,
        "explicit_zero_regret_initialization": True,
        "candidate_algorithm": candidate.algorithm.to_artifact(),
        "comparison_algorithm": comparison.algorithm.to_artifact(),
        "diagnostics": diagnostics,
        "candidate_evaluation": _compact_independent(candidate_evaluation),
        "comparison_evaluation": _compact_independent(comparison_evaluation),
        "gates": gates,
        "passed": all(gates.values()),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preregistration", type=Path, default=DEFAULT_PREREGISTRATION)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    plan = json.loads(args.preregistration.read_text(encoding="utf-8"))
    if not plan["frozen_before_training"]:
        raise ValueError("estimator validation must be frozen before training")

    games = {
        "canonical_kuhn_poker": _kuhn(plan["games"]["canonical_kuhn_poker"]),
        "one_die_stepwise_liars_dice": _one_die(
            plan["games"]["one_die_stepwise_liars_dice"]
        ),
    }
    passed = all(game["passed"] for game in games.values())
    artifact = {
        "experiment_id": plan["experiment_id"],
        "preregistration": str(args.preregistration.relative_to(ROOT)),
        "games": games,
        "all_small_game_gates_passed": passed,
        "five_die_preregistration_allowed": passed,
        "five_die_training_performed": False,
        "audit_completed": True,
        "passed": passed,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(artifact, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
