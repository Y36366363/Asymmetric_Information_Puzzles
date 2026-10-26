from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from aip.benchmark.gamespec_scope_ablation import materialize as v3_materialize
from aip.benchmark.gamespec_interface import (InterfaceRunner, ParameterClient, evaluate, materialize,
    messages_for, parameters, proposal_schema, replay, serialize_proposal)

ROOT = Path(__file__).resolve().parents[1]
read = lambda p: json.loads((ROOT / p).read_text())
V3 = v3_materialize(read("configs/llm_gamespec_smoke_execution_2026-10-21.json"),
                    read("configs/llm_gamespec_smoke_v2_2026-10-23.json"),
                    read("configs/gamespec_scope_ablation_v3_2026-10-25.json"))
SPEC = read("configs/gamespec_interface_v4_2026-10-26.json")
M, B = materialize(*V3, SPEC, "mini41")


def correct_proposal(item):
    if item["kind"] == "dynamic":
        return {"decision": "refusal", "candidates": [], "witness": item["control"]["required_witness"]}
    owners = item["case"]["reference_owners"]
    return {"decision": "candidate", "candidates": [{"public_fields": [k for k, v in owners.items() if v == "public"],
            "private_fields_by_player": {p: [k for k, v in owners.items() if v == p] for p in ("player_0", "player_1")}}], "witness": None}


class Client:
    def __init__(self, bundle, invalid=False, fail=False):
        self.chat = SimpleNamespace(completions=self)
        self.bundle, self.invalid, self.fail = bundle, invalid, fail
        self.requests = []

    def create(self, **kwargs):
        self.requests.append(kwargs)
        if self.fail:
            raise RuntimeError("SECRET never print")
        case_id = kwargs["messages"][-1]["content"].split("Case: ")[1].split("\n")[0]
        text = "not json" if self.invalid else json.dumps(correct_proposal(self.bundle["cases"][case_id]))
        raw = {"model": kwargs["model"], "usage": {"prompt_tokens": 200, "completion_tokens": 100},
               "choices": [{"finish_reason": "stop", "message": {"content": text}}]}
        return SimpleNamespace(model=kwargs["model"], usage=SimpleNamespace(prompt_tokens=200, completion_tokens=100),
            choices=[SimpleNamespace(finish_reason="stop", message=SimpleNamespace(content=text, refusal=None))], model_dump=lambda **_:raw)


def test_plan_and_source_feedback_separation():
    assert len(B["plan"]) == len({p["trial_id"] for p in B["plan"]}) == 112
    for p in B["plan"]:
        messages = messages_for(M, B, p)
        text = json.dumps(messages)
        assert "reference_owners" not in text and "final_reference" not in text
        if p["task"] == "witness_repair":
            assert len(messages) == 3 and '"witnesses"' in messages[-1]["content"]
            envelope = serialize_proposal(json.loads(messages[1]["content"]), B["cases"][p["case_id"]]["case"])
            from aip.benchmark.gamespec_smoke_v2 import compile_v2
            compiled = compile_v2(envelope, B["cases"][p["case_id"]]["case"])
            assert not any(dict(s) == B["cases"][p["case_id"]]["case"]["reference_owners"] for s in compiled.signatures)


def test_serializer_has_no_semantic_oracle_and_owns_constants():
    item = B["cases"]["slice_42"]
    proposal = correct_proposal(item)
    encoded = serialize_proposal(proposal, {"case_id": "slice_42", "fields": item["case"]["fields"]})
    assert encoded["error_code"] == "OUT_OF_SCHEMA_STATIC_VISIBILITY"
    wrong = deepcopy(proposal)
    wrong["witness"]["player"] = 0
    assert serialize_proposal(wrong, item["case"])["witness"]["player"] == 0
    assert not evaluate(json.dumps(wrong), item)["correct"]
    assert evaluate(json.dumps(proposal), item)["correct"]


@pytest.mark.parametrize("bad_player", [True, 1.0, "player_1", "1"])
def test_no_type_coercion(bad_player):
    proposal = deepcopy(correct_proposal(B["cases"]["slice_42"]))
    proposal["witness"]["player"] = bad_player
    with pytest.raises(ValueError):
        serialize_proposal(proposal, B["cases"]["slice_42"]["case"])


def test_mixed_branch_and_self_certificate_rejected():
    proposal = correct_proposal(B["cases"]["slice_17"])
    for field, value in (("witness", {"field": "die_0", "player": 1, "before_visible": False, "after_visible": True}), ("certified", True)):
        bad = deepcopy(proposal); bad[field] = value
        with pytest.raises(ValueError):
            serialize_proposal(bad, B["cases"]["slice_17"]["case"])


@pytest.mark.parametrize("tag", ["mini41", "luna6", "sol61"])
def test_full_fixture_and_actual_provider_parameters(tmp_path, tag):
    manifest, bundle = materialize(*V3, SPEC, tag)
    raw = Client(bundle)
    client = ParameterClient(raw)
    runner = InterfaceRunner(manifest, bundle, client, tmp_path / f"{tag}.json", lambda _: 200)
    client.runner = runner
    result = runner.run()
    assert result["status"] == "completed"
    assert len(raw.requests) == 112
    assert not result["analysis"]["all_failures"]
    assert replay(manifest, bundle, result) == result["analysis"]
    assert {r["response_format"]["type"] for r in raw.requests} == {"json_object", "json_schema"}
    if tag == "sol61":
        assert all("temperature" not in r and r["reasoning_effort"] == "low" for r in raw.requests)
    else:
        assert all(r["temperature"] == 0 for r in raw.requests)
    altered = deepcopy(result)
    altered["attempts"][0]["provider_parameters"]["response_format"] = {"type": "bogus"}
    with pytest.raises(ValueError, match="request mismatch"):
        replay(manifest, bundle, altered)
    altered = deepcopy(result)
    altered["trials"][0]["arm"] = "f9_s9"
    with pytest.raises(ValueError, match="assignment mismatch"):
        replay(manifest, bundle, altered)


def test_invalid_json_replays_without_repair(tmp_path):
    raw = Client(B, invalid=True); client = ParameterClient(raw)
    runner = InterfaceRunner(M, B, client, tmp_path / "invalid.json", lambda _: 200); client.runner = runner
    result = runner.run()
    assert len(result["analysis"]["all_failures"]) == 112
    assert replay(M, B, result) == result["analysis"]


def test_provider_stop_keeps_denominators_and_secret_safe(tmp_path):
    raw = Client(B, fail=True); client = ParameterClient(raw)
    runner = InterfaceRunner(M, B, client, tmp_path / "stop.json", lambda _: 200); client.runner = runner
    result = runner.run()
    assert result["status"] == "stopped"
    assert len(raw.requests) == 1 and len(result["analysis"]["all_failures"]) == 112
    assert "SECRET" not in json.dumps(result)


def test_surface_probes_preserve_independent_scoring():
    for case_id in ("slice_55", "slice_12", "slice_84", "slice_07"):
        item = B["cases"][case_id]
        assert evaluate(json.dumps(correct_proposal(item)), item)["correct"]
        assert proposal_schema(item["case"])["additionalProperties"] is False
