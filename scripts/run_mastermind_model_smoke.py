#!/usr/bin/env python3
"""Prepare and execute the frozen two-model/two-repeat Mastermind smoke test."""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict
from pathlib import Path
from statistics import mean

from aip.benchmark import (
    FROZEN_MASTERMIND_SMOKE_PROTOCOL_SHA256,
    FROZEN_MASTERMIND_SMOKE_PROTOCOL_V1,
    FROZEN_TRANSFER_BUNDLE_V1,
    BudgetedCompletionBackend,
    MastermindBenchmarkAdapter,
    OpenAIResponsesBackend,
    audit_mastermind_holdout,
    load_dotenv_value,
    make_mastermind_completion_pair,
    run_episode,
    verify_frozen_smoke_protocol,
)


MODEL_PRICES_PER_MILLION = {
    "gpt-5.6-luna": {"input": 0.20, "output": 1.20},
    "gpt-5.6-terra": {"input": 2.00, "output": 12.00},
}
PRICE_SOURCE = "https://developers.openai.com/api/docs/models/"


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def prepare_plan(path: Path) -> dict[str, object]:
    verify_frozen_smoke_protocol()
    audit = audit_mastermind_holdout(FROZEN_TRANSFER_BUNDLE_V1)
    if not audit.passed:
        raise RuntimeError(f"held-out leakage audit failed: {audit.findings}")
    plan = {
        "status": "prepared_before_api_calls",
        "protocolSha256": FROZEN_MASTERMIND_SMOKE_PROTOCOL_SHA256,
        "protocol": FROZEN_MASTERMIND_SMOKE_PROTOCOL_V1.as_dict(),
        "leakageAudit": {
            "passed": audit.passed,
            "findings": list(audit.findings),
            "manifest": dict(audit.manifest),
        },
    }
    _write_json(path, plan)
    return plan


def _validate_plan(path: Path) -> dict[str, object]:
    verify_frozen_smoke_protocol()
    plan = json.loads(path.read_text(encoding="utf-8"))
    expected = {
        "status": "prepared_before_api_calls",
        "protocolSha256": FROZEN_MASTERMIND_SMOKE_PROTOCOL_SHA256,
        "protocol": FROZEN_MASTERMIND_SMOKE_PROTOCOL_V1.as_dict(),
        "leakageAudit": {
            "passed": True,
            "findings": [],
            "manifest": dict(audit_mastermind_holdout(FROZEN_TRANSFER_BUNDLE_V1).manifest),
        },
    }
    if plan != expected:
        raise ValueError("prepared smoke plan does not match the frozen v1 protocol")
    return plan


def _telemetry_summary(agent: object) -> dict[str, object]:
    history = tuple(agent.telemetry_history)
    attempts = tuple(attempt for item in history for attempt in item.attempts)
    return {
        "decisionInvocations": len(history),
        "providerAttempts": len(attempts),
        "retries": sum(item.retry_count for item in history),
        "parseFailures": sum(item.parse_failure_count for item in history),
        "validationFailures": sum(item.validation_failure_count for item in history),
        "transportFailures": sum(item.transport_failure_count for item in history),
        "inputTokens": sum(item.input_tokens for item in history),
        "outputTokens": sum(item.output_tokens for item in history),
        "totalTokens": sum(item.total_tokens for item in history),
        "totalLatencyMs": sum(item.total_latency_ms for item in history),
        "confidences": [item.final_confidence for item in history],
        "resolvedModels": sorted(
            {
                attempt.resolved_model
                for attempt in attempts
                if attempt.resolved_model is not None
            }
        ),
        "attempts": [asdict(attempt) for attempt in attempts],
    }


def _safe_error(error: Exception) -> dict[str, str]:
    return {
        "type": error.__class__.__name__,
        "message": " ".join(str(error).split())[:240],
    }


def _estimated_cost(model: str, telemetry: dict[str, object]) -> float:
    price = MODEL_PRICES_PER_MILLION[model]
    return (
        int(telemetry["inputTokens"]) * price["input"]
        + int(telemetry["outputTokens"]) * price["output"]
    ) / 1_000_000


