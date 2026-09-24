#!/usr/bin/env python3
"""Run the preregistered four-condition experiment on the invariant 30-state panel."""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

from aip.benchmark.completion import completion_input_text
from aip.benchmark.liar_transfer import (
    ARMS,
    REPEATS,
    SEED,
    ExactLiarDecisionProgram,
    analyze_results,
    base_memory_prompts,
    build_consensus_reference_profiles,
    canonical_json,
    digest,
    select_profile_invariant_probes,
    source_experience_records,
    target_oracle_metadata,
)
from scripts.run_liar_positive_control_check import MODEL, ensure_key, write_json
from scripts.run_liar_program_control_check import _pad_cell_prompts, execute_plan


OUTPUT = Path("research/results/liar_transfer_30_state_2026-09-24")


def panel():
    profiles = build_consensus_reference_profiles()
    return select_profile_invariant_probes(profiles, count=30)


def prepare_plan(env_file: Path):
    ensure_key(env_file)
    from openai import OpenAI

    client = OpenAI(max_retries=1, timeout=60.0)
    probes, panel_audit = panel()
    program = ExactLiarDecisionProgram()
    common = base_memory_prompts(probes)
    inputs = {probe.probe_id: completion_input_text(probe.decision_input()) for probe in probes}
    base = {}
    for probe in probes:
        for arm in ARMS:
            base[(probe.probe_id, arm)] = (
                program.prompt_for(probe) if arm == "same_game" else common[arm]
            )
    prompts, padding, counts = _pad_cell_prompts(
        client, base, inputs, arms=ARMS
    )
    cells = [
        {
            "probeId": probe.probe_id,
            "arm": arm,
            "repeat": repeat,
            "expectedInputTokens": counts[(probe.probe_id, arm)],
        }
        for probe in probes for arm in ARMS for repeat in range(1, REPEATS + 1)
    ]
    random.Random(SEED).shuffle(cells)
    records = source_experience_records()
    plan = {
        "schemaVersion": "aip-liar-transfer-30-state-prereg-v1",
        "date": "2026-09-24",
        "model": MODEL,
        "reasoningEffort": "low",
        "maxOutputTokens": 4096,
        "maxAttemptsPerCell": 1,
        "seed": SEED,
        "repeats": REPEATS,
        "arms": list(ARMS),
        "probes": [probe.to_artifact() for probe in probes],
        "panelAudit": panel_audit,
        "sameGameControl": {
            "programId": program.program_id,
            "scope": "oracle-assisted positive control; excluded from transfer claim",
        },
        "sourceExperienceRecords": records,
        "sourceExperienceSha256": digest(records),
        "prompts": {
            probe_id: {arm: prompts[(probe_id, arm)] for arm in ARMS}
            for probe_id in inputs
        },
        "basePromptSha256": {
            probe_id: {arm: digest(base[(probe_id, arm)]) for arm in ARMS}
            for probe_id in inputs
        },
        "paddingTokenCounts": {
            probe_id: {arm: padding[(probe_id, arm)] for arm in ARMS}
            for probe_id in inputs
        },
        "cellOrder": cells,
        "maxProviderCalls": len(cells),
        "primaryEndpoint": (
            "Mean exact conditional action regret, abstract_memory minus no_memory, "
            "paired by probe and repeat with invalid-output penalties retained."
        ),
        "interpretationRule": (
            "A fixed-seed 10000-resample paired bootstrap interval wholly below zero "
            "is benefit, wholly above zero is harm, otherwise inconclusive."
        ),
        "qualityGates": {
            "allCellsValid": True,
            "inputTokenMismatches": 0,
            "minimumRepeatActionAgreementEachArm": 0.80,
        },
        "claimRules": {
            "sameGameExcludedFromTransferClaim": True,
            "fullLoveLetterCertified": False,
            "runtimeLabelsChanged": False,
        },
    }
    validate_plan(plan)
    return plan


