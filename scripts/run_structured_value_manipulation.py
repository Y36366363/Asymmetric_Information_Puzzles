#!/usr/bin/env python3
"""Run frozen structured-value manipulation checks on Liar and Goofspiel."""

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
from aip.benchmark.goofspiel import (
    GoofspielValueDecompositionOracle,
    build_goofspiel_oracle_probes,
)
from aip.benchmark.liar_transfer import (
    PAD_TOKEN,
    LiarValueDecompositionOracle,
    build_consensus_reference_profiles,
    canonical_json,
    digest,
    select_profile_invariant_probes,
)
from aip.benchmark.value_decomposition import (
    VALUE_DECOMPOSITION_JSON_SCHEMA,
    parse_value_decomposition,
    score_value_decomposition,
)
from scripts.run_liar_positive_control_check import MODEL, ensure_key, write_json


ROOT = Path(__file__).resolve().parents[1]
DATE = "2026-09-27"
SEED = 20260927
REPEATS = 2
PROBE_COUNT = 6
ARMS = ("unaided_structured", "oracle_assisted_structured")
GATE = {
    "allCellsValid": True,
    "inputTokenMismatches": 0,
    "minimumRepeatActionAgreementEachArm": 0.80,
    "minimumAssistedOptimalActionRate": 0.95,
    "maximumAssistedPosteriorBrier": 1e-6,
    "maximumAssistedImmediateValueMae": 1e-6,
    "maximumAssistedContinuationValueMae": 1e-6,
    "maximumAssistedTotalValueMae": 1e-6,
    "maximumAssistedAdditivityResidual": 1e-6,
}
DEFAULT_OUTPUTS = {
    "liar": ROOT / "research/results/liar_structured_manipulation_2026-09-27",
    "goofspiel": ROOT / "research/results/goofspiel_structured_manipulation_2026-09-27",
}
DEFAULT_LIAR_REPORT = DEFAULT_OUTPUTS["liar"] / "report.json"

BASE_INSTRUCTIONS = (
    "You are completing an auditable two-player zero-sum strategic calculation. "
    "Use only the supplied rules, observation, information state, public history, "
    "and legal actions. Return the exact required JSON shape. The posterior must "
    "use every supplied belief-state label exactly once and sum to one. For every "
    "legal action, report immediate_value (utility resolved by that action now), "
    "continuation_value (expected utility from later play), and total_value (their "
    "sum), all from the acting player's perspective. chosen_action_id must be a "
    "legal action maximizing the reported total_value. Do not emit explanations "
    "or private reasoning."
)


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _game_material(game: str):
    if game == "liar":
        panel = select_profile_invariant_probes(
            build_consensus_reference_profiles(), count=30
        )[0]
        challenge = [
            probe for probe in panel
            if max(probe.exact_action_values, key=probe.exact_action_values.get)
            == "challenge"
        ]
        raises = [probe for probe in panel if probe not in challenge]

        def rank(probe):
            return digest({"seed": SEED, "purpose": "structured_liar", "id": probe.probe_id})

        probes = sorted(challenge, key=rank)[:3] + sorted(raises, key=rank)[:3]
        return tuple(probes), LiarValueDecompositionOracle()
    if game == "goofspiel":
        panel = build_goofspiel_oracle_probes()

        def rank(probe):
            return digest({"seed": SEED, "purpose": "structured_goofspiel", "id": probe.probe_id})

        probes = []
        for remaining in (4, 3, 2):
            group = [probe for probe in panel if len(probe.player_cards) == remaining]
            probes.extend(sorted(group, key=rank)[:2])
        return tuple(probes), GoofspielValueDecompositionOracle()
    raise ValueError(f"unsupported game: {game}")


def _base_prompts(game: str, probes, oracle):
    prompts = {}
    for probe in probes:
        prompts[(probe.probe_id, "unaided_structured")] = (
            BASE_INSTRUCTIONS
            + f"\nCondition: unaided_structured_{game}. Compute every field yourself."
        )
        exact = canonical_json(oracle.decompose(probe).to_response_payload())
        prompts[(probe.probe_id, "oracle_assisted_structured")] = (
            BASE_INSTRUCTIONS
            + "\nCondition: oracle_assisted_structured. This is a positive-control "
            "instruction-following check, not evidence of independent game-solving "
            "or transfer. Reproduce the independently computed reference below "
            "exactly in the required response shape.\nREFERENCE="
            + exact
        )
    return prompts