def analyze_report(report: dict[str, object]) -> dict[str, object]:
    trials = list(report["trials"])
    groups: dict[str, object] = {}
    for condition in FROZEN_MASTERMIND_SMOKE_PROTOCOL_V1.conditions:
        selected = [trial for trial in trials if trial["condition"] == condition]
        completed = [trial for trial in selected if trial["status"] == "completed"]
        groups[condition] = {
            "episodes": len(selected),
            "completedEpisodes": len(completed),
            "completionRate": len(completed) / len(selected),
            "solvedRateAmongCompleted": (
                mean(bool(trial["result"]["solved"]) for trial in completed)
                if completed
                else None
            ),
            "meanAttemptsAmongCompleted": (
                mean(int(trial["result"]["attempts"]) for trial in completed)
                if completed
                else None
            ),
            "meanHeuristicAgreementAmongCompleted": (
                mean(float(trial["meanHeuristicAgreement"]) for trial in completed)
                if completed
                else None
            ),
            "meanBeliefOutputRateAmongCompleted": (
                mean(float(trial["beliefOutputRate"]) for trial in completed)
                if completed
                else None
            ),
            "meanOfEpisodeBeliefBrierAmongCompleted": (
                mean(float(trial["meanBeliefBrier"]) for trial in completed)
                if completed
                else None
            ),
        }
    empty_at_cap = sum(
        attempt["outcome"] == "parse_error"
        and attempt["output_characters"] == 0
        and attempt["output_tokens"]
        == FROZEN_MASTERMIND_SMOKE_PROTOCOL_V1.max_output_tokens_per_request
        for trial in trials
        for attempt in trial["telemetry"].get("attempts", [])
    )
    return {
        "evidenceLevel": "exploratory_llm_behavior",
        "primaryPurpose": "completion_and_scoring_reliability_smoke",
        "conditionSummary": groups,
        "emptyOutputsAtExactOutputTokenCap": empty_at_cap,
        "reliabilityGatePassed": (
            len(trials) == FROZEN_MASTERMIND_SMOKE_PROTOCOL_V1.planned_episodes
            and all(trial["status"] == "completed" for trial in trials)
            and empty_at_cap == 0
        ),
        "transferGainClaimed": False,
        "interpretation": (
            "Directional condition differences are not a transfer estimate: the "
            "panel has only two repeats, two failed episodes, and one interrupted "
            "request with unknown reported-token usage."
        ),
    }


