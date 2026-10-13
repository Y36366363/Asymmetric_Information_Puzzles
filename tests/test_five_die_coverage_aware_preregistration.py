import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PREREGISTRATION = (
    ROOT / "configs/five_die_coverage_aware_joint_preregistration_2026-10-13.json"
)


def plan():
    return json.loads(PREREGISTRATION.read_text())


def test_five_die_protocol_is_new_frozen_work_not_a_budget_extension():
    value = plan()
    assert value["status"] == "frozen_before_implementation_and_training"
    assert value["scope_boundary"][
        "this_is_a_new_run_not_an_extension_of_prior_budget"
    ] is True
    assert len(value["retained_failed_experiments"]) == 3


def test_budget_contains_complete_joint_stratification_epochs():
    algorithm = plan()["algorithm"]
    assert algorithm["iterations"] == algorithm["epoch_size"] * algorithm["epochs"]
    assert algorithm["checkpoints"][-1] == algorithm["iterations"]
    assert all(
        point % algorithm["epoch_size"] == 0
        for point in algorithm["checkpoints"]
    )


def test_candidate_keeps_independent_gates_and_runtime_closed():
    value = plan()
    gates = value["candidate_gates"]
    assert gates["maximum_final_independent_exploitability"] == 0.05
    assert gates["minimum_positive_visit_coverage"] == 0.65
    assert gates["maximum_final_fallback_fraction"] == 0.4
    assert value["scope_boundary"][
        "runtime_epsilon_gto_allowed_during_experiment"
    ] is False
    assert value["scope_boundary"][
        "complete_resumable_tree_audit_required_for_runtime"
    ] is True
