#!/usr/bin/env python3
"""Run the preregistered one-variable Mastermind output-ceiling diagnostic."""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict
from pathlib import Path

from aip.benchmark import (
    FROZEN_MASTERMIND_CEILING_DIAGNOSTIC_SHA256,
    FROZEN_MASTERMIND_CEILING_DIAGNOSTIC_V1,
    BudgetedCompletionBackend,
    MastermindBenchmarkAdapter,
    OpenAIResponsesBackend,
    load_dotenv_value,
    make_mastermind_completion_pair,
    run_episode,
    verify_frozen_ceiling_diagnostic,
)


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def telemetry(agent: object) -> dict[str, object]:
    history = tuple(agent.telemetry_history)
    attempts = tuple(attempt for item in history for attempt in item.attempts)
    return {
        "decisions": len(history),
        "providerAttempts": len(attempts),
        "retries": sum(item.retry_count for item in history),
        "parseFailures": sum(item.parse_failure_count for item in history),
        "validationFailures": sum(item.validation_failure_count for item in history),
        "transportFailures": sum(item.transport_failure_count for item in history),
        "inputTokens": sum(item.input_tokens for item in history),
        "outputTokens": sum(item.output_tokens for item in history),
        "totalTokens": sum(item.total_tokens for item in history),
        "attempts": [asdict(attempt) for attempt in attempts],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    args = parser.parse_args()
    protocol = FROZEN_MASTERMIND_CEILING_DIAGNOSTIC_V1
    verify_frozen_ceiling_diagnostic()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    plan = {
        "status": "prepared_before_api_calls",
        "protocolSha256": FROZEN_MASTERMIND_CEILING_DIAGNOSTIC_SHA256,
        "protocol": protocol.as_dict(),
    }
    write_json(args.output_dir / "protocol.json", plan)

    if not os.environ.get("OPENAI_API_KEY"):
        key = load_dotenv_value(args.env_file, "OPENAI_API_KEY")
        if key:
            os.environ["OPENAI_API_KEY"] = key
    if not os.environ.get("OPENAI_API_KEY"):
        parser.error("OPENAI_API_KEY is required")

    report: dict[str, object] = {
        "schemaVersion": "aip-mastermind-ceiling-diagnostic-v1",
        "protocol": plan,
        "trials": [],
        "budget": {},
    }
    progress = args.output_dir / "report.in-progress.json"
    journal = args.output_dir / "budget.journal.json"
    backend = BudgetedCompletionBackend(
        OpenAIResponsesBackend(
            reasoning_effort=protocol.reasoning_effort,
            max_output_tokens=protocol.max_output_tokens_per_request,
        ),
        max_provider_calls=protocol.max_provider_calls,
        reported_token_stop_threshold=protocol.reported_token_stop_threshold,
        on_usage=lambda usage: write_json(journal, dict(usage)),
    )
    for model in protocol.model_ids:
        pair = make_mastermind_completion_pair(
            backend, model, max_attempts=protocol.max_attempts_per_decision
        )
        for condition, agent in (
            ("generic", pair.generic),
            ("cross_game_experience", pair.cross_game),
        ):
            trace = None
            error_payload = None
            try:
                trace = run_episode(
                    MastermindBenchmarkAdapter(
                        protocol.secret,
                        episode_id="mastermind:ceiling-diagnostic:repeat-0",
                    ),
                    agent,
                    agent_id=f"completion:{model}:{condition}",
                    agent_metadata={
                        **agent.agent_metadata(),
                        "protocolSha256": FROZEN_MASTERMIND_CEILING_DIAGNOSTIC_SHA256,
                        "heldOut": True,
                    },
                    max_steps=10,
                )
            except Exception as error:
                error_payload = {
                    "type": error.__class__.__name__,
                    "message": " ".join(str(error).split())[:240],
                }
            trial: dict[str, object] = {
                "requestedModel": model,
                "condition": condition,
                "status": "completed" if trace else "failed",
                "terminalError": error_payload,
                "telemetry": telemetry(agent),
            }
            if trace:
                trace_path = args.output_dir / "traces" / f"{model}__{condition}.json"
                trace_path.parent.mkdir(parents=True, exist_ok=True)
                trace.write_json(trace_path)
                trial["trace"] = str(trace_path)
                trial["result"] = dict(trace.result)
            report["trials"].append(trial)
            report["budget"] = backend.usage()
            write_json(progress, report)

    incomplete = [
        attempt
        for trial in report["trials"]
        for attempt in trial["telemetry"]["attempts"]
        if attempt["incomplete_reason"] == "max_output_tokens"
    ]
    all_completed = all(trial["status"] == "completed" for trial in report["trials"])
    report["summary"] = {
        "plannedEpisodes": 4,
        "completedEpisodes": sum(
            trial["status"] == "completed" for trial in report["trials"]
        ),
        "maxOutputTokenIncompleteResponses": len(incomplete),
        "allEpisodesCompleted": all_completed,
        "ceilingDiagnosisPassed": all_completed and not incomplete,
        "changesFromSmokeV1": ["max_output_tokens_per_request: 2048 -> 8192"],
        "transferGainClaimed": False,
    }
    report["budget"] = backend.usage()
    write_json(args.output_dir / "report.json", report)
    progress.unlink(missing_ok=True)
    print(json.dumps(report["summary"], indent=2, sort_keys=True))
    return 0 if report["summary"]["ceilingDiagnosisPassed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