def execute(
    plan_path: Path,
    output_dir: Path,
    env_file: Path,
    *,
    resume_path: Path | None = None,
    reserve_interrupted_calls: int = 0,
) -> tuple[dict[str, object], bool]:
    plan = _validate_plan(plan_path)
    protocol = FROZEN_MASTERMIND_SMOKE_PROTOCOL_V1
    if not os.environ.get("OPENAI_API_KEY"):
        key = load_dotenv_value(env_file, "OPENAI_API_KEY")
        if key:
            os.environ["OPENAI_API_KEY"] = key
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is required in the environment or .env")

    output_dir.mkdir(parents=True, exist_ok=True)
    partial_path = output_dir / "report.in-progress.json"
    budget_journal = output_dir / "budget.journal.json"
    if resume_path is not None:
        report = json.loads(resume_path.read_text(encoding="utf-8"))
        if report.get("plan") != plan:
            raise ValueError("resume report does not use the prepared frozen plan")
        prior_budget = dict(report["budget"])
        report.setdefault("incidents", []).append(
            {
                "kind": "interrupted_provider_request",
                "reservedProviderCalls": reserve_interrupted_calls,
                "reportedTokensUnknown": reserve_interrupted_calls > 0,
                "note": (
                    "The interrupted request is reserved against the call ceiling; "
                    "its token usage was unavailable locally."
                ),
            }
        )
    else:
        prior_budget = {
            "providerCalls": 0,
            "reportedTokens": 0,
            "inputTokens": 0,
            "outputTokens": 0,
        }
        report = {
            "reportSchemaVersion": "aip-mastermind-model-smoke-v1",
            "status": "running",
            "plan": plan,
            "trials": [],
            "budget": {},
        }

    raw_backend = OpenAIResponsesBackend(
        reasoning_effort=protocol.reasoning_effort,
        max_output_tokens=protocol.max_output_tokens_per_request,
    )
    backend = BudgetedCompletionBackend(
        raw_backend,
        max_provider_calls=protocol.max_provider_calls,
        reported_token_stop_threshold=protocol.reported_token_stop_threshold,
        initial_provider_calls=int(prior_budget["providerCalls"])
        + reserve_interrupted_calls,
        initial_reported_tokens=int(prior_budget["reportedTokens"]),
        initial_input_tokens=int(prior_budget["inputTokens"]),
        initial_output_tokens=int(prior_budget["outputTokens"]),
        on_usage=lambda usage: _write_json(budget_journal, dict(usage)),
    )
    report["budget"] = backend.usage()
    completed_trial_ids = {trial["trialId"] for trial in report["trials"]}

    for repeat in range(protocol.repeats):
        for model in protocol.model_ids:
            pair = make_mastermind_completion_pair(
                backend,
                model,
                max_attempts=protocol.max_attempts_per_decision,
            )
            for condition, agent in (
                ("generic", pair.generic),
                ("cross_game_experience", pair.cross_game),
            ):
                trial_id = f"repeat-{repeat}:{model}:{condition}"
                if trial_id in completed_trial_ids:
                    continue
                trace = None
                terminal_error = None
                try:
                    trace = run_episode(
                        MastermindBenchmarkAdapter(
                            protocol.secret,
                            episode_id=f"mastermind:smoke:repeat-{repeat}",
                        ),
                        agent,
                        agent_id=f"completion:{model}:{condition}",
                        agent_metadata={
                            **agent.agent_metadata(),
                            "repeat": repeat,
                            "protocolSha256": FROZEN_MASTERMIND_SMOKE_PROTOCOL_SHA256,
                            "heldOut": True,
                        },
                        max_steps=10,
                    )
                except Exception as error:
                    terminal_error = _safe_error(error)
                telemetry = _telemetry_summary(agent)
                trial: dict[str, object] = {
                    "trialId": trial_id,
                    "repeat": repeat,
                    "requestedModel": model,
                    "condition": condition,
                    "status": "completed" if trace else "failed",
                    "terminalError": terminal_error,
                    "telemetry": telemetry,
                    "estimatedUncachedUsd": _estimated_cost(model, telemetry),
                }
                if trace is not None:
                    trace_path = output_dir / "traces" / f"{trial_id.replace(':', '__')}.json"
                    trace_path.parent.mkdir(parents=True, exist_ok=True)
                    trace.write_json(trace_path)
                    trial["trace"] = str(trace_path)
                    trial["result"] = dict(trace.result)
                    trial["meanHeuristicAgreement"] = mean(
                        bool(step.evaluation["heuristicReferenceAgreement"])
                        for step in trace.steps
                    )
                    belief_steps = tuple(
                        step
                        for step in trace.steps
                        if step.evaluation["beliefBrier"] is not None
                    )
                    trial["beliefOutputRate"] = len(belief_steps) / len(trace.steps)
                    trial["meanBeliefBrier"] = (
                        mean(float(step.evaluation["beliefBrier"]) for step in belief_steps)
                        if belief_steps
                        else None
                    )
                report["trials"].append(trial)
                report["budget"] = backend.usage()
                _write_json(partial_path, report)

    trials = report["trials"]
    all_completed = all(trial["status"] == "completed" for trial in trials)
    resolved_match = all(
        trial["telemetry"]["resolvedModels"] == [trial["requestedModel"]]
        for trial in trials
        if trial["status"] == "completed"
    )
    report["status"] = "completed" if all_completed and resolved_match else "completed_with_failures"
    report["summary"] = {
        "plannedEpisodes": protocol.planned_episodes,
        "completedEpisodes": sum(trial["status"] == "completed" for trial in trials),
        "failedEpisodes": sum(trial["status"] != "completed" for trial in trials),
        "allResolvedModelsMatchRequested": resolved_match,
        "totalRetries": sum(trial["telemetry"]["retries"] for trial in trials),
        "totalParseFailures": sum(trial["telemetry"]["parseFailures"] for trial in trials),
        "totalValidationFailures": sum(
            trial["telemetry"]["validationFailures"] for trial in trials
        ),
        "estimatedUncachedUsd": sum(trial["estimatedUncachedUsd"] for trial in trials),
        "pricingAssumption": (
            "Estimate uses current listed uncached text input/output prices; actual "
            "billing may differ due to caching or account terms."
        ),
        "pricingSource": PRICE_SOURCE,
    }
    report["budget"] = backend.usage()
    report["analysis"] = analyze_report(report)
    _write_json(output_dir / "report.json", report)
    if partial_path.exists():
        partial_path.unlink()
    return report, all_completed and resolved_match


def main() -> int:
    parser = argparse.ArgumentParser()
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--prepare", type=Path)
    modes.add_argument("--execute", type=Path, metavar="PLAN")
    modes.add_argument("--analyze", type=Path, metavar="REPORT")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--analysis-output", type=Path)
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--resume", type=Path)
    parser.add_argument("--reserve-interrupted-calls", type=int, default=0)
    args = parser.parse_args()
    if args.prepare:
        prepare_plan(args.prepare)
        print(args.prepare)
        return 0
    if args.analyze:
        if args.analysis_output is None:
            parser.error("--analysis-output is required with --analyze")
        report = json.loads(args.analyze.read_text(encoding="utf-8"))
        analysis = analyze_report(report)
        _write_json(args.analysis_output, analysis)
        print(args.analysis_output)
        return 0
    if args.output_dir is None:
        parser.error("--output-dir is required with --execute")
    if args.reserve_interrupted_calls < 0:
        parser.error("--reserve-interrupted-calls cannot be negative")
    report, passed = execute(
        args.execute,
        args.output_dir,
        args.env_file,
        resume_path=args.resume,
        reserve_interrupted_calls=args.reserve_interrupted_calls,
    )
    print(json.dumps(report["summary"], indent=2, sort_keys=True))
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
