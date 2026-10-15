"""Run the frozen bounded confirmation for observation stratification."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from aip.core import run_independent_evaluation, strategy_profile_fingerprint
from aip.puzzles.liars_dice import (
    CoverageAwareJointStratifiedFiveDieTrainer,
    FiveDieStepwiseIndependentEvaluator,
    ObservationStratifiedFiveDieTrainer,
    required_five_die_information_sets,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PLAN = (
    ROOT
    / "configs/five_die_observation_stratification_confirmation_2026-10-15.json"
)
DEFAULT_OUTPUT = (
    ROOT
    / "research/results/five_die_observation_stratification_confirmation_2026-10-15.json"
)


def _compact(report) -> dict[str, object]:
    artifact = report.to_artifact()
    artifact.pop("action_values")
    artifact["action_value_information_sets"] = len(report.action_values)
    return artifact


def _metrics(result, required: int) -> dict[str, object]:
    positive = sum(
        weight > 0
        for weight in result.average_strategy_observation_weight.values()
    )
    fallback = {
        key
        for key, used in result.average_strategy_fallback_used.items()
        if used
    }
    zero_weight = {
        key
        for key, weight in result.average_strategy_observation_weight.items()
        if weight <= 0
    }
    normalized = len(result.policy) == required and all(
        distribution and abs(sum(distribution.values()) - 1.0) <= 1e-9
        for distribution in result.policy.values()
    )
    return {
        "positive_observation_weight_information_sets": positive,
        "raw_observation_weight_coverage": positive / required,
        "fallback_information_sets": len(fallback),
        "fallback_fraction": len(fallback) / required,
        "fallback_exactly_equals_zero_weight_set": fallback == zero_weight,
        "normalized_complete_policy": normalized,
        "profile_fingerprint": strategy_profile_fingerprint(result.policy),
    }


def _evaluate(result, threshold: float):
    return run_independent_evaluation(
        FiveDieStepwiseIndependentEvaluator(),
        result.policy,
        maximum_exploitability=threshold,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preregistration", type=Path, default=DEFAULT_PLAN)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    plan = json.loads(args.preregistration.read_text(encoding="utf-8"))
    if plan["status"] != "frozen_before_confirmation":
        raise ValueError("bounded confirmation was not frozen")
    pilot = json.loads((ROOT / plan["pilot_artifact"]).read_text(encoding="utf-8"))
    replicas = int(plan["selected_observation_replicas"])
    if replicas != int(pilot["selected_observation_replicas"]):
        raise ValueError("confirmation dose differs from frozen pilot selection")

    seed = int(plan["seed"])
    iterations = int(plan["iterations"])
    required = len(required_five_die_information_sets())
    baseline = CoverageAwareJointStratifiedFiveDieTrainer(seed=seed).train(iterations)
    candidate = ObservationStratifiedFiveDieTrainer(
        seed=seed, observation_replicas=replicas
    ).train(iterations)
    repeated = ObservationStratifiedFiveDieTrainer(
        seed=seed, observation_replicas=replicas
    ).train(iterations)
    baseline_metrics = _metrics(baseline, required)
    candidate_metrics = _metrics(candidate, required)
    threshold = float(plan["gates"]["maximum_absolute_independent_exploitability"])
    baseline_evaluation = _evaluate(baseline, threshold)
    candidate_evaluation = _evaluate(candidate, threshold)
    coverage_gain = (
        candidate_metrics["raw_observation_weight_coverage"]
        - baseline_metrics["raw_observation_weight_coverage"]
    )
    exploitability_increase = (
        candidate_evaluation.exploitability - baseline_evaluation.exploitability
    )
    frozen = plan["gates"]
    gates = {
        "observation_coverage_gain": coverage_gain
        >= float(frozen["minimum_absolute_observation_coverage_gain_vs_paired_baseline"]),
        "candidate_observation_coverage": candidate_metrics[
            "raw_observation_weight_coverage"
        ]
        >= float(frozen["minimum_candidate_raw_observation_weight_coverage"]),
        "candidate_fallback_fraction": candidate_metrics["fallback_fraction"]
        <= float(frozen["maximum_candidate_fallback_fraction"]),
        "exploitability_noninferiority": exploitability_increase
        <= float(frozen["maximum_exploitability_increase_vs_paired_baseline"]),
        "absolute_independent_exploitability": candidate_evaluation.exploitability
        <= threshold,
        "regret_trace_parity": candidate.average_positive_regret
        == baseline.average_positive_regret,
        "visit_trace_parity": candidate.information_set_visits
        == baseline.information_set_visits,
        "fallback_exactly_equals_zero_weight_set": candidate_metrics[
            "fallback_exactly_equals_zero_weight_set"
        ],
        "normalized_complete_policy": candidate_metrics[
            "normalized_complete_policy"
        ],
        "fixed_seed_reproducibility": candidate.policy == repeated.policy,
    }
    passed = all(gates.values())
    artifact = {
        "experiment_id": plan["experiment_id"],
        "preregistration": str(args.preregistration.relative_to(ROOT)),
        "pilot_artifact": plan["pilot_artifact"],
        "seed": seed,
        "iterations": iterations,
        "observation_replicas": replicas,
        "baseline": {
            "algorithm": baseline.algorithm.to_artifact(),
            "metrics": baseline_metrics,
            "independent_evaluation": _compact(baseline_evaluation),
        },
        "candidate": {
            "algorithm": candidate.algorithm.to_artifact(),
            "metrics": candidate_metrics,
            "independent_evaluation": _compact(candidate_evaluation),
        },
        "paired_observation_coverage_gain": coverage_gain,
        "paired_exploitability_increase": exploitability_increase,
        "gates": gates,
        "bounded_confirmation_passed": passed,
        "full_budget_preregistration_allowed": passed,
        "full_budget_training_performed": False,
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
