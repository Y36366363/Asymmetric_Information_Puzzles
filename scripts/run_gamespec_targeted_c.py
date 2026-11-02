#!/usr/bin/env python3
"""v10 frozen C-only developmental retest; no changes to v7/v8 truth/scorers."""
import argparse
from collections import Counter
from copy import deepcopy
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess

from aip.benchmark.completion import load_dotenv_value
from aip.benchmark.gamespec_attribution import AttributionClient, messages_for, parameters
from aip.benchmark.gamespec_smoke import SmokeRunner, digest, write_json
from aip.benchmark.gamespec_validation import verify_frozen_output
from run_gamespec_attribution import SOURCES as OLD_SOURCES, package as old_package, validate as old_validate

ROOT = Path(__file__).resolve().parents[1]
SPEC = "configs/gamespec_targeted_c_v10_2026-11-02.json"
LOCK = "configs/gamespec_targeted_c_v10_lock_2026-11-02.json"
OUT = ROOT / "research/results/gamespec_targeted_c_v10_2026-11-02"
SOURCES = list(dict.fromkeys(OLD_SOURCES + [SPEC, "scripts/run_gamespec_targeted_c.py",
    "src/aip/core/observation_validation.py", "src/aip/core/evaluation.py", "src/aip/core/cfr.py",
    "src/aip/benchmark/gamespec_validation.py", "src/aip/benchmark/gamespec_local_checks.py",
    "scripts/audit_gamespec_validation.py", "tests/test_gamespec_targeted_c.py"]))


def specification():
    spec = json.loads((ROOT / SPEC).read_text())
    if spec["selection"]["case_ids"] != ["case_417", "case_345"] or spec["schedule"] != {
        "condition": "C", "repeats_per_case_per_model": 5, "models": ["luna6", "sol61"],
        "calls_per_model": 10, "maximum_generation_calls": 20,
        "order": "repeat 0..4 then case_417,case_345; each reply independent, no prior replies or error hints",
        "maximum_global_concurrency": 2, "per_model_concurrency": 1,
        "no_retries_topups_or_resampling": True}:
        raise ValueError("fixed two-case C-only schedule required")
    return spec


def package(tag):
    spec = specification()
    m, b = deepcopy(old_package(tag))
    m["manifest_id"] = spec["manifest_id"] + ":" + tag
    m["targeted_c_spec"] = spec
    m["schedule"] = {"maximum_calls": 10}
    b["plan"] = [next(deepcopy(p) for p in b["plan"] if p["condition"] == "C"
        and p["case_id"] == case and p["repeat"] == repeat)
        for repeat in range(5) for case in spec["selection"]["case_ids"]]
    b["manifest_sha256"] = digest(m)
    return m, b


def analyze(manifest, bundle, report):
    trials = {t["trial_id"]: t for t in report["trials"]}
    rows = []
    for p in bundle["plan"]:
        t = trials.get(p["trial_id"], {})
        e = t.get("evaluation")
        if e is None:
            quadrant = "incomplete"
        elif e["interface_errors"] or e["transport_errors"] or not e["legacy"]["serialization_ok"]:
            quadrant = "interface_or_transport_error"
        else:
            quadrant = ("table_correct" if e["table_correct"] else "table_wrong") + (
                "_proposal_correct" if e["legacy"]["correct"] else "_proposal_wrong")
        rows.append(dict(p, status=t.get("status", "unexecuted"), quadrant=quadrant,
            table_correct=bool(e and e["table_correct"]), proposal_correct=bool(e and e["legacy"]["correct"]),
            valid_proposal=bool(e and e["legacy"]["serialization_ok"]),
            table_cell_differences=e["table_cell_differences"] if e else [],
            categories=e["categories"] if e else ["incomplete"],
            validation=t.get("validation"), raw_text=t.get("raw_text")))
    def summary(selected):
        return {"assigned": len(selected), "completed": sum(r["status"] == "completed" for r in selected),
            "table_correct": sum(r["table_correct"] for r in selected),
            "proposal_correct": sum(r["proposal_correct"] for r in selected),
            "quadrants": dict(Counter(r["quadrant"] for r in selected)),
            "states": {s: sum((r["validation"] or {}).get("status") == s for r in selected)
                       for s in ("reject_local", "locally_consistent_unverified", "verified")},
            "unexecuted_without_validation": sum(r["validation"] is None for r in selected)}
    attempts = report["attempts"]
    return {"rows": rows, "overall": summary(rows),
        "cases": {c: summary([r for r in rows if r["case_id"] == c])
                  for c in manifest["targeted_c_spec"]["selection"]["case_ids"]},
        "resources": {"calls": len(attempts),
            "cost_usd_estimate_including_unknown_reservations": sum(a["cost_usd"] for a in attempts),
            "unknown_usage_attempts": sum(not a.get("raw_response", {}).get("usage") for a in attempts),
            "tokens": {k: sum((a.get("raw_response", {}).get("usage") or {}).get(k, 0) for a in attempts)
                       for k in ("prompt_tokens", "completion_tokens")},
            "latency_seconds": sum(a.get("latency_seconds", 0) for a in attempts),
            "errors": dict(Counter(e for a in attempts for e in a["errors"]))},
        "all_failures": [r for r in rows if r["quadrant"] != "table_correct_proposal_correct"],
        "old_A_latent_error_layer_identified": False, "overall_scientific_pass": None,
        "development_diagnostic": True, "independent_held_out": False,
        "formal_trial_started": False, "new_runtime_epsilon_gto_allowed": False,
        "adaptive_opponent_line_released": False, "old_scores_changed": False}


