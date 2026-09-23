#!/usr/bin/env python3
"""Run the preregistered small Liar's Dice positive-control manipulation check."""

from __future__ import annotations

import argparse
import json
import os
import random
from pathlib import Path

from aip.benchmark.completion import (
    DECISION_JSON_SCHEMA,
    CompletionAgentError,
    CompletionBackedAgent,
    OpenAIResponsesBackend,
    PromptCondition,
    completion_input_text,
    completion_instructions,
    load_dotenv_value,
)
from aip.benchmark.liar_transfer import (
    PAD_TOKEN,
    build_consensus_reference_profiles,
    canonical_json,
    digest,
    positive_control_material,
    positive_control_prompt,
    select_profile_invariant_probes,
)


OUTPUT = Path("research/results/liar_positive_control_check_2026-09-23")
MODEL = "gpt-5.6-luna"
ARMS = ("no_memory", "same_game_positive_control")
REPEATS = 2
SEED = 20260923
GATE = {
    "allCellsValid": True,
    "inputTokenMismatches": 0,
    "minimumRepeatActionAgreementEachArm": 0.80,
    "minimumPositiveControlOptimalActionRate": 0.85,
    "minimumOptimalActionRateLift": 0.15,
    "positiveControlMeanRegretMustBeLower": True,
}


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def ensure_key(env_file: Path) -> None:
    if not os.environ.get("OPENAI_API_KEY"):
        key = load_dotenv_value(env_file, "OPENAI_API_KEY")
        if key:
            os.environ["OPENAI_API_KEY"] = key
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is unavailable")


def manipulation_panel():
    profiles = build_consensus_reference_profiles()
    panel, panel_audit = select_profile_invariant_probes(profiles, count=30)
    challenge = panel[:6]
    player_zero_raise = tuple(probe for probe in panel if probe.player == 0)[-3:]
    player_one_raise = tuple(probe for probe in panel if probe.player == 1)[-3:]
    selected = challenge + player_zero_raise + player_one_raise
    if len(selected) != 12:
        raise ValueError("manipulation panel must contain 12 probes")
    labels = [max(probe.exact_action_values, key=probe.exact_action_values.get) for probe in selected]
    if sum(label == "challenge" for label in labels) != 6:
        raise ValueError("manipulation panel must contain six challenge labels")
    if sum(label.startswith("raise:") for label in labels) != 6:
        raise ValueError("manipulation panel must contain six raise labels")
    return selected, panel, panel_audit, profiles


def _count(client, *, prompt: str, input_text: str) -> int:
    response = client.responses.input_tokens.count(
        model=MODEL,
        instructions=completion_instructions(prompt),
        input=input_text,
        text={
            "format": {
                "type": "json_schema",
                "name": "aip_agent_decision",
                "strict": True,
                "schema": DECISION_JSON_SCHEMA,
            }
        },
        reasoning={"effort": "low"},
    )
    return int(response.input_tokens)


def _pad_prompts(client, base_prompts: dict[str, str], inputs: dict[str, str]):
    labeled = {
        arm: prompt + "\nNeutral padding tokens follow and carry no game information:"
        for arm, prompt in base_prompts.items()
    }
    blank_counts = {
        arm: _count(client, prompt=prompt, input_text=" ")
        for arm, prompt in labeled.items()
    }
    target = max(blank_counts.values()) + 16
    padded = {}
    padding = {}
    for arm in ARMS:
        amount = target - blank_counts[arm]
        for _ in range(64):
            candidate = labeled[arm] + PAD_TOKEN * amount
            observed = _count(client, prompt=candidate, input_text=" ")
            if observed == target:
                padded[arm] = candidate
                padding[arm] = amount
                break
            amount += target - observed
        else:
            raise RuntimeError(f"could not token-balance {arm}")
    counts = {
        (probe_id, arm): _count(client, prompt=padded[arm], input_text=input_text)
        for probe_id, input_text in inputs.items()
        for arm in ARMS
    }
    for probe_id in inputs:
        if len({counts[(probe_id, arm)] for arm in ARMS}) != 1:
            raise ValueError(f"provider token counts differ for {probe_id}")
    return padded, padding, counts


