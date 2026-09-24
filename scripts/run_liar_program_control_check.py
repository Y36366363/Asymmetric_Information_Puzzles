#!/usr/bin/env python3
"""Run the frozen fresh-panel oracle-assisted Liar manipulation check."""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

from aip.benchmark.completion import (
    CompletionAgentError,
    CompletionBackedAgent,
    OpenAIResponsesBackend,
    PromptCondition,
    completion_input_text,
)
from aip.benchmark.liar_transfer import (
    PAD_TOKEN,
    ExactLiarDecisionProgram,
    canonical_json,
    digest,
)
from scripts.run_liar_positive_control_check import (
    MODEL,
    _count,
    ensure_key,
    manipulation_panel,
    write_json,
)


OUTPUT = Path("research/results/liar_program_control_check_2026-09-24")
ARMS = ("no_memory", "oracle_assisted_same_game")
REPEATS = 2
SEED = 20260924
GATE = {
    "allCellsValid": True,
    "inputTokenMismatches": 0,
    "minimumRepeatActionAgreementEachArm": 0.80,
    "minimumAssistedOptimalActionRate": 0.95,
    "minimumOptimalActionRateLift": 0.15,
    "assistedMeanRegretMustBeLower": True,
}


def fresh_panel():
    prior, full_panel, panel_audit, _ = manipulation_panel()
    prior_ids = {probe.probe_id for probe in prior}
    remaining = [probe for probe in full_panel if probe.probe_id not in prior_ids]
    groups = {"challenge": [], "raise_p0": [], "raise_p1": []}
    for probe in remaining:
        best = max(probe.exact_action_values, key=probe.exact_action_values.get)
        if best == "challenge":
            groups["challenge"].append(probe)
        else:
            groups[f"raise_p{probe.player}"].append(probe)
    rank = lambda probe: digest({
        "seed": SEED,
        "purpose": "fresh_program_manipulation_panel",
        "probe": probe.probe_id,
    })
    selected = (
        sorted(groups["challenge"], key=rank)[:6]
        + sorted(groups["raise_p0"], key=rank)[:4]
        + sorted(groups["raise_p1"], key=rank)[:2]
    )
    if len(selected) != 12 or prior_ids.intersection(p.probe_id for p in selected):
        raise ValueError("fresh panel is incomplete or overlaps the prior model run")
    return tuple(selected), tuple(prior), full_panel, panel_audit


def _pad_cell_prompts(client, base_prompts, inputs, *, arms=ARMS):
    prompts = {}
    padding = {}
    counts = {}
    for probe_id, input_text in inputs.items():
        labeled = {
            arm: base_prompts[(probe_id, arm)]
            + "\nNeutral padding tokens follow and carry no game information:"
            for arm in arms
        }
        initial = {
            arm: _count(client, prompt=labeled[arm], input_text=input_text)
            for arm in arms
        }
        target = max(initial.values()) + 16
        for arm in arms:
            amount = target - initial[arm]
            for _ in range(64):
                candidate = labeled[arm] + PAD_TOKEN * amount
                observed = _count(client, prompt=candidate, input_text=input_text)
                if observed == target:
                    prompts[(probe_id, arm)] = candidate
                    padding[(probe_id, arm)] = amount
                    counts[(probe_id, arm)] = observed
                    break
                amount += target - observed
            else:
                raise RuntimeError(f"could not token-balance {probe_id}/{arm}")
    return prompts, padding, counts