def _count(client, *, prompt: str, input_text: str) -> int:
    response = client.responses.input_tokens.count(
        model=MODEL,
        instructions=prompt,
        input=input_text,
        text={
            "format": {
                "type": "json_schema",
                "name": "aip_agent_decision",
                "strict": True,
                "schema": VALUE_DECOMPOSITION_JSON_SCHEMA,
            }
        },
        reasoning={"effort": "low"},
    )
    return int(response.input_tokens)


def _balance_prompts(client, base, inputs):
    prompts, padding, counts = {}, {}, {}
    for probe_id, input_text in inputs.items():
        labeled = {
            arm: base[(probe_id, arm)]
            + "\nNeutral padding tokens follow and carry no game information:"
            for arm in ARMS
        }
        initial = {
            arm: _count(client, prompt=labeled[arm], input_text=input_text)
            for arm in ARMS
        }
        target = max(initial.values()) + 16
        for arm in ARMS:
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


def require_liar_gate(path: Path) -> dict[str, object]:
    report = json.loads(path.read_text(encoding="utf-8"))
    if report.get("schemaVersion") != "aip-structured-value-manipulation-report-v1":
        raise ValueError("Goofspiel prerequisite is not a structured-value report")
    if report.get("game") != "liar" or report.get("gatePassed") is not True:
        raise ValueError("Goofspiel is blocked until the Liar gate passes")
    return report


def prepare_plan(game: str, env_file: Path, liar_report: Path) -> dict[str, object]:
    ensure_key(env_file)
    from openai import OpenAI

    prerequisite = None
    if game == "goofspiel":
        prerequisite = require_liar_gate(liar_report)
    probes, oracle = _game_material(game)
    if len(probes) != PROBE_COUNT:
        raise ValueError("frozen structured panel must contain six probes")
    inputs = {
        probe.probe_id: completion_input_text(probe.decision_input())
        for probe in probes
    }
    base = _base_prompts(game, probes, oracle)
    client = OpenAI(max_retries=1, timeout=60.0)
    prompts, padding, counts = _balance_prompts(client, base, inputs)
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
    random.Random(SEED + (1 if game == "goofspiel" else 0)).shuffle(cells)
    plan = {
        "schemaVersion": "aip-structured-value-manipulation-prereg-v1",
        "date": DATE,
        "game": game,
        "model": MODEL,
        "reasoningEffort": "low",
        "maxOutputTokens": 4096,
        "maxAttemptsPerCell": 1,
        "seed": SEED,
        "repeats": REPEATS,
        "probeCount": PROBE_COUNT,
        "arms": list(ARMS),
        "gate": GATE,
        "oracleId": oracle.oracle_id,
        "probes": [probe.to_artifact() for probe in probes],
        "references": {
            probe.probe_id: oracle.decompose(probe).to_artifact()
            for probe in probes
        },
        "prompts": {
            probe.probe_id: {
                arm: prompts[(probe.probe_id, arm)] for arm in ARMS
            }
            for probe in probes
        },
        "basePromptSha256": {
            probe.probe_id: {
                arm: digest(base[(probe.probe_id, arm)]) for arm in ARMS
            }
            for probe in probes
        },
        "paddingToken": PAD_TOKEN,
        "paddingTokenCounts": {
            probe.probe_id: {
                arm: padding[(probe.probe_id, arm)] for arm in ARMS
            }
            for probe in probes
        },
        "cellOrder": cells,
        "maxProviderCalls": len(cells),
        "prerequisite": (
            None if prerequisite is None else {
                "game": "liar",
                "reportPath": str(liar_report.relative_to(ROOT)),
                "reportSha256": digest(prerequisite),
                "gatePassed": True,
            }
        ),
        "claimRestriction": (
            "The assisted arm tests schema and signal following only; it is excluded "
            "from independent solving, transfer, equilibrium, and GTO claims."
        ),
        "nextStepRule": (
            "Goofspiel may be prepared only after every Liar gate passes."
            if game == "liar"
            else "Love Letter positive-reach design may proceed only after every Goofspiel gate passes."
        ),
    }
    validate_plan(plan)
    return plan


