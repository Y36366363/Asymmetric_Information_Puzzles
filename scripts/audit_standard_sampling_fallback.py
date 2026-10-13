"""Run the frozen multiseed confirmation for the standard-sampling fallback."""

from __future__ import annotations

import argparse
from statistics import fmean
import json
from pathlib import Path

from aip.core import (
    CoverageAwareExternalSamplingCFRTrainer,
    ExternalSamplingCFRTrainer,
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
    ROOT / "configs/standard_sampling_fallback_confirmation_2026-10-13.json"
)
DEFAULT_OUTPUT = (
    ROOT / "research/results/standard_sampling_fallback_confirmation_2026-10-13.json"
)


def _initialize_one_die(trainer) -> None:
    for player, information_set in sorted(required_one_die_information_sets(), key=repr):
        own_die, bids = information_set
        dice = (own_die, 1) if player == 0 else (1, own_die)
        actions = trainer.game.legal_actions(OneDieLiarState(dice, bids))
        trainer.initialize_information_set(player, information_set, actions)


def _normalized_complete(result, required: int) -> bool:
    return len(result.policy) == required and all(
        distribution
        and all(probability >= 0 for probability in distribution.values())
        and abs(sum(distribution.values()) - 1.0) <= 1e-9
        for distribution in result.policy.values()
    )


def _compact_independent(report) -> dict[str, object]:
    artifact = report.to_artifact()
    artifact.pop("action_values")
    artifact["action_value_information_sets"] = len(report.action_values)
    return artifact


def _run_seed(game_factory, evaluator, plan, seed: int, initialize=None):
    iterations = int(plan["iterations_per_seed"])
    candidate_trainer = CoverageAwareExternalSamplingCFRTrainer(
        game_factory(), seed=seed
    )
    legacy_trainer = ExternalSamplingCFRTrainer(game_factory(), seed=seed)
    if initialize:
        initialize(candidate_trainer)
        initialize(legacy_trainer)
    candidate = candidate_trainer.train(iterations)
    legacy = legacy_trainer.train(iterations)
    candidate_evaluation = evaluator(candidate)
    legacy_evaluation = evaluator(legacy)
    keys = set(candidate.policy)
    fallback = {
        key
        for key, used in candidate.average_strategy_fallback_used.items()
        if used
    }
    zero_weight = {
        key
        for key, weight in candidate.average_strategy_observation_weight.items()
        if weight <= 0
    }
    changed = {
        key for key in keys if candidate.policy[key] != legacy.policy[key]
    }
    trace_parity = (
        candidate.information_set_visits == legacy.information_set_visits
        and candidate.average_positive_regret == legacy.average_positive_regret
        and candidate.average_strategy_observations
        == legacy.average_strategy_observations
        and candidate.average_strategy_observation_weight
        == legacy.average_strategy_observation_weight
    )
    candidate_exploitability = candidate_evaluation["exploitability"]
    legacy_exploitability = legacy_evaluation["exploitability"]
    return {
        "seed": seed,
        "iterations": iterations,
        "candidate_algorithm": candidate.algorithm.to_artifact(),
        "legacy_algorithm": legacy.algorithm.to_artifact(),
        "candidate_evaluation": candidate_evaluation,
        "legacy_evaluation": legacy_evaluation,
        "paired_exploitability_difference": (
            candidate_exploitability - legacy_exploitability
        ),
        "diagnostics": {
            "information_sets": len(keys),
            "fallback_information_sets": len(fallback),
            "fallback_fraction": len(fallback) / len(keys),
            "raw_observation_weight_coverage": 1 - len(zero_weight) / len(keys),
            "resolved_policy_coverage": len(candidate.policy) / len(keys),
            "fallback_exactly_equals_zero_weight_set": fallback == zero_weight,
            "policy_changes_confined_to_fallback_set": changed <= fallback,
            "trace_parity_with_paired_legacy": trace_parity,
            "normalized_complete_policy": _normalized_complete(
                candidate, int(plan["required_information_sets"])
            ),
            "candidate_profile_fingerprint": strategy_profile_fingerprint(
                candidate.policy
            ),
        },
    }


