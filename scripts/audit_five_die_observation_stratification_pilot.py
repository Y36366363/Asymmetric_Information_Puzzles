"""Run the frozen observation-stratification dose pilot."""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
from time import perf_counter

from aip.core import run_independent_evaluation
from aip.puzzles.liars_dice import (
    ORDERED_DICE_HISTOGRAMS,
    CoverageAwareJointStratifiedFiveDieTrainer,
    FiveDieStepwiseIndependentEvaluator,
    ObservationStratifiedFiveDieTrainer,
    ObservationStratifiedJointTraversal,
    required_five_die_information_sets,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PLAN = (
    ROOT / "configs/five_die_observation_stratification_pilot_2026-10-15.json"
)
DEFAULT_OUTPUT = (
    ROOT / "research/results/five_die_observation_stratification_pilot_2026-10-15.json"
)


def _compact(report) -> dict[str, object]:
    artifact = report.to_artifact()
    artifact.pop("action_values")
    artifact["action_value_information_sets"] = len(report.action_values)
    return artifact


def _normalized(policy) -> bool:
    return all(
        distribution
        and all(probability >= 0 for probability in distribution.values())
        and abs(sum(distribution.values()) - 1.0) <= 1e-9
        for distribution in policy.values()
    )


def _schedule_valid(seed: int, replicas: int) -> bool:
    expected = Counter(ORDERED_DICE_HISTOGRAMS)
    traversal = ObservationStratifiedJointTraversal(
        seed=seed, observation_replicas=replicas
    )
    return all(
        Counter(own) == expected and Counter(opponent) == expected
        for replica in range(replicas)
        for own, opponent in traversal._observation_schedules(0, replica)
    )


def _evaluate(result):
    return run_independent_evaluation(
        FiveDieStepwiseIndependentEvaluator(),
        result.policy,
        maximum_exploitability=1.0,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preregistration", type=Path, default=DEFAULT_PLAN)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    plan = json.loads(args.preregistration.read_text(encoding="utf-8"))
    if plan["status"] != "frozen_exploratory_pilot_before_execution":
        raise ValueError("observation-stratification pilot was not frozen")
    retained = json.loads(
        (ROOT / plan["retained_failed_candidate"]).read_text(encoding="utf-8")
    )
    if retained.get("candidate_passed") is not False:
        raise ValueError("retained coverage failure is no longer negative evidence")

    seed = int(plan["seed"])
    iterations = int(plan["iterations"])
    started = perf_counter()
    baseline = CoverageAwareJointStratifiedFiveDieTrainer(seed=seed).train(iterations)
    baseline_seconds = perf_counter() - started
    baseline_evaluation = _evaluate(baseline)
    required = len(required_five_die_information_sets())
    baseline_positive = sum(
        weight > 0
        for weight in baseline.average_strategy_observation_weight.values()
    )

    doses = []
    for replicas in plan["observation_replica_doses"]:
        started = perf_counter()
        trainer = ObservationStratifiedFiveDieTrainer(
            seed=seed, observation_replicas=int(replicas)
        )
        result = trainer.train(iterations)
        elapsed = perf_counter() - started
        evaluation = _evaluate(result)
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
        gates = {
            "regret_trace_parity": (
                result.average_positive_regret == baseline.average_positive_regret
            ),
            "visit_trace_parity": (
                result.information_set_visits == baseline.information_set_visits
            ),
            "exact_private_histogram_marginals": _schedule_valid(
                seed, int(replicas)
            ),
            "independent_evaluator_unchanged": (
                evaluation.evaluator_id
                == "five_die_stepwise_histogram_best_response_v1"
            ),
            "fallback_exactly_equals_zero_weight_set": fallback == zero_weight,
            "normalized_complete_policy": (
                len(result.policy) == required and _normalized(result.policy)
            ),
        }
        doses.append(
            {
                "observation_replicas": replicas,
                "algorithm": result.algorithm.to_artifact(),
                "elapsed_seconds": elapsed,
                "positive_observation_weight_information_sets": positive,
                "raw_observation_weight_coverage": positive / required,
                "fallback_information_sets": len(fallback),
                "fallback_fraction": len(fallback) / required,
                "coverage_gain_vs_baseline": (positive - baseline_positive) / required,
                "coverage_gain_per_replica": (
                    (positive - baseline_positive) / required / int(replicas)
                ),
                "independent_evaluation": _compact(evaluation),
                "gates": gates,
                "valid": all(gates.values()),
            }
        )
        print(
            f"replicas={replicas} coverage={positive / required:.6f} "
            f"fallback={len(fallback) / required:.6f} "
            f"exploitability={evaluation.exploitability:.12f}",
            flush=True,
        )

    eligible = [dose for dose in doses if dose["valid"]]
    target = [dose for dose in eligible if dose["raw_observation_weight_coverage"] >= 0.40]
    selected = min(target or eligible, key=lambda dose: (
        dose["observation_replicas"] if target else -dose["raw_observation_weight_coverage"]
    ))
    artifact = {
        "experiment_id": plan["experiment_id"],
        "status": "exploratory_pilot_not_certification",
        "preregistration": str(args.preregistration.relative_to(ROOT)),
        "retained_failed_candidate": plan["retained_failed_candidate"],
        "baseline": {
            "algorithm": baseline.algorithm.to_artifact(),
            "elapsed_seconds": baseline_seconds,
            "positive_observation_weight_information_sets": baseline_positive,
            "raw_observation_weight_coverage": baseline_positive / required,
            "independent_evaluation": _compact(baseline_evaluation),
        },
        "doses": doses,
        "selected_observation_replicas": selected["observation_replicas"],
        "selection_rule_applied": plan["dose_selection_rule"]["choose"],
        "separate_confirmation_required": True,
        "runtime_epsilon_gto_enabled": False,
        "audit_completed": len(doses) == len(plan["observation_replica_doses"]),
        "passed": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(artifact, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(args.output, flush=True)
    return 0 if artifact["audit_completed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