def validate_plan(plan: dict[str, object]) -> None:
    if plan.get("schemaVersion") != "aip-structured-value-manipulation-prereg-v1":
        raise ValueError("unsupported structured-value preregistration")
    game = plan.get("game")
    if game not in {"liar", "goofspiel"}:
        raise ValueError("unsupported preregistered game")
    if plan.get("model") != MODEL or plan.get("gate") != GATE:
        raise ValueError("model or frozen gate changed")
    if plan.get("repeats") != REPEATS or plan.get("probeCount") != PROBE_COUNT:
        raise ValueError("panel size or repeat count changed")
    probes, oracle = _game_material(str(game))
    artifacts = {probe.probe_id: probe.to_artifact() for probe in probes}
    if {item["id"]: item for item in plan["probes"]} != artifacts:
        raise ValueError("probe panel or exact oracle artifact changed")
    references = {
        probe.probe_id: oracle.decompose(probe).to_artifact() for probe in probes
    }
    if plan.get("references") != references:
        raise ValueError("value-decomposition reference changed")
    expected = {
        (probe.probe_id, arm, repeat)
        for probe in probes for arm in ARMS for repeat in range(1, REPEATS + 1)
    }
    actual = [
        (cell["probeId"], cell["arm"], cell["repeat"])
        for cell in plan["cellOrder"]
    ]
    if len(actual) != len(expected) or set(actual) != expected:
        raise ValueError("cell schedule is incomplete or duplicated")
    if plan.get("maxProviderCalls") != len(actual):
        raise ValueError("provider-call budget differs from frozen schedule")
    for probe_id in artifacts:
        token_counts = {
            cell["expectedInputTokens"]
            for cell in plan["cellOrder"] if cell["probeId"] == probe_id
        }
        if len(token_counts) != 1:
            raise ValueError("input tokens differ across arms")


def read_plan(path: Path) -> dict[str, object]:
    plan = json.loads(path.read_text(encoding="utf-8"))
    validate_plan(plan)
    return plan


def execute_plan(plan, rows_path: Path, env_file: Path):
    ensure_key(env_file)
    from openai import OpenAI

    probes, oracle = _game_material(plan["game"])
    by_id = {probe.probe_id: probe for probe in probes}
    references = {probe.probe_id: oracle.decompose(probe) for probe in probes}
    client = OpenAI(max_retries=0, timeout=60.0)
    backend = OpenAIResponsesBackend(
        client=client,
        reasoning_effort=plan["reasoningEffort"],
        max_output_tokens=plan["maxOutputTokens"],
    )
    plan_sha = digest(plan)
    rows = []
    if rows_path.exists():
        envelope = json.loads(rows_path.read_text(encoding="utf-8"))
        if envelope.get("preregistrationSha256") != plan_sha:
            raise ValueError("existing rows belong to a different preregistration")
        rows = envelope["rows"]
    complete = {(row["probeId"], row["arm"], row["repeat"]) for row in rows}
    for index, cell in enumerate(plan["cellOrder"], start=1):
        key = cell["probeId"], cell["arm"], cell["repeat"]
        if key in complete:
            continue
        probe = by_id[cell["probeId"]]
        request = CompletionRequest(
            model=plan["model"],
            condition=(
                PromptCondition.GENERIC
                if cell["arm"] == "unaided_structured"
                else PromptCondition.SINGLE_GAME
            ),
            instructions=plan["prompts"][probe.probe_id][cell["arm"]],
            input_text=completion_input_text(probe.decision_input()),
            response_schema=VALUE_DECOMPOSITION_JSON_SCHEMA,
        )
        started = time.perf_counter()
        row = {**cell, "status": "failed"}
        try:
            response = backend.complete(request)
            candidate = parse_value_decomposition(response.output_text)
            score = score_value_decomposition(candidate, references[probe.probe_id])
            row.update(
                status="valid",
                chosenActionId=candidate.chosen_action_id,
                decomposition=candidate.to_artifact(),
                score=score.to_artifact(),
                responseStatus=response.status,
                incompleteReason=response.incomplete_reason,
                responseId=response.response_id,
                resolvedModel=response.resolved_model,
                observedInputTokens=response.input_tokens,
                outputTokens=response.output_tokens,
                totalTokens=response.total_tokens,
                outputSha256=_sha256_text(response.output_text),
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
            "schemaVersion": "aip-structured-value-manipulation-rows-v1",
            "preregistrationSha256": plan_sha,
            "rows": rows,
        })
        print(
            f"{index}/{len(plan['cellOrder'])} {cell['arm']} r{cell['repeat']}: {row['status']}",
            flush=True,
        )
    return rows


