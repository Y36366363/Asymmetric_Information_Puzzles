import json
from pathlib import Path

from scripts.audit_five_die_liar_feasibility import report


ROOT = Path(__file__).resolve().parents[1]
RULES = ROOT / "configs/five_die_liar_stepwise_rules_v1.json"


def test_five_die_stepwise_contract_is_separate_and_fail_closed():
    rules = json.loads(RULES.read_text())
    assert rules["rules_id"] == "five_die_liar_two_player_stepwise_v1"
    assert rules["players"] == 2
    assert rules["dice_per_player"] == 5
    assert rules["wild_ones"] is True
    assert rules["opening_rule"] == "quantity_one_any_face"
    assert rules["raise_rule"].startswith("advance_exactly_one_position")
    assert rules["scope_boundary"][
        "separate_from_live_five_die_arbitrary_raise_mode"
    ] is True
    assert rules["scope_boundary"][
        "no_runtime_epsilon_gto_until_independent_gate"
    ] is True


def test_live_arbitrary_raise_state_family_is_exponential():
    audit = report()
    live = audit["live_arbitrary_raise_mode"]
    assert live["bid_ladder_size"] == 60
    assert live["nonempty_public_bid_histories"] == 2**60 - 1
    assert live[
        "information_set_lower_bound_from_private_histogram_and_public_history"
    ] == 252 * (2**60 - 1)
    assert live["full_tree_route"].startswith("reject_as_intractable")


def test_stepwise_candidate_has_measurable_bounded_adapter_target():
    audit = report()
    candidate = audit["stepwise_candidate"]
    assert candidate["private_hand_histograms_per_player"] == 252
    assert candidate["joint_histogram_chance_outcomes"] == 252**2
    assert candidate["public_bid_histories"] == sum(range(55, 61))
    assert candidate["information_sets_including_preopening"] == 252 * 346
    assert candidate["estimated_complete_histories_with_histogram_chance"] == (
        1 + 252**2 * (1 + 2 * 345)
    )
    assert audit["decision"]["live_mode"] == (
        "retain_heuristic_and_do_not_claim_gto"
    )
    assert audit["decision"]["new_stepwise_variant"] == (
        "continue_as_separately_scoped_adapter"
    )
    assert audit["passed"] is True