def prepare_plan(env_file: Path) -> dict[str, object]:
    ensure_key(env_file)
    from openai import OpenAI

    client = OpenAI(max_retries=1, timeout=60.0)
    probes, prior, full_panel, panel_audit = fresh_panel()
    program = ExactLiarDecisionProgram()
    inputs = {probe.probe_id: completion_input_text(probe.decision_input()) for probe in probes}
    base = {}
    for probe in probes:
        base[(probe.probe_id, "no_memory")] = (
            "Condition: no_memory. Solve only from the current rules and public decision state."
        )
        base[(probe.probe_id, "oracle_assisted_same_game")] = program.prompt_for(probe)
    prompts, padding, counts = _pad_cell_prompts(client, base, inputs)
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
    plan = {
        "schemaVersion": "aip-liar-program-control-prereg-v1",
        "date": "2026-09-24",
        "model": MODEL,
        "reasoningEffort": "low",
        "maxOutputTokens": 4096,
        "maxAttemptsPerCell": 1,
        "seed": SEED,
        "repeats": REPEATS,
        "gate": GATE,
        "programId": program.program_id,
        "programScope": "oracle-assisted manipulation control; excluded from transfer claims",
        "fullPanelSize": len(full_panel),
        "freshPanelSize": len(probes),
        "priorModelRunProbeIds": sorted(probe.probe_id for probe in prior),
        "freshPanelDisjointFromPriorRun": True,
        "fullPanelAudit": panel_audit,
        "probes": [probe.to_artifact() for probe in probes],
        "prompts": {
            probe_id: {arm: prompts[(probe_id, arm)] for arm in ARMS}
            for probe_id in inputs
        },
        "basePromptSha256": {
            probe_id: {arm: digest(base[(probe_id, arm)]) for arm in ARMS}
            for probe_id in inputs
        },
        "paddingToken": PAD_TOKEN,
        "paddingTokenCounts": {
            probe_id: {arm: padding[(probe_id, arm)] for arm in ARMS}
            for probe_id in inputs
        },
        "cellOrder": cells,
        "maxProviderCalls": len(cells),
        "nextStepRule": (
            "Only if every gate passes may the four-condition 30-state experiment "
            "be prepared; this control does not count as transfer evidence."
        ),
        "certificationScope": {
            "fullLoveLetterCertified": False,
            "runtimeLabelsChanged": False,
        },
    }
    validate_plan(plan)
    return plan


def validate_plan(plan):
    if plan.get("schemaVersion") != "aip-liar-program-control-prereg-v1":
        raise ValueError("unsupported preregistration")
    if plan.get("model") != MODEL or plan.get("repeats") != REPEATS:
        raise ValueError("model or repeat count changed")
    if plan.get("gate") != GATE:
        raise ValueError("manipulation gate changed")
    probes = {probe["id"]: probe for probe in plan["probes"]}
    expected = {
        (probe_id, arm, repeat)
        for probe_id in probes for arm in ARMS for repeat in range(1, REPEATS + 1)
    }
    actual = [(cell["probeId"], cell["arm"], cell["repeat"]) for cell in plan["cellOrder"]]
    if len(actual) != len(expected) or set(actual) != expected:
        raise ValueError("cell schedule is incomplete or duplicated")
    if plan["maxProviderCalls"] != len(actual):
        raise ValueError("provider-call budget differs from schedule")
    fresh, prior, _, _ = fresh_panel()
    if probes != {probe.probe_id: probe.to_artifact() for probe in fresh}:
        raise ValueError("fresh-panel oracle changed")
    if set(plan["priorModelRunProbeIds"]) != {probe.probe_id for probe in prior}:
        raise ValueError("prior-run exclusion set changed")
    if set(probes).intersection(plan["priorModelRunProbeIds"]):
        raise ValueError("fresh panel overlaps the prior model run")
    for probe_id in probes:
        counts = {
            cell["expectedInputTokens"] for cell in plan["cellOrder"]
            if cell["probeId"] == probe_id
        }
        if len(counts) != 1:
            raise ValueError("input tokens are not equal across arms")


def read_plan(path: Path):
    plan = json.loads(path.read_text(encoding="utf-8"))
    validate_plan(plan)
    return plan


