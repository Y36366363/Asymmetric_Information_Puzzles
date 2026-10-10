"""Joint-marginal stratification for the frozen five-die stepwise game."""

from __future__ import annotations

from itertools import product
import random

from aip.core import (
    AlgorithmSpec,
    ExternalSamplingTraversal,
    RegretMinimizationTrainer,
    UniformAverageStrategy,
    VanillaRegretUpdate,
)
from aip.puzzles.liars_dice.five_die_stepwise import (
    HISTOGRAMS,
    FiveDieStepwiseLiarGame,
    FiveDieStepwiseState,
    Histogram,
    required_five_die_information_sets,
)


def _ordered_dice_histogram(faces: tuple[int, ...]) -> Histogram:
    counts = [0] * 6
    for face in faces:
        counts[face] += 1
    return tuple(counts)  # type: ignore[return-value]


ORDERED_DICE_HISTOGRAMS: tuple[Histogram, ...] = tuple(
    _ordered_dice_histogram(faces) for faces in product(range(6), repeat=5)
)
JOINT_STRATIFICATION_EPOCH_SIZE = 6**5


def joint_stratified_epoch(
    *, seed: int, epoch: int
) -> tuple[
    tuple[tuple[Histogram, ...], tuple[Histogram, ...]],
    tuple[tuple[Histogram, ...], tuple[Histogram, ...]],
]:
    """Return independently permuted true-marginal schedules for both updates.

    Each update-player entry is ``(own_hands, opponent_hands)``.  Every list is
    a permutation of all 7,776 equally likely ordered-dice microstates after
    lossless histogram compression.  Random pairing is unbiased for the joint
    chance law but is not exhaustive enumeration of all 252x252 histogram pairs.
    """

    if epoch < 0:
        raise ValueError("joint-stratification epoch must be nonnegative")
    schedules = []
    for update_player in (0, 1):
        hands = []
        for role in (0, 1):
            values = list(ORDERED_DICE_HISTOGRAMS)
            stream_seed = (
                int(seed) * 1_000_003
                + epoch * 10_007
                + update_player * 101
                + role
            )
            random.Random(stream_seed).shuffle(values)
            hands.append(tuple(values))
        schedules.append((hands[0], hands[1]))
    return schedules[0], schedules[1]


class JointMarginalStratifiedExternalSamplingTraversal(
    ExternalSamplingTraversal
):
    """External sampling with exact true-distribution strata for both hands."""

    policy_id = "joint_marginal_stratified_external_sampling"
    update_schedule = "alternating_players_7776_microstate_epochs"

    def __init__(self, *, seed: int) -> None:
        super().__init__(seed=seed)
        self._seed = seed
        self._cached_epoch = -1
        self._cached_schedules = None

    def run_iteration(
        self,
        trainer: RegretMinimizationTrainer[FiveDieStepwiseState],
        root: FiveDieStepwiseState,
        iteration: int,
    ) -> None:
        if root != FiveDieStepwiseState():
            raise ValueError("joint-stratified traversal requires the initial state")
        epoch, offset = divmod(iteration - 1, JOINT_STRATIFICATION_EPOCH_SIZE)
        if epoch != self._cached_epoch:
            self._cached_schedules = joint_stratified_epoch(
                seed=self._seed, epoch=epoch
            )
            self._cached_epoch = epoch
        assert self._cached_schedules is not None
        for update_player in (0, 1):
            own_schedule, opponent_schedule = self._cached_schedules[update_player]
            own_hand = own_schedule[offset]
            opponent_hand = opponent_schedule[offset]
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


class JointStratifiedFiveDieExternalSamplingTrainer(
    RegretMinimizationTrainer[FiveDieStepwiseState]
):
    """Frozen joint-stratification MCCFR experiment trainer."""

    ALGORITHM_ID = "joint_marginal_stratified_external_sampling_mccfr_v1"

    def __init__(self, *, seed: int = 20261010) -> None:
        super().__init__(
            FiveDieStepwiseLiarGame(),
            algorithm_id=self.ALGORITHM_ID,
            traversal_policy=JointMarginalStratifiedExternalSamplingTraversal(
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
                "chance_epoch_size": float(JOINT_STRATIFICATION_EPOCH_SIZE),
                "histogram_strata": float(len(HISTOGRAMS)),
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
            self._node(player, information_set, self.game.legal_actions(state))


def train_five_die_joint_stratified_external_sampling(
    iterations: int, *, seed: int = 20261010
):
    return JointStratifiedFiveDieExternalSamplingTrainer(seed=seed).train(iterations)
