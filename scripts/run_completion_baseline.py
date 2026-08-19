#!/usr/bin/env python3
"""Run one real-model generic/single-game Guess Who pair and export traces."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from aip.benchmark import (
    CompletionAgentError,
    GuessWhoBenchmarkAdapter,
    OpenAIResponsesBackend,
    make_guess_who_completion_pair,
    run_episode,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the same OpenAI Responses model under two prompt conditions."
    )
    parser.add_argument("--model", required=True, help="Exact API model or snapshot ID")
    parser.add_argument("--secret", default="Ada", help="Guess Who hidden character")
    parser.add_argument("--max-attempts", type=int, default=3)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("completion-traces"),
    )
    args = parser.parse_args()
    if not os.environ.get("OPENAI_API_KEY"):
        parser.error("OPENAI_API_KEY is required for a real-model run")

    backend = OpenAIResponsesBackend()
    pair = make_guess_who_completion_pair(
        backend, args.model, max_attempts=args.max_attempts
    )
    conditions = (
        ("generic", pair.generic),
        ("single-game", pair.single_game),
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    report: dict[str, object] = {
        "model": args.model,
        "secret": args.secret,
        "conditions": {},
    }
    for label, agent in conditions:
        try:
            trace = run_episode(
                GuessWhoBenchmarkAdapter(
                    args.secret,
                    episode_id="guess-who:completion-pair",
                    include_rules=True,
                ),
                agent,
                agent_id=f"completion:{label}:{args.model}",
                agent_metadata=agent.agent_metadata(),
            )
        except CompletionAgentError as error:
            trace = None
            terminal_error = str(error)
        else:
            terminal_error = None
        telemetry = [item.as_dict() for item in agent.telemetry_history]
        condition_report = {
            "status": "completed" if trace else "failed",
            "terminalError": terminal_error,
            "calls": len(telemetry),
            "retries": sum(int(item["retryCount"]) for item in telemetry),
            "parseFailures": sum(
                int(item["parseFailureCount"]) for item in telemetry
            ),
            "validationFailures": sum(
                int(item["validationFailureCount"]) for item in telemetry
            ),
            "transportFailures": sum(
                int(item["transportFailureCount"]) for item in telemetry
            ),
            "totalTokens": sum(int(item["totalTokens"]) for item in telemetry),
            "totalLatencyMs": sum(
                float(item["totalLatencyMs"]) for item in telemetry
            ),
            "confidences": [item["finalConfidence"] for item in telemetry],
            "resolvedModels": sorted(
                {
                    str(attempt["resolved_model"])
                    for item in telemetry
                    for attempt in item["attempts"]
                    if attempt["resolved_model"] is not None
                }
            ),
        }
        if trace:
            trace_path = trace.write_json(args.output_dir / f"{label}.json")
            condition_report["trace"] = str(trace_path)
            condition_report["result"] = dict(trace.result)
        report["conditions"][label] = condition_report
    resolved_models = {
        model
        for condition in report["conditions"].values()
        for model in condition["resolvedModels"]
    }
    report["sameResolvedModel"] = len(resolved_models) == 1
    report["allConditionsCompleted"] = all(
        condition["status"] == "completed"
        for condition in report["conditions"].values()
    )
    report_path = args.output_dir / "report.json"
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, sort_keys=True, allow_nan=False))
    return (
        0
        if report["sameResolvedModel"] and report["allConditionsCompleted"]
        else 2
    )


if __name__ == "__main__":
    raise SystemExit(main())
