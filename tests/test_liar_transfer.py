"""Tests for the token-balanced held-out Liar's Dice evaluation layer."""

from types import SimpleNamespace

import pytest

from aip.benchmark.liar_transfer import (
    ARMS,
    ExactLiarDecisionProgram,
    REPEATS,
    analyze_results,
    base_memory_prompts,
    build_consensus_reference_profiles,
    build_oracle_probes,
    positive_control_material,
    positive_control_prompt,
    select_profile_invariant_probes,
    source_experience_records,
    target_oracle_metadata,
)
from aip.benchmark.types import AgentDecision, BeliefOutput
from scripts.run_liar_transfer_confirmatory import _pad_prompts
from scripts.run_liar_program_control_check import (
    ARMS as PROGRAM_ARMS,
    REPEATS as PROGRAM_REPEATS,
    _pad_cell_prompts,
    build_report as build_program_report,
    fresh_panel,
)
from scripts.run_liar_positive_control_check import (
    ARMS as CHECK_ARMS,
    REPEATS as CHECK_REPEATS,
    build_report as build_check_report,
    manipulation_panel,
)


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


def test_positive_control_material_is_balanced_disjoint_and_deterministic():
    probes, full_panel, audit, profiles = manipulation_panel()
    material = positive_control_material(full_panel, profiles)
    assert len(probes) == 12
    assert audit["selectedProbes"] == 30
    assert material == positive_control_material(full_panel, profiles)
    assert material["testDisjoint"] is True
    assert material["challengeBestExamples"] == 8
    assert material["raiseBestExamples"] == 8
    assert "Do not default to challenge" in positive_control_prompt(material)


def test_consensus_profiles_generate_a_profile_invariant_30_state_panel():
    profiles = build_consensus_reference_profiles()
    probes, audit = select_profile_invariant_probes(profiles, count=30)
    assert len(probes) == 30
    assert audit["allSelectedProfileInvariant"] is True
    assert audit["challengeOptimal"] == audit["raiseOptimal"] == 15


def test_positive_control_gate_requires_repeatability_and_effect():
    probes = manipulation_panel()[0]
    plan = {
        "maxProviderCalls": len(probes) * len(CHECK_ARMS) * CHECK_REPEATS,
        "probes": [probe.to_artifact() for probe in probes],
    }
    rows = []
    for probe in probes:
        best = max(probe.exact_action_values, key=probe.exact_action_values.get)
        worst = min(probe.exact_action_values, key=probe.exact_action_values.get)
        for arm in CHECK_ARMS:
            for repeat in range(1, CHECK_REPEATS + 1):
                is_control = arm == "same_game_positive_control"
                rows.append({
                    "probeId": probe.probe_id,
                    "arm": arm,
                    "repeat": repeat,
                    "status": "valid",
                    "actionId": best if is_control else worst,
                    "penalizedActionRegret": 0.0 if is_control else 1.0,
                    "optimalPolicyAgreement": is_control,
                    "inputTokenMatch": True,
                    "telemetry": {"attempts": [{"resolved_model": "model"}]},
                })
    report = build_check_report(plan, rows)
    assert report["gatePassed"] is True
    changed = 0
    for row in rows:
        if row["arm"] == "no_memory" and row["repeat"] == 1 and changed < 3:
            row["actionId"] = "different"
            changed += 1
    assert build_check_report(plan, rows)["gateChecks"]["repeatActionAgreementEachArm"] is False


def test_exact_decision_program_recomputes_advice_from_information_set():
    program = ExactLiarDecisionProgram()
    for probe in fresh_panel()[0]:
        advice = program.advise(probe.player, probe.own_die, probe.bids)
        optimum = max(probe.exact_action_values.values())
        expected = sorted(
            action for action, value in probe.exact_action_values.items()
            if abs(value - optimum) <= 1e-12
        )
        assert advice["recommendedActionIds"] == expected
        assert advice["certificationScope"] == "manipulation_control_only"
        assert "Follow its recommendedActionIds exactly" in program.prompt_for(probe)


def test_program_control_panel_is_fresh_balanced_and_prior_disjoint():
    fresh, prior, full, audit = fresh_panel()
    assert len(full) == 30
    assert len(fresh) == len(prior) == 12
    assert not {probe.probe_id for probe in fresh}.intersection(
        probe.probe_id for probe in prior
    )
    labels = [
        max(probe.exact_action_values, key=probe.exact_action_values.get)
        for probe in fresh
    ]
    assert sum(label == "challenge" for label in labels) == 6
    assert sum(label.startswith("raise:") for label in labels) == 6
    assert audit["allSelectedProfileInvariant"] is True


def test_program_control_gate_accepts_only_strong_repeatable_manipulation():
    probes = fresh_panel()[0]
    plan = {
        "maxProviderCalls": len(probes) * len(PROGRAM_ARMS) * PROGRAM_REPEATS,
        "probes": [probe.to_artifact() for probe in probes],
    }
    rows = []
    for probe in probes:
        best = max(probe.exact_action_values, key=probe.exact_action_values.get)
        worst = min(probe.exact_action_values, key=probe.exact_action_values.get)
        for arm in PROGRAM_ARMS:
            assisted = arm == "oracle_assisted_same_game"
            for repeat in range(1, PROGRAM_REPEATS + 1):
                rows.append({
                    "probeId": probe.probe_id,
                    "arm": arm,
                    "repeat": repeat,
                    "status": "valid",
                    "actionId": best if assisted else worst,
                    "penalizedActionRegret": 0.0 if assisted else 1.0,
                    "optimalPolicyAgreement": assisted,
                    "inputTokenMatch": True,
                })
    report = build_program_report(plan, rows)
    assert report["gatePassed"] is True
    assert report["claimRestriction"] == (
        "oracle-assisted condition is not transfer evidence"
    )


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


def test_cell_padding_accepts_explicit_four_arm_schedule():
    arms = ("a", "b", "c", "d")
    base = {("probe", arm): arm + (" word" * index) for index, arm in enumerate(arms)}
    prompts, amounts, counts = _pad_cell_prompts(
        _FakeClient(), base, {"probe": "input"}, arms=arms
    )
    assert set(prompts) == {("probe", arm) for arm in arms}
    assert set(amounts) == set(prompts)
    assert len({counts[("probe", arm)] for arm in arms}) == 1


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
