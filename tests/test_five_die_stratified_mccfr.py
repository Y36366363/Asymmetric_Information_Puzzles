from aip.puzzles.liars_dice import (
    FIVE_DIE_HISTOGRAMS,
    StratifiedFiveDieExternalSamplingTrainer,
    required_five_die_information_sets,
    train_five_die_stratified_external_sampling,
    visited_information_set_count,
)


def test_explicit_initialization_is_complete_but_not_counted_as_coverage():
    trainer = StratifiedFiveDieExternalSamplingTrainer(seed=20261009)
    result = trainer.result()
    assert result.iterations == 0
    assert set(result.policy) == set(required_five_die_information_sets())
    assert len(result.policy) == 87_192
    assert visited_information_set_count(result.information_set_visits) == 0
    assert all(count == 0 for count in result.information_set_visits.values())


def test_one_cycle_reaches_every_player_zero_opening_private_hand():
    result = train_five_die_stratified_external_sampling(252, seed=20261009)
    for histogram in FIVE_DIE_HISTOGRAMS:
        assert result.information_set_visits[(0, (histogram, ()))] > 0


def test_algorithm_identity_and_seed_are_recorded():
    result = train_five_die_stratified_external_sampling(1, seed=17)
    assert result.algorithm is not None
    assert result.algorithm.algorithm_id == (
        "stratified_private_hand_external_sampling_mccfr_v1"
    )
    assert result.algorithm.traversal == (
        "stratified_private_hand_external_sampling"
    )
    assert result.algorithm.update_schedule == (
        "alternating_players_252_histogram_cycle"
    )
    assert result.algorithm.parameters == {
        "private_hand_strata": 252.0,
        "preinitialized_information_sets": 87_192.0,
    }
    assert result.algorithm.seed == 17


def test_fixed_seed_is_deterministic():
    first = train_five_die_stratified_external_sampling(10, seed=91)
    second = train_five_die_stratified_external_sampling(10, seed=91)
    assert first.policy == second.policy
    assert first.information_set_visits == second.information_set_visits


def test_visited_coverage_ignores_initialized_policy_presence():
    result = train_five_die_stratified_external_sampling(1, seed=3)
    assert len(result.policy) == 87_192
    assert 0 < visited_information_set_count(result.information_set_visits) < 87_192