def _confirm_game(game_factory, evaluator, plan, seeds, initialize=None):
    runs = [
        _run_seed(game_factory, evaluator, plan, seed, initialize)
        for seed in seeds
    ]
    candidate_values = [
        run["candidate_evaluation"]["exploitability"] for run in runs
    ]
    legacy_values = [run["legacy_evaluation"]["exploitability"] for run in runs]
    differences = [run["paired_exploitability_difference"] for run in runs]

    first_seed = seeds[0]
    repeat_trainer = CoverageAwareExternalSamplingCFRTrainer(
        game_factory(), seed=first_seed
    )
    if initialize:
        initialize(repeat_trainer)
    repeated = repeat_trainer.train(int(plan["iterations_per_seed"]))
    first_policy_reproduced = strategy_profile_fingerprint(repeated.policy) == (
        runs[0]["diagnostics"]["candidate_profile_fingerprint"]
    )

    per_run_diagnostics_pass = all(
        run["diagnostics"]["fallback_exactly_equals_zero_weight_set"]
        and run["diagnostics"]["policy_changes_confined_to_fallback_set"]
        and run["diagnostics"]["trace_parity_with_paired_legacy"]
        and run["diagnostics"]["normalized_complete_policy"]
        and run["diagnostics"]["resolved_policy_coverage"] == 1
        and run["diagnostics"]["fallback_fraction"]
        <= float(plan["maximum_fallback_fraction"])
        for run in runs
    )
    gates = {
        "five_confirmation_seeds": len(runs) == 5,
        "fixed_seed_exact_reproduction": first_policy_reproduced,
        "all_structural_and_trace_gates": per_run_diagnostics_pass,
        "absolute_exploitability_each_seed": max(candidate_values)
        <= float(plan["maximum_independent_exploitability_each_seed"]),
        "paired_mean_noninferiority": fmean(differences)
        <= float(plan["maximum_mean_exploitability_increase_vs_paired_legacy"]),
        "single_seed_noninferiority": max(differences)
        <= float(plan["maximum_single_seed_exploitability_increase_vs_paired_legacy"]),
    }
    return {
        "runs": runs,
        "summary": {
            "candidate_mean_exploitability": fmean(candidate_values),
            "legacy_mean_exploitability": fmean(legacy_values),
            "mean_paired_exploitability_difference": fmean(differences),
            "maximum_paired_exploitability_difference": max(differences),
            "maximum_candidate_exploitability": max(candidate_values),
        },
        "gates": gates,
        "passed": all(gates.values()),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preregistration", type=Path, default=DEFAULT_PREREGISTRATION)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    plan = json.loads(args.preregistration.read_text(encoding="utf-8"))
    if not plan["frozen_before_confirmation"]:
        raise ValueError("confirmation must be frozen before execution")
    seeds = [int(seed) for seed in plan["confirmation_seeds"]]
    if set(seeds) & set(plan["pilot_seeds_must_be_excluded"]):
        raise ValueError("confirmation seeds overlap exploratory pilot seeds")

    kuhn_evaluator = lambda result: evaluate_kuhn_cfr(result).to_report()

    def one_die_evaluator(result):
        report = run_independent_evaluation(
            OneDieLiarIndependentEvaluator(),
            result.policy,
            maximum_exploitability=float(
                plan["games"]["one_die_stepwise_liars_dice"][
                    "maximum_independent_exploitability_each_seed"
                ]
            ),
        )
        return _compact_independent(report)

    games = {
        "canonical_kuhn_poker": _confirm_game(
            KuhnCFRGame,
            kuhn_evaluator,
            plan["games"]["canonical_kuhn_poker"],
            seeds,
        ),
        "one_die_stepwise_liars_dice": _confirm_game(
            OneDieLiarDiceCFRGame,
            one_die_evaluator,
            plan["games"]["one_die_stepwise_liars_dice"],
            seeds,
            _initialize_one_die,
        ),
    }
    passed = all(game["passed"] for game in games.values())
    artifact = {
        "experiment_id": plan["experiment_id"],
        "preregistration": str(args.preregistration.relative_to(ROOT)),
        "exploratory_pilot": plan["exploratory_pilot"],
        "confirmation_seeds": seeds,
        "games": games,
        "all_small_game_gates_passed": passed,
        "five_die_preregistration_allowed": passed,
        "five_die_training_performed": False,
        "runtime_epsilon_gto_enabled": False,
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
