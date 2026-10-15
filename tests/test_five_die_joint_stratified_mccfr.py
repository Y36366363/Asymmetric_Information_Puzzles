from collections import Counter

from aip.puzzles.liars_dice import (
    FIVE_DIE_HISTOGRAMS,
    JOINT_STRATIFICATION_EPOCH_SIZE,
    ORDERED_DICE_HISTOGRAMS,
    CoverageAwareJointStratifiedFiveDieTrainer,
    JointStratifiedFiveDieExternalSamplingTrainer,
    ObservationStratifiedFiveDieTrainer,
    ObservationStratifiedJointTraversal,
    joint_stratified_epoch,
    train_five_die_joint_stratified_external_sampling,
    train_five_die_coverage_aware_joint_stratified,
    visited_information_set_count,
)


def test_ordered_microstates_recover_exact_multinomial_histogram_counts():
    counts = Counter(ORDERED_DICE_HISTOGRAMS)
    assert len(ORDERED_DICE_HISTOGRAMS) == JOINT_STRATIFICATION_EPOCH_SIZE == 7_776
    assert set(counts) == set(FIVE_DIE_HISTOGRAMS)
    assert counts[(5, 0, 0, 0, 0, 0)] == 1
    assert counts[(1, 1, 1, 1, 1, 0)] == 120
    assert sum(counts.values()) == 7_776


def test_every_hand_schedule_has_exact_true_marginal_each_epoch():
    expected = Counter(ORDERED_DICE_HISTOGRAMS)
    schedules = joint_stratified_epoch(seed=20261010, epoch=0)
    for own, opponent in schedules:
        assert Counter(own) == expected
        assert Counter(opponent) == expected
        assert own != opponent


def test_joint_pairing_is_reproducible_but_not_false_exhaustive_enumeration():
    first = joint_stratified_epoch(seed=20261010, epoch=2)
    repeated = joint_stratified_epoch(seed=20261010, epoch=2)
    different = joint_stratified_epoch(seed=20261011, epoch=2)
    assert first == repeated
    assert first != different
    pairs = set(zip(first[0][0], first[0][1]))
    assert len(pairs) <= 7_776 < 252 * 252


def test_joint_trainer_keeps_complete_initialization_out_of_visit_coverage():
    trainer = JointStratifiedFiveDieExternalSamplingTrainer(seed=20261010)
    initial = trainer.result()
    assert len(initial.policy) == 87_192
    assert visited_information_set_count(initial.information_set_visits) == 0


def test_joint_algorithm_identity_configuration_and_seed_are_recorded():
    result = train_five_die_joint_stratified_external_sampling(1, seed=23)
    assert result.algorithm is not None
    assert result.algorithm.algorithm_id == (
        "joint_marginal_stratified_external_sampling_mccfr_v1"
    )
    assert result.algorithm.traversal == (
        "joint_marginal_stratified_external_sampling"
    )
    assert result.algorithm.update_schedule == (
        "alternating_players_7776_microstate_epochs"
    )
    assert result.algorithm.averaging_rule == "uniform_iteration_weighting"
    assert result.algorithm.parameters == {
        "chance_epoch_size": 7_776.0,
        "histogram_strata": 252.0,
        "preinitialized_information_sets": 87_192.0,
    }
    assert result.algorithm.seed == 23


def test_fixed_seed_training_is_deterministic():
    first = train_five_die_joint_stratified_external_sampling(10, seed=47)
    second = train_five_die_joint_stratified_external_sampling(10, seed=47)
    assert first.policy == second.policy
    assert first.information_set_visits == second.information_set_visits


def test_coverage_aware_joint_trainer_has_frozen_identity_and_complete_fallback():
    result = train_five_die_coverage_aware_joint_stratified(1, seed=731101)
    assert result.algorithm.algorithm_id == (
        "coverage_aware_joint_marginal_stratified_external_sampling_mccfr_v1"
    )
    assert result.algorithm.averaging_rule == (
        "uniform_iteration_zero_weight_current_strategy_fallback"
    )
    fallback = {
        key
        for key, used in result.average_strategy_fallback_used.items()
        if used
    }
    zero_weight = {
        key
        for key, weight in result.average_strategy_observation_weight.items()
        if weight <= 0
    }
    assert fallback == zero_weight


def test_coverage_aware_joint_trainer_preserves_training_trace():
    candidate = CoverageAwareJointStratifiedFiveDieTrainer(seed=31).train(20)
    comparison = JointStratifiedFiveDieExternalSamplingTrainer(seed=31).train(20)
    assert candidate.information_set_visits == comparison.information_set_visits
    assert candidate.average_positive_regret == comparison.average_positive_regret
    assert candidate.average_strategy_observations == (
        comparison.average_strategy_observations
    )
    assert candidate.average_strategy_observation_weight == (
        comparison.average_strategy_observation_weight
    )
    changed = {
        key
        for key in candidate.policy
        if candidate.policy[key] != comparison.policy[key]
    }
    assert changed <= {
        key
        for key, used in candidate.average_strategy_fallback_used.items()
        if used
    }


def test_observation_strata_preserve_regret_and_visit_semantics():
    candidate_trainer = ObservationStratifiedFiveDieTrainer(
        seed=59, observation_replicas=2
    )
    comparison_trainer = CoverageAwareJointStratifiedFiveDieTrainer(seed=59)
    candidate = candidate_trainer.train(50)
    comparison = comparison_trainer.train(50)
    assert candidate.information_set_visits == comparison.information_set_visits
    assert candidate.average_positive_regret == comparison.average_positive_regret
    assert {
        key: tuple(node.regrets)
        for key, node in candidate_trainer._nodes.items()
    } == {
        key: tuple(node.regrets)
        for key, node in comparison_trainer._nodes.items()
    }
    assert sum(candidate.average_strategy_observations.values()) > sum(
        comparison.average_strategy_observations.values()
    )
    assert sum(candidate.average_strategy_observation_weight.values()) > sum(
        comparison.average_strategy_observation_weight.values()
    )


def test_observation_strata_have_exact_private_histogram_marginals():
    traversal = ObservationStratifiedJointTraversal(
        seed=61, observation_replicas=2
    )
    expected = Counter(ORDERED_DICE_HISTOGRAMS)
    for replica in range(2):
        for own, opponent in traversal._observation_schedules(0, replica):
            assert Counter(own) == expected
            assert Counter(opponent) == expected


def test_observation_replica_parameter_is_validated_and_exported():
    for invalid in (0, -1, 1.5, True):
        try:
            ObservationStratifiedFiveDieTrainer(
                seed=67, observation_replicas=invalid
            )
        except ValueError as error:
            assert "positive integer" in str(error)
        else:
            raise AssertionError("invalid observation replica count was accepted")
    result = ObservationStratifiedFiveDieTrainer(
        seed=67, observation_replicas=3
    ).train(1)
    assert result.algorithm.algorithm_id == "observation_stratified_five_die_mccfr_v1"
    assert result.algorithm.parameters["observation_replicas"] == 3