class TargetedRunner(SmokeRunner):
    def __init__(self, *args, halt_path, **kwargs):
        super().__init__(*args, **kwargs)
        self.halt_path = halt_path

    def run(self):
        self.report["schema_version"] = "aip-gamespec-targeted-c-v10"
        self.persist()
        try:
            for p in self.bundle["plan"]:
                if self.halt_path.exists(): raise RuntimeError("global_oracle_stop")
                self.active_trial = p
                t = dict(p, status="started", attempt_ids=[])
                self.report["trials"].append(t)
                try:
                    _, text, attempt = self.call(p["trial_id"], messages_for(self.manifest, self.bundle, p))
                finally:
                    t["attempt_ids"] = [a["attempt_id"] for a in self.report["attempts"] if a["trial_id"] == p["trial_id"]]
                t["raw_text"] = text
                try:
                    record, local, _, e = verify_frozen_output(text, "C", self.bundle["cases"][p["case_id"]], attempt["errors"])
                except ValueError as error:
                    counterexample = {"trial_id": p["trial_id"], "raw_text": text, "error": str(error)}
                    self.report["oracle_counterexample"] = counterexample
                    write_json(self.halt_path, counterexample)
                    raise RuntimeError("independent_oracle_disagreement") from None
                t.update(status="completed", evaluation=e, validation=record.to_artifact(), local=local)
                self.persist()
            self.report["status"] = "completed"
        except RuntimeError as error:
            self.report["status"], self.report["stop_reason"] = "stopped", str(error)
        self.report["analysis"] = analyze(self.manifest, self.bundle, self.report)
        self.persist()
        return self.report


