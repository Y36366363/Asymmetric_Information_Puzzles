#!/usr/bin/env python3
"""Prepare and run the token-balanced held-out Liar's Dice transfer experiment."""

from __future__ import annotations

import argparse
import json
import os
import random
from concurrent.futures import ThreadPoolExecutor
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
    ARMS,
    PAD_TOKEN,
    REPEATS,
    SEED,
    analyze_results,
    base_memory_prompts,
    build_oracle_probes,
    canonical_json,
    digest,
    source_experience_records,
    target_oracle_metadata,
)


OUTPUT = Path("research/results/liar_transfer_confirmatory_2026-09-21")
MODEL = "gpt-5.6-luna"


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


def _condition(arm: str) -> PromptCondition:
    if arm == "no_memory":
        return PromptCondition.GENERIC
    if arm == "same_game":
        return PromptCondition.SINGLE_GAME
    return PromptCondition.CROSS_GAME_EXPERIENCE


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


def _pad_prompts(client, base_prompts: dict[str, str]) -> tuple[dict[str, str], dict[str, int]]:
    labeled = {
        arm: prompt + "\nNeutral padding tokens follow and carry no game information:"
        for arm, prompt in base_prompts.items()
    }
    counts = {arm: _count(client, prompt=prompt, input_text=" ") for arm, prompt in labeled.items()}
    target = max(counts.values()) + 16
    padded = {}
    padding = {}
    for arm in ARMS:
        amount = target - counts[arm]
        for _ in range(32):
            candidate = labeled[arm] + PAD_TOKEN * amount
            observed = _count(client, prompt=candidate, input_text=" ")
            if observed == target:
                padded[arm] = candidate
                padding[arm] = amount
                break
            amount += target - observed
            if amount < 0:
                raise ValueError("token equalizer produced negative padding")
        else:
            raise RuntimeError(f"could not token-balance {arm}")
    return padded, padding


def prepare_plan(env_file: Path) -> dict[str, object]:
    ensure_key(env_file)
    from openai import OpenAI

    client = OpenAI(max_retries=1, timeout=60.0)
    probes = build_oracle_probes()
    records = source_experience_records()
    base_prompts = base_memory_prompts(probes)
    padded_prompts, padding = _pad_prompts(client, base_prompts)
    inputs = {probe.probe_id: completion_input_text(probe.decision_input()) for probe in probes}

    def token_cell(item: tuple[str, str]) -> tuple[tuple[str, str], int]:
        probe_id, arm = item
        return item, _count(client, prompt=padded_prompts[arm], input_text=inputs[probe_id])

    pairs = [(probe.probe_id, arm) for probe in probes for arm in ARMS]
    with ThreadPoolExecutor(max_workers=4) as executor:
        token_counts = dict(executor.map(token_cell, pairs))
    for probe in probes:
        counts = {token_counts[(probe.probe_id, arm)] for arm in ARMS}
        if len(counts) != 1:
            raise ValueError(f"provider token counts differ within {probe.probe_id}: {counts}")

    cells = [
        {
            "probeId": probe.probe_id,
            "arm": arm,
            "repeat": repeat,
            "expectedInputTokens": token_counts[(probe.probe_id, arm)],
        }
        for probe in probes
        for arm in ARMS
        for repeat in range(1, REPEATS + 1)
    ]
    random.Random(SEED).shuffle(cells)
    plan = {
        "schemaVersion": "aip-liar-transfer-prereg-v1",
        "date": "2026-09-21",
        "sourceGames": ["guess-who", "love-letter-four-card-subgame"],
        "targetGame": "one-die-liars-dice",
        "model": MODEL,
        "reasoningEffort": "low",
        "maxOutputTokens": 4096,
        "maxAttemptsPerCell": 1,
        "repeats": REPEATS,
        "seed": SEED,
        "probes": [probe.to_artifact() for probe in probes],
        "sourceExperienceRecords": records,
        "sourceExperienceSha256": digest(records),
        "basePromptSha256": {arm: digest(base_prompts[arm]) for arm in ARMS},
        "prompts": padded_prompts,
        "paddingToken": PAD_TOKEN,
        "paddingTokenCounts": padding,
        "cellOrder": cells,
        "maxProviderCalls": len(cells),
        "primaryEndpoint": (
            "Mean exact conditional action regret against the independently solved "
            "equilibrium opponent, including preregistered penalties for invalid "
            "outputs; abstract_memory minus no_memory, paired by probe and repeat."
        ),
        "interpretationRule": (
            "A fixed-seed 10000-resample paired bootstrap interval wholly below zero "
            "is benefit, wholly above zero is harm, otherwise inconclusive."
        ),
        "controls": {
            "sameGame": "positive control excluded from transfer claim",
            "surfaceExperience": "negative/control arm with raw cross-game records",
            "tokenLength": "exact provider-counted full input tokens equal within every probe",
            "fullLoveLetterUsed": False,
        },
    }
    validate_plan(plan)
    return plan


