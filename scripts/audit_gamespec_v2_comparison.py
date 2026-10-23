#!/usr/bin/env python3
"""Descriptive, raw-response-based v1/v2 comparison; no provider requests."""
from collections import Counter
import json

from aip.benchmark.gamespec_smoke import write_json
from aip.benchmark.gamespec_smoke_v2 import compile_v2, independent_replay
from run_gamespec_smoke_v2 import OUTPUT, ROOT, package


def audit(diagnostic=False):
    manifest, bundle = package(diagnostic)
    path = OUTPUT.with_name("diagnostic_report.json") if diagnostic else OUTPUT
    report = json.loads(path.read_text())
    analysis = independent_replay(manifest, bundle, report)
    details = []
    exposures = Counter()
    intermediate_errors = []
    for t in report["trials"]:
        for i in t["attempt_ids"]:
            a = report["attempts"][i]
            feedback = json.loads(a["messages"][-1]["content"].split("\nFeedback: ", 1)[1])
            if feedback.get("witnesses"):
                exposures[t["kind"]] += 1
            if a["errors"]:
                intermediate_errors.append({"trial_id": t["trial_id"], "attempt_id": i,
                                            "errors": a["errors"]})
        if t["kind"] != "oos":
            continue
        a = report["attempts"][t["attempt_ids"][-1]]
        payload = json.loads(a["raw_response"]["choices"][0]["message"]["content"])
        scope_case = {"case_id": manifest["out_of_schema"]["case_id"],
                      "fields": manifest["cases"][0]["fields"]}
        structurally_valid = False
        try:
            compile_v2(payload, scope_case, t["arm"] == "single_no_feedback")
            structurally_valid = True
        except (ValueError, TypeError):
            pass
        details.append({"trial_id": t["trial_id"], "passed": t["scope_result"]["passed"],
                        "static_candidate_compiles": structurally_valid, "reply": payload})
    return {"analysis": analysis, "semantic_witness_exposures_by_kind": dict(exposures),
            "all_scope_cases": details, "all_attempt_errors": intermediate_errors,
            "caveat": "Exposure counts matter: arm labels alone do not show feedback was actually received. Static compilation success does not imply the dynamic rule is representable."}


def main():
    base = json.loads((ROOT / "research/results/gamespec_model_smoke_2026-10-22/report.json").read_text())
    result = {"schema_version": "gamespec-v2-descriptive-comparison-v1",
              "v1_original_engineering_status": base["analysis"]["gates"]["status"],
              "primary": audit(), "diagnostic": audit(True),
              "interpretation": {
                  "population_confidence_interval": None,
                  "reason": "Four public templates with technical repeats; no identifiable novel-game sampling distribution",
                  "formal_effectiveness_established": False,
                  "model_ranking_established": False,
                  "deployment_released": False}}
    write_json(OUTPUT.with_name("descriptive_comparison.json"), result)
    print(json.dumps({"v1_status": result["v1_original_engineering_status"],
                      "primary_exposures": result["primary"]["semantic_witness_exposures_by_kind"],
                      "diagnostic_exposures": result["diagnostic"]["semantic_witness_exposures_by_kind"]}, indent=2))


if __name__ == "__main__":
    main()
