from collections import Counter
from copy import deepcopy
import importlib.util
import inspect
import json
from pathlib import Path
import socket
import sys
from types import SimpleNamespace

import pytest

import aip.benchmark.gamespec_feedback_repair as core
from aip.benchmark.gamespec_attribution import derive_proposal, normalize_table, output_schema
from aip.benchmark.gamespec_smoke import digest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
try:
    spec = importlib.util.spec_from_file_location("feedback_repair_dispatch", ROOT / "scripts/run_gamespec_feedback_repair.py")
    D = importlib.util.module_from_spec(spec); spec.loader.exec_module(D)
finally:
    sys.path.pop(0)


class Client:
    def __init__(self, bundle, fault=None):
        self.b, self.fault, self.requests = bundle, fault, []
        self.chat = self.completions = self

    def create(self, **kwargs):
        self.requests.append(kwargs)
        if self.fault == "timeout": raise TimeoutError("PRIVATE credential must not be logged")
        p = self.b["plan"][len(self.requests) - 1]; item = self.b["cases"][p["case_id"]]
        table = normalize_table(item["visibility_contexts"], tuple(item["case"]["fields"]))
        if self.fault == "only_semantic" and p["feedback_arm"] != "semantic":
            table = deepcopy(core.proposed_table(self.b, p))
        if self.fault == "degrade_control" and p["seed_kind"] == "correct_control":
            table = deepcopy(self.b["seeds"][p["seed_id"]]["original_table"])
        if self.fault == "extra_handbook" and p["case_id"] == "case_608": table[1][0].append("handbook")
        proposal = derive_proposal(table, tuple(item["case"]["fields"]))
        if self.fault == "export": proposal["witness"]["player"] = 1 - proposal["witness"]["player"]
        text = "{" if self.fault == "invalid_json" else json.dumps({"stage_table": table, "proposal": proposal})
        reason = "length" if self.fault == "truncated" else "stop"
        raw = {"model": kwargs["model"], "usage": {"prompt_tokens": 500, "completion_tokens": 120},
               "choices": [{"finish_reason": reason, "message": {"content": text}}]}
        return SimpleNamespace(model=kwargs["model"], usage=SimpleNamespace(prompt_tokens=500, completion_tokens=120),
            choices=[SimpleNamespace(finish_reason=reason, message=SimpleNamespace(content=text, refusal=None))],
            model_dump=lambda **_: raw)


def mock_run(tmp_path, tag="luna6", fault=None):
    m, b = D.package(tag); raw = Client(b, fault); client = core.RepairClient(raw)
    runner = core.RepairRunner(m, b, client, tmp_path / f"{tag}.json", lambda _: 100, halt_path=tmp_path / "halt.json")
    client.runner = runner
    return m, b, raw, runner.run()


def test_seed_provenance_exact_originals_three_patterns_and_twelve_controls():
    m, b = D.package("luna6")
    raw = json.loads((ROOT / D.specification()["sources"]["raw"]).read_text())
    by_id = {t["trial_id"]: t for t in raw["trials"]}
    counts = Counter()
    for seed in b["seeds"].values():
        item = b["cases"][seed["case_id"]]; fields = tuple(item["case"]["fields"])
        old = raw["attempts"][by_id[seed["source_trial_id"]]["attempt_ids"][0]]
        table = json.loads(old["raw_response"]["choices"][0]["message"]["content"])["stage_table"]
        assert table == seed["original_table"]
        assert normalize_table(seed["correct_control"], fields) == normalize_table(item["visibility_contexts"], fields)
        assert core.cell_errors(seed["original_table"], item) > 0
        assert core.cell_errors(seed["correct_control"], item) == 0
        counts[seed["canonical_pattern"]] += 1
    assert sorted(counts.values()) == [2, 5, 5]
    assert all(b["cases"][s["case_id"]]["kind"] == "dynamic" for s in b["seeds"].values())
    assert len(b["plan"]) == 72 and len({p["trial_id"] for p in b["plan"]}) == 72
    assert Counter((p["feedback_arm"], p["seed_kind"]) for p in b["plan"]) == {
        (a, k): 12 for a in core.ARMS for k in core.KINDS}