def validate_plan(plan: dict[str, object]) -> None:
    if plan.get("schemaVersion") != "aip-liar-transfer-prereg-v1":
        raise ValueError("unsupported preregistration")
    if plan.get("sourceExperienceSha256") != digest(plan["sourceExperienceRecords"]):
        raise ValueError("source experience fingerprint mismatch")
    if plan.get("model") != MODEL or plan.get("repeats") != REPEATS:
        raise ValueError("model or repeat count changed")
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
        raise ValueError("provider-call budget differs from cell schedule")
    for probe_id in probes:
        counts = {
            cell["expectedInputTokens"]
            for cell in plan["cellOrder"]
            if cell["probeId"] == probe_id
        }
        if len(counts) != 1:
            raise ValueError("input tokens are not equal across arms")
    regenerated = {probe.probe_id: probe.to_artifact() for probe in build_oracle_probes()}
    if probes != regenerated:
        raise ValueError("independent Liar's Dice oracle changed")


def read_plan(path: Path) -> dict[str, object]:
    plan = json.loads(path.read_text(encoding="utf-8"))
    validate_plan(plan)
    return plan


def run(plan: dict[str, object], output: Path, env_file: Path) -> list[dict[str, object]]:
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
    if len(complete) != len(rows):
        raise ValueError("duplicate result cells")
    probes = {probe.probe_id: probe for probe in build_oracle_probes()}
    plan_probes = {probe["id"]: probe for probe in plan["probes"]}
    for index, cell in enumerate(plan["cellOrder"], start=1):
        key = cell["probeId"], cell["arm"], cell["repeat"]
        if key in complete:
            continue
        probe = probes[cell["probeId"]]
        penalty = plan_probes[probe.probe_id]["failurePenalty"]
        agent = CompletionBackedAgent(
            backend,
            plan["model"],
            _condition(cell["arm"]),
            condition_prompt=plan["prompts"][cell["arm"]],
            max_attempts=plan["maxAttemptsPerCell"],
        )
        row = {
            **cell,
            "status": "failed",
            "actionId": None,
            "penalizedActionRegret": penalty,
            "optimalPolicyAgreement": False,
            "beliefBrierToExactPosterior": None,
        }
        try:
            decision = agent.choose_action(probe.decision_input())
            evaluation = probe.evaluate(decision)
            row.update({
                "status": "valid",
                "actionId": decision.action_id,
                "penalizedActionRegret": evaluation["actionRegret"],
                "optimalPolicyAgreement": evaluation["optimalPolicyAgreement"],
                "beliefBrierToExactPosterior": evaluation["beliefBrierToExactPosterior"],
                "optimalActionIds": evaluation["optimalActionIds"],
            })
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
            "schemaVersion": "aip-liar-transfer-rows-v1",
            "preregistrationSha256": plan_sha,
            "rows": rows,
        })
        print(
            f"{index}/{len(plan['cellOrder'])} {probe.probe_id} {cell['arm']} "
            f"r{cell['repeat']}: {row['status']}", flush=True,
        )
    return rows


def build_report(plan: dict[str, object], rows: list[dict[str, object]]) -> dict[str, object]:
    transport_failures = sum(
        any(attempt["outcome"] == "transport_error" for attempt in row.get("telemetry", {}).get("attempts", []))
        for row in rows
    )
    token_mismatches = sum(not row.get("inputTokenMatch", False) for row in rows)
    resolved = sorted({
        attempt["resolved_model"]
        for row in rows
        for attempt in row.get("telemetry", {}).get("attempts", [])
        if attempt.get("resolved_model")
    })
    complete = len(rows) == plan["maxProviderCalls"]
    estimable = complete and transport_failures == 0 and token_mismatches == 0 and len(resolved) == 1
    return {
        "schemaVersion": "aip-liar-transfer-report-v1",
        "preregistrationSha256": digest(plan),
        "runStatus": "complete" if estimable else "infrastructure_or_protocol_failure",
        "completedCells": len(rows),
        "validDecisions": sum(row["status"] == "valid" for row in rows),
        "transportFailures": transport_failures,
        "inputTokenMismatches": token_mismatches,
        "resolvedModels": resolved,
        "targetOracle": target_oracle_metadata(),
        "analysis": analyze_results(plan, rows) if estimable else None,
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
