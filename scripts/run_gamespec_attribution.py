#!/usr/bin/env python3
"""Preregistered API dispatch and fully offline replay of v8 attribution."""
import argparse
import csv
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess

from aip.benchmark.completion import load_dotenv_value
from aip.benchmark.gamespec_attribution import (AttributionClient, AttributionRunner, compare_statistics,
    derive_proposal, evaluate, materialize, normalize_table, output_schema, replay)
from aip.benchmark.gamespec_smoke import digest, write_json
from run_gamespec_boundary_panel import SOURCES as V7_SOURCES, package as v7_package, validate as validate_v7

ROOT = Path(__file__).resolve().parents[1]
SPEC = "configs/gamespec_attribution_v8_2026-10-30.json"
LOCK = "configs/gamespec_attribution_v8_lock_2026-10-30.json"
OUT = ROOT / "research/results/gamespec_attribution_v8_2026-10-30"
SOURCES = list(dict.fromkeys(V7_SOURCES + [SPEC,"src/aip/benchmark/gamespec_attribution.py",
    "scripts/run_gamespec_attribution.py","tests/test_gamespec_attribution.py"]))


def specification():
    spec = json.loads((ROOT/SPEC).read_text())
    ref = spec["reference"]
    if sha256((ROOT/ref["source"]).read_bytes()).hexdigest()!=ref["sha256"]:
        raise ValueError("v7 reference bytes changed")
    return spec


def package(tag):
    if tag not in ("luna6","sol61"): raise ValueError("only frozen Luna/Sol allowed")
    return materialize(*v7_package(tag),specification())


def hashes():
    return {p:sha256((ROOT/p).read_bytes()).hexdigest() for p in SOURCES}


def schemas():
    m,b = package("luna6")
    return {case_id:{c:output_schema(m,item["case"],c) for c in ("A","B","C")}
            for case_id,item in b["cases"].items()}


def validate():
    validate_v7()
    lock = json.loads((ROOT/LOCK).read_text())
    if hashes()!=lock["sha256"]: raise ValueError("frozen implementation changed")
    if digest(schemas())!=lock["schemas_sha256"]: raise ValueError("frozen schemas changed")
    for p,h in lock["historical_sha256"].items():
        if sha256((ROOT/p).read_bytes()).hexdigest()!=h: raise ValueError("old result changed")
    if {t:digest(package(t)[1]) for t in ("luna6","sol61")}!=lock["bundle_sha256"]:
        raise ValueError("frozen plan or references changed")


def preflight():
    m,b = package("luna6")
    old = v7_package("luna6")[1]
    if b["cases"]!=old["cases"] or b["pairs"]!=old["pairs"]:
        raise ValueError("reference/case mutation")
    checks = []
    for case_id,item in b["cases"].items():
        table = normalize_table(item["visibility_contexts"],item["case"]["fields"])
        proposal = derive_proposal(table,item["case"]["fields"])
        for c,payload in (("A",proposal),("B",{"stage_table":table}),
                           ("C",{"stage_table":table,"proposal":proposal})):
            e = evaluate(json.dumps(payload),c,item)
            if not e["whole_response_correct"]: raise ValueError("frozen-reference preflight failed")
        checks.append({"case_id":case_id,"reference_sha256":digest(item["visibility_contexts"]),
                       "program_proposal":proposal,"all_three_reference_roundtrips_passed":True})
    return checks


