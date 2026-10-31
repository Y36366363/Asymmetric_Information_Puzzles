#!/usr/bin/env python3
"""Offline-only v9 audit: reference-free detector vs frozen reference evaluation."""
from collections import Counter
from copy import deepcopy
from hashlib import sha256
from itertools import product
import json
from pathlib import Path

from aip.benchmark.gamespec_local_checks import check_local
from aip.benchmark.gamespec_attribution import normalize_table, replay
from aip.benchmark.gamespec_smoke import digest, write_json
from run_gamespec_attribution import package, validate

ROOT = Path(__file__).resolve().parents[1]
SPEC = "configs/gamespec_local_checker_audit_v9_2026-10-31.json"
OUT = ROOT/"research/results/gamespec_local_checker_audit_v9_2026-10-31.json"


def aggregate(rows):
    wrong = [r for r in rows if not r["reference_whole_response_correct"]]
    table_rows = [r for r in rows if r["condition"]!="A"]
    wrong_tables = [r for r in table_rows if not r["reference_table_correct"]]
    correct = [r for r in rows if r["reference_whole_response_correct"]]
    return {"outputs":len(rows),"reference_failures":len(wrong),
        "local_rejections":sum(r["local"]["status"]=="reject_local" for r in rows),
        "detected_reference_failures":sum(r["local"]["status"]=="reject_local" for r in wrong),
        "residual_reference_failures":sum(r["local"]["status"]!="reject_local" for r in wrong),
        "false_local_rejections_of_reference_correct_outputs":sum(r["local"]["status"]=="reject_local" for r in correct),
        "table_outputs":len(table_rows),"reference_wrong_tables":len(wrong_tables),
        "detected_wrong_tables":sum(r["local"]["status"]=="reject_local" for r in wrong_tables),
        "residual_wrong_tables":sum(r["local"]["status"]!="reject_local" for r in wrong_tables),
        "naive_false_table_certifications_if_unverified_promoted":sum(r["local"]["status"]!="reject_local" for r in wrong_tables),
        "violation_counts":dict(Counter(v["code"] for r in rows for v in r["local"]["violations"]))}


def audit_reports(packages,reports):
    """Inputs supplied by caller; no provider import, credentials or network calls."""
    rows=[]
    for tag,(m,b) in packages.items():
        replayed = replay(m,b,reports[tag])
        for r in replayed["rows"]:
            if r["evaluation"] is None:
                raise ValueError("complete frozen input required")
            e=r["evaluation"]; item=b["cases"][r["case_id"]]
            kwargs={}
            # Only MODEL declarations (or B's recorded deterministic proposal) are
            # sent to the local checker. No reference cells or truth kind are sent.
            payload=json.loads(r["raw_text"])
            if r["condition"]!="A":kwargs["table"]=payload["stage_table"]
            if e["proposal"] is not None:kwargs["proposal"]=e["proposal"]
            local=check_local(tuple(item["case"]["fields"]),**kwargs)
            rows.append({"model":tag,"trial_id":r["trial_id"],"case_id":r["case_id"],
                "pair_id":r["pair_id"],"condition":r["condition"],"repeat":r["repeat"],
                "local":local,"reference_whole_response_correct":e["whole_response_correct"],
                "reference_table_correct":e["table_correct"],"reference_proposal_correct":e["legacy"]["correct"],
                "reference_table_cell_differences":e["table_cell_differences"],
                "frozen_failure_categories":e["categories"],
                "requires_semantic_reference_to_resolve":not e["whole_response_correct"] and local["status"]!="reject_local"})
    controls=[]
    # All labels below are computed from existing v7 tables, never new manual gold.
    b=next(iter(packages.values()))[1]
    for case_id,item in b["cases"].items():
        fields=tuple(item["case"]["fields"])
        reference=normalize_table(item["visibility_contexts"],fields)
        control=check_local(fields,table=reference)
        controls.append({"case_id":case_id,"mutation":None,"reference_match":True,"local":control})
        for phase,player,field in product(range(2),range(2),fields):
            mutated=deepcopy(reference)
            if field in mutated[phase][player]:mutated[phase][player].remove(field)
            else:mutated[phase][player].append(field)
            if normalize_table(mutated,fields)==reference:raise ValueError("mutation did not change frozen reference")
            controls.append({"case_id":case_id,"mutation":{"phase":phase,"player":player,"field":field},
                "reference_match":False,"local":check_local(fields,table=mutated)})
    mutated=[c for c in controls if not c["reference_match"]]
    clean=[c for c in controls if c["reference_match"]]
    return {"schema_version":"aip-local-observation-checker-audit-v9","all_raw_replays_agree":True,
        "rows":rows,"summary":aggregate(rows),
        "models":{tag:{"overall":aggregate([r for r in rows if r["model"]==tag]),
            "conditions":{c:aggregate([r for r in rows if r["model"]==tag and r["condition"]==c]) for c in ("A","B","C")}}
            for tag in packages},
        "derived_controls":{"reference_tables":len(clean),
            "false_local_rejections":sum(c["local"]["status"]=="reject_local" for c in clean),
            "single_cell_mutations":len(mutated),
            "locally_rejected_mutations":sum(c["local"]["status"]=="reject_local" for c in mutated),
            "not_flagged_but_reference_wrong_mutations":sum(c["local"]["status"]!="reject_local" for c in mutated),
            "all_remain_semantically_uncertified":all(not c["local"]["semantic_certification_allowed"] for c in controls),
            "not_independent_game_samples":True,"rows":controls},
        "new_manual_reference":False,"old_scores_changed":False,"model_generation_calls":0,"model_cost_usd":0,
        "semantic_approval_issued":False,"overall_scientific_pass":None,"development_diagnostic":True,
        "formal_trial_started":False,"new_runtime_epsilon_gto_allowed":False,
        "adaptive_opponent_line_released":False,"new_game_or_cfr_variant":False}


def main():
    if OUT.exists():raise FileExistsError("preserve completed audit; no silent overwrite")
    validate()
    protocol=json.loads((ROOT/SPEC).read_text())
    packages={t:package(t) for t in ("luna6","sol61")}
    reports={t:json.loads((ROOT/p).read_text()) for t,p in zip(packages,protocol["inputs"]["raw_reports"])}
    input_paths=protocol["inputs"]["raw_reports"]+[protocol["inputs"]["reference"],SPEC,
        "src/aip/benchmark/gamespec_local_checks.py","scripts/audit_gamespec_local_checks.py",
        "tests/test_gamespec_local_checks.py"]
    report=audit_reports(packages,reports)
    report["sha256"]={p:sha256((ROOT/p).read_bytes()).hexdigest() for p in input_paths}
    report["reference_digest"]={t:digest(p[1]["cases"]) for t,p in packages.items()}
    write_json(OUT,report)
    print(json.dumps({"summary":report["summary"],"models":report["models"],
        "controls":{k:v for k,v in report["derived_controls"].items() if k!="rows"}},indent=2))


if __name__=="__main__":main()
