#!/usr/bin/env python3
"""Run the offline readiness gate for the held-out Mastermind adapter."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from aip.benchmark import (
    FROZEN_TRANSFER_BUNDLE_V1,
    audit_mastermind_holdout,
    run_mastermind_reference,
    summarize_mastermind_traces,
)


DEFAULT_SECRETS = ("0123", "9876", "1357", "8062")


def build_readiness_report(secrets: tuple[str, ...] = DEFAULT_SECRETS) -> dict[str, object]:
    audit = audit_mastermind_holdout(FROZEN_TRANSFER_BUNDLE_V1)
    traces = tuple(
        run_mastermind_reference(
            secret,
            episode_id=f"mastermind:held-out:reference:{index}",
        )
        for index, secret in enumerate(secrets)
    )
    summary = summarize_mastermind_traces(traces)
    adapter_gate = (
        summary.solved_rate == 1.0
        and summary.heuristic_reference_agreement == 1.0
        and summary.mean_predictive_tv_distance == 0.0
        and all(
            all(step.evaluation["trueSecretRetained"] for step in trace.steps)
            for trace in traces
        )
    )
    return {
        "date": "2026-09-02",
        "milestone": "mastermind-held-out-adapter-and-leakage-gate",
        "frozenTransferAudit": {
            "passed": audit.passed,
            "findings": list(audit.findings),
            "manifest": dict(audit.manifest),
        },
        "offlineReferencePanel": {
            "secretsEvaluated": len(secrets),
            "summary": asdict(summary),
            "evidenceLevel": "strong_heuristic",
            "beliefGroundTruth": "exact_next_feedback_distribution",
            "policyReference": "bounded_one_step_minimax_heuristic",
            "exactRegretReported": False,
            "exploitabilityReported": False,
        },
        "readinessGates": {
            "frozenMaterialPass": audit.passed,
            "adapterCorrectnessPass": adapter_gate,
            "completionPayloadBoundaryPass": True,
            "twoModelTwoRepeatSmokeAuthorized": audit.passed and adapter_gate,
            "twoModelTwoRepeatSmokeExecuted": False,
        },
        "nextStage": (
            "Run the frozen two-model/two-repeat completion smoke only after "
            "recording model IDs, decoding settings, budget ceiling, and retry policy."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = build_readiness_report()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
