from aip.core import (
    CoverageAwareReachWeightedExternalSamplingCFRTrainer,
    ReachWeightedExternalSamplingCFRTrainer,
    create_regret_minimization_trainer,
)
from aip.puzzles.kuhn_poker import KuhnCFRGame
from aip.puzzles.liars_dice import (
    OneDieLiarDiceCFRGame,
    OneDieLiarState,
    required_one_die_information_sets,
)


def initialize_one_die(trainer):
    for player, information_set in required_one_die_information_sets():
        own_die, bids = information_set
        dice = (own_die, 1) if player == 0 else (1, own_die)
        actions = trainer.game.legal_actions(OneDieLiarState(dice, bids))
        trainer.initialize_information_set(player, information_set, actions)


def test_zero_weight_node_uses_current_regret_matching_without_evidence():
    trainer = CoverageAwareReachWeightedExternalSamplingCFRTrainer(
        KuhnCFRGame(), seed=1
    )
    key = (0, ("J", ""))
    trainer.initialize_information_set(0, key[1], ("check", "bet"))
    trainer._nodes[key].regrets[:] = [0.0, 3.0]
    result = trainer.result()
    assert result.policy[key] == {"check": 0.0, "bet": 1.0}
    assert result.average_strategy_observations[key] == 0
    assert result.average_strategy_observation_weight[key] == 0
    assert result.average_strategy_fallback_used[key] is True


def test_positive_weight_node_never_uses_fallback():
    result = CoverageAwareReachWeightedExternalSamplingCFRTrainer(
        KuhnCFRGame(), seed=2
    ).train(100)
    for key, weight in result.average_strategy_observation_weight.items():
        assert result.average_strategy_fallback_used[key] is (weight <= 0)


def test_fallback_changes_only_reported_zero_weight_policies():
    candidate = CoverageAwareReachWeightedExternalSamplingCFRTrainer(
        OneDieLiarDiceCFRGame(), seed=7
    )
    comparison = ReachWeightedExternalSamplingCFRTrainer(
        OneDieLiarDiceCFRGame(), seed=7
    )
    initialize_one_die(candidate)
    initialize_one_die(comparison)
    candidate_result = candidate.train(2_000)
    comparison_result = comparison.train(2_000)
    assert candidate_result.information_set_visits == (
        comparison_result.information_set_visits
    )
    assert candidate_result.average_positive_regret == (
        comparison_result.average_positive_regret
    )
    assert candidate_result.average_strategy_observations == (
        comparison_result.average_strategy_observations
    )
    assert candidate_result.average_strategy_observation_weight == (
        comparison_result.average_strategy_observation_weight
    )
    differences = {
        key
        for key in candidate_result.policy
        if candidate_result.policy[key] != comparison_result.policy[key]
    }
    assert differences
    assert differences <= {
        key
        for key, used in candidate_result.average_strategy_fallback_used.items()
        if used
    }


def test_fallback_algorithm_has_separate_identity_and_rejects_parameters():
    result = create_regret_minimization_trainer(
        KuhnCFRGame(),
        "coverage_aware_reach_weighted_external_sampling_mccfr_v1",
        seed=11,
    ).train(1)
    assert result.algorithm.algorithm_id == (
        "coverage_aware_reach_weighted_external_sampling_mccfr_v1"
    )
    assert result.algorithm.averaging_rule == (
        "own_reach_weighted_zero_weight_current_strategy_fallback"
    )
