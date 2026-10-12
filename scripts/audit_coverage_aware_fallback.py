"""Audit a preregistered zero-weight average-strategy fallback on small games."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from aip.core import (
    CoverageAwareReachWeightedExternalSamplingCFRTrainer,
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
    ROOT / "configs/coverage_aware_average_strategy_fallback_validation_2026-10-12.json"
)
DEFAULT_OUTPUT = (
    ROOT
    / "research/results/coverage_aware_average_strategy_fallback_validation_2026-10-12.json"
)


def _initialize_one_die(trainer) -> None:
    game = trainer.game
    for player, information_set in sorted(required_one_die_information_sets(), key=repr):
        own_die, bids = information_set
        dice = (own_die, 1) if player == 0 else (1, own_die)
        actions = game.legal_actions(OneDieLiarState(dice, bids))
        trainer.initialize_information_set(player, information_set, actions)


def _normalized_complete(result, required: int) -> bool:
    return len(result.policy) == required and all(
        distribution
        and all(probability >= 0 for probability in distribution.values())
        and abs(sum(distribution.values()) - 1.0) <= 1e-9
        for distribution in result.policy.values()
    )


def _same_trace(candidate, reach_weighted) -> dict[str, bool]:
    return {
        "regret": (
            candidate.average_positive_regret
            == reach_weighted.average_positive_regret
        ),
        "visits": candidate.information_set_visits == reach_weighted.information_set_visits,
        "observation_counts": (
            candidate.average_strategy_observations
            == reach_weighted.average_strategy_observations
        ),
        "observation_weights": (
            candidate.average_strategy_observation_weight
            == reach_weighted.average_strategy_observation_weight
        ),
    }


def _diagnostics(candidate, reach_weighted) -> dict[str, object]:
    keys = set(candidate.policy)
    positive_count = {
        key
        for key, count in candidate.average_strategy_observations.items()
        if count > 0
    }
    positive_weight = {
        key
        for key, weight in candidate.average_strategy_observation_weight.items()
        if weight > 0
    }
    zero_weight = keys - positive_weight
    fallback = {
        key
        for key, used in candidate.average_strategy_fallback_used.items()
        if used
    }
    changed = {
        key
        for key in keys
        if candidate.policy[key] != reach_weighted.policy[key]
    }
    trace = _same_trace(candidate, reach_weighted)
    return {
        "information_sets": len(keys),
        "positive_observation_count_information_sets": len(positive_count),
        "raw_observation_count_coverage": len(positive_count) / len(keys),
        "positive_observation_weight_information_sets": len(positive_weight),
        "raw_observation_weight_coverage": len(positive_weight) / len(keys),
        "zero_observation_weight_information_sets": len(zero_weight),
        "fallback_information_sets": len(fallback),
        "fallback_fraction": len(fallback) / len(keys),
        "resolved_policy_coverage": len(candidate.policy) / len(keys),
        "fallback_exactly_equals_zero_weight_set": fallback == zero_weight,
        "policy_changes_confined_to_fallback_set": changed <= fallback,
        "changed_policy_information_sets": len(changed),
        # A node can be traversed with zero own reach, so a zero-weight fallback
        # may legitimately have a positive observation count.  The fallback
        # creates no evidence iff both evidence maps remain identical to the
        # otherwise-equivalent reach-weighted run.
        "fallback_creates_no_observation_evidence": (
            trace["observation_counts"] and trace["observation_weights"]
        ),
        "trace_parity_with_reach_weighted": trace,
        "candidate_profile_fingerprint": strategy_profile_fingerprint(candidate.policy),
        "reach_weighted_profile_fingerprint": strategy_profile_fingerprint(
            reach_weighted.policy
        ),
    }


def _train(game_factory, seed: int, iterations: int, *, initialize=None):
    trainers = {
        "candidate": CoverageAwareReachWeightedExternalSamplingCFRTrainer(
            game_factory(), seed=seed
        ),
        "repeat": CoverageAwareReachWeightedExternalSamplingCFRTrainer(
            game_factory(), seed=seed
        ),
        "reach_weighted": ReachWeightedExternalSamplingCFRTrainer(
            game_factory(), seed=seed
        ),
        "legacy": ExternalSamplingCFRTrainer(game_factory(), seed=seed),
    }
    if initialize is not None:
        for trainer in trainers.values():
            initialize(trainer)
    return {name: trainer.train(iterations) for name, trainer in trainers.items()}


def _gates(plan, results, evaluations) -> tuple[dict[str, bool], dict[str, object]]:
    candidate = results["candidate"]
    reach_weighted = results["reach_weighted"]
    legacy = results["legacy"]
    diagnostics = _diagnostics(candidate, reach_weighted)
    trace = diagnostics["trace_parity_with_reach_weighted"]
    gates = {
        "fixed_seed_reproducibility": candidate.policy == results["repeat"].policy,
        "regret_visit_and_observation_trace_parity": all(trace.values()),
        "normalized_complete_policy": _normalized_complete(
            candidate, int(plan["required_information_sets"])
        ),
        "resolved_policy_coverage": diagnostics["resolved_policy_coverage"] == 1,
        "fallback_exactly_equals_zero_weight_set": diagnostics[
            "fallback_exactly_equals_zero_weight_set"
        ],
        "fallback_creates_no_observation_evidence": diagnostics[
            "fallback_creates_no_observation_evidence"
        ],
        "policy_changes_confined_to_fallback_set": diagnostics[
            "policy_changes_confined_to_fallback_set"
        ],
        "fallback_fraction": diagnostics["fallback_fraction"]
        <= float(plan["maximum_fallback_fraction"]),
        "independent_exploitability": evaluations["candidate"].exploitability
        <= float(plan["maximum_independent_exploitability"]),
        "not_materially_worse_than_reach_weighted": (
            evaluations["candidate"].exploitability
            <= evaluations["reach_weighted"].exploitability
            + float(plan["maximum_exploitability_increase_vs_reach_weighted"])
        ),
        "not_materially_worse_than_legacy": (
            evaluations["candidate"].exploitability
            <= evaluations["legacy"].exploitability
            + float(plan["maximum_exploitability_increase_vs_legacy"])
        ),
    }
    return gates, diagnostics


def _compact(report) -> dict[str, object]:
    artifact = report.to_artifact()
    artifact.pop("action_values")
    artifact["action_value_information_sets"] = len(report.action_values)
    return artifact


def _kuhn(plan: dict) -> dict[str, object]:
    seed, iterations = int(plan["seed"]), int(plan["iterations"])
    results = _train(KuhnCFRGame, seed, iterations)
    evaluations = {name: evaluate_kuhn_cfr(result) for name, result in results.items()}
    gates, diagnostics = _gates(plan, results, evaluations)
    return {
        "seed": seed,
        "iterations": iterations,
        "algorithms": {name: value.algorithm.to_artifact() for name, value in results.items()},
        "diagnostics": diagnostics,
        "evaluations": {name: value.to_report() for name, value in evaluations.items()},
        "gates": gates,
        "passed": all(gates.values()),
    }


def _one_die(plan: dict) -> dict[str, object]:
    seed, iterations = int(plan["seed"]), int(plan["iterations"])
    results = _train(
        OneDieLiarDiceCFRGame, seed, iterations, initialize=_initialize_one_die
    )
    threshold = float(plan["maximum_independent_exploitability"])
    evaluations = {
        name: run_independent_evaluation(
            OneDieLiarIndependentEvaluator(),
            result.policy,
            maximum_exploitability=threshold,
        )
        for name, result in results.items()
    }
    gates, diagnostics = _gates(plan, results, evaluations)
    return {
        "seed": seed,
        "iterations": iterations,
        "explicit_zero_regret_initialization": True,
        "algorithms": {name: value.algorithm.to_artifact() for name, value in results.items()},
        "diagnostics": diagnostics,
        "evaluations": {name: _compact(value) for name, value in evaluations.items()},
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
        raise ValueError("fallback validation must be frozen before training")
    retained = json.loads((ROOT / plan["retained_failed_experiment"]).read_text())
    if retained["passed"] is not False:
        raise ValueError("the preregistered failed experiment was not retained")

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
        "retained_failed_experiment": plan["retained_failed_experiment"],
        "retained_failure_unchanged": True,
        "games": games,
        "all_small_game_gates_passed": passed,
        "five_die_preregistration_allowed": passed,
        "five_die_preregistration_created": False,
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
