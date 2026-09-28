#!/usr/bin/env python3
"""Run the explicit-prior/fixed-policy value check on Liar then Goofspiel."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import time
from pathlib import Path
from statistics import mean

from aip.benchmark.completion import (
    CompletionRequest,
    OpenAIResponsesBackend,
    PromptCondition,
    completion_input_text,
)
from aip.benchmark.liar_transfer import canonical_json, digest
from aip.benchmark.value_decomposition import (
    CONDITIONED_VALUE_DECOMPOSITION_JSON_SCHEMA,
    ConditionedValueDecomposition,
    condition_value_decomposition,
    parse_conditioned_value_decomposition,
    score_conditioned_value_decomposition,
)
from scripts.run_liar_positive_control_check import MODEL, ensure_key, write_json
from scripts.run_structured_value_manipulation import _game_material
from aip.puzzles.liars_dice import OneDieLiarDiceCFRGame, OneDieLiarState


ROOT = Path(__file__).resolve().parents[1]
DATE = "2026-09-28"
SEED = 20260928
REPEATS = 2
PROBE_COUNT = 6
PROTOCOL_ID = "fixed_policy_belief_value_v2"
SCHEMA_NAME = "aip_conditioned_value_decomposition"
GATE = {
    "allCellsValid": True,
    "inputTokenMismatches": 0,
    "minimumRepeatActionAgreement": 0.80,
    "minimumOptimalActionRate": 0.95,
    "maximumMeanBasePriorBrier": 1e-6,
    "maximumMeanPolicyReachWeightMae": 1e-6,
    "maximumMeanConditionedPosteriorBrier": 1e-6,
    "maximumMeanImmediateValueMae": 1e-6,
    "maximumMeanContinuationValueMae": 1e-6,
    "maximumMeanTotalValueMae": 1e-6,
    "maximumAdditivityResidual": 1e-6,
}
DEFAULT_OUTPUTS = {
    "liar": ROOT / "research/results/liar_fixed_policy_value_check_v2_2026-09-28",
    "goofspiel": ROOT / "research/results/goofspiel_fixed_policy_value_check_v2_2026-09-28",
}
DEFAULT_LIAR_REPORT = DEFAULT_OUTPUTS["liar"] / "report.json"

INSTRUCTIONS = """You are executing a declared Bayesian decision program, not
inferring which opponent strategy is in force. Use every listed hidden-state label.
First set base_prior to the uniform distribution over those labels. Copy the supplied
relative policy reach weight for each label. Compute conditioned_posterior by
normalizing base_prior[state] * policy_reach_weight[state]. For every legal action,
compute immediate_value as the conditioned-posterior weighted mean of the supplied
per-state immediate-payoff table; copy the supplied continuation-value anchor; and
set total_value to their sum. Values are from the acting player's perspective. Choose
a legal action with maximum total_value.
Return only the required JSON. Do not provide private reasoning or explanations."""


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _reference(game: str, probe, oracle) -> ConditionedValueDecomposition:
    values = oracle.decompose(probe)
    labels = tuple(values.posterior)
    uniform = {label: 1.0 / len(labels) for label in labels}
    return condition_value_decomposition(values, uniform)


def _immediate_payoff_table(game: str, probe) -> dict[str, dict[str, float]]:
    if game == "liar":
        liar_game = OneDieLiarDiceCFRGame()
        result = {}
        for action in probe.exact_action_values:
            result[action] = {}
            for label in probe.exact_posterior:
                if action != "challenge":
                    payoff = 0.0
                else:
                    opponent_die = int(label)
                    dice = (
                        (probe.own_die, opponent_die)
                        if probe.player == 0
                        else (opponent_die, probe.own_die)
                    )
                    terminal = OneDieLiarState(
                        dice=dice, bids=probe.bids, challenger=probe.player
                    )
                    utility = liar_game.utility_player_zero(terminal)
                    payoff = float(utility if probe.player == 0 else -utility)
                result[action][label] = payoff
        return result
    if game == "goofspiel":
        result = {}
        for player_bid in probe.player_cards:
            action = f"bid:{player_bid}"
            result[action] = {
                str(opponent_bid): float(
                    probe.current_prize
                    * ((player_bid > opponent_bid) - (player_bid < opponent_bid))
                )
                for opponent_bid in probe.opponent_cards
            }
        return result
    raise ValueError(f"unsupported game: {game}")


def _context(game: str, probe, reference: ConditionedValueDecomposition) -> dict[str, object]:
    return {
        "protocolId": PROTOCOL_ID,
        "basePriorDefinition": "uniform_over_all_listed_hidden_states",
        "policyReachWeightSemantics": (
            "fixed externally supplied relative reach; scale is arbitrary and "
            "posterior is normalize(base_prior * weight)"
        ),
        "hiddenStateLabels": sorted(reference.base_prior),
        "fixedPolicyReachWeights": dict(reference.policy_reach_weights),
        "immediatePayoffByActionAndHiddenState": _immediate_payoff_table(game, probe),
        "continuationValueAnchors": dict(
            reference.values.continuation_action_values
        ),
        "claimScope": (
            "calculation manipulation check only; supplied policy and continuation "
            "anchors are not independent solving or transfer evidence"
        ),
    }


def _input_text(game: str, probe, reference) -> str:
    return (
        completion_input_text(probe.decision_input())
        + "\nDECLARED_FIXED_POLICY_CONTEXT="
        + canonical_json(_context(game, probe, reference))
    )


def _count(client, input_text: str) -> int:
    response = client.responses.input_tokens.count(
        model=MODEL,
        instructions=INSTRUCTIONS,
        input=input_text,
        text={
            "format": {
                "type": "json_schema",
                "name": SCHEMA_NAME,
                "strict": True,
                "schema": CONDITIONED_VALUE_DECOMPOSITION_JSON_SCHEMA,
            }
        },
        reasoning={"effort": "low"},
    )
    return int(response.input_tokens)


def require_liar_gate(path: Path) -> dict[str, object]:
    report = json.loads(path.read_text(encoding="utf-8"))
    if report.get("schemaVersion") != "aip-fixed-policy-value-report-v1":
        raise ValueError("Goofspiel prerequisite is not a fixed-policy report")
    if report.get("game") != "liar" or report.get("gatePassed") is not True:
        raise ValueError("Goofspiel is blocked until the redefined Liar gate passes")
    return report


def prepare_plan(game: str, env_file: Path, liar_report: Path) -> dict[str, object]:
    ensure_key(env_file)
    from openai import OpenAI

    prerequisite = require_liar_gate(liar_report) if game == "goofspiel" else None
    probes, oracle = _game_material(game)
    references = {
        probe.probe_id: _reference(game, probe, oracle) for probe in probes
    }
    client = OpenAI(max_retries=1, timeout=60.0)
    inputs = {
        probe.probe_id: _input_text(game, probe, references[probe.probe_id])
        for probe in probes
    }
    counts = {probe_id: _count(client, text) for probe_id, text in inputs.items()}
    cells = [
        {
            "probeId": probe.probe_id,
            "repeat": repeat,
            "expectedInputTokens": counts[probe.probe_id],
        }
        for probe in probes
        for repeat in range(1, REPEATS + 1)
    ]
    random.Random(SEED + (game == "goofspiel")).shuffle(cells)
    plan = {
        "schemaVersion": "aip-fixed-policy-value-prereg-v1",
        "date": DATE,
        "game": game,
        "protocolId": PROTOCOL_ID,
        "model": MODEL,
        "reasoningEffort": "low",
        "maxOutputTokens": 4096,
        "maxAttemptsPerCell": 1,
        "seed": SEED,
        "repeats": REPEATS,
        "probeCount": PROBE_COUNT,
        "gate": GATE,
        "instructions": INSTRUCTIONS,
        "instructionsSha256": digest(INSTRUCTIONS),
        "oracleId": oracle.oracle_id,
        "probes": [probe.to_artifact() for probe in probes],
        "declaredContexts": {
            probe.probe_id: _context(game, probe, references[probe.probe_id])
            for probe in probes
        },
        "references": {
            probe_id: reference.to_artifact()
            for probe_id, reference in references.items()
        },
        "cellOrder": cells,
        "maxProviderCalls": len(cells),
        "prerequisite": (
            None if prerequisite is None else {
                "game": "liar",
                "reportSha256": digest(prerequisite),
                "gatePassed": True,
            }
        ),
        "claimRestriction": (
            "The model receives fixed reach weights and continuation anchors. This "
            "tests Bayesian normalization, immediate payoff calculation, value "
            "composition, and action selection—not equilibrium discovery."
        ),
        "nextStepRule": (
            "Prepare identical Goofspiel protocol only if every Liar gate passes."
            if game == "liar"
            else "Consider the 17 positive-reach Love Letter states only if every Goofspiel gate passes."
        ),
    }
    validate_plan(plan)
    return plan


def validate_plan(plan: dict[str, object]) -> None:
    if plan.get("schemaVersion") != "aip-fixed-policy-value-prereg-v1":
        raise ValueError("unsupported fixed-policy preregistration")
    game = plan.get("game")
    if game not in {"liar", "goofspiel"}:
        raise ValueError("unsupported game")
    if plan.get("protocolId") != PROTOCOL_ID or plan.get("gate") != GATE:
        raise ValueError("protocol or frozen gate changed")
    if plan.get("model") != MODEL or plan.get("instructions") != INSTRUCTIONS:
        raise ValueError("model or instructions changed")
    probes, oracle = _game_material(str(game))
    if len(probes) != PROBE_COUNT:
        raise ValueError("frozen panel must contain six probes")
    if {item["id"]: item for item in plan["probes"]} != {
        probe.probe_id: probe.to_artifact() for probe in probes
    }:
        raise ValueError("probe panel changed")
    references = {
        probe.probe_id: _reference(str(game), probe, oracle) for probe in probes
    }
    if plan.get("references") != {
        key: value.to_artifact() for key, value in references.items()
    }:
        raise ValueError("conditioned reference changed")
    if plan.get("declaredContexts") != {
        probe.probe_id: _context(str(game), probe, references[probe.probe_id])
        for probe in probes
    }:
        raise ValueError("declared fixed-policy context changed")
    expected = {
        (probe.probe_id, repeat)
        for probe in probes for repeat in range(1, REPEATS + 1)
    }
    actual = [(cell["probeId"], cell["repeat"]) for cell in plan["cellOrder"]]
    if len(actual) != len(expected) or set(actual) != expected:
        raise ValueError("cell schedule is incomplete or duplicated")
    if plan.get("maxProviderCalls") != len(actual):
        raise ValueError("provider-call budget differs from schedule")


def read_plan(path: Path) -> dict[str, object]:
    plan = json.loads(path.read_text(encoding="utf-8"))
    validate_plan(plan)
    return plan


def execute_plan(plan, rows_path: Path, env_file: Path):
    ensure_key(env_file)
    from openai import OpenAI

    probes, oracle = _game_material(plan["game"])
    by_id = {probe.probe_id: probe for probe in probes}
    references = {
        probe.probe_id: _reference(plan["game"], probe, oracle) for probe in probes
    }
    backend = OpenAIResponsesBackend(
        client=OpenAI(max_retries=0, timeout=60.0),
        reasoning_effort=plan["reasoningEffort"],
        max_output_tokens=plan["maxOutputTokens"],
    )
    plan_sha = digest(plan)
    rows = []
    if rows_path.exists():
        envelope = json.loads(rows_path.read_text(encoding="utf-8"))
        if envelope.get("preregistrationSha256") != plan_sha:
            raise ValueError("existing rows belong to another preregistration")
        rows = envelope["rows"]
    complete = {(row["probeId"], row["repeat"]) for row in rows}
    for index, cell in enumerate(plan["cellOrder"], start=1):
        key = cell["probeId"], cell["repeat"]
        if key in complete:
            continue
        probe = by_id[cell["probeId"]]
        reference = references[probe.probe_id]
        request = CompletionRequest(
            model=plan["model"],
            condition=PromptCondition.SINGLE_GAME,
            instructions=plan["instructions"],
            input_text=_input_text(plan["game"], probe, reference),
            response_schema=CONDITIONED_VALUE_DECOMPOSITION_JSON_SCHEMA,
            response_schema_name=SCHEMA_NAME,
        )
        started = time.perf_counter()
        row = {**cell, "status": "failed"}
        try:
            response = backend.complete(request)
            candidate = parse_conditioned_value_decomposition(response.output_text)
            score = score_conditioned_value_decomposition(candidate, reference)
            row.update(
                status="valid",
                chosenActionId=candidate.values.chosen_action_id,
                decomposition=candidate.to_artifact(),
                score=score.to_artifact(),
                responseStatus=response.status,
                incompleteReason=response.incomplete_reason,
                responseId=response.response_id,
                resolvedModel=response.resolved_model,
                observedInputTokens=response.input_tokens,
                outputTokens=response.output_tokens,
                totalTokens=response.total_tokens,
                outputSha256=_sha256(response.output_text),
            )
        except Exception as error:
            row.update(
                errorType=error.__class__.__name__,
                errorMessage=str(error)[:500],
                observedInputTokens=0,
            )
        row["latencyMs"] = (time.perf_counter() - started) * 1000
        row["inputTokenMatch"] = (
            row["observedInputTokens"] == row["expectedInputTokens"]
        )
        rows.append(row)
        complete.add(key)
        write_json(rows_path, {
            "schemaVersion": "aip-fixed-policy-value-rows-v1",
            "preregistrationSha256": plan_sha,
            "rows": rows,
        })
        print(
            f"{index}/{len(plan['cellOrder'])} {probe.probe_id} r{cell['repeat']}: {row['status']}",
            flush=True,
        )
    return rows


def build_report(plan, rows):
    valid = [row for row in rows if row["status"] == "valid"]
    grouped = {}
    for row in rows:
        grouped.setdefault(row["probeId"], []).append(row)
    agreements = [
        len(group) == REPEATS
        and all(row["status"] == "valid" for row in group)
        and len({row.get("chosenActionId") for row in group}) == 1
        for group in grouped.values()
    ]

    def average(field):
        return mean(row["score"][field] for row in valid) if valid else None

    summary = {
        "cells": len(rows),
        "validCells": len(valid),
        "repeatActionAgreement": mean(agreements) if agreements else 0.0,
        "optimalActionRate": mean(
            row["score"]["optimalActionAgreement"] for row in valid
        ) if valid else 0.0,
        "decisionConsistencyRate": mean(
            row["score"]["decisionConsistentWithReportedValues"] for row in valid
        ) if valid else 0.0,
        "meanBasePriorBrier": average("basePriorBrier"),
        "meanPolicyReachWeightMae": average("policyReachWeightMae"),
        "meanConditionedPosteriorBrier": average("posteriorBrier"),
        "meanImmediateValueMae": average("immediateValueMae"),
        "meanContinuationValueMae": average("continuationValueMae"),
        "meanTotalValueMae": average("totalValueMae"),
        "maximumAdditivityResidual": max(
            (row["score"]["maximumAdditivityResidual"] for row in valid),
            default=None,
        ),
        "meanFinalActionRegret": average("finalActionRegret"),
    }
    complete = len(rows) == plan["maxProviderCalls"]
    mismatches = sum(not row.get("inputTokenMatch", False) for row in rows)
    gates = {
        "allCellsValid": complete and len(valid) == len(rows),
        "inputTokenMismatchesZero": mismatches == 0,
        "repeatActionAgreement": summary["repeatActionAgreement"] >= 0.80,
        "optimalActionRate": summary["optimalActionRate"] >= 0.95,
        "basePriorBrier": summary["meanBasePriorBrier"] is not None
        and summary["meanBasePriorBrier"] <= 1e-6,
        "policyReachWeightMae": summary["meanPolicyReachWeightMae"] is not None
        and summary["meanPolicyReachWeightMae"] <= 1e-6,
        "conditionedPosteriorBrier": summary["meanConditionedPosteriorBrier"] is not None
        and summary["meanConditionedPosteriorBrier"] <= 1e-6,
        "immediateValueMae": summary["meanImmediateValueMae"] is not None
        and summary["meanImmediateValueMae"] <= 1e-6,
        "continuationValueMae": summary["meanContinuationValueMae"] is not None
        and summary["meanContinuationValueMae"] <= 1e-6,
        "totalValueMae": summary["meanTotalValueMae"] is not None
        and summary["meanTotalValueMae"] <= 1e-6,
        "additivityResidual": summary["maximumAdditivityResidual"] is not None
        and summary["maximumAdditivityResidual"] <= 1e-6,
    }
    passed = all(gates.values())
    return {
        "schemaVersion": "aip-fixed-policy-value-report-v1",
        "date": DATE,
        "game": plan["game"],
        "protocolId": PROTOCOL_ID,
        "preregistrationSha256": digest(plan),
        "runStatus": "complete" if complete else "incomplete",
        "completedCells": len(rows),
        "inputTokenMismatches": mismatches,
        "summary": summary,
        "gateChecks": gates,
        "gatePassed": passed,
        "nextStep": (
            "prepare_identical_goofspiel_protocol"
            if plan["game"] == "liar" and passed
            else "consider_love_letter_17_positive_reach_states"
            if plan["game"] == "goofspiel" and passed
            else "stop_and_retain_failed_evidence"
        ),
        "claimRestriction": plan["claimRestriction"],
        "fullLoveLetterCertified": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("game", choices=("liar", "goofspiel"))
    parser.add_argument("phase", choices=("prepare", "run", "analyze"))
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--env-file", type=Path, default=ROOT / ".env")
    parser.add_argument("--liar-report", type=Path, default=DEFAULT_LIAR_REPORT)
    args = parser.parse_args()
    output = args.output_dir or DEFAULT_OUTPUTS[args.game]
    plan_path = output / "preregistration.json"
    rows_path = output / "trial_rows.json"
    if args.phase == "prepare":
        proposed = prepare_plan(args.game, args.env_file, args.liar_report)
        if plan_path.exists() and read_plan(plan_path) != proposed:
            raise ValueError("refusing to overwrite a different preregistration")
        write_json(plan_path, proposed)
        print(canonical_json({"path": str(plan_path), "sha256": digest(proposed)}))
        return 0
    plan = read_plan(plan_path)
    if plan["game"] != args.game:
        raise ValueError("requested game differs from preregistration")
    if args.game == "goofspiel":
        liar = require_liar_gate(args.liar_report)
        if plan["prerequisite"]["reportSha256"] != digest(liar):
            raise ValueError("Liar prerequisite report changed")
    rows = (
        execute_plan(plan, rows_path, args.env_file)
        if args.phase == "run"
        else json.loads(rows_path.read_text(encoding="utf-8"))["rows"]
    )
    report = build_report(plan, rows)
    write_json(output / "report.json", report)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["runStatus"] == "complete" else 2


if __name__ == "__main__":
    raise SystemExit(main())
