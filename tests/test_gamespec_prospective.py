from copy import deepcopy
import importlib.util
from itertools import product
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

from aip.benchmark.gamespec_prospective import (ProspectiveRunner, audit_references, projection, replay, score)
from aip.benchmark.gamespec_interface import ParameterClient, messages_for, parameters

ROOT = Path(__file__).resolve().parents[1]


def load_dispatch():
    sys.path.insert(0, str(ROOT / "scripts"))
    try:
        spec = importlib.util.spec_from_file_location("prospective_dispatch", ROOT / "scripts/run_gamespec_prospective.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.pop(0)


DISPATCH = load_dispatch()
M, B = DISPATCH.package("luna6")


def proposal(item, owners=None):
    if item["kind"] == "dynamic" and owners is None:
        return {"decision": "refusal", "candidates": [], "witness": item["control"]["required_witness"]}
    owners = owners or item["case"]["reference_owners"]
    return {"decision": "candidate", "candidates": [{"public_fields": [k for k, v in owners.items() if v == "public"],
        "private_fields_by_player": {p: [k for k, v in owners.items() if v == p] for p in ("player_0", "player_1")}}], "witness": None}


class Client:
    def __init__(self, bundle, wrong=False, fail=False):
        self.bundle, self.wrong, self.fail = bundle, wrong, fail
        self.chat = SimpleNamespace(completions=self)
        self.requests = []

    def create(self, **kwargs):
        self.requests.append(kwargs)
        if self.fail:
            raise RuntimeError("SECRET must not be published")
        case_id = kwargs["messages"][-1]["content"].split("Case: ")[1].split("\n")[0]
        item = self.bundle["cases"][case_id]
        payload = proposal(item, dict.fromkeys(item["case"]["fields"], "public")) if self.wrong else proposal(item)
        text = json.dumps(payload)
        raw = {"model": kwargs["model"], "usage": {"prompt_tokens": 200, "completion_tokens": 100},
               "choices": [{"finish_reason": "stop", "message": {"content": text}}]}
        return SimpleNamespace(model=kwargs["model"], usage=SimpleNamespace(prompt_tokens=200, completion_tokens=100),
            choices=[SimpleNamespace(finish_reason="stop", message=SimpleNamespace(content=text, refusal=None))], model_dump=lambda **_:raw)


def test_configuration_exactly_preserves_v4_selected_arm_and_has_no_41mini():
    for tag in ("luna6", "sol61"):
        m, b = DISPATCH.package(tag)
        old_m, _ = DISPATCH.v4_package(tag)
        assert m["model"] == old_m["model"]
        for key in ("system_prompt", "source_priority_prompt", "output_contract"):
            assert m["interface_spec"][key] == old_m["interface_spec"][key]
        assert len(b["plan"]) == 24
        assert {p["arm"] for p in b["plan"]} == {"f1_s1"}
        assert all(parameters(m, b, p)["response_format"]["type"] == "json_schema" for p in b["plan"])
    with pytest.raises(ValueError):
        DISPATCH.package("mini41")


def test_new_instances_not_old_rules_and_no_reference_in_requests():
    _, old = DISPATCH.v4_package("luna6")
    old_rules = {c["case"]["rules"] for c in old["cases"].values()}
    assert all(c["case"]["rules"] not in old_rules for c in B["cases"].values())
    for p in B["plan"]:
        messages = messages_for(M, B, p)
        text = json.dumps(messages)
        assert "reference_owners" not in text and "visibility_contexts" not in text
        assert "required_witness" not in text and "final_reference" not in text
        if p["task"] == "witness_repair":
            assert '"witnesses"' in messages[-1]["content"]


def test_reference_disagreement_blocks_before_dispatch():
    spec = DISPATCH.specification()
    assert audit_references(spec)["passed"]
    bad = deepcopy(spec)
    bad["pairs"][0]["owners"]["route"] = "public"
    with pytest.raises(ValueError, match="disagrees"):
        audit_references(bad)


@pytest.mark.parametrize("pair", B["pairs"], ids=lambda p:p["pair_id"])
def test_all_static_partitions_crosscheck_independent_oracle(pair):
    static, dynamic = B["cases"][pair["static_id"]], B["cases"][pair["dynamic_id"]]
    fields = list(pair["fields"])
    correct = []
    for xs in product(("public", "player_0", "player_1"), repeat=len(fields)):
        owners = dict(zip(fields, xs))
        scored = score(json.dumps(proposal(static, owners)), static)
        if scored["correct"]:
            correct.append(owners)
        assert not score(json.dumps(proposal(dynamic, owners)), dynamic)["correct"]
    assert correct == [pair["owners"]]
    assert score(json.dumps(proposal(dynamic)), dynamic)["correct"]


@pytest.mark.parametrize("tag", ["luna6", "sol61"])
def test_fixture_whole_plan_raw_replay_and_tamper_checks(tmp_path, tag):
    m, b = DISPATCH.package(tag)
    raw = Client(b); client = ParameterClient(raw)
    runner = ProspectiveRunner(m, b, client, tmp_path / "report.json", lambda _: 200); client.runner = runner
    report = runner.run()
    assert report["status"] == "completed" and len(raw.requests) == 24
    assert report["analysis"]["joint_pair_success"] == 8
    assert report["analysis"]["feedback_exposures"] == 8
    assert replay(m, b, report) == report["analysis"]
    for kind in ("cost", "request", "score"):
        bad = deepcopy(report)
        if kind == "cost": bad["attempts"][0]["cost_usd"] = 0
        elif kind == "request": bad["attempts"][0]["messages"][-1]["content"] += " reference leak"
        else: bad["trials"][0]["evaluation"]["correct"] = False
        with pytest.raises(ValueError): replay(m, b, bad)


def test_negative_control_and_provider_error_keep_assigned_denominators(tmp_path):
    for fail in (False, True):
        raw = Client(B, wrong=True, fail=fail); client = ParameterClient(raw)
        runner = ProspectiveRunner(M, B, client, tmp_path / f"{fail}.json", lambda _: 200); client.runner = runner
        report = runner.run()
        assert report["analysis"]["joint_pair_success"] == 0
        assert len(report["analysis"]["all_failures"]) == 24
        assert all(g["assigned"] == 8 for g in report["analysis"]["groups"].values())
        assert "SECRET" not in json.dumps(report)
        if fail: assert len(raw.requests) == 1
