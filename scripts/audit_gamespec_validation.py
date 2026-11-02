#!/usr/bin/env python3
"""Offline v10 state/guard audit, with real-output and mutation denominators apart."""
from hashlib import sha256
import json
from pathlib import Path

from aip.benchmark.gamespec_attribution import normalize_table, replay
from aip.benchmark.gamespec_smoke import write_json
from aip.benchmark.gamespec_validation import inspect_observation, state_counts, verify_frozen_output
from aip.core.cfr import CFRCertificationGate
from aip.core.evaluation import PromotionEvidence, decide_promotion
from aip.core.observation_validation import ObservationValidationError
from run_gamespec_attribution import package, validate

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "research/results/gamespec_targeted_c_v10_2026-11-02"


def assert_promotion_blocked(record):
    for admission in (lambda: decide_promotion(PromotionEvidence(observation_validation=record)),
                      lambda: CFRCertificationGate().evaluate(None, evaluation=None, observation_validation=record)):
        try: admission()
        except ObservationValidationError: continue
        raise AssertionError("observation diagnostic crossed strategy admission boundary")


def audit():
    validate()
    old = json.loads((ROOT / "research/results/gamespec_local_checker_audit_v9_2026-10-31.json").read_text())
    notes = {
        "post_run_reporting_clarification": True, "old_reports_or_scores_modified": False,
        "actual_model_outputs": {"outputs": 360, "table_outputs_B_C": 240, "reference_wrong_tables": 19,
                                 "locally_detected_wrong_tables": 7, "residual_wrong_tables": 12},
        "derived_mutation_controls": {"wrong_tables": 192, "locally_rejected": 41,
                                     "unflagged_wrong_tables": 151, "independent_rule_samples": False},
        "mandatory_boundary_warning": "151/192 refers to mechanically mutated wrong-table controls, NOT to the 360 model outputs; those contain 12 residual wrong tables out of 19 wrong tables among 240 B/C tables. Local consistency is never semantic verification.",
        "states": {
            "reject_local": "A declared-data contract check found a contradiction; not a repair or a truth model",
            "locally_consistent_unverified": "No local contradiction; semantic truth not assessed OR reference mismatch. Separate semantic_result records which",
            "verified": "Only this exact output matches its frozen developer reference through the existing semantic/direct-oracle path; no strategy or deployment authority"},
        "no_combined_local_and_semantic_pass_rate": True,
        "diagnostic_reference_verification_is_not_runtime_certificate": True}
    rows, records = [], []
    for tag in ("luna6", "sol61"):
        m, b = package(tag)
        path = ROOT / f"research/results/gamespec_attribution_v8_2026-10-30/{tag}.json"
        rescored = replay(m, b, json.loads(path.read_text()))
        for r in rescored["rows"]:
            item = b["cases"][r["case_id"]]
            record, local, _, e = verify_frozen_output(r["raw_text"], r["condition"], item)
            if e != r["evaluation"]: raise AssertionError("frozen score changed")
            assert_promotion_blocked(record)
            records.append(record)
            rows.append({"model": tag, "trial_id": r["trial_id"], "status": record.status.value,
                "semantic_result": record.semantic_result, "reference_whole_response_correct": e["whole_response_correct"],
                "runtime_and_freeze_blocked": True, "local": local})
    _, b = package("luna6")
    for c in old["derived_controls"]["rows"]:
        item = b["cases"][c["case_id"]]
        # Guard every existing frozen local verdict; no new manual reference.
        # Static references may share phase-list identities. Normalize first so
        # a one-cell mutation cannot also mutate the other phase via aliasing.
        table = normalize_table(item["visibility_contexts"], tuple(item["case"]["fields"]))
        if c["mutation"] is not None:
            p = c["mutation"]
            view = table[p["phase"]][p["player"]]
            if p["field"] in view: view.remove(p["field"])
            else: view.append(p["field"])
        record, local, _ = inspect_observation(tuple(item["case"]["fields"]), table=table)
        if local != c["local"]: raise AssertionError("frozen local result changed")
        assert_promotion_blocked(record)
    return {"schema_version": "aip-observation-three-state-guard-v10", "states": state_counts(records),
        "rows": rows, "all_360_diagnostic_records_blocked_from_runtime_and_freeze": True,
        "all_204_reference_and_mutation_local_records_blocked": True,
        "local_coverage": {"boundary_warning": notes["mandatory_boundary_warning"],
            "actual_model_outputs": notes["actual_model_outputs"],
            "derived_mutation_controls": notes["derived_mutation_controls"]},
        "measurement_notes": notes, "model_generation_calls": 0,
        "old_scores_changed": False, "new_runtime_epsilon_gto_allowed": False}


def main():
    paths = [OUT / "validation_guard_audit.json", OUT / "measurement_notes.json"]
    if any(p.exists() for p in paths): raise FileExistsError("preserve completed offline audit")
    report = audit()
    report["source_sha256"] = {p: sha256((ROOT / p).read_bytes()).hexdigest() for p in (
        "scripts/audit_gamespec_validation.py", "src/aip/benchmark/gamespec_validation.py",
        "src/aip/core/observation_validation.py", "src/aip/core/evaluation.py", "src/aip/core/cfr.py")}
    write_json(paths[0], report)
    write_json(paths[1], report["measurement_notes"])
    print(json.dumps({"states": report["states"], "local_coverage": report["local_coverage"]}, indent=2))


if __name__ == "__main__": main()
