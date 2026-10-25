#!/usr/bin/env python3
"""Post-hoc failure localization, never normalization or primary rescoring."""
from collections import Counter
import json

from aip.benchmark.gamespec_smoke import digest, write_json
from aip.benchmark.gamespec_scope_ablation import replay, strict_json
from run_gamespec_scope_ablation import OUTPUT, package


def refusal_components(payload, item):
    expected = item["control"]
    obj = payload if isinstance(payload, dict) else {}
    witness = obj.get("witness")
    allowed = [expected["required_witness"]] + item.get("additional_witnesses", [])
    witness_matches = (isinstance(witness, dict)
                       and type(witness.get("player")) is int
                       and type(witness.get("before_visible")) is bool
                       and type(witness.get("after_visible")) is bool
                       and any(witness == w for w in allowed))
    header = (set(obj) == {"schema_version", "game_id", "status", "error_code", "witness"}
              and obj.get("schema_version") == "aip-observation-refusal-v1"
              and obj.get("game_id") == expected["case_id"]
              and obj.get("status") == "out_of_schema")
    code = obj.get("error_code")
    case_only = (isinstance(code, str) and code != expected["expected_code"]
                 and code.casefold() == expected["expected_code"].casefold())
    return {
        "refusal_header_exact": header,
        "registered_visibility_change_exact": witness_matches,
        "error_code_exact": code == expected["expected_code"],
        "only_error_code_case_failure": header and witness_matches and case_only,
        "forced_candidate": "candidates" in obj,
    }


def main():
    manifest, bundle = package()
    report = json.loads(OUTPUT.read_text())
    analysis = replay(manifest, bundle, report)
    rows = []
    for trial in report["trials"]:
        item = bundle["cases"][trial["case_id"]]
        if trial["status"] != "completed" or item["kind"] != "dynamic":
            continue
        attempt = report["attempts"][trial["attempt_ids"][0]]
        text = attempt["raw_response"]["choices"][0]["message"]["content"]
        try:
            payload = strict_json(text)
        except (ValueError, TypeError):
            payload = None
        rows.append(dict(refusal_components(payload, item), trial_id=trial["trial_id"],
                         arm=trial["arm"], strict_correct=trial["evaluation"]["correct"]))
    groups = {}
    for arm in manifest["ablation"]["arms"]:
        selected = [r for r in rows if r["arm"] == arm["id"]]
        groups[arm["id"]] = {k: sum(bool(r[k]) for r in selected) for k in (
            "strict_correct", "registered_visibility_change_exact", "only_error_code_case_failure", "forced_candidate")}
        groups[arm["id"]]["completed"] = len(selected)
    result = {
        "schema_version": "gamespec-scope-component-diagnostics-v1",
        "posthoc_diagnostics": True, "primary_scores_changed": False,
        "primary_analysis_sha256": digest(analysis), "groups": groups, "rows": rows,
        "interpretation": "The frozen wrong_refusal_witness label comes from a joint validator and can co-occur with a code-only error. These component checks localize failures; lowercase codes still FAIL primary strict scoring. No canonicalization or adjusted pass rate.",
        "failure_counts": dict(Counter(e for f in analysis["all_failures"] for e in f["errors"])),
    }
    write_json(OUTPUT.with_name("component_diagnostics.json"), result)
    print(json.dumps(groups, indent=2))


if __name__ == "__main__":
    main()