def prepare_plan(env_file: Path) -> dict[str, object]:
    ensure_key(env_file)
    from openai import OpenAI

    client = OpenAI(max_retries=1, timeout=60.0)
    probes, full_panel, panel_audit, profiles = manipulation_panel()
    material = positive_control_material(full_panel, profiles)
    base_prompts = {
        "no_memory": (
            "Condition: no_memory. Solve only from the current rules and public decision state."
        ),
        "same_game_positive_control": positive_control_prompt(material),
    }
    inputs = {probe.probe_id: completion_input_text(probe.decision_input()) for probe in probes}
    prompts, padding, counts = _pad_prompts(client, base_prompts, inputs)
    cells = [
        {
            "probeId": probe.probe_id,
            "arm": arm,
            "repeat": repeat,
            "expectedInputTokens": counts[(probe.probe_id, arm)],
        }
        for probe in probes
        for arm in ARMS
        for repeat in range(1, REPEATS + 1)
    ]
    random.Random(SEED).shuffle(cells)
    plan = {
        "schemaVersion": "aip-liar-positive-control-prereg-v1",
        "date": "2026-09-23",
        "model": MODEL,
        "reasoningEffort": "low",
        "maxOutputTokens": 4096,
        "maxAttemptsPerCell": 1,
        "seed": SEED,
        "repeats": REPEATS,
        "fullPanelSize": len(full_panel),
        "manipulationPanelSize": len(probes),
        "fullPanelAudit": panel_audit,
        "probes": [probe.to_artifact() for probe in probes],
        "positiveControlMaterial": material,
        "positiveControlMaterialSha256": digest(material),
        "prompts": prompts,
        "basePromptSha256": {arm: digest(base_prompts[arm]) for arm in ARMS},
        "paddingToken": PAD_TOKEN,
        "paddingTokenCounts": padding,
        "cellOrder": cells,
        "maxProviderCalls": len(cells),
        "gate": GATE,
        "nextStepRule": (
            "Run the 30-state four-condition main experiment only if every gate passes; "
            "otherwise retain the failed evidence and do not expand model calls."
        ),
        "certificationScope": {
            "fullLoveLetterCertified": False,
            "runtimeLabelsChanged": False,
        },
    }
    validate_plan(plan)
    return plan


def validate_plan(plan: dict[str, object]) -> None:
    if plan.get("schemaVersion") != "aip-liar-positive-control-prereg-v1":
        raise ValueError("unsupported preregistration")
    if plan.get("model") != MODEL or plan.get("repeats") != REPEATS:
        raise ValueError("model or repeat count changed")
    if plan.get("gate") != GATE:
        raise ValueError("manipulation gate changed")
    if plan.get("positiveControlMaterialSha256") != digest(plan["positiveControlMaterial"]):
        raise ValueError("positive-control material fingerprint mismatch")
    probes = {probe["id"]: probe for probe in plan["probes"]}
    expected = {
        (probe_id, arm, repeat)
        for probe_id in probes
        for arm in ARMS
        for repeat in range(1, REPEATS + 1)
    }
    actual = [(cell["probeId"], cell["arm"], cell["repeat"]) for cell in plan["cellOrder"]]
    if len(actual) != len(expected) or set(actual) != expected:
        raise ValueError("cell schedule is incomplete or duplicated")
    if plan["maxProviderCalls"] != len(actual):
        raise ValueError("provider-call budget differs from schedule")
    for probe_id in probes:
        counts = {
            cell["expectedInputTokens"]
            for cell in plan["cellOrder"] if cell["probeId"] == probe_id
        }
        if len(counts) != 1:
            raise ValueError("input tokens are not equal across arms")
    regenerated = {probe.probe_id: probe.to_artifact() for probe in manipulation_panel()[0]}
    if probes != regenerated:
        raise ValueError("manipulation probe oracle changed")


def read_plan(path: Path) -> dict[str, object]:
    plan = json.loads(path.read_text(encoding="utf-8"))
    validate_plan(plan)
    return plan