def test_local_feedback_has_no_reference_arguments_or_semantic_failure_bit():
    assert set(inspect.signature(core.local_feedback).parameters) == {"fields", "table"}
    _, b = D.package("luna6")
    for p in b["plan"]:
        if p["feedback_arm"] != "local": continue
        f = core.feedback_for(b, p)
        assert f["status"] == "locally_consistent_unverified" and f["semantic_result"] == "not_assessed"
        assert not f["violations"] and "rule_excerpts" not in f
        assert "mismatched" not in json.dumps(f) and "reference" not in json.dumps(f)


def test_common_rules_schema_source_priority_and_only_feedback_block_varies():
    for tag in ("luna6", "sol61"):
        m, b = D.package(tag); om, ob = D.old_package(tag)
        for seed_id in b["seeds"]:
            for kind in core.KINDS:
                trials = [p for p in b["plan"] if p["seed_id"] == seed_id and p["seed_kind"] == kind]
                msgs = [core.messages_for(m, b, p) for p in trials]
                assert all(msg[:2] == msgs[0][:2] for msg in msgs)
                assert len({msg[-1]["content"].split("\nFEEDBACK: ")[0] for msg in msgs}) == 1
                for p, msg in zip(trials, msgs):
                    case = b["cases"][p["case_id"]]["case"]
                    assert case["rules"] in msg[-1]["content"]
                    assert msg[0] == core.old_messages(om, ob, p)[0]
                    assert core.parameters(m, b, p) == core.old_parameters(om, ob, p)
                    assert core.parameters(m, b, p)["response_format"]["json_schema"]["schema"] == output_schema(om, case, "C")
                    for forbidden in ("correct_control", "source_trial_id", "reference_owners", "visibility_contexts", "canonical_pattern"):
                        assert forbidden not in json.dumps(msg)
        assert m["model"] == om["model"]


def test_excerpts_have_exact_offsets_and_identical_wrong_correct_feedback_evidence():
    _, b = D.package("luna6")
    for case_id, entries in b["evidence_registry"].items():
        rules = b["cases"][case_id]["case"]["rules"]
        for e in entries: assert rules[e["start"]:e["end"]] == e["quote"] and rules.count(e["quote"]) == 1
        feedbacks = [core.feedback_for(b, p)["rule_excerpts"] for p in b["plan"] if p["case_id"] == case_id and p["feedback_arm"] == "semantic"]
        assert all(f == entries for f in feedbacks)
    spec = D.specification(); spec["evidence_registry"]["excerpts"]["case_281"][0] = "invented rule"
    with pytest.raises(ValueError): core.evidence_registry(spec, b["cases"])


@pytest.mark.parametrize("tag", ["luna6", "sol61"])
def test_mock_ceiling_offline_replay_no_gain_no_runtime_authority(tmp_path, monkeypatch, tag):
    m, b, raw, report = mock_run(tmp_path, tag)
    monkeypatch.setattr(socket, "create_connection", lambda *a, **k: pytest.fail("network in offline replay"))
    assert core.replay(m, b, report)["raw_rescoring_agrees"]
    assert len(raw.requests) == 72
    for arm in core.ARMS:
        assert report["analysis"]["conditions"][arm]["wrong"]["joint_correct"] == 12
        assert report["analysis"]["conditions"][arm]["correct_control"]["incorrect_joint_completed"] == 0
    assert report["analysis"]["semantic_minus_local_joint_repair"] == 0
    assert report["analysis"]["overall_scientific_pass"] is None
    assert not report["runtime_epsilon_gto_allowed"] and not report["adaptive_opponent_line_released"]


def test_semantic_only_mock_produces_cross_checks_without_erasing_local_failures(tmp_path):
    m, b, _, report = mock_run(tmp_path, fault="only_semantic")
    assert core.replay(m, b, report)["raw_rescoring_agrees"]
    a = report["analysis"]
    assert a["conditions"]["local"]["wrong"]["table_correct"] == 0
    assert a["conditions"]["semantic"]["wrong"]["joint_correct"] == 12
    assert a["semantic_minus_local_joint_repair"] == 1
    assert len(a["cross_checks"]["joint_correct"]["local_fail_semantic_success"]) == 12
    assert len(a["all_failures"]) == 24


