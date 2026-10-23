from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from aip.benchmark.gamespec_smoke import candidate_payload, make_bundle
from aip.benchmark.gamespec_smoke_v2 import (
    V2SmokeRunner, compile_v2, diagnostic_required, independent_replay,
    materialize_manifest, v2_bundle,
)
from aip.core.game_spec_smoke import validate_scope_refusal

ROOT = Path(__file__).resolve().parents[1]
BASE = json.loads((ROOT / "configs/llm_gamespec_smoke_execution_2026-10-21.json").read_text())
SPEC = json.loads((ROOT / "configs/llm_gamespec_smoke_v2_2026-10-23.json").read_text())
MANIFEST = materialize_manifest(BASE, SPEC)


class Client:
    def __init__(self, wrong_scope=False, fail=False):
        self.chat = SimpleNamespace(completions=self)
        self.requests = []
        self.wrong_scope, self.fail = wrong_scope, fail

    def create(self, **kwargs):
        self.requests.append(kwargs)
        if self.fail:
            raise RuntimeError("SECRET never publish")
        case_id = kwargs["messages"][-1]["content"].split("Case: ")[1].split("\n")[0]
        if case_id == "dice_paid_reveal":
            payload = {"schema_version": "aip-observation-refusal-v1", "game_id": case_id,
                       "status": "out_of_schema", "error_code": "OUT_OF_SCHEMA_STATIC_VISIBILITY",
                       "witness": deepcopy(BASE["out_of_schema"]["required_witness"])}
            if self.wrong_scope:
                payload["witness"]["player"] = "player_1"
        else:
            case = next(c for c in BASE["cases"] if c["case_id"] == case_id)
            payload = candidate_payload(case, [case["reference_owners"]])
        content = json.dumps(payload)
        raw = {"model": kwargs["model"], "usage": {"prompt_tokens": 200, "completion_tokens": 100},
               "choices": [{"finish_reason": "stop", "message": {"content": content}}]}
        return SimpleNamespace(model=kwargs["model"], usage=SimpleNamespace(prompt_tokens=200, completion_tokens=100),
                               choices=[SimpleNamespace(finish_reason="stop", message=SimpleNamespace(content=content, refusal=None))],
                               model_dump=lambda **_: raw)


def test_v2_range_accepts_one_and_three_but_not_duplicates_or_four():
    case = BASE["cases"][0]
    owners = [case["reference_owners"], dict.fromkeys(case["fields"], "public"), dict.fromkeys(case["fields"], "player_0")]
    for count in (1, 2, 3):
        assert len(compile_v2(candidate_payload(case, owners[:count]), case).hypotheses) == count
    with pytest.raises(ValueError):
        compile_v2(candidate_payload(case, owners[:2]), case, single=True)
    for invalid in ([], owners + [dict.fromkeys(case["fields"], "player_1")], [owners[0], owners[0]]):
        with pytest.raises(ValueError):
            compile_v2(candidate_payload(case, invalid), case)


@pytest.mark.parametrize("player", ["player_1", "1", True, 1.0, None])
def test_refusal_remains_strict_no_type_coercion(player):
    payload = {"schema_version": "aip-observation-refusal-v1", "game_id": "dice_paid_reveal",
               "status": "out_of_schema", "error_code": "OUT_OF_SCHEMA_STATIC_VISIBILITY",
               "witness": dict(BASE["out_of_schema"]["required_witness"], player=player)}
    assert not validate_scope_refusal(payload, BASE["out_of_schema"])["passed"]


def test_v1_evidence_and_settings_unchanged():
    assert v2_bundle(BASE, MANIFEST)["cases"] == make_bundle(BASE)["cases"]
    assert MANIFEST["cases"] == BASE["cases"]
    assert MANIFEST["model"] == BASE["model"]
    assert MANIFEST["schedule"] == BASE["schedule"]
    assert set(MANIFEST["gates"]) == {"maximum_call_usd", "maximum_total_usd"}


def test_full_v2_fixture_and_independent_raw_replay(tmp_path):
    client = Client()
    bundle = v2_bundle(BASE, MANIFEST)
    runner = V2SmokeRunner(MANIFEST, bundle, client, tmp_path / "report.json", lambda _: 200)
    report = runner.run()
    assert report["status"] == "completed"
    assert len(report["attempts"]) == len(report["trials"]) == 93
    assert report["analysis"]["overall_scientific_pass"] is None
    assert report["analysis"]["final_failures"] == []
    assert independent_replay(MANIFEST, bundle, report) == report["analysis"]
    assert not diagnostic_required(report)
    assert not report["runtime_epsilon_gto_allowed"]
    assert not report["adaptive_opponent_line_released"]
    for request in client.requests:
        text = json.dumps(request["messages"])
        assert "reference_owners" not in text
        assert "final_reference" not in text
    tampered = deepcopy(report)
    tampered["trials"][0]["score"]["false_certification"] = True
    with pytest.raises(ValueError, match="replay mismatch"):
        independent_replay(MANIFEST, bundle, tampered)
    tampered = deepcopy(report)
    tampered["attempts"][0]["cost_usd"] = 0
    with pytest.raises(ValueError, match="cost replay mismatch"):
        independent_replay(MANIFEST, bundle, tampered)


def test_all_fifteen_scope_failures_retained_and_trigger_model_control(tmp_path):
    report = V2SmokeRunner(MANIFEST, v2_bundle(BASE, MANIFEST), Client(wrong_scope=True),
                           tmp_path / "report.json", lambda _: 200).run()
    assert report["analysis"]["correct_oos"] == 0
    assert len(report["analysis"]["final_failures"]) == 15
    assert diagnostic_required(report)


def test_provider_failure_stops_without_secret_or_model_escalation(tmp_path):
    client = Client(fail=True)
    report = V2SmokeRunner(MANIFEST, v2_bundle(BASE, MANIFEST), client,
                           tmp_path / "report.json", lambda _: 200).run()
    assert report["status"] == "stopped"
    assert len(client.requests) == 1
    assert "SECRET" not in json.dumps(report)
    assert not diagnostic_required(report)