def replay(manifest, bundle, report):
    """Re-evaluate raw responses and audit exact requests, costs and assignments."""
    if report["manifest_sha256"] != digest(manifest) or report["bundle_sha256"] != digest(bundle):
        raise ValueError("manifest/bundle changed")
    plan = bundle["plan"]
    if len(report["trials"]) > len(plan) or len(report["attempts"]) > len(plan):
        raise ValueError("excess trials or attempts")
    used = set()
    for p, t in zip(plan, report["trials"]):
        if any(t[k] != v for k, v in p.items()): raise ValueError("assignment changed")
        if t["status"] != "completed": continue
        if len(t["attempt_ids"]) != 1: raise ValueError("one attempt required")
        i = t["attempt_ids"][0]
        if i in used: raise ValueError("attempt reused")
        used.add(i)
        a = report["attempts"][i]
        raw = a["raw_response"]
        choice = raw["choices"][0]
        text = choice["message"]["content"] or ""
        errors = [] if choice["finish_reason"] == "stop" else ["truncated_output" if choice["finish_reason"] == "length" else "provider_error"]
        try: json.loads(text, parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite")))
        except (ValueError, TypeError): errors.append("invalid_json")
        model, usage = manifest["model"], raw["usage"]
        if raw["model"] != model["model_id"] or any(usage[k] > model[cap] for k, cap in (
            ("prompt_tokens", "maximum_input_tokens"), ("completion_tokens", "maximum_output_tokens"))):
            raise ValueError("model or token cap changed")
        cost = (usage["prompt_tokens"] * model["input_usd_per_million"] + usage["completion_tokens"] * model["output_usd_per_million"]) / 1e6
        if a["errors"] != errors or abs(cost - a["cost_usd"]) > 1e-12 or text != t["raw_text"]:
            raise ValueError("raw reply, errors or cost changed")
        record, local, _, e = verify_frozen_output(text, "C", bundle["cases"][p["case_id"]], errors)
        if e != t["evaluation"] or local != t["local"] or record.to_artifact() != t["validation"]:
            raise ValueError("raw rescoring differs")
    by_id = {p["trial_id"]: p for p in plan}
    for i, a in enumerate(report["attempts"]):
        p = by_id.get(a["trial_id"])
        if p is None or a["attempt_id"] != i or a["messages"] != messages_for(manifest, bundle, p) or a["provider_parameters"] != parameters(manifest, bundle, p):
            raise ValueError("unassigned or changed request")
    if report["status"] == "completed" and (len(used) != len(plan) or len(report["trials"]) != len(plan)):
        raise ValueError("completed report missing trials")
    analysis = analyze(manifest, bundle, report)
    if analysis != report["analysis"]: raise ValueError("summary changed")
    return {"raw_rescoring_agrees": True, "analysis": analysis}


def hashes():
    return {p: sha256((ROOT / p).read_bytes()).hexdigest() for p in SOURCES}


def requests():
    return {tag: [{"trial": p, "messages": messages_for(m, b, p), "parameters": parameters(m, b, p)}
        for p in b["plan"]] for tag in ("luna6", "sol61") for m, b in [package(tag)]}


def validate(committed=False):
    old_validate()
    lock = json.loads((ROOT / LOCK).read_text())
    if lock["sha256"] != hashes() or lock["requests_sha256"] != digest(requests()):
        raise ValueError("frozen source or requests changed")
    for p, h in lock["historical_sha256"].items():
        if sha256((ROOT / p).read_bytes()).hexdigest() != h: raise ValueError("historical evidence changed")
    if committed:
        for p in SOURCES + [LOCK]:
            if subprocess.check_output(["git", "show", f"HEAD:{p}"], cwd=ROOT) != (ROOT / p).read_bytes():
                raise ValueError("uncommitted implementation or lock")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("prepare", "check", "run", "compare"))
    parser.add_argument("--model", choices=("luna6", "sol61"))
    args = parser.parse_args()
    if args.mode == "prepare":
        if (ROOT / LOCK).exists() or OUT.exists(): raise FileExistsError("already frozen")
        old_validate()
        prereg = subprocess.check_output(["git", "log", "-1", "--format=%H", "--", SPEC], cwd=ROOT).decode().strip()
        if not prereg or subprocess.check_output(["git", "show", f"{prereg}:{SPEC}"], cwd=ROOT) != (ROOT / SPEC).read_bytes():
            raise ValueError("commit preregistration first")
        historical = [f"research/results/{directory}/{tag}.json" for directory in (
            "gamespec_attribution_v8_2026-10-30", "gamespec_boundary_panel_v7_2026-10-29") for tag in ("luna6", "sol61")]
        write_json(ROOT / LOCK, {"preregistration_commit": prereg, "sha256": hashes(),
            "requests_sha256": digest(requests()), "requests": requests(),
            "bundle_sha256": {t: digest(package(t)[1]) for t in ("luna6", "sol61")},
            "historical_sha256": {p: sha256((ROOT / p).read_bytes()).hexdigest() for p in historical},
            "generation_calls_executed": 0})
        print("Frozen 20 exact C requests; commit implementation/lock before dispatch.")
        return
    validate(committed=args.mode in ("check", "run"))
    if args.mode == "check":
        print("Committed sources, reference, requests and old evidence verified; zero calls.")
        return
    if args.mode == "compare":
        for tag in ("luna6", "sol61"):
            m, b = package(tag)
            write_json(OUT / f"{tag}_rescored.json", replay(m, b, json.loads((OUT / f"{tag}.json").read_text())))
        return
    if not args.model: parser.error("run requires --model")
    if (OUT / "oracle_stop.json").exists(): raise RuntimeError("global oracle stop exists")
    output = OUT / f"{args.model}.json"
    if output.exists(): raise FileExistsError("preserve previous run; no automatic resume")
    key = os.environ.get("OPENAI_API_KEY") or load_dotenv_value(ROOT / ".env", "OPENAI_API_KEY")
    if not key: raise RuntimeError("API credential unavailable")
    from openai import OpenAI
    client = AttributionClient(OpenAI(api_key=key, base_url="https://api.openai.com/v1", timeout=60, max_retries=0))
    m, b = package(args.model)
    runner = TargetedRunner(m, b, client, output, lambda text: len(text.encode("utf-8")), halt_path=OUT / "oracle_stop.json")
    client.runner = runner
    report = runner.run()
    print(json.dumps({"status": report["status"], "analysis": report["analysis"]}, indent=2))
    if report["status"] != "completed": raise SystemExit(1)


if __name__ == "__main__": main()
