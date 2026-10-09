"""Coverage-controlled MCCFR for the frozen five-die stepwise game.

The traversal stratifies the updating player's private histogram while keeping
the opponent histogram distributed according to the game's true multinomial
chance law.  Preinitializing nodes makes the output profile complete, but node
visits remain zero until a traversal actually reaches the information set.
"""

from __future__ import annotations

from typing import Hashable, Mapping

from aip.core import (
    AlgorithmSpec,
    ExternalSamplingTraversal,
    RegretMinimizationTrainer,
    UniformAverageStrategy,
    VanillaRegretUpdate,
)
from aip.puzzles.liars_dice.five_die_stepwise import (
    HISTOGRAMS,
    HISTOGRAM_OUTCOMES,
    FiveDieStepwiseLiarGame,
    FiveDieStepwiseState,
    required_five_die_information_sets,
)


class StratifiedPrivateHandExternalSamplingTraversal(ExternalSamplingTraversal):
    """External sampling with deterministic coverage of each own histogram."""

    policy_id = "stratified_private_hand_external_sampling"
    update_schedule = "alternating_players_252_histogram_cycle"

    def run_iteration(
        self,
        trainer: RegretMinimizationTrainer[FiveDieStepwiseState],
        root: FiveDieStepwiseState,
        iteration: int,
    ) -> None:
        if root != FiveDieStepwiseState():
            raise ValueError("stratified five-die traversal requires the initial state")
        own_hand = HISTOGRAMS[(iteration - 1) % len(HISTOGRAMS)]
        for update_player in (0, 1):
            opponent_hand = self._sample_opponent_histogram()
            hands = (
                (own_hand, opponent_hand)
                if update_player == 0
                else (opponent_hand, own_hand)
            )
            self._traverse(
                trainer,
                FiveDieStepwiseState(hands),
                update_player=update_player,
                sampled_opponent_actions={},
                iteration=iteration,
            )

    def _sample_opponent_histogram(self):
        target = self._rng.random()
        cumulative = 0.0
        for histogram, probability in HISTOGRAM_OUTCOMES:
            cumulative += probability
            if target <= cumulative:
                return histogram
        return HISTOGRAM_OUTCOMES[-1][0]


class StratifiedFiveDieExternalSamplingTrainer(
    RegretMinimizationTrainer[FiveDieStepwiseState]
):
    """Preregistered five-die trainer with complete zero-regret initialization."""

    ALGORITHM_ID = "stratified_private_hand_external_sampling_mccfr_v1"

    def __init__(self, *, seed: int = 20261009) -> None:
        super().__init__(
            FiveDieStepwiseLiarGame(),
            algorithm_id=self.ALGORITHM_ID,
            traversal_policy=StratifiedPrivateHandExternalSamplingTraversal(
                seed=seed
            ),
            regret_update_policy=VanillaRegretUpdate(),
            average_strategy_policy=UniformAverageStrategy(),
            seed=seed,
        )
        self._initialize_all_information_sets()

    @property
    def algorithm_spec(self) -> AlgorithmSpec:
        return AlgorithmSpec(
            algorithm_id=self.ALGORITHM_ID,
            parameters={
                "private_hand_strata": float(len(HISTOGRAMS)),
                "preinitialized_information_sets": float(
                    len(required_five_die_information_sets())
                ),
            },
            traversal=self.traversal_policy.policy_id,
            update_schedule=self.traversal_policy.update_schedule,
            averaging_rule=self.average_strategy_policy.policy_id,
            seed=self.seed,
        )

    def _initialize_all_information_sets(self) -> None:
        game = self.game
        reference_hand = HISTOGRAMS[0]
        for player, information_set in sorted(
            required_five_die_information_sets(), key=repr
        ):
            own_hand, bids = information_set
            hands = (
                (own_hand, reference_hand)
                if player == 0
                else (reference_hand, own_hand)
            )
            state = FiveDieStepwiseState(hands, bids)
            actions = game.legal_actions(state)
            self._node(player, information_set, actions)


def visited_information_set_count(
    visits: Mapping[tuple[int, Hashable], int],
) -> int:
    """Count actual traversal coverage, excluding initialized-only nodes."""

    return sum(1 for count in visits.values() if count > 0)


def train_five_die_stratified_external_sampling(
    iterations: int, *, seed: int = 20261009
):
    return StratifiedFiveDieExternalSamplingTrainer(seed=seed).train(iterations)
