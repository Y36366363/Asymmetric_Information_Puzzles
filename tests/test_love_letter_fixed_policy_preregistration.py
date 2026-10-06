import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PREREGISTRATION = (
    ROOT
    / "configs/love_letter_fixed_policy_conditioning_preregistration_2026-10-06.json"
)


def test_love_letter_fixed_policy_experiment_is_frozen_before_results():
    plan = json.loads(PREREGISTRATION.read_text())
    assert plan["frozen_before_outcome_evaluation"] is True
    assert plan["scope"] == "certified_four_card_late_round_subgame_only"
    assert plan["prior_method_id"] == (
        "love_letter_chance_reach_combinatorial_prior_v1"
    )
    assert plan["reporting"]["fixed_policy_must_not_be_labeled_gto"] is True
    assert plan["reporting"]["no_full_round_generalization"] is True
    assert plan["reporting"]["no_runtime_epsilon_gto_promotion"] is True


def test_fixed_policy_formula_and_primary_gates_are_explicit():
    plan = json.loads(PREREGISTRATION.read_text())
    policy = plan["fixed_policy"]
    assert policy == {
        "policy_id": "love_letter_private_hand_full_support_v1",
        "description": (
            "normalize a strictly positive raw weight at every information set; "
            "this is an experimental opponent likelihood model, not an equilibrium "
            "candidate"
        ),
        "raw_weight_formula": (
            "floor + kept_card_coefficient * kept_card + "
            "played_card_coefficient * played_card + "
            "guard_guess_coefficient * guard_guess_or_zero"
        ),
        "floor": 1.0,
        "kept_card_coefficient": 0.75,
        "played_card_coefficient": 0.05,
        "guard_guess_coefficient": 0.02,
        "full_support_required": True,
        "deterministic": True,
    }
    endpoints = plan["primary_endpoints"]
    assert endpoints[
        "maximum_posterior_l1_shift_from_combinatorial_prior"
    ]["positive_threshold"] == 1e-6
    assert endpoints["information_sets_with_posterior_shift"]["minimum_count"] == 1


def test_fixed_policy_is_required_to_remain_a_negative_equilibrium_control():
    plan = json.loads(PREREGISTRATION.read_text())
    assert plan["controls"]["fixed_policy_must_fail_equilibrium_gate"] == 1e-3
    assert plan["controls"]["equilibrium_maximum_exploitability"] == 1e-12
    assert plan["mechanical_gates"]["expected_total_information_sets"] == 60
    assert plan["mechanical_gates"][
        "expected_zero_reach_information_sets_under_full_support"
    ] == 0