def _summary(rows, arm):
    selected = [row for row in rows if row["arm"] == arm]
    valid = [row for row in selected if row["status"] == "valid"]
    grouped = {}
    for row in selected:
        grouped.setdefault(row["probeId"], []).append(row)
    repeat_agreements = [
        len(group) == REPEATS
        and all(row["status"] == "valid" for row in group)
        and len({row.get("chosenActionId") for row in group}) == 1
        for group in grouped.values()
    ]

    def average(field):
        return mean(row["score"][field] for row in valid) if valid else None

    return {
        "cells": len(selected),
        "validCells": len(valid),
        "repeatActionAgreement": mean(repeat_agreements) if repeat_agreements else 0.0,
        "optimalActionRate": mean(
            row["score"]["optimalActionAgreement"] for row in valid
        ) if valid else 0.0,
        "decisionConsistencyRate": mean(
            row["score"]["decisionConsistentWithReportedValues"] for row in valid
        ) if valid else 0.0,
        "meanPosteriorBrier": average("posteriorBrier"),
        "meanImmediateValueMae": average("immediateValueMae"),
        "meanContinuationValueMae": average("continuationValueMae"),
        "meanTotalValueMae": average("totalValueMae"),
        "maximumAdditivityResidual": max(
            (row["score"]["maximumAdditivityResidual"] for row in valid),
            default=None,
        ),
        "meanFinalActionRegret": average("finalActionRegret"),
    }


def build_report(plan, rows):
    summaries = {arm: _summary(rows, arm) for arm in ARMS}
    assisted = summaries["oracle_assisted_structured"]
    complete = len(rows) == plan["maxProviderCalls"]
    mismatches = sum(not row.get("inputTokenMatch", False) for row in rows)
    all_valid = complete and all(row["status"] == "valid" for row in rows)
    gates = {
        "allCellsValid": all_valid,
        "inputTokenMismatchesZero": mismatches == 0,
        "repeatActionAgreementEachArm": all(
            summary["repeatActionAgreement"] >= 0.80
            for summary in summaries.values()
        ),
        "assistedOptimalActionRate": assisted["optimalActionRate"] >= 0.95,
        "assistedPosteriorBrier": (
            assisted["meanPosteriorBrier"] is not None
            and assisted["meanPosteriorBrier"] <= 1e-6
        ),
        "assistedImmediateValueMae": (
            assisted["meanImmediateValueMae"] is not None
            and assisted["meanImmediateValueMae"] <= 1e-6
        ),
        "assistedContinuationValueMae": (
            assisted["meanContinuationValueMae"] is not None
            and assisted["meanContinuationValueMae"] <= 1e-6
        ),
        "assistedTotalValueMae": (
            assisted["meanTotalValueMae"] is not None
            and assisted["meanTotalValueMae"] <= 1e-6
        ),
        "assistedAdditivityResidual": (
            assisted["maximumAdditivityResidual"] is not None
            and assisted["maximumAdditivityResidual"] <= 1e-6
        ),
    }
    passed = all(gates.values())
    return {
        "schemaVersion": "aip-structured-value-manipulation-report-v1",
        "date": DATE,
        "game": plan["game"],
        "preregistrationSha256": digest(plan),
        "runStatus": "complete" if complete else "incomplete",
        "completedCells": len(rows),
        "validCells": sum(row["status"] == "valid" for row in rows),
        "inputTokenMismatches": mismatches,
        "summaries": summaries,
        "gateChecks": gates,
        "gatePassed": passed,
        "nextStep": (
            "prepare_same_protocol_goofspiel"
            if plan["game"] == "liar" and passed
            else "design_love_letter_17_positive_reach_panel"
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
    if args.phase == "run":
        rows = execute_plan(plan, rows_path, args.env_file)
    else:
        rows = json.loads(rows_path.read_text(encoding="utf-8"))["rows"]
    report = build_report(plan, rows)
    write_json(output / "report.json", report)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["runStatus"] == "complete" else 2


if __name__ == "__main__":
    raise SystemExit(main())
