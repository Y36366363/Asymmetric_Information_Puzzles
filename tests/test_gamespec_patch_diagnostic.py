from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import socket
import sys
from types import SimpleNamespace

import pytest

from aip.benchmark import gamespec_patch_diagnostic as core
from aip.benchmark.gamespec_attribution import derive_proposal
from aip.benchmark.gamespec_cell_audit import difference_patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
try:
    import audit_gamespec_copy as copy_audit
    spec = importlib.util.spec_from_file_location("patch_dispatch", ROOT / "scripts/run_gamespec_patch_diagnostic.py")
    D = importlib.util.module_from_spec(spec); spec.loader.exec_module(D)
finally:
    sys.path.pop(0)


class Client:
    def __init__(self, b, fault=None):
        self.b, self.fault, self.requests = b, fault, []
        self.chat = self.completions = self

    def create(self, **kwargs):
        self.requests.append(kwargs)
        if self.fault == "timeout": raise TimeoutError("PRIVATE credential must not be printed")
        p = self.b["plan"][len(self.requests)-1]; item = self.b["cases"][p["case_id"]]
        fields = tuple(item["case"]["fields"]); original = core.input_table(self.b, p)
        table = deepcopy(item["visibility_contexts"])
        if self.fault == "no_change": table = deepcopy(original)
        if self.fault == "degrade" and p["seed_kind"] == "correct_control":
            table = deepcopy(self.b["seeds"][p["seed_id"]]["original_table"])
        payload = {"proposal": derive_proposal(item["visibility_contexts"], fields)}
        payload["edits" if p["representation"] == "patch" else "stage_table"] = (
            difference_patch(original, table, fields) if p["representation"] == "patch" else table)
        if self.fault == "bad_patch" and p["representation"] == "patch":
            payload["edits"] = [{"stage": True, "player": 0, "field": fields[0], "action": "add"}]
        if self.fault == "wrong_proposal": payload["proposal"]["witness"]["player"] = 1-payload["proposal"]["witness"]["player"]
        text = "{" if self.fault == "invalid_json" else json.dumps(payload)
        raw = {"model": "wrong" if self.fault == "model" else kwargs["model"],
            "usage": None if self.fault == "usage" else {"prompt_tokens": 500, "completion_tokens": 100},
            "choices": [{"finish_reason": "length" if self.fault == "truncated" else "stop",
                         "message": {"content": text, "refusal": "no" if self.fault == "refusal" else None}}]}
        return SimpleNamespace(model=raw["model"],
            usage=SimpleNamespace(**raw["usage"]) if raw["usage"] else None,
            choices=[SimpleNamespace(finish_reason=raw["choices"][0]["finish_reason"],
                message=SimpleNamespace(**raw["choices"][0]["message"]))], model_dump=lambda **_: raw)


def mock_run(tmp_path, fault=None):
    m, b = D.package(); actual = Client(b, fault); client = core.PatchClient(actual)
    runner = core.PatchRunner(m, b, client, tmp_path / "raw.json", lambda s: len(s.encode()), halt_path=tmp_path / "stop.json")
    client.runner = runner
    return m, b, actual, runner.run()


def test_copy_audit_distinguishes_observation_from_hidden_edit_history(monkeypatch):
    monkeypatch.setattr(socket, "create_connection", lambda *a, **k: pytest.fail("network forbidden"))
    a = copy_audit.build()
    assert a == json.loads(copy_audit.DEST.read_text())
    assert a["classes"] == {"same_final_cells": 10, "changed_final_cells": 2}
    assert (a["raw_fragment_equal"], a["same_order_whitespace_only"], a["same_cells_different_order"]) == (0, 9, 1)
    assert a["changed_then_reverted_count"] is None
    fields = ("a", "b"); original = '{"stage_table":[[["a","b"],["b"]],[["a"],["b"]]]}'
    for text in ('{}', '{"stage_table":[]}', '{"stage_table":null}', '{'):
        assert copy_audit.compare(original, text, fields)["class"] == "missing_or_invalid_table"
    same = copy_audit.compare(original, original, fields)
    assert same["raw_fragment_equal"] and same["changed_then_reverted"] is None
    assert copy_audit.table_fragment('{"proposal":{}, "stage_table":[[],[]]}') == '[[],[]]'


