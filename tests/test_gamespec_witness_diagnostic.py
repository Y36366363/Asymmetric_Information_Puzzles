from copy import deepcopy
from hashlib import sha256
import importlib.util
from itertools import product
import json
from pathlib import Path
import sys

import pytest

from aip.benchmark.gamespec_interface import ParameterClient, messages_for, parameters
from aip.benchmark.gamespec_prospective import ProspectiveRunner, change_witnesses, score
from aip.benchmark.gamespec_witness_diagnostic import diagnostic_analysis, review_intake
from test_gamespec_prospective import Client, proposal

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
try:
    spec = importlib.util.spec_from_file_location("witness_dispatch", ROOT / "scripts/run_gamespec_witness_diagnostic.py")
    D = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(D)
finally:
    sys.path.pop(0)
M, B = D.package("luna6")


def test_factor_balance_scope_only_and_frozen_configuration():
    cells = [change_witnesses(p["dynamic_visibility"])[0] for p in B["pairs"]]
    assert {(c["player"], c["before_visible"], c["after_visible"]) for c in cells} == {
        (0, False, True), (0, True, False), (1, False, True), (1, True, False)}
    assert len(B["plan"]) == 16 and {p["task"] for p in B["plan"]} == {"scope"}
    for tag in ("luna6", "sol61"):
        m, b = D.package(tag)
        old, _ = D.v4_package(tag)
        assert m["model"] == old["model"]
        for k in ("system_prompt", "source_priority_prompt", "output_contract"):
            assert m["interface_spec"][k] == old["interface_spec"][k]
        for p in b["plan"]:
            assert parameters(m, b, p)["response_format"]["type"] == "json_schema"
            text = json.dumps(messages_for(m, b, p))
            assert "reference_owners" not in text and "dynamic_visibility" not in text
    with pytest.raises(ValueError): D.package("mini41")


@pytest.mark.parametrize("pair", B["pairs"], ids=lambda p:p["pair_id"])
def test_every_player_direction_mutation_rejected_by_existing_scorers(pair):
    item = B["cases"][pair["dynamic_id"]]
    expected = change_witnesses(item["visibility_contexts"])[0]
    for player, before, after in product((0, 1), (False, True), (False, True)):
        payload = proposal(item)
        w = dict(field="route", player=player, before_visible=before, after_visible=after)
        payload["witness"] = w
        assert score(json.dumps(payload), item)["correct"] == (w == expected)
    bad = deepcopy(proposal(item)); bad["witness"]["field"] = "window"
    assert not score(json.dumps(bad), item)["correct"]


@pytest.mark.parametrize("tag", ["luna6", "sol61"])
def test_full_mock_run_replays_without_repair_and_tampering_fails(tmp_path, tag):
    m, b = D.package(tag)
    raw = Client(b); client = ParameterClient(raw)
    runner = ProspectiveRunner(m, b, client, tmp_path / "report.json", lambda _:200); client.runner = runner
    report = runner.run()
    a = diagnostic_analysis(m, b, report)
    assert len(raw.requests) == 16 and a["joint_correct"] == 8 and not a["all_failures"]
    assert a["independent_rule_instances"] == 0 and not a["held_out"] and not a["deployment_permission"]
    bad = deepcopy(report); bad["attempts"][0]["provider_parameters"]["reasoning_effort"] = "high"
    with pytest.raises(ValueError, match="request mismatch"): diagnostic_analysis(m, b, bad)


def test_failure_taxonomy_does_not_change_score_or_hide_player_and_direction(tmp_path):
    class ReversedClient(Client):
        def create(self, **kwargs):
            result = super().create(**kwargs)
            raw = result.model_dump()
            payload = json.loads(raw["choices"][0]["message"]["content"])
            if payload["decision"] == "refusal":
                w = payload["witness"]
                w["player"] = 1 - w["player"]
                w["before_visible"], w["after_visible"] = w["after_visible"], w["before_visible"]
                text = json.dumps(payload)
                raw["choices"][0]["message"]["content"] = text
                result.choices[0].message.content = text
            return result
    raw = ReversedClient(B); client = ParameterClient(raw)
    runner = ProspectiveRunner(M, B, client, tmp_path / "report.json", lambda _:200); client.runner = runner
    a = diagnostic_analysis(M, B, runner.run())
    assert a["groups"]["static"]["correct"] == 8 and a["groups"]["dynamic"]["correct"] == 0
    assert len(a["all_failures"]) == 8
    for failure in a["all_failures"]:
        assert set(failure["categories"]) == {"wrong_affected_player", "wrong_initial_visibility", "wrong_final_visibility", "reversed_change_direction"}


def intake_fixture(tmp_path):
    rules = {"pairs": deepcopy(B["pairs"])}
    references = {p["pair_id"]: {k:p[k] for k in ("owners", "static_visibility", "dynamic_visibility")} for p in rules["pairs"]}
    record = {"status":"ready_for_freeze", "author_id":"author-A", "reviewer_id":"reviewer-B", "provenance_note":"TEST FIXTURE, not actual independent review"}
    for k in ("reviewer_not_in_development", "reviewer_blind_to_author_reference", "reviewer_blind_to_model_outputs", "rules_not_used_in_development", "all_submitted_pairs_included", "no_unresolved_disagreements"):
        record[k] = True
    for k, obj in (("rules", rules), ("author_reference", references), ("reviewer_reference", references)):
        raw = json.dumps(obj).encode()
        (tmp_path / f"{k}.json").write_bytes(raw)
        record[k] = {"path":f"{k}.json", "sha256":sha256(raw).hexdigest()}
    return record


def test_documentary_intake_is_not_dispatch_or_identity_certificate(tmp_path):
    r = review_intake(intake_fixture(tmp_path), tmp_path)
    assert r["documentary_gate_passed"] and r["rule_pairs"] == 4
    assert not r["generation_calls_authorized"] and not r["identity_independently_verified"]


@pytest.mark.parametrize("fault", ["pending", "self_review", "developer", "seen_labels", "used_rules", "unresolved", "hash", "disagreement", "escape", "empty"])
def test_independent_intake_rejects_ineligible_or_changed_evidence(tmp_path, fault):
    r = intake_fixture(tmp_path)
    if fault == "pending": r["status"] = "pending"
    elif fault == "self_review": r["reviewer_id"] = r["author_id"]
    elif fault == "developer": r["reviewer_not_in_development"] = False
    elif fault == "seen_labels": r["reviewer_blind_to_author_reference"] = False
    elif fault == "used_rules": r["rules_not_used_in_development"] = False
    elif fault == "unresolved": r["no_unresolved_disagreements"] = False
    elif fault == "hash": r["rules"]["sha256"] = "0" * 64
    elif fault == "escape": r["rules"]["path"] = "../outside.json"
    else:
        key = "reviewer_reference" if fault == "disagreement" else "rules"
        obj = json.loads((tmp_path / r[key]["path"]).read_text())
        if fault == "disagreement": obj["p0_gain"]["owners"]["route"] = "public"
        else: obj["pairs"] = []
        raw = json.dumps(obj).encode()
        (tmp_path / r[key]["path"]).write_bytes(raw)
        r[key]["sha256"] = sha256(raw).hexdigest()
    with pytest.raises(ValueError): review_intake(r, tmp_path)
