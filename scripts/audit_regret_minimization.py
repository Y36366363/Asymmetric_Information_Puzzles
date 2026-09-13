#!/usr/bin/env python3
"""Audit AIP's composable trainers against frozen independent poker references."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from aip.core import CFRArtifactExporter, create_regret_minimization_trainer
from aip.puzzles.kuhn_poker import (
    KuhnCFRGame,
    evaluate_kuhn_cfr,
    kuhn_policy_from_cfr,
    policy_value,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REFERENCE = ROOT / "configs/poker_capability_lab_regret_reference_v1.json"
DEFAULT_OUTPUT = ROOT / "research/results/regret_minimization_audit_2026-09-13.json"
CHECKPOINTS = (10, 100, 1_000, 10_000)


def _independent_metrics(result):
    return evaluate_kuhn_cfr(result).to_report()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference", type=Path, default=DEFAULT_REFERENCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    reference = json.loads(args.reference.read_text(encoding="utf-8"))
    algorithms = {}
    checks = {}
    exporter = CFRArtifactExporter()
    for algorithm_id in ("vanilla_cfr", "cfr_plus", "dcfr"):
        result = create_regret_minimization_trainer(
            KuhnCFRGame(), algorithm_id
        ).train(
            CHECKPOINTS[-1],
            checkpoints=set(CHECKPOINTS),
            independent_evaluator=_independent_metrics,
        )
        policy = kuhn_policy_from_cfr(result)
        evaluation = evaluate_kuhn_cfr(result)
        value = float(policy_value(policy, policy, hero_first=True))
        artifact = exporter.build(
            result,
            game_id="canonical_kuhn_poker",
            independent_evaluation=evaluation,
        )
        external = reference["kuhn_10000"][algorithm_id]
        trace = [
            point.independent_evaluation["exploitability"]
            for point in result.convergence_trace
        ]
        checks[f"{algorithm_id}_value"] = (
            abs(value - external["value_to_player_0"]) <= 1e-8
        )
        checks[f"{algorithm_id}_exploitability"] = (
            abs(evaluation.exploitability - external["exploitability"]) <= 5e-8
        )
        checks[f"{algorithm_id}_trace"] = all(
            abs(actual - expected) <= 5e-8
            for actual, expected in zip(
                trace, external["exploitability_trace_10_100_1000_10000"]
            )
        )
        algorithms[algorithm_id] = {
            "value_to_player_0": value,
            "solver_artifact": artifact,
            "external_reference": external,
        }
    report = {
        "audit_version": "1.0.0",
        "reference": {
            "id": reference["reference_id"],
            "source_commit": reference["source_commit"],
            "dependency_policy": reference["dependency_policy"],
        },
        "kuhn": algorithms,
        "leduc_external_transfer_reference": reference["leduc_release"],
        "leduc_status": (
            "reference recorded for the next adapter milestone; AIP does not claim "
            "Leduc parity until it has its own game tree and independent best response"
        ),
        "checks": checks,
        "passed": all(checks.values()),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(args.output)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