def test_preflight_fairness_requests_and_dependencies(tmp_path, monkeypatch):
    assert D.preflight()["reference_roundtrips"] == 72
    m, b = D.package()
    requests = D.requests()
    assert len(requests) == 72 and {r["parameters"]["model"] for r in requests} == {"gpt-6-luna"}
    for p in b["plan"]:
        other = dict(p, representation="rewrite" if p["representation"] == "patch" else "patch")
        a, c = core.messages_for(m, b, p), core.messages_for(m, b, other)
        assert a[:2] == c[:2]
        assert a[-1]["content"].split("\nProposal JSON schema:")[0] == c[-1]["content"].split("\nProposal JSON schema:")[0]
        for forbidden in ("correct_control", "reference_table", "oracle", "canonical_pattern"):
            assert forbidden not in json.dumps(a)
        params = core.parameters(m, b, p)
        assert params["temperature"] == 0 and params["reasoning_effort"] == "none"
        assert params["response_format"]["json_schema"]["strict"]
    # The CI verification environment intentionally omits the optional SDK.
    # Exercise traversal/hashing with installed-distribution stand-ins instead.
    from pathlib import PurePosixPath
    (tmp_path / "sdk.py").write_text("sdk source")
    (tmp_path / "METADATA").write_text("package metadata")
    (tmp_path / "cache.pyc").write_bytes(b"mutable cache")
    def distribution(name):
        return SimpleNamespace(version="2.14.0" if name == "openai" else "1.0",
            files=[PurePosixPath(p) for p in ("sdk.py", "METADATA", "cache.pyc")],
            locate_file=lambda p: tmp_path / p,
            requires=['httpx>=0.1', 'unavailable; extra == "unused"'] if name == "openai" else [])
    monkeypatch.setattr(D.metadata, "distribution", distribution)
    deps = D.runtime_dependencies()
    assert deps == D.runtime_dependencies() and deps["distributions"]["openai"]["version"]
    assert deps["distributions"]["httpx"]["installed_files_sha256"]
    assert set(deps["distributions"]) == {"openai", "packaging", "httpx"}
    assert "cache.pyc" not in deps["distributions"]["openai"]["installed_files_sha256"]
    (tmp_path / "sdk.py").write_text("changed SDK source")
    assert deps != D.runtime_dependencies()


def test_mock_ceiling_replay_controls_and_no_runtime_authority(tmp_path, monkeypatch):
    m, b, client, report = mock_run(tmp_path)
    monkeypatch.setattr(socket, "create_connection", lambda *a, **k: pytest.fail("replay network forbidden"))
    assert core.replay(m, b, report)["raw_rescoring_agrees"]
    assert len(client.requests) == 72 and not report["analysis"]["sol_reentry"]["triggered"]
    for f in ("none", "local"):
        for fmt in ("rewrite", "patch"):
            assert report["analysis"]["conditions"][f][fmt]["wrong"]["joint_correct"] == 9
            assert report["analysis"]["conditions"][f][fmt]["correct_control"]["correct_input_table_degraded"] == 0
    assert report["analysis"]["overall_scientific_pass"] is None
    assert not report["runtime_epsilon_gto_allowed"] and not report["adaptive_opponent_line_released"]
    with pytest.raises(FileExistsError): mock_run(tmp_path)


