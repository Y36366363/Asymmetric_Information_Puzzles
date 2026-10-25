from copy import deepcopy
from itertools import product
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from aip.benchmark.gamespec_smoke import candidate_payload
from aip.benchmark.gamespec_scope_ablation import (
    ScopeAblationRunner, compile_v2, evaluate_reply, materialize, messages_for, replay, strict_json,
)

ROOT = Path(__file__).resolve().parents[1]
BASE = json.loads((ROOT / "configs/llm_gamespec_smoke_execution_2026-10-21.json").read_text())
V2 = json.loads((ROOT / "configs/llm_gamespec_smoke_v2_2026-10-23.json").read_text())
SPEC = json.loads((ROOT / "configs/gamespec_scope_ablation_v3_2026-10-25.json").read_text())
MANIFEST, BUNDLE = materialize(BASE, V2, SPEC)


def correct_reply(case_id):
    item = BUNDLE["cases"][case_id]
    if item["kind"] == "static":
        return candidate_payload(item["case"], [item["case"]["reference_owners"]])
    return {"schema_version": "aip-observation-refusal-v1", "game_id": case_id,
            "status": "out_of_schema", "error_code": "OUT_OF_SCHEMA_STATIC_VISIBILITY",
            "witness": deepcopy(item["control"]["required_witness"])}


class Client:
    def __init__(self, fail=False, forced_scope=False):
        self.chat = SimpleNamespace(completions=self)
        self.fail, self.forced_scope = fail, forced_scope
        self.requests = []

    def create(self, **kwargs):
        self.requests.append(kwargs)
        if self.fail:
            raise RuntimeError("SECRET must never be logged")
        case_id = kwargs["messages"][-1]["content"].split("Case: ")[1].split("\n")[0]
        payload = correct_reply(case_id)
        if self.forced_scope and BUNDLE["cases"][case_id]["kind"] == "dynamic":
            payload = candidate_payload(BUNDLE["cases"][case_id]["case"],
                                        [dict.fromkeys(BUNDLE["cases"][case_id]["case"]["fields"], "public")])
        text = json.dumps(payload)
        raw = {"model": kwargs["model"], "usage": {"prompt_tokens": 200, "completion_tokens": 100},
               "choices": [{"finish_reason": "stop", "message": {"content": text}}]}
        return SimpleNamespace(model=kwargs["model"], usage=SimpleNamespace(prompt_tokens=200, completion_tokens=100),
                               choices=[SimpleNamespace(finish_reason="stop", message=SimpleNamespace(content=text, refusal=None))],
                               model_dump=lambda **_: raw)


def test_schedule_balanced_and_all_repair_trials_receive_identical_evidence():
    assert len(BUNDLE["plan"]) == len({p["trial_id"] for p in BUNDLE["plan"]}) == 144
    assert MANIFEST["model"] == BASE["model"]
    for task, count in (("scope", 24), ("witness_repair", 12)):
        for arm in SPEC["arms"]:
            trials = [p for p in BUNDLE["plan"] if p["task"] == task and p["arm"] == arm["id"]]
            assert len(trials) == count
            for trial in trials:
                messages = messages_for(MANIFEST, BUNDLE, trial)
                request = json.dumps(messages)
                assert "reference_owners" not in request
                assert "final_reference" not in request
                assert "expected_code" not in request
                if task == "witness_repair":
                    assert len(messages) == 3
                    assert '"witnesses"' in messages[-1]["content"]
                    item = BUNDLE["cases"][trial["case_id"]]
                    compiled = compile_v2(json.loads(messages[1]["content"]), item["case"])
                    assert all(dict(s) != item["case"]["reference_owners"] for s in compiled.signatures)
                    ids = {w["evidence_id"] for w in item["evidence"]["feedback_evidence"]}
                    assert ids.isdisjoint(e["evidence_id"] for e in item["evidence"]["final_evidence"])


@pytest.mark.parametrize("pair", SPEC["pairs"])
def test_exact_finite_partition_reference_and_dynamic_refusal(pair):
    static = BUNDLE["cases"][pair["static_id"]]
    fields = list(static["case"]["fields"])
    accepted = []
    for owners in product(("public", "player_0", "player_1"), repeat=len(fields)):
        payload = candidate_payload(static["case"], [dict(zip(fields, owners))])
        if evaluate_reply(json.dumps(payload), static)["correct"]:
            accepted.append(dict(zip(fields, owners)))
    assert accepted == [static["case"]["reference_owners"]]
    dynamic = BUNDLE["cases"][pair["dynamic_id"]]
    assert evaluate_reply(json.dumps(correct_reply(pair["dynamic_id"])), dynamic)["correct"]
    assert not evaluate_reply(json.dumps(correct_reply(pair["static_id"])), static)["errors"]


