"""Tests for the token-balanced held-out Liar's Dice evaluation layer."""

from types import SimpleNamespace

import pytest

from aip.benchmark.liar_transfer import (
    ARMS,
    REPEATS,
    analyze_results,
    base_memory_prompts,
    build_oracle_probes,
    source_experience_records,
    target_oracle_metadata,
)
from aip.benchmark.types import AgentDecision, BeliefOutput
from scripts.run_liar_transfer_confirmatory import _pad_prompts


def test_probe_panel_balances_challenge_raise_and_player_one_decisions():
    probes = build_oracle_probes()
    best = [max(probe.exact_action_values, key=probe.exact_action_values.get) for probe in probes]
    assert len(probes) == 12
    assert sum(action == "challenge" for action in best) == 6
    assert sum(action.startswith("raise:") for action in best) == 6
    assert sum(probe.player == 1 for probe in probes) == 3
    assert len({probe.to_artifact()["publicStateSha256"] for probe in probes}) == 12


def test_probe_uses_independent_action_values_and_exact_posterior():
    probe = build_oracle_probes()[0]
    best = max(probe.exact_action_values, key=probe.exact_action_values.get)
    worst = min(probe.exact_action_values, key=probe.exact_action_values.get)
    belief = BeliefOutput("opponent_die", probe.exact_posterior)
    assert probe.evaluate(AgentDecision(best, 1.0, belief=belief))["actionRegret"] == 0
    assert probe.evaluate(AgentDecision(best, 1.0, belief=belief))["beliefBrierToExactPosterior"] == 0
    assert probe.evaluate(AgentDecision(worst, 1.0))["actionRegret"] > 0


def test_source_records_are_mechanical_and_do_not_claim_full_love_letter():
    records = source_experience_records()
    assert records == source_experience_records()
    assert records["provenance"]["fullLoveLetterUsed"] is False
    assert all(record["actionRegret"] == pytest.approx(0) for record in records["guessWhoExactEpisodes"])
    prompts = base_memory_prompts(build_oracle_probes())
    assert set(prompts) == set(ARMS)
    assert "Source-record SHA-256" in prompts["abstract_memory"]


def test_target_oracle_is_independent_exact_and_zero_gap():
    oracle = target_oracle_metadata()
    assert oracle["evaluatorId"] == "one_die_liar_exhaustive_best_response_v1"
    assert oracle["treeAudit"]["passed"] is True
    assert oracle["exploitability"] == pytest.approx(0)
    assert oracle["primalDualGap"] == pytest.approx(0)


class _TokenCounter:
    def count(self, *, instructions, input, **kwargs):
        del kwargs
        return SimpleNamespace(input_tokens=len(instructions.split()) + len(input.split()))


class _FakeClient:
    responses = SimpleNamespace(input_tokens=_TokenCounter())


def test_padding_uses_provider_counter_to_make_prompts_exactly_equal():
    base = {arm: f"{arm} " + ("word " * index) for index, arm in enumerate(ARMS)}
    padded, amounts = _pad_prompts(_FakeClient(), base)
    counts = {
        len((padded[arm]).split()) for arm in ARMS
    }
    assert len(counts) == 1
    assert all(amount >= 0 for amount in amounts.values())


def test_analysis_keeps_invalid_output_penalties_in_primary_endpoint():
    probes = build_oracle_probes()
    plan = {
        "repeats": REPEATS,
        "probes": [probe.to_artifact() for probe in probes],
        "cellOrder": [
            {"probeId": probe.probe_id, "arm": arm, "repeat": repeat}
            for probe in probes
            for arm in ARMS
            for repeat in range(1, REPEATS + 1)
        ],
    }
    rows = [
        {
            **cell,
            "status": "valid",
            "penalizedActionRegret": 0.0,
            "optimalPolicyAgreement": True,
            "beliefBrierToExactPosterior": None,
        }
        for cell in plan["cellOrder"]
    ]
    failure = next(row for row in rows if row["arm"] == "abstract_memory")
    failure.update(status="failed", penalizedActionRegret=2.0, optimalPolicyAgreement=False)
    report = analyze_results(plan, rows)
    assert report["summaries"]["abstract_memory"]["validDecisions"] == 23
    assert report["contrastsVersusNoMemory"]["abstract_memory"]["meanDifference"] > 0
    with pytest.raises(ValueError, match="exactly cover"):
        analyze_results(plan, rows[:-1])