@pytest.mark.parametrize("fault", ["no_change", "degrade", "bad_patch", "wrong_proposal", "invalid_json", "truncated"])
def test_failures_not_fixed_or_dropped(tmp_path, fault):
    m, b, _, report = mock_run(tmp_path, fault)
    assert core.replay(m, b, report)["raw_rescoring_agrees"] and len(report["trials"]) == 72
    if fault == "no_change":
        assert report["analysis"]["sol_reentry"]["triggered"]
        assert report["analysis"]["sol_reentry"]["correct_proposal_wrong_table_failures"] == 18
    if fault == "bad_patch":
        rows = [t for t in report["trials"] if t["representation"] == "patch"]
        assert all(t["proposal_only"]["correct"] and t["expanded_output"] is None and not t["metrics"]["joint_correct"] for t in rows)
    if fault == "degrade":
        assert all(report["analysis"]["conditions"][f][fmt]["correct_control"]["correct_input_table_degraded"] == 9
                   for f in ("none", "local") for fmt in ("rewrite", "patch"))
    if fault in ("invalid_json", "truncated"):
        assert len(report["analysis"]["all_failures"]) == 72


@pytest.mark.parametrize("fault", ["timeout", "usage", "refusal", "model"])
def test_provider_stop_retains_every_assigned_denominator(tmp_path, fault):
    m, b, client, report = mock_run(tmp_path, fault)
    assert report["status"] == "stopped" and len(client.requests) == 1
    assert core.replay(m, b, report)["raw_rescoring_agrees"]
    assert report["analysis"]["assigned"] == 72 and not report["analysis"]["sol_reentry"]["eligible"]
    assert "PRIVATE" not in json.dumps(report)
    if fault in ("timeout", "usage"):
        assert report["analysis"]["resources"]["known_cost_usd_estimate"] == 0
        assert report["analysis"]["resources"]["failed_or_unknown_usage_reserved_usd"] > 0


def test_scoring_disagreement_halts_without_another_dispatch(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "verify_frozen_output", lambda *a, **k: (_ for _ in ()).throw(ValueError("paths disagree")))
    _, _, client, report = mock_run(tmp_path)
    assert report["status"] == "stopped" and len(client.requests) == 1
    assert (tmp_path / "stop.json").exists() and report["oracle_counterexample"]["raw_text"]


@pytest.mark.parametrize("field", ["assignment", "request", "parameters", "raw", "cost", "metrics", "ledger", "summary", "runtime", "usage"])
def test_tampering_is_rejected(tmp_path, field):
    m, b, _, report = mock_run(tmp_path)
    t, a = report["trials"][0], report["attempts"][0]
    if field == "assignment": t["seed_id"] = "other"
    elif field == "request": a["messages"][1]["content"] += "tamper"
    elif field == "parameters": a["provider_parameters"]["temperature"] = 1
    elif field == "raw": a["raw_response"]["choices"][0]["message"]["content"] = '{}'
    elif field == "cost": a["cost_usd"] += .1
    elif field == "metrics": t["metrics"]["table_correct"] = False
    elif field == "ledger": t["cell_ledger"][0]["reference"] = "changed"
    elif field == "summary": report["analysis"]["resources"]["attempts"] = 0
    elif field == "runtime": report["runtime_epsilon_gto_allowed"] = True
    elif field == "usage": a["raw_response"]["usage"]["completion_tokens"] += 1
    with pytest.raises(ValueError): core.replay(m, b, report)


def test_trigger_strict_boundary_and_no_claim_of_understanding():
    _, b = D.package()
    rows = [dict(p, status="completed", metrics={"table_correct": True, "reference_proposal_correct": True}) for p in b["plan"]]
    patches = [r for r in rows if r["seed_kind"] == "wrong" and r["representation"] == "patch"]
    for r in patches[:9]: r["metrics"]["table_correct"] = False
    assert core.sol_trigger(rows)["patch_wrong_table_correct"] == 9
    assert not core.sol_trigger(rows)["triggered"]  # exactly 50% is not <50%
    patches[9]["metrics"]["table_correct"] = False
    assert core.sol_trigger(rows)["triggered"]
    for r in patches[:5]: r["metrics"]["reference_proposal_correct"] = False
    assert not core.sol_trigger(rows)["triggered"]  # exactly half is not a majority
    patches[0]["metrics"]["reference_proposal_correct"] = True
    assert core.sol_trigger(rows)["triggered"] and not core.sol_trigger(rows)["scientific_pass_or_cognitive_label"]
    rows[0]["status"] = "started"
    assert not core.sol_trigger(rows)["eligible"]
