from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from aip.benchmark.gamespec_smoke import (
    SmokeRunner, analyze, candidate_payload, digest, final_score,
    make_bundle, output_labels,
)

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = json.loads((ROOT / "configs/llm_gamespec_smoke_execution_2026-10-21.json").read_text())


class FixtureClient:
    def __init__(self, fail=False, usage=True, version=None, refuse=False):
        self.chat = SimpleNamespace(completions=self)
        self.fail, self.usage, self.version = fail, usage, version
        self.refuse = refuse
        self.requests = []

    def create(self, **kwargs):
        self.requests.append(kwargs)
        if self.fail:
            raise RuntimeError("SECRET must not appear in public report")
        text = kwargs["messages"][-1]["content"]
        case_id = text.split("Case: ")[1].split("\n")[0]
        count = int(text.split("Requested candidates: ")[1].split("\n")[0])
        if case_id == "dice_paid_reveal":
            payload = {
                "schema_version": "aip-observation-refusal-v1", "game_id": case_id,
                "status": "out_of_schema", "error_code": "OUT_OF_SCHEMA_STATIC_VISIBILITY",
                "witness": MANIFEST["out_of_schema"]["required_witness"],
            }
        else:
            case = next(c for c in MANIFEST["cases"] if c["case_id"] == case_id)
            owners = [case["reference_owners"]]
            for owner in ("public", "player_0", "player_1"):
                wrong = dict.fromkeys(case["fields"], owner)
                if wrong not in owners:
                    owners.append(wrong)
            payload = candidate_payload(case, owners[:count])
        raw = {
            "id": "fake-response", "model": self.version or kwargs["model"],
            "usage": {"prompt_tokens": 200, "completion_tokens": 100} if self.usage else None,
            "choices": [{"finish_reason": "stop", "message": {"content": json.dumps(payload)}}],
        }
        return SimpleNamespace(
            model=raw["model"], usage=SimpleNamespace(prompt_tokens=200, completion_tokens=100) if self.usage else None,
            choices=[SimpleNamespace(finish_reason="stop", message=SimpleNamespace(content=json.dumps(payload), refusal="fixture refusal" if self.refuse else None))],
            model_dump=lambda **_: raw,
        )


def test_entire_dispatch_with_fixture_client_and_replay(tmp_path):
    bundle = make_bundle(MANIFEST)
    client = FixtureClient()
    runner = SmokeRunner(MANIFEST, bundle, client, tmp_path / "report.json", lambda _: 200)
    report = runner.run()
    assert report["status"] == "completed"
    assert len(report["trials"]) == 60 + 15 + 12 + 6
    assert len(report["attempts"]) == 93
    assert report["analysis"]["gates"]["status"] == "pass"
    assert analyze(MANIFEST, report) == report["analysis"]
    assert all(r["max_completion_tokens"] == 2500 for r in client.requests)
    assert all("reference_owners" not in json.dumps(r["messages"]) for r in client.requests)
    assert all("p0_history" not in json.dumps(r["messages"]) for r in client.requests)
    assert report["runtime_epsilon_gto_allowed"] is False
    with pytest.raises(FileExistsError):
        SmokeRunner(MANIFEST, bundle, client, tmp_path / "report.json", lambda _: 200)


@pytest.mark.parametrize("options,reason", [
    ({"fail": True}, "provider_error_stop"),
    ({"usage": False}, "missing_usage"),
    ({"version": "unapproved-model"}, "provider_model_or_budget_mismatch"),
    ({"refuse": True}, "provider_refusal_stop"),
])
def test_failure_stops_and_keeps_journal(tmp_path, options, reason):
    client = FixtureClient(**options)
    report = SmokeRunner(MANIFEST, make_bundle(MANIFEST), client,
                         tmp_path / "stopped.json", lambda _: 200).run()
    assert len(client.requests) == 1
    assert report["status"] == "stopped"
    assert report["stop_reason"] == reason
    assert "SECRET" not in json.dumps(report)
    assert report["analysis"]["gates"]["status"] == "insufficient_evidence"


def test_budget_stops_before_dispatch(tmp_path):
    manifest = deepcopy(MANIFEST)
    manifest["gates"]["maximum_total_usd"] = 0.001
    client = FixtureClient()
    report = SmokeRunner(manifest, make_bundle(manifest), client,
                         tmp_path / "budget.json", lambda _: 200).run()
    assert report["stop_reason"] == "budget_exceeded"
    assert not client.requests


def test_evidence_is_separate_and_trust_missing_candidates_fail():
    bundle = make_bundle(MANIFEST)
    case = MANIFEST["cases"][0]
    materialized = bundle["cases"][case["case_id"]]
    assert {i["evidence_id"] for i in materialized["feedback_evidence"]}.isdisjoint(
        {i["evidence_id"] for i in materialized["final_evidence"]})
    for item in materialized["feedback_evidence"]:
        assert set(item["left_fields"].values()) == {2}
    compiled, _, _ = output_labels(materialized["missing_truth_initial"], case, 2)
    score = final_score(compiled, case, materialized)
    assert not score["true_model_candidate_coverage"]
    assert score["verification"]["status"] == "conflicted"
    assert not score["false_certification"]
