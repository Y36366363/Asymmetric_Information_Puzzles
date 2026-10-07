import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "research/results/love_letter_collapsed_posterior_2026-10-07.json"


def load_report():
    return json.loads(AUDIT.read_text())


def test_collapsed_target_is_complete_and_mechanically_exact():
    report = load_report()
    panel = report["panel"]
    assert panel["total_information_sets"] == 60
    assert panel["positive_reach_information_sets"] == 60
    assert panel["zero_reach_information_sets"] == 0
    assert panel["maximum_bayes_reconstruction_error"] <= 1e-12
    assert panel["maximum_value_reconstruction_error"] <= 1e-12
    assert panel["maximum_additivity_residual"] <= 1e-12
    assert all(report["checks"].values())
    assert report["passed"] is True


def test_collapsed_target_has_no_nontrivial_post_action_belief_state():
    report = load_report()
    panel = report["panel"]
    result = report["primary_result"]
    assert panel["support_size_counts"] == {"1": 48, "2": 12}
    assert panel["information_sets_after_observed_opponent_action"] == 48
    assert panel[
        "information_sets_with_nontrivial_support_after_observed_opponent_action"
    ] == 0
    assert result["prediction_matched"] is True
    assert result["classification"] == "no_identifiable_post_action_belief_target"
    assert panel["maximum_posterior_l1_shift"] == 0


def test_routing_retires_belief_target_without_promoting_fixed_policy():
    report = load_report()
    assert report["routing_decision"] == (
        "retire_four_card_subgame_as_belief_update_target_and_retain_it_as_"
        "exact_value_decomposition_control"
    )
    assert report["fixed_policy"]["independent_exploitability"] > 0.001
    assert report["fixed_policy"]["equilibrium_gate_passed"] is False
    assert report["fixed_policy"]["gto_label_allowed"] is False
    assert report["runtime_epsilon_gto_allowed"] is False
    assert report["full_round_certified"] is False
