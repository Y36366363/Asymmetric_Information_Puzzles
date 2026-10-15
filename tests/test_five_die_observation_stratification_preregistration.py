import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "configs/five_die_observation_stratification_pilot_2026-10-15.json"


def plan():
    return json.loads(PLAN.read_text())


def test_pilot_is_frozen_with_complete_epoch_doses():
    value = plan()
    assert value["status"] == "frozen_exploratory_pilot_before_execution"
    assert value["iterations"] == 7_776 * value["complete_chance_epochs"]
    assert value["observation_replica_doses"] == [1, 2, 4]


def test_observation_pass_cannot_modify_training_semantics():
    contract = plan()["mechanism_contract"]
    assert contract["updates_regret"] is False
    assert contract["increments_training_visits"] is False
    assert contract["increments_average_strategy_observations"] is True
    assert contract["initialization_counts_as_evidence"] is False


def test_pilot_cannot_certify_or_promote_runtime():
    value = plan()
    assert value["dose_selection_rule"]["pilot_does_not_certify_candidate"] is True
    assert value["dose_selection_rule"][
        "selected_dose_requires_separate_preregistration"
    ] is True
    assert value["scope_boundary"]["do_not_enable_runtime_epsilon_gto"] is True