def execute_plan(plan, output: Path, env_file: Path, probes):
    """Execute any compatible preregistered Liar panel with atomic checkpoints."""

    ensure_key(env_file)
    from openai import OpenAI

    backend = OpenAIResponsesBackend(
        client=OpenAI(max_retries=0, timeout=60.0),
        reasoning_effort=plan["reasoningEffort"],
        max_output_tokens=plan["maxOutputTokens"],
    )
    plan_sha = digest(plan)
    rows = []
    if output.exists():
        envelope = json.loads(output.read_text(encoding="utf-8"))
        if envelope.get("preregistrationSha256") != plan_sha:
            raise ValueError("existing rows belong to a different preregistration")
        rows = envelope["rows"]
    complete = {(r["probeId"], r["arm"], r["repeat"]) for r in rows}
    probes = {probe.probe_id: probe for probe in probes}
    artifacts = {probe["id"]: probe for probe in plan["probes"]}
    for index, cell in enumerate(plan["cellOrder"], start=1):
        key = cell["probeId"], cell["arm"], cell["repeat"]
        if key in complete:
            continue
        probe = probes[cell["probeId"]]
        condition = (
            PromptCondition.GENERIC
            if cell["arm"] == "no_memory"
            else PromptCondition.SINGLE_GAME
            if cell["arm"] in {"same_game", "oracle_assisted_same_game"}
            else PromptCondition.CROSS_GAME_EXPERIENCE
        )
        agent = CompletionBackedAgent(
            backend, plan["model"], condition,
            condition_prompt=plan["prompts"][probe.probe_id][cell["arm"]],
            max_attempts=plan["maxAttemptsPerCell"],
        )
        row = {
            **cell, "status": "failed", "actionId": None,
            "penalizedActionRegret": artifacts[probe.probe_id]["failurePenalty"],
            "optimalPolicyAgreement": False,
        }
        try:
            decision = agent.choose_action(probe.decision_input())
            evaluation = probe.evaluate(decision)
            row.update(
                status="valid", actionId=decision.action_id,
                penalizedActionRegret=evaluation["actionRegret"],
                optimalPolicyAgreement=evaluation["optimalPolicyAgreement"],
                optimalActionIds=evaluation["optimalActionIds"],
            )
        except CompletionAgentError as error:
            row["errorType"] = error.__class__.__name__
        except Exception as error:
            row["errorType"] = error.__class__.__name__
        telemetry = agent.telemetry_history[-1].as_dict() if agent.telemetry_history else {}
        row["telemetry"] = telemetry
        row["observedInputTokens"] = telemetry.get("inputTokens", 0)
        row["inputTokenMatch"] = row["observedInputTokens"] == row["expectedInputTokens"]
        rows.append(row)
        complete.add(key)
        write_json(output, {
            "schemaVersion": "aip-liar-program-control-rows-v1",
            "preregistrationSha256": plan_sha,
            "rows": rows,
        })
        print(f"{index}/{len(plan['cellOrder'])} {cell['arm']} r{cell['repeat']}: {row['status']}", flush=True)
    return rows


def run(plan, output: Path, env_file: Path):
    return execute_plan(plan, output, env_file, fresh_panel()[0])


def _summary(rows, arm):
    selected = [row for row in rows if row["arm"] == arm]
    grouped = {}
    for row in selected:
        grouped.setdefault(row["probeId"], []).append(row)
    agreements = [
        len(group) == REPEATS and len({row["actionId"] for row in group}) == 1
        for group in grouped.values()
    ]
    return {
        "cells": len(selected),
        "validDecisions": sum(row["status"] == "valid" for row in selected),
        "optimalActionRate": sum(row["optimalPolicyAgreement"] for row in selected) / len(selected),
        "meanExactActionRegret": sum(row["penalizedActionRegret"] for row in selected) / len(selected),
        "repeatActionAgreement": sum(agreements) / len(agreements),
        "repeatAgreementProbeCount": sum(agreements),
    }


def build_report(plan, rows):
    summaries = {arm: _summary(rows, arm) for arm in ARMS}
    baseline = summaries["no_memory"]
    assisted = summaries["oracle_assisted_same_game"]
    complete = len(rows) == plan["maxProviderCalls"]
    mismatches = sum(not row.get("inputTokenMatch", False) for row in rows)
    gates = {
        "allCellsValid": complete and all(row["status"] == "valid" for row in rows),
        "inputTokenMismatchesZero": mismatches == 0,
        "repeatActionAgreementEachArm": all(s["repeatActionAgreement"] >= .80 for s in summaries.values()),
        "assistedOptimalActionRate": assisted["optimalActionRate"] >= .95,
        "optimalActionRateLift": assisted["optimalActionRate"] - baseline["optimalActionRate"] >= .15,
        "assistedMeanRegretLower": assisted["meanExactActionRegret"] < baseline["meanExactActionRegret"],
    }
    passed = all(gates.values())
    return {
        "schemaVersion": "aip-liar-program-control-report-v1",
        "preregistrationSha256": digest(plan),
        "runStatus": "complete" if complete else "incomplete",
        "completedCells": len(rows),
        "validDecisions": sum(row["status"] == "valid" for row in rows),
        "inputTokenMismatches": mismatches,
        "summaries": summaries,
        "contrasts": {
            "optimalActionRateLift": assisted["optimalActionRate"] - baseline["optimalActionRate"],
            "meanExactActionRegretDifference": assisted["meanExactActionRegret"] - baseline["meanExactActionRegret"],
        },
        "gateChecks": gates,
        "gatePassed": passed,
        "nextStep": "prepare_four_condition_30_state_experiment" if passed else "stop_before_main_experiment",
        "claimRestriction": "oracle-assisted condition is not transfer evidence",
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
    rows = run(plan, rows_path, args.env_file) if args.phase == "run" else json.loads(rows_path.read_text())["rows"]
    report = build_report(plan, rows)
    write_json(args.output_dir / "report.json", report)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["runStatus"] == "complete" else 2


if __name__ == "__main__":
    raise SystemExit(main())