def run(plan: dict[str, object], output: Path, env_file: Path):
    ensure_key(env_file)
    from openai import OpenAI

    client = OpenAI(max_retries=0, timeout=60.0)
    backend = OpenAIResponsesBackend(
        client=client,
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
    complete = {(row["probeId"], row["arm"], row["repeat"]) for row in rows}
    probes = {probe.probe_id: probe for probe in manipulation_panel()[0]}
    artifacts = {probe["id"]: probe for probe in plan["probes"]}
    for index, cell in enumerate(plan["cellOrder"], start=1):
        key = cell["probeId"], cell["arm"], cell["repeat"]
        if key in complete:
            continue
        probe = probes[cell["probeId"]]
        condition = (
            PromptCondition.GENERIC if cell["arm"] == "no_memory"
            else PromptCondition.SINGLE_GAME
        )
        agent = CompletionBackedAgent(
            backend,
            plan["model"],
            condition,
            condition_prompt=plan["prompts"][cell["arm"]],
            max_attempts=plan["maxAttemptsPerCell"],
        )
        row = {
            **cell,
            "status": "failed",
            "actionId": None,
            "penalizedActionRegret": artifacts[probe.probe_id]["failurePenalty"],
            "optimalPolicyAgreement": False,
        }
        try:
            decision = agent.choose_action(probe.decision_input())
            evaluation = probe.evaluate(decision)
            row.update(
                status="valid",
                actionId=decision.action_id,
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
            "schemaVersion": "aip-liar-positive-control-rows-v1",
            "preregistrationSha256": plan_sha,
            "rows": rows,
        })
        print(f"{index}/{len(plan['cellOrder'])} {cell['arm']} r{cell['repeat']}: {row['status']}", flush=True)
    return rows


def _arm_summary(rows, arm: str) -> dict[str, object]:
    selected = [row for row in rows if row["arm"] == arm]
    by_probe: dict[str, list[dict[str, object]]] = {}
    for row in selected:
        by_probe.setdefault(row["probeId"], []).append(row)
    agreements = [
        len(group) == REPEATS and len({row["actionId"] for row in group}) == 1
        for group in by_probe.values()
    ]
    return {
        "cells": len(selected),
        "validDecisions": sum(row["status"] == "valid" for row in selected),
        "optimalActionRate": sum(row["optimalPolicyAgreement"] for row in selected) / len(selected),
        "meanExactActionRegret": sum(row["penalizedActionRegret"] for row in selected) / len(selected),
        "repeatActionAgreement": sum(agreements) / len(agreements),
        "repeatAgreementProbeCount": sum(agreements),
    }


def build_report(plan: dict[str, object], rows: list[dict[str, object]]) -> dict[str, object]:
    summaries = {arm: _arm_summary(rows, arm) for arm in ARMS}
    no_memory = summaries["no_memory"]
    control = summaries["same_game_positive_control"]
    complete = len(rows) == plan["maxProviderCalls"]
    token_mismatches = sum(not row.get("inputTokenMatch", False) for row in rows)
    resolved = sorted({
        attempt["resolved_model"]
        for row in rows
        for attempt in row.get("telemetry", {}).get("attempts", [])
        if attempt.get("resolved_model")
    })
    gate = {
        "allCellsValid": complete and all(row["status"] == "valid" for row in rows),
        "inputTokenMismatchesZero": token_mismatches == 0,
        "repeatActionAgreementEachArm": all(
            summary["repeatActionAgreement"] >= 0.80 for summary in summaries.values()
        ),
        "positiveControlOptimalActionRate": control["optimalActionRate"] >= 0.85,
        "optimalActionRateLift": (
            control["optimalActionRate"] - no_memory["optimalActionRate"] >= 0.15
        ),
        "positiveControlMeanRegretLower": (
            control["meanExactActionRegret"] < no_memory["meanExactActionRegret"]
        ),
    }
    passed = all(gate.values())
    return {
        "schemaVersion": "aip-liar-positive-control-report-v1",
        "preregistrationSha256": digest(plan),
        "runStatus": "complete" if complete else "incomplete",
        "completedCells": len(rows),
        "validDecisions": sum(row["status"] == "valid" for row in rows),
        "inputTokenMismatches": token_mismatches,
        "resolvedModels": resolved,
        "summaries": summaries,
        "contrasts": {
            "optimalActionRateLift": control["optimalActionRate"] - no_memory["optimalActionRate"],
            "meanExactActionRegretDifference": (
                control["meanExactActionRegret"] - no_memory["meanExactActionRegret"]
            ),
        },
        "gateChecks": gate,
        "gatePassed": passed,
        "nextStep": "run_four_condition_30_state_experiment" if passed else "stop_before_main_experiment",
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
    rows = (
        run(plan, rows_path, args.env_file)
        if args.phase == "run"
        else json.loads(rows_path.read_text(encoding="utf-8"))["rows"]
    )
    report = build_report(plan, rows)
    write_json(args.output_dir / "report.json", report)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["runStatus"] == "complete" else 2


if __name__ == "__main__":
    raise SystemExit(main())
