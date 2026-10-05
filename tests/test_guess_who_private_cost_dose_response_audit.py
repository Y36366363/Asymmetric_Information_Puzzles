import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AUDIT = (
    ROOT / "research/results/guess_who_private_cost_dose_response_2026-10-05.json"
)


def load_report():
    return json.loads(AUDIT.read_text())


def test_every_preregistered_dose_is_independently_certified():
    report = load_report()
    levels = report["dose_response"]
    assert [level["unit_cost"] for level in levels] == [
        0.0,
        0.005,
        0.01,
        0.02,
        0.04,
        0.08,
        0.16,
    ]
    assert all(level["checks"]["exact_certification"] for level in levels)
    assert all(level["checks"]["enumeration_invariance"] for level in levels)
    assert all(
        level["independent_evaluation"]["exploitability"] <= 1e-10
        for level in levels
    )
    assert report["checks"]["all_doses_exactly_certified"] is True
    assert report["checks"]["all_doses_enumeration_invariant"] is True


def test_fixed_dose_grid_is_a_retained_zero_signal_result():
    report = load_report()
    levels = report["dose_response"]
    endpoint = report["primary_endpoint"]
    assert endpoint["smallest_preregistered_unit_cost_with_positive_signal"] == (
        "none_in_grid"
    )
    assert all(level["classification"] == "zero_result" for level in levels)
    assert max(level["primary_endpoint"] for level in levels) <= endpoint[
        "null_result_threshold"
    ]
    assert max(level["reversed_enumeration_endpoint"] for level in levels) <= endpoint[
        "null_result_threshold"
    ]
    assert report["runtime_epsilon_gto_allowed"] is False


def test_dose_changes_timing_but_not_the_preregistered_signal_endpoint():
    levels = load_report()["dose_response"]
    baseline = levels[0]["equilibrium_behavior"]
    positive_cost = levels[1]["equilibrium_behavior"]
    assert baseline["expected_both_ask_rounds"] > positive_cost[
        "expected_both_ask_rounds"
    ]
    assert baseline["ambiguous_terminal_guess_probability"] < positive_cost[
        "ambiguous_terminal_guess_probability"
    ]
    assert positive_cost["expected_question_cost_by_seat"]["player_0"] > 0
    assert positive_cost["expected_question_cost_by_seat"]["player_1"] > 0


def test_highest_dose_cfr_cross_checks_and_negative_control_are_valid():
    report = load_report()
    cross_check = report["regret_minimization_cross_check"]
    assert cross_check["unit_cost"] == 0.16
    algorithms = cross_check["algorithms"]
    assert set(algorithms) == {"vanilla_cfr", "cfr_plus", "dcfr"}
    assert all(record["iterations"] == 5_000 for record in algorithms.values())
    assert all(
        record["independent_evaluation"]["passed"]
        for record in algorithms.values()
    )
    assert report["checks"]["all_cfr_cross_checks"] is True
    assert report["undertrained_negative_control"]["passed_gate"] is False
    assert report["checks"]["undertrained_negative_control_rejected"] is True
    assert report["passed"] is True
