import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AUDIT = (
    ROOT
    / "research/results/love_letter_fixed_policy_conditioning_2026-10-06.json"
)


def load_report():
    return json.loads(AUDIT.read_text())


def test_fixed_policy_panel_is_complete_and_mechanically_exact():
    report = load_report()
    panel = report["fixed_policy_panel"]
    assert panel["total_information_sets"] == 60
    assert panel["positive_reach_information_sets"] == 60
    assert panel["zero_reach_information_sets"] == 0
    assert panel["maximum_bayes_reconstruction_error"] <= 1e-12
    assert panel["maximum_value_reconstruction_error"] <= 1e-12
    assert panel["maximum_additivity_residual"] <= 1e-12
    assert all(report["checks"].values())
    assert report["passed"] is True


def test_preregistered_private_hand_policy_retains_zero_conditioning_result():
    report = load_report()
    result = report["primary_result"]
    assert result["classification"] == "zero_conditioning_signal"
    assert result["maximum_posterior_l1_shift"] == 0
    assert result["shifted_information_sets"] == 0
    assert report["hypothesis_checks"][
        "fixed_policy_positive_conditioning_signal"
    ] is False
    assert all(
        len(set(row["policy_reach_weights"].values())) == 1
        for row in report["fixed_policy_panel"]["rows"]
    )


def test_equilibrium_control_and_non_gto_boundary_remain_explicit():
    report = load_report()
    equilibrium = report["equilibrium_control"]
    assert equilibrium["panel"]["positive_reach_information_sets"] == 17
    assert equilibrium["panel"]["zero_reach_information_sets"] == 43
    assert equilibrium["panel"]["shifted_information_sets"] == 0
    assert equilibrium["independent_evaluation"]["passed"] is True
    assert report["fixed_policy"]["independent_evaluation"]["passed"] is False
    assert report["fixed_policy"]["independent_evaluation"]["exploitability"] > 0.001
    assert report["fixed_policy"]["gto_label_allowed"] is False
    assert report["runtime_epsilon_gto_allowed"] is False
    assert report["full_round_certified"] is False