def test_control_degradation_is_measured_separately(tmp_path):
    m, b, _, report = mock_run(tmp_path, fault="degrade_control")
    assert core.replay(m, b, report)["raw_rescoring_agrees"]
    for arm in core.ARMS:
        assert report["analysis"]["conditions"][arm]["wrong"]["joint_correct"] == 12
        assert report["analysis"]["conditions"][arm]["correct_control"]["semantic_table_degradation_valid_subset"] == 12


def test_duplicate_weighting_does_not_masquerade_as_independent_patterns():
    m, b = D.package("luna6"); trials = []
    for p in b["plan"]:
        item = b["cases"][p["case_id"]]
        table = item["visibility_contexts"] if p["case_id"] == "case_281" else core.proposed_table(b, p)
        text = json.dumps({"stage_table": table,
            "proposal": derive_proposal(table, tuple(item["case"]["fields"]))})
        trials.append(dict(p, status="completed", **core.evaluate(text, m, b, p)))
    analysis = core.analyze(m, b, {"trials": trials, "attempts": []})
    assert analysis["conditions"]["semantic"]["wrong"]["joint_correct"] == 5
    assert analysis["equal_group_rates"]["canonical_pattern"]["semantic"]["joint_correct"] == pytest.approx(1 / 3)
    assert analysis["equal_group_rates"]["case_id"]["semantic"]["joint_correct"] == pytest.approx(1 / 2)


def test_wrong_handbook_can_have_right_proposal_but_never_joint_repair(tmp_path):
    m, b, _, report = mock_run(tmp_path, fault="extra_handbook")
    assert core.replay(m, b, report)["raw_rescoring_agrees"]
    rows = [t for t in report["trials"] if t["case_id"] == "case_608"]
    assert all(t["evaluation"]["legacy"]["correct"] and not t["metrics"]["joint_correct"] for t in rows)
    assert all(t["metrics"]["output_cell_errors"] == 1 for t in rows)


@pytest.mark.parametrize("fault", ["invalid_json", "truncated", "export"])
def test_interface_and_export_failures_preserved(tmp_path, fault):
    m, b, _, report = mock_run(tmp_path, fault=fault)
    assert core.replay(m, b, report)["raw_rescoring_agrees"]
    assert len(report["analysis"]["all_failures"]) == 72
    if fault == "invalid_json":
        assert all(t["metrics"]["output_cell_errors"] is None for t in report["trials"])


def test_timeout_stops_and_retains_assigned_denominators_no_credential_messages(tmp_path):
    m, b, raw, report = mock_run(tmp_path, fault="timeout")
    assert report["status"] == "stopped" and len(raw.requests) == 1
    assert "PRIVATE" not in json.dumps(report)
    assert core.replay(m, b, report)["raw_rescoring_agrees"]
    assert all(report["analysis"]["conditions"][a][k]["assigned"] == 12 for a in core.ARMS for k in core.KINDS)
    with pytest.raises(FileExistsError): mock_run(tmp_path)


def test_oracle_disagreement_preserves_reply_stops_globally(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "verify_frozen_output", lambda *a, **k: (_ for _ in ()).throw(ValueError("paths disagree")))
    _, _, raw, report = mock_run(tmp_path)
    assert len(raw.requests) == 1 and report["status"] == "stopped"
    assert (tmp_path / "halt.json").exists() and report["oracle_counterexample"]["raw_text"]


@pytest.mark.parametrize("change", ["request", "cost", "score", "raw", "assignment", "summary", "metrics"])
def test_offline_tampering_rejected(tmp_path, change):
    m, b, _, report = mock_run(tmp_path)
    if change == "request": report["attempts"][0]["messages"][0]["content"] += "tampered"
    elif change == "cost": report["attempts"][0]["cost_usd"] += 1
    elif change == "score": report["trials"][0]["evaluation"]["table_correct"] = False
    elif change == "raw": report["trials"][0]["raw_text"] = "{}"
    elif change == "assignment": report["trials"][0]["seed_kind"] = "correct_control"
    elif change == "metrics": report["trials"][0]["metrics"]["output_cell_errors"] = 99
    else: report["analysis"]["semantic_minus_local_joint_repair"] = 99
    with pytest.raises(ValueError): core.replay(m, b, report)