def export_comparison():
    analyses = {}
    trial_rows,instance_rows,cross_rows = [],[],[]
    for tag in ("luna6","sol61"):
        m,b = package(tag)
        raw = json.loads((OUT/f"{tag}.json").read_text())
        rescored = replay(m,b,raw)
        write_json(OUT/f"{tag}_rescored.json",rescored)
        analyses[tag] = rescored["summary"]
        for row in rescored["rows"]:
            e = row["evaluation"] or {"legacy":{"correct":False},"table_correct":None,
                "proposal_consistent_with_own_table":None,"categories":["incomplete"]}
            trial_rows.append({"model":tag,"case_id":row["case_id"],"condition":row["condition"],
                "repeat":row["repeat"],"status":row["status"],"legacy_correct":e["legacy"]["correct"],
                "table_correct":e["table_correct"],"self_consistent":e["proposal_consistent_with_own_table"],
                "categories":json.dumps(e["categories"]),"raw_text":row["raw_text"]})
        for row in analyses[tag]["instances"]:
            for c,metrics in row["conditions"].items():
                instance_rows.append({"model":tag,"case_id":row["case_id"],"kind":row["kind"],
                    "condition":c,**metrics})
        for c,metrics in analyses[tag]["conditions"].items():
            for name in ("dynamic_witness_correct","static_correct","table_correct_all","table_correct_dynamic",
                         "correct_table_wrong_witness_conditional","correct_table_wrong_witness_assigned",
                         "correct_table_valid_proposal_wrong_witness"):
                if metrics[name] is not None:
                    cross_rows.append({"model":tag,"condition":c,"metric":name,**metrics[name]})
    comparison = {"models":analyses,"exploratory_statistics":compare_statistics(analyses),
        "development_diagnostic":True,"independent_held_out":False,"formal_feedback_research":False,
        "formal_trial_started":False,"new_manual_reference":False,"new_game_or_cfr_variant":False,
        "new_runtime_epsilon_gto_allowed":False,"adaptive_opponent_line_released":False,
        "historical_failures_reinterpreted":False}
    write_json(OUT/"comparison.json",comparison)
    for name,rows in (("trials.csv",trial_rows),("instances.csv",instance_rows),("cross_analysis.csv",cross_rows)):
        with (OUT/name).open("w",newline="") as f:
            writer = csv.DictWriter(f,fieldnames=list(rows[0]) if rows else [])
            writer.writeheader(); writer.writerows(rows)
    print(json.dumps({tag:a["conditions"] for tag,a in analyses.items()},indent=2))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode",choices=("prepare","check","run","compare"))
    parser.add_argument("--model",choices=("luna6","sol61"))
    args = parser.parse_args()
    if args.mode=="prepare":
        if OUT.exists() or (ROOT/LOCK).exists(): raise FileExistsError("already frozen; no refreeze")
        validate_v7()
        prereg = subprocess.check_output(["git","log","-1","--format=%H","--",SPEC],cwd=ROOT).decode().strip()
        if not prereg or subprocess.check_output(["git","show",f"{prereg}:{SPEC}"],cwd=ROOT)!=(ROOT/SPEC).read_bytes():
            raise ValueError("preregistration must already be committed")
        historical = [f"research/results/{directory}/{tag}.json" for directory in (
            "gamespec_prospective_v5_2026-10-27","gamespec_witness_diagnostic_v6_2026-10-28",
            "gamespec_boundary_panel_v7_2026-10-29") for tag in ("luna6","sol61")]
        write_json(ROOT/LOCK,{"preregistration_commit":prereg,"generation_calls_executed":0,
            "sha256":hashes(),"historical_sha256":{p:sha256((ROOT/p).read_bytes()).hexdigest() for p in historical},
            "schemas":schemas(),"schemas_sha256":digest(schemas()),
            "pre_call_statistical_limit":{"dynamic_rule_pairs":6,"minimum_two_sided_p":2/64,
                "minimum_first_Holm_p_four_tests":4*2/64,"can_reach_adjusted_005":False},
            "bundle_sha256":{t:digest(package(t)[1]) for t in ("luna6","sol61")},
            "unchanged_reference_preflight":preflight()})
        print("Implementation, unchanged references and schemas frozen; commit before any generation.")
        return
    validate()
    if args.mode=="compare":
        export_comparison(); return
    for p in SOURCES+[LOCK]:
        if subprocess.check_output(["git","show",f"HEAD:{p}"],cwd=ROOT)!=(ROOT/p).read_bytes():
            raise ValueError(f"source not committed: {p}")
    if args.mode=="check":
        print("Committed preregistration, implementation, schemas, old results and exact references verified; zero calls.")
        return
    if args.model is None: parser.error("run requires --model")
    if (OUT/"oracle_stop.json").exists(): raise RuntimeError("oracle disagreement previously recorded")
    output = OUT/f"{args.model}.json"
    if output.exists(): raise FileExistsError("preserve existing run; no automatic resume/retry")
    key = os.environ.get("OPENAI_API_KEY") or load_dotenv_value(ROOT/".env","OPENAI_API_KEY")
    if not key: raise RuntimeError("API credential unavailable")
    from openai import OpenAI
    client = AttributionClient(OpenAI(api_key=key,base_url="https://api.openai.com/v1",timeout=60,max_retries=0))
    m,b = package(args.model)
    runner = AttributionRunner(m,b,client,output,lambda text:len(text.encode("utf-8")),halt_path=OUT/"oracle_stop.json")
    client.runner = runner
    report = runner.run()
    print(json.dumps({"status":report["status"],"stop_reason":report["stop_reason"],
                      "conditions":report["analysis"]["conditions"]},indent=2))
    if report["status"]!="completed": raise SystemExit(1)


if __name__=="__main__": main()