def validate_plan(plan):
    if plan.get("schemaVersion") != "aip-liar-transfer-30-state-prereg-v1":
        raise ValueError("unsupported preregistration")
    if plan.get("model") != MODEL or plan.get("repeats") != REPEATS:
        raise ValueError("model or repeat count changed")
    if tuple(plan.get("arms", ())) != ARMS:
        raise ValueError("experiment arms changed")
    if plan.get("sourceExperienceSha256") != digest(plan["sourceExperienceRecords"]):
        raise ValueError("source experience fingerprint mismatch")
    probes = {probe["id"]: probe for probe in plan["probes"]}
    regenerated = {probe.probe_id: probe.to_artifact() for probe in panel()[0]}
    if probes != regenerated or len(probes) != 30:
        raise ValueError("30-state invariant panel changed")
    expected = {
        (probe_id, arm, repeat)
        for probe_id in probes for arm in ARMS for repeat in range(1, REPEATS + 1)
    }
    actual = [(cell["probeId"], cell["arm"], cell["repeat"]) for cell in plan["cellOrder"]]
    if len(actual) != len(expected) or set(actual) != expected:
        raise ValueError("cell schedule is incomplete or duplicated")
    if plan["maxProviderCalls"] != len(actual):
        raise ValueError("provider-call budget differs from schedule")
    for probe_id in probes:
        counts = {
            cell["expectedInputTokens"] for cell in plan["cellOrder"]
            if cell["probeId"] == probe_id
        }
        if len(counts) != 1:
            raise ValueError("provider token counts differ across arms")


def read_plan(path: Path):
    value = json.loads(path.read_text(encoding="utf-8"))
    validate_plan(value)
    return value


def build_report(plan, rows):
    analysis = analyze_results(plan, rows)
    complete = len(rows) == plan["maxProviderCalls"]
    mismatches = sum(not row.get("inputTokenMatch", False) for row in rows)
    transport_failures = sum(
        any(
            attempt["outcome"] == "transport_error"
            for attempt in row.get("telemetry", {}).get("attempts", [])
        )
        for row in rows
    )
    resolved = sorted({
        attempt["resolved_model"]
        for row in rows
        for attempt in row.get("telemetry", {}).get("attempts", [])
        if attempt.get("resolved_model")
    })
    gates = {
        "allCellsValid": complete and all(row["status"] == "valid" for row in rows),
        "inputTokenMismatchesZero": mismatches == 0,
        "repeatActionAgreementEachArm": all(
            summary["repeatActionAgreementRate"] >= .80
            for summary in analysis["summaries"].values()
        ),
    }
    return {
        "schemaVersion": "aip-liar-transfer-30-state-report-v1",
        "preregistrationSha256": digest(plan),
        "runStatus": "complete" if complete else "incomplete",
        "completedCells": len(rows),
        "validDecisions": sum(row["status"] == "valid" for row in rows),
        "inputTokenMismatches": mismatches,
        "transportFailures": transport_failures,
        "resolvedModels": resolved,
        "qualityGateChecks": gates,
        "qualityGatePassed": all(gates.values()),
        "targetOracle": target_oracle_metadata(),
        "analysis": analysis,
        "primaryConclusion": analysis["contrastsVersusNoMemory"]["abstract_memory"]["interpretation"],
        "sameGameExcludedFromTransferClaim": True,
        "fullLoveLetterCertified": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("prepare", "run", "analyze"))
    parser.add_argument("--output-dir", type=Path, default=OUTPUT)
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    args = parser.parse_args()
    plan_path = args.output_dir / "preregistration.json"
    rows_path = args.output_dir / "trial_rows.json"
    if args.phase == "prepare":
        proposed = prepare_plan(args.env_file)
        if plan_path.exists() and read_plan(plan_path) != proposed:
            raise ValueError("refusing to overwrite a different preregistration")
        write_json(plan_path, proposed)
        print(canonical_json({"path": str(plan_path), "sha256": digest(proposed)}))
        return 0
    plan = read_plan(plan_path)
    probes = panel()[0]
    rows = execute_plan(plan, rows_path, args.env_file, probes) if args.phase == "run" else json.loads(rows_path.read_text())["rows"]
    report = build_report(plan, rows)
    write_json(args.output_dir / "report.json", report)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["runStatus"] == "complete" else 2


if __name__ == "__main__":
    raise SystemExit(main())
