import pytest

from aip.core import (
    CFRTrainer,
    ExternalSamplingCFRTrainer,
    ReachWeightedExternalSamplingCFRTrainer,
    create_regret_minimization_trainer,
)
from aip.puzzles.kuhn_poker import KuhnCFRGame


def test_full_tree_reports_average_strategy_observations_separately_from_visits():
    result = CFRTrainer(KuhnCFRGame()).train(2)
    assert set(result.average_strategy_observations) == set(result.policy)
    assert set(result.average_strategy_observation_weight) == set(result.policy)
    assert all(value > 0 for value in result.average_strategy_observations.values())
    assert all(
        value > 0 for value in result.average_strategy_observation_weight.values()
    )


def test_legacy_external_sampling_observation_weight_matches_simple_count():
    result = ExternalSamplingCFRTrainer(KuhnCFRGame(), seed=19).train(100)
    assert result.average_strategy_observations
    for key, count in result.average_strategy_observations.items():
        assert result.average_strategy_observation_weight[key] == pytest.approx(count)
        assert count <= result.information_set_visits[key]


def test_reach_weighted_estimator_has_independent_count_and_weight():
    result = ReachWeightedExternalSamplingCFRTrainer(
        KuhnCFRGame(), seed=19
    ).train(100)
    assert result.average_strategy_observations
    assert any(
        0 < result.average_strategy_observation_weight[key] < count
        for key, count in result.average_strategy_observations.items()
    )
    assert all(
        0 <= result.average_strategy_observation_weight[key] <= count
        for key, count in result.average_strategy_observations.items()
    )


def test_new_estimator_changes_only_average_policy_not_regret_or_visit_trace():
    legacy = ExternalSamplingCFRTrainer(KuhnCFRGame(), seed=23).train(500)
    candidate = ReachWeightedExternalSamplingCFRTrainer(
        KuhnCFRGame(), seed=23
    ).train(500)
    assert candidate.information_set_visits == legacy.information_set_visits
    assert candidate.average_positive_regret == legacy.average_positive_regret
    assert candidate.policy != legacy.policy


def test_new_estimator_is_available_under_separate_algorithm_id():
    result = create_regret_minimization_trainer(
        KuhnCFRGame(),
        "reach_weighted_external_sampling_mccfr_v1",
        seed=29,
    ).train(1)
    assert result.algorithm is not None
    assert result.algorithm.algorithm_id == (
        "reach_weighted_external_sampling_mccfr_v1"
    )
    assert result.algorithm.traversal == "external_sampling_reach_weighted_average"
    assert result.algorithm.averaging_rule == (
        "own_reach_weighted_uniform_iteration"
    )
    with pytest.raises(ValueError, match="does not accept"):
        create_regret_minimization_trainer(
            KuhnCFRGame(),
            "reach_weighted_external_sampling_mccfr_v1",
            parameters={"gamma": 2.0},
        )


def test_explicit_initialization_does_not_fabricate_observations():
    trainer = ReachWeightedExternalSamplingCFRTrainer(KuhnCFRGame(), seed=31)
    trainer.initialize_information_set(0, ("J", ""), ("check", "bet"))
    result = trainer.result()
    key = (0, ("J", ""))
    assert result.information_set_visits[key] == 0
    assert result.average_strategy_observations[key] == 0
    assert result.average_strategy_observation_weight[key] == 0
