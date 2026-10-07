import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PREREGISTRATION = (
    ROOT
    / "configs/love_letter_collapsed_posterior_preregistration_2026-10-07.json"
)


def test_collapsed_posterior_target_is_frozen_before_evaluation():
    plan = json.loads(PREREGISTRATION.read_text())
    assert plan["frozen_before_outcome_evaluation"] is True
    assert plan["source_experiment"] == (
        "love_letter_four_card_fixed_policy_conditioning_v1"
    )
    assert plan["reporting"]["do_not_replace_target_after_outcomes"] is True
    assert plan["reporting"]["no_full_round_generalization"] is True


def test_collapsed_target_removes_only_acquisition_order():
    plan = json.loads(PREREGISTRATION.read_text())
    target = plan["posterior_target"]
    assert target["target_id"] == "love_letter_strategic_hidden_state_v1"
    assert target["retained_fields"] == [
        "remaining_card_counts",
        "burn_card",
        "opponent_current_hand",
    ]
    assert target["removed_fields"] == [
        "opponent_private_acquisition_history"
    ]


def test_policy_is_reused_unchanged_and_stopping_rule_is_explicit():
    plan = json.loads(PREREGISTRATION.read_text())
    policy = plan["fixed_policy"]
    assert policy["policy_id"] == "love_letter_private_hand_full_support_v1"
    assert policy["reuse_without_parameter_changes"] is True
    assert policy["floor"] == 1.0
    assert policy["kept_card_coefficient"] == 0.75
    assert policy["played_card_coefficient"] == 0.05
    assert policy["guard_guess_coefficient"] == 0.02
    assert plan["primary_endpoints"][
        "information_sets_with_nontrivial_support_after_observed_opponent_action"
    ]["predicted_value"] == 0
    assert plan["decision_rule"]["if_no_nontrivial_post_action_support"].startswith(
        "retire_four_card_subgame"
    )