@pytest.mark.parametrize("player", ["player_1", "1", True, 1.0])
def test_refusal_types_remain_strict(player):
    payload = correct_reply("slice_42")
    payload["witness"]["player"] = player
    assert not evaluate_reply(json.dumps(payload), BUNDLE["cases"]["slice_42"])["correct"]


def test_mixed_branches_invalid_json_and_false_refusal_fail():
    payload = correct_reply("slice_42")
    payload["candidates"] = []
    result = evaluate_reply(json.dumps(payload), BUNDLE["cases"]["slice_42"])
    assert "mixed_output_branches" in result["errors"]
    assert not result["correct"]
    for text in ('{"x":1,"x":2}', '{"x":NaN}', 'not json'):
        with pytest.raises(ValueError):
            strict_json(text)
    payload = correct_reply("slice_42")
    payload["game_id"] = "slice_17"
    assert "incorrect_rejection_in_scope" in evaluate_reply(json.dumps(payload), BUNDLE["cases"]["slice_17"])["errors"]


def test_preserved_preflight_counterexample_accepts_both_real_changes():
    record = json.loads((ROOT / "configs/gamespec_scope_v3_preflight_counterexample_2026-10-25.json").read_text())
    item = BUNDLE["cases"]["slice_08"]
    assert not record["initial_single_witness_contract_result"]
    assert evaluate_reply(json.dumps(record["counterexample"]), item)["correct"]
    assert evaluate_reply(json.dumps(correct_reply("slice_08")), item)["correct"]
    wrong = deepcopy(record["counterexample"])
    wrong["witness"]["player"] = "player_0"
    assert not evaluate_reply(json.dumps(wrong), item)["correct"]


def test_whole_schedule_with_fixture_and_raw_replay(tmp_path):
    client = Client()
    report = ScopeAblationRunner(MANIFEST, BUNDLE, client, tmp_path / "report.json", lambda _: 200).run()
    assert report["status"] == "completed"
    assert len(client.requests) == 144
    assert report["analysis"]["all_failures"] == []
    assert set(report["analysis"]["feedback_exposures_by_arm"].values()) == {12}
    assert report["analysis"]["overall_scientific_pass"] is None
    assert replay(MANIFEST, BUNDLE, report) == report["analysis"]
    assert not report["runtime_epsilon_gto_allowed"]
    assert not report["adaptive_opponent_line_released"]
    for target in ("cost", "request", "score", "assignment"):
        altered = deepcopy(report)
        if target == "cost":
            altered["attempts"][0]["cost_usd"] = 0
        elif target == "request":
            altered["attempts"][0]["messages"][-1]["content"] += " hidden reference"
        elif target == "score":
            altered["trials"][0]["evaluation"]["correct"] = False
        else:
            altered["trials"][0]["arm"] = "a9_b9"
        with pytest.raises(ValueError):
            replay(MANIFEST, BUNDLE, altered)


def test_structurally_legal_oos_false_acceptance_not_hidden_by_zero_certifications(tmp_path):
    report = ScopeAblationRunner(MANIFEST, BUNDLE, Client(forced_scope=True),
                                 tmp_path / "report.json", lambda _: 200).run()
    assert report["analysis"]["scope_false_acceptances"] == 48
    assert report["analysis"]["false_certifications_in_scope"] == 0
    assert all(c["joint_pair_success"]["correct"] == 0 for c in report["analysis"]["cells"].values())
    assert len(report["analysis"]["all_failures"]) == 48


def test_provider_failure_preserves_all_assigned_denominators(tmp_path):
    report = ScopeAblationRunner(MANIFEST, BUNDLE, Client(fail=True),
                                 tmp_path / "report.json", lambda _: 200).run()
    assert report["status"] == "stopped"
    assert len(report["attempts"]) == 1
    assert len(report["analysis"]["all_failures"]) == 144
    assert "SECRET" not in json.dumps(report)
