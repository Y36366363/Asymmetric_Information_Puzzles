#!/usr/bin/env python3
"""Preregister, run and score the frozen four-arm held-out Guess Who probe."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from aip.benchmark.completion import (
    CompletionAgentError,
    CompletionBackedAgent,
    OpenAIResponsesBackend,
    PromptCondition,
    load_dotenv_value,
)
from aip.benchmark.focused_transfer import (
    analyze_results,
    digest,
    make_preregistration,
    probe_adapter,
    public_probe_fingerprint,
    validate_preregistration,
)


DEFAULT_OUTPUT = Path("research/results/focused_transfer_2026-09-20")
DEFAULT_SOURCES = (
    Path("research/results/love_letter_liar_algorithm_audit_2026-09-19.json"),
    Path("research/results/one_die_liar_exact_2026-09-18.json"),
)


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def read_plan(path: Path) -> dict[str, object]:
    plan = json.loads(path.read_text(encoding="utf-8"))
    validate_preregistration(plan)
    for source in plan["sourceArtifacts"]:
        if digest(Path(source["path"]).read_text(encoding="utf-8")) != source["sha256"]:
            raise ValueError(f"source audit changed: {source['path']}")
    return plan


def _condition(arm: str) -> PromptCondition:
    if arm == "no_memory":
        return PromptCondition.GENERIC
    if arm == "same_game":
        return PromptCondition.SINGLE_GAME
    return PromptCondition.CROSS_GAME_EXPERIENCE


def run_cells(plan: dict[str, object], results_path: Path, env_file: Path) -> list[dict[str, object]]:
    if not os.environ.get("OPENAI_API_KEY"):
        key = load_dotenv_value(env_file, "OPENAI_API_KEY")
        if key:
            os.environ["OPENAI_API_KEY"] = key
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is unavailable; no model calls made")
    from openai import OpenAI

    backend = OpenAIResponsesBackend(
        client=OpenAI(max_retries=0, timeout=60.0),
        reasoning_effort=plan["reasoningEffort"],
        max_output_tokens=plan["maxOutputTokens"],
    )
    plan_sha = digest(plan)
    if results_path.exists():
        envelope = json.loads(results_path.read_text(encoding="utf-8"))
        if envelope.get("preregistrationSha256") != plan_sha:
            raise ValueError("existing results were produced from a different plan")
        rows = envelope["rows"]
    else:
        rows = []
    completed = {(row["probeId"], row["arm"]) for row in rows}
    if len(completed) != len(rows):
        raise ValueError("duplicate completed cells")
    probes = {probe["id"]: probe for probe in plan["probes"]}
    for index, cell in enumerate(plan["cellOrder"], start=1):
        probe_id, arm = cell["probeId"], cell["arm"]
        if (probe_id, arm) in completed:
            continue
        if len(rows) >= plan["maxProviderCalls"]:
            raise RuntimeError("provider-call budget exhausted")
        probe = probes[probe_id]
        adapter = probe_adapter(probe["secret"], probe["depth"])
        if public_probe_fingerprint(adapter) != probe["publicStateSha256"]:
            raise ValueError("probe changed since preregistration")
        agent = CompletionBackedAgent(
            backend,
            plan["model"],
            _condition(arm),
            condition_prompt=plan["memoryPrompts"][arm],
            max_attempts=plan["maxAttemptsPerCell"],
        )
        row: dict[str, object] = {
            "probeId": probe_id,
            "arm": arm,
            "status": "failed",
            "penalizedRegretTurns": probe["failurePenaltyTurns"],
            "beliefBrier": None,
            "actionId": None,
            "totalTokens": 0,
        }
        try:
            decision = agent.choose_action(adapter.decision_input())
            evaluation = adapter.apply_decision(decision).evaluation
            row.update({
                "status": "valid",
                "penalizedRegretTurns": float(evaluation["actionRegret"]),
                "beliefBrier": evaluation["beliefBrier"],
                "actionId": decision.action_id,
            })
        except CompletionAgentError as error:
            row["errorType"] = error.__class__.__name__
        except Exception as error:
            row["errorType"] = error.__class__.__name__
        if agent.telemetry_history:
            telemetry = agent.telemetry_history[-1].as_dict()
            row["telemetry"] = telemetry
            row["totalTokens"] = telemetry["totalTokens"]
        rows.append(row)
        completed.add((probe_id, arm))
        write_json(results_path, {
            "schemaVersion": "aip-focused-transfer-rows-v1",
            "preregistrationSha256": plan_sha,
            "rows": rows,
        })
        print(f"{index}/{len(plan['cellOrder'])} {probe_id} {arm}: {row['status']}", flush=True)
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("prepare", "run", "analyze"))
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument(
        "--trial-tag", default="", help="separate run label; preserves earlier trial evidence"
    )
    args = parser.parse_args()
    if args.trial_tag and not args.trial_tag.replace("-", "").replace("_", "").isalnum():
        parser.error("trial tag must contain only letters, numbers, hyphens or underscores")
    suffix = f"_{args.trial_tag}" if args.trial_tag else ""
    plan_path = args.output_dir / "preregistration.json"
    results_path = args.output_dir / f"trial_rows{suffix}.json"
    if args.phase == "prepare":
        proposed = make_preregistration(DEFAULT_SOURCES)
        validate_preregistration(proposed)
        if plan_path.exists():
            if read_plan(plan_path) != proposed:
                raise ValueError("existing preregistration differs; refusing to rewrite it")
        else:
            write_json(plan_path, proposed)
        print(json.dumps({"preregistration": str(plan_path), "sha256": digest(proposed)}))
        return 0
    plan = read_plan(plan_path)
    if args.phase == "run":
        rows = run_cells(plan, results_path, args.env_file)
    else:
        rows = json.loads(results_path.read_text(encoding="utf-8"))["rows"]
    transport_failures = sum(
        any(attempt["outcome"] == "transport_error" for attempt in row.get("telemetry", {}).get("attempts", []))
        for row in rows
    )
    valid_decisions = sum(row["status"] == "valid" for row in rows)
    resolved_models = sorted({
        attempt["resolved_model"]
        for row in rows
        for attempt in row.get("telemetry", {}).get("attempts", [])
        if attempt["resolved_model"] is not None
    })
    estimable = (
        valid_decisions > 0
        and transport_failures == 0
        and len(resolved_models) == 1
    )
    report = {
        "schemaVersion": "aip-focused-transfer-report-v1",
        "preregistrationSha256": digest(plan),
        "model": plan["model"],
        "completedCells": len(rows),
        "runStatus": "complete" if estimable else "infrastructure_or_completion_failure",
        "transportFailures": transport_failures,
        "validDecisions": valid_decisions,
        "resolvedModels": resolved_models,
        "analysis": analyze_results(plan, rows) if estimable else None,
    }
    write_json(args.output_dir / f"report{suffix}.json", report)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if estimable else 2


if __name__ == "__main__":
    raise SystemExit(main())
