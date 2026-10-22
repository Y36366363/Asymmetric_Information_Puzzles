#!/usr/bin/env python3
"""Recompute provider smoke scores from saved raw responses, without API calls."""
from __future__ import annotations

import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path

from aip.benchmark.gamespec_smoke import (
    analyze, digest, final_score, output_labels,
)
from aip.core.game_spec_pilot import compile_game_spec_candidate_json
from aip.core.game_spec_smoke import validate_scope_refusal
from aip.benchmark.gamespec_smoke import vocab_for

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "research/results/gamespec_model_smoke_2026-10-22/report.json"
MANIFEST = ROOT / "configs/llm_gamespec_smoke_execution_2026-10-21.json"
BUNDLE = ROOT / "configs/gamespec_smoke_dispatch_bundle_2026-10-22.json"


def audit(manifest, bundle, report):
    attempts = report["attempts"]
    cases = {case["case_id"]: case for case in manifest["cases"]}
    discrepancies = []
    diagnostics = Counter()
    input_tokens = output_tokens = 0
    costs = []
    associated = []
    for index, attempt in enumerate(attempts):
        raw = attempt.get("raw_response", {})
        usage = raw.get("usage")
        if attempt["attempt_id"] != index or raw.get("model") != manifest["model"]["model_id"]:
            discrepancies.append(f"attempt_identity_or_model:{index}")
        if not usage:
            discrepancies.append(f"usage_missing:{index}")
            continue
        input_tokens += usage["prompt_tokens"]
        output_tokens += usage["completion_tokens"]
        cost = (usage["prompt_tokens"] * manifest["model"]["input_usd_per_million"]
                + usage["completion_tokens"] * manifest["model"]["output_usd_per_million"]) / 1e6
        if abs(cost - attempt["cost_usd"]) > 1e-12:
            discrepancies.append(f"cost:{index}")
        costs.append(cost)
    for trial in report["trials"]:
        associated.extend(trial["attempt_ids"])
        if trial["status"] != "completed" or not trial["attempt_ids"]:
            discrepancies.append(f"trial_incomplete:{trial['trial_id']}")
            continue
        last = attempts[trial["attempt_ids"][-1]]
        raw = last["raw_response"]
        try:
            payload = json.loads(raw["choices"][0]["message"]["content"])
        except (ValueError, TypeError):
            payload = None
        if trial["kind"] == "oos":
            score = validate_scope_refusal(payload, manifest["out_of_schema"])
            if score != trial["scope_result"]:
                discrepancies.append(f"scope_score:{trial['trial_id']}")
            if isinstance(payload, dict) and payload.get("status") == "out_of_schema":
                diagnostics["oos_refusal_envelopes"] += 1
                expected = manifest["out_of_schema"]["required_witness"]
                witness = payload.get("witness", {})
                if witness == {**expected, "player": "player_1"}:
                    diagnostics["oos_correct_relation_but_string_player_id"] += 1
            continue
        case = cases[trial["case_id"]]
        count = 1 if trial["arm"] == "single_no_feedback" else 3
        compiled, _, _ = output_labels(payload, case, count)
        if raw["choices"][0]["finish_reason"] != "stop":
            compiled = None
        score = final_score(compiled, case, bundle["cases"][case["case_id"]])
        if score != trial["score"]:
            discrepancies.append(f"final_score:{trial['trial_id']}")
        first = attempts[trial["attempt_ids"][0]]["raw_response"]
        try:
            first_payload = json.loads(first["choices"][0]["message"]["content"])
        except (ValueError, TypeError):
            first_payload = None
        first_compiled, _, _ = output_labels(first_payload, case, count)
        first_valid = first_compiled is not None and first["choices"][0]["finish_reason"] == "stop"
        if first_valid != trial["first_schema_valid"]:
            discrepancies.append(f"first_schema:{trial['trial_id']}")
        if trial["kind"] == "main" and trial["arm"] != "single_no_feedback":
            diagnostics["multi_main_trials"] += 1
            if isinstance(first_payload, dict):
                candidate_list = first_payload.get("candidates", [])
                valid_signatures = []
                for candidate in candidate_list if isinstance(candidate_list, list) else []:
                    # Posthoc diagnostic only: inspect each candidate separately;
                    # never deduplicate or repair the primary candidate-set score.
                    isolated = {**first_payload, "candidates": [candidate]}
                    try:
                        isolated_set = compile_game_spec_candidate_json(isolated, vocab_for(case), exact_candidates=1)
                    except (ValueError, TypeError):
                        continue
                    valid_signatures.append(isolated_set.signatures[0])
                if len(set(valid_signatures)) < len(valid_signatures):
                    diagnostics["multi_first_response_contains_repeated_partition"] += 1
                if any(dict(signature) == case["reference_owners"] for signature in valid_signatures):
                    diagnostics["multi_first_response_has_correct_individual_candidate_posthoc"] += 1
    if sorted(associated) != list(range(len(attempts))):
        discrepancies.append("attempt_trial_association")
    if report["manifest_sha256"] != digest(manifest) or report["bundle_sha256"] != digest(bundle):
        discrepancies.append("frozen_package_hash")
    replay = analyze(manifest, report)
    if replay != report["analysis"]:
        discrepancies.append("aggregate_analysis")
    return {
        "date": "2026-10-22", "experiment_id": "gamespec_model_smoke_v1",
        "raw_response_replay_passed": not discrepancies,
        "discrepancies": discrepancies,
        "execution_status": report["status"],
        "model_snapshot": manifest["model"]["model_id"],
        "provider_attempts": len(attempts),
        "usage": {"input_tokens": input_tokens, "output_tokens": output_tokens,
                  "estimated_uncached_usd": sum(costs), "maximum_call_usd": max(costs, default=0)},
        "groups": replay["groups"],
        "observations": {key: value for key, value in replay["observations"].items() if key != "call_costs_usd"},
        "frozen_gate_result": replay["gates"],
        "posthoc_diagnostics_not_used_for_gates": dict(diagnostics),
        "initial_missing_truth_controls": [
            {"trial_id": t["trial_id"], "initial_coverage": t["initial_coverage"],
             "final_coverage": t["score"]["true_model_candidate_coverage"],
             "false_certification": t["score"]["false_certification"],
             "final_status": t["score"]["verification"]["status"]}
            for t in report["trials"] if t["kind"] == "missing_truth"
        ],
        "interpretation": {
            "smoke_passed": replay["gates"]["status"] == "pass",
            "semantic_feedback_advantage_established": False,
            "can_infer_general_model_incompetence": False,
            "formal_trial_execution_allowed": False,
            "llm_candidate_runtime_epsilon_gto_allowed": False,
            "adaptive_opponent_line_released": False,
        },
        "limitations": [
            "Smoke templates are public and engineering holdouts only; repeated temperature-zero calls are not independent game families.",
            "The exact-three-distinct-candidates requirement conflicts with unambiguous rules in many observed outputs; failure cannot isolate semantic reasoning from the elicitation contract.",
            "A string player_1 instead of integer 1 fails the frozen refusal schema even when the reported visibility relation is correct.",
            "Diagnostics that inspect individual candidates or recognize string player IDs are posthoc and never alter frozen gate results.",
            "Reference partitions and final evidence are authored under known rules; no claim of automatic truth discovery.",
            "No strategy training, conditional solver execution or adaptive opponent experiment was performed.",
            "Costs are conservative uncached token estimates, not a billing receipt.",
        ],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=REPORT.parent / "independent_replay.json")
    args = parser.parse_args()
    report = json.loads(REPORT.read_text())
    result = audit(json.loads(MANIFEST.read_text()), json.loads(BUNDLE.read_text()), report)
    result["raw_report_sha256"] = sha256(REPORT.read_bytes()).hexdigest()
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n")
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["raw_response_replay_passed"] else 1)
