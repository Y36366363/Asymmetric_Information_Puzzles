"""Reusable tabular CFR engine and evidence gate for finite two-player games."""

from __future__ import annotations

from dataclasses import dataclass, field
from math import fsum, isfinite
import random
from typing import Callable, Generic, Hashable, Mapping, Protocol, TypeVar


State = TypeVar("State")
Action = Hashable
InformationSet = Hashable


class ExtensiveFormGame(Protocol[State]):
    """Adapter boundary for finite, two-player, zero-sum extensive-form games."""

    def initial_state(self) -> State: ...

    def is_terminal(self, state: State) -> bool: ...

    def utility_player_zero(self, state: State) -> float: ...

    def current_player(self, state: State) -> int | None: ...

    def chance_outcomes(self, state: State) -> tuple[tuple[Action, float], ...]: ...

    def legal_actions(self, state: State) -> tuple[Action, ...]: ...

    def information_set(self, state: State) -> InformationSet: ...

    def next_state(self, state: State, action: Action) -> State: ...


# Backward-compatible name retained for every existing game adapter.
CFRGame = ExtensiveFormGame


@dataclass(frozen=True, slots=True)
class AlgorithmSpec:
    """Serializable identity of one regret-minimization run."""

    algorithm_id: str
    parameters: Mapping[str, float]
    traversal: str
    update_schedule: str
    averaging_rule: str
    seed: int | None

    def to_artifact(self) -> dict[str, object]:
        return {
            "algorithm_id": self.algorithm_id,
            "parameters": dict(sorted(self.parameters.items())),
            "traversal": self.traversal,
            "update_schedule": self.update_schedule,
            "averaging_rule": self.averaging_rule,
            "seed": self.seed,
        }


class RegretUpdatePolicy(Protocol):
    """How a completed traversal changes cumulative counterfactual regret."""

    policy_id: str

    def apply(
        self, current: float, delta: float, *, iteration: int
    ) -> float: ...

    def parameters(self) -> Mapping[str, float]: ...


@dataclass(frozen=True, slots=True)
class VanillaRegretUpdate:
    policy_id: str = "regret_matching"

    def apply(self, current: float, delta: float, *, iteration: int) -> float:
        return current + delta

    def parameters(self) -> Mapping[str, float]:
        return {}


@dataclass(frozen=True, slots=True)
class RegretMatchingPlusUpdate:
    policy_id: str = "regret_matching_plus"

    def apply(self, current: float, delta: float, *, iteration: int) -> float:
        return max(0.0, current + delta)

    def parameters(self) -> Mapping[str, float]:
        return {}


@dataclass(frozen=True, slots=True)
class DiscountedRegretUpdate:
    alpha: float = 1.5
    beta: float = 0.0
    policy_id: str = "discounted_regret"

    def __post_init__(self) -> None:
        if not isfinite(self.alpha) or not isfinite(self.beta):
            raise ValueError("DCFR alpha and beta must be finite")

    def apply(self, current: float, delta: float, *, iteration: int) -> float:
        exponent = self.alpha if current > 0 else self.beta
        power = iteration**exponent
        if not isfinite(power) or power < 0:
            raise ValueError("DCFR regret discount must be finite and nonnegative")
        return current * (power / (power + 1.0)) + delta

    def parameters(self) -> Mapping[str, float]:
        return {"alpha": self.alpha, "beta": self.beta}


class AverageStrategyPolicy(Protocol):
    """How one traversal contributes to the reported average strategy."""

    policy_id: str

    def apply(
        self, current: float, delta: float, *, iteration: int
    ) -> float: ...

    def parameters(self) -> Mapping[str, float]: ...


@dataclass(frozen=True, slots=True)
class UniformAverageStrategy:
    policy_id: str = "uniform_iteration_weighting"

    def apply(self, current: float, delta: float, *, iteration: int) -> float:
        return current + delta

    def parameters(self) -> Mapping[str, float]:
        return {}


@dataclass(frozen=True, slots=True)
class LinearAverageStrategy:
    policy_id: str = "linear_iteration_weighting"

    def apply(self, current: float, delta: float, *, iteration: int) -> float:
        return current + iteration * delta

    def parameters(self) -> Mapping[str, float]:
        return {}


@dataclass(frozen=True, slots=True)
class DiscountedAverageStrategy:
    gamma: float = 2.0
    policy_id: str = "discounted_iteration_weighting"

    def __post_init__(self) -> None:
        if not isfinite(self.gamma) or self.gamma < 0:
            raise ValueError("DCFR gamma must be finite and nonnegative")

    def apply(self, current: float, delta: float, *, iteration: int) -> float:
        discount = ((iteration - 1.0) / iteration) ** self.gamma
        if not isfinite(discount) or discount < 0:
            raise ValueError(
                "DCFR average-strategy discount must be finite and nonnegative"
            )
        return current * discount + delta

    def parameters(self) -> Mapping[str, float]:
        return {"gamma": self.gamma}


class TraversalPolicy(Protocol[State]):
    """Select which branches a trainer visits during one iteration."""

    policy_id: str
    update_schedule: str

    def run_iteration(
        self, trainer: "RegretMinimizationTrainer[State]", root: State, iteration: int
    ) -> None: ...


@dataclass(slots=True)
class _Node:
    actions: tuple[Action, ...]
    regrets: list[float]
    strategy_sum: list[float]
    visits: int = 0

    @classmethod
    def create(cls, actions: tuple[Action, ...]) -> _Node:
        return cls(actions, [0.0] * len(actions), [0.0] * len(actions))

    def strategy(self) -> tuple[float, ...]:
        positive = [max(0.0, regret) for regret in self.regrets]
        total = sum(positive)
        if total <= 0:
            return tuple(1 / len(self.actions) for _ in self.actions)
        return tuple(value / total for value in positive)

    def average_strategy(self) -> tuple[float, ...]:
        total = sum(self.strategy_sum)
        if total <= 0:
            return tuple(1 / len(self.actions) for _ in self.actions)
        return tuple(value / total for value in self.strategy_sum)


@dataclass(slots=True)
class _CFRBatch:
    """Per-player full-tree deltas committed only after traversal finishes."""

    regrets: dict[tuple[int, InformationSet], list[float]] = field(
        default_factory=dict
    )
    strategy: dict[tuple[int, InformationSet], list[float]] = field(
        default_factory=dict
    )
    visits: dict[tuple[int, InformationSet], int] = field(default_factory=dict)

    @staticmethod
    def _add(
        table: dict[tuple[int, InformationSet], list[float]],
        key: tuple[int, InformationSet],
        values: tuple[float, ...],
    ) -> None:
        totals = table.setdefault(key, [0.0] * len(values))
        for index, value in enumerate(values):
            totals[index] += value


@dataclass(frozen=True, slots=True)
class CFRCheckpoint:
    iteration: int
    independent_evaluation: Mapping[str, float]

    def to_artifact(self) -> dict[str, object]:
        return {
            "iteration": self.iteration,
            "independent_evaluation": dict(self.independent_evaluation),
        }


@dataclass(frozen=True, slots=True)
class CFRResult:
    iterations: int
    policy: Mapping[tuple[int, InformationSet], Mapping[Action, float]]
    information_set_visits: Mapping[tuple[int, InformationSet], int]
    average_positive_regret: tuple[float, float]
    algorithm: AlgorithmSpec | None = None
    convergence_trace: tuple[CFRCheckpoint, ...] = ()

    @property
    def information_set_count(self) -> int:
        return len(self.policy)


class FullTreeTraversal:
    """Deterministic full-tree traversal with per-player batched commits."""

    policy_id = "full_tree"
    update_schedule = "alternating_players"

    def run_iteration(
        self, trainer: "RegretMinimizationTrainer[State]", root: State, iteration: int
    ) -> None:
        for update_player in (0, 1):
            batch = _CFRBatch()
            trainer._traverse_full_tree(
                root,
                1.0,
                1.0,
                1.0,
                update_player=update_player,
                batch=batch,
            )
            trainer._apply_batch(batch, iteration=iteration)


class RegretMinimizationTrainer(Generic[State]):
    """Composable tabular trainer for finite two-player extensive-form games.

    Each player traversal reads one fixed regret-matching strategy. Regret and
    average-strategy deltas from every chance outcome are committed together
    only after that complete traversal, making deterministic results independent
    of chance and action enumeration order (up to floating-point roundoff).
    """

    def __init__(
        self,
        game: ExtensiveFormGame[State],
        *,
        algorithm_id: str,
        traversal_policy: TraversalPolicy[State],
        regret_update_policy: RegretUpdatePolicy,
        average_strategy_policy: AverageStrategyPolicy,
        seed: int | None,
    ) -> None:
        self.game = game
        self.algorithm_id = algorithm_id
        self.traversal_policy = traversal_policy
        self.regret_update_policy = regret_update_policy
        self.average_strategy_policy = average_strategy_policy
        self.seed = seed
        self._nodes: dict[tuple[int, InformationSet], _Node] = {}
        self.iterations = 0
        self._convergence_trace: list[CFRCheckpoint] = []

    @property
    def algorithm_spec(self) -> AlgorithmSpec:
        parameters = {
            **self.regret_update_policy.parameters(),
            **self.average_strategy_policy.parameters(),
        }
        return AlgorithmSpec(
            algorithm_id=self.algorithm_id,
            parameters=parameters,
            traversal=self.traversal_policy.policy_id,
            update_schedule=self.traversal_policy.update_schedule,
            averaging_rule=self.average_strategy_policy.policy_id,
            seed=self.seed,
        )

    def train(
        self,
        iterations: int,
        *,
        checkpoints: set[int] | None = None,
        independent_evaluator: (
            Callable[[CFRResult], Mapping[str, float]] | None
        ) = None,
    ) -> CFRResult:
        if iterations <= 0:
            raise ValueError("CFR iterations must be positive")
        if checkpoints and independent_evaluator is None:
            raise ValueError("CFR checkpoints require an independent evaluator")
        if checkpoints and any(point <= self.iterations for point in checkpoints):
            raise ValueError("CFR checkpoints must be later than completed iterations")
        target_iteration = self.iterations + iterations
        if checkpoints and any(point > target_iteration for point in checkpoints):
            raise ValueError("CFR checkpoint exceeds the requested training horizon")
        root = self.game.initial_state()
        for _ in range(iterations):
            iteration = self.iterations + 1
            self.traversal_policy.run_iteration(self, root, iteration)
            self.iterations += 1
            if checkpoints and self.iterations in checkpoints:
                assert independent_evaluator is not None
                metrics = dict(independent_evaluator(self.result()))
                required = {
                    "nash_conv",
                    "exploitability",
                    "player_0_deviation_gain",
                    "player_1_deviation_gain",
                    "maximum_unilateral_deviation_gain",
                }
                if set(metrics) != required or any(
                    not isfinite(value) or value < 0 for value in metrics.values()
                ):
                    raise ValueError(
                        "independent evaluator must return the five finite, nonnegative equilibrium metrics"
                    )
                canonical = EquilibriumEvaluation(
                    metrics["player_0_deviation_gain"],
                    metrics["player_1_deviation_gain"],
                ).to_report()
                if any(
                    abs(metrics[name] - canonical[name]) > 1e-12
                    for name in required
                ):
                    raise ValueError(
                        "independent evaluator returned inconsistent equilibrium metrics"
                    )
                self._convergence_trace.append(
                    CFRCheckpoint(self.iterations, metrics)
                )
        return self.result()

    def _apply_batch(self, batch: _CFRBatch, *, iteration: int) -> None:
        for key, deltas in batch.regrets.items():
            node = self._nodes[key]
            for index, delta in enumerate(deltas):
                node.regrets[index] = self.regret_update_policy.apply(
                    node.regrets[index], delta, iteration=iteration
                )
        for key, deltas in batch.strategy.items():
            node = self._nodes[key]
            for index, delta in enumerate(deltas):
                node.strategy_sum[index] = self.average_strategy_policy.apply(
                    node.strategy_sum[index], delta, iteration=iteration
                )
        for key, visits in batch.visits.items():
            self._nodes[key].visits += visits

    def result(self) -> CFRResult:
        policy: dict[tuple[int, InformationSet], dict[Action, float]] = {}
        visits: dict[tuple[int, InformationSet], int] = {}
        regret_totals = [0.0, 0.0]
        for key, node in self._nodes.items():
            policy[key] = dict(zip(node.actions, node.average_strategy()))
            visits[key] = node.visits
            regret_totals[key[0]] += sum(max(0.0, value) for value in node.regrets)
        denominator = max(1, self.iterations)
        return CFRResult(
            iterations=self.iterations,
            policy=policy,
            information_set_visits=visits,
            average_positive_regret=(
                regret_totals[0] / denominator,
                regret_totals[1] / denominator,
            ),
            algorithm=self.algorithm_spec,
            convergence_trace=tuple(self._convergence_trace),
        )

    def _node(
        self, player: int, information_set: InformationSet, actions: tuple[Action, ...]
    ) -> _Node:
        if len(set(actions)) != len(actions):
            raise ValueError(
                f"information set {information_set!r} has duplicate legal actions"
            )
        key = (player, information_set)
        node = self._nodes.get(key)
        if node is None:
            if not actions:
                raise ValueError("non-terminal CFR states need at least one legal action")
            node = _Node.create(actions)
            self._nodes[key] = node
        elif node.actions != actions:
            raise ValueError(
                f"information set {information_set!r} has inconsistent legal actions"
            )
        return node

    def _traverse_full_tree(
        self,
        state: State,
        reach_zero: float,
        reach_one: float,
        chance_reach: float,
        *,
        update_player: int,
        batch: _CFRBatch,
    ) -> float:
        if self.game.is_terminal(state):
            utility = self.game.utility_player_zero(state)
            if not isfinite(utility):
                raise ValueError("terminal CFR utility must be finite")
            return utility
        player = self.game.current_player(state)
        if player is None:
            outcomes = self.game.chance_outcomes(state)
            total_probability = sum(probability for _, probability in outcomes)
            if (
                not outcomes
                or len({action for action, _ in outcomes}) != len(outcomes)
                or any(
                    not isfinite(probability) or probability < 0
                    for _, probability in outcomes
                )
                or abs(total_probability - 1.0) > 1e-9
            ):
                raise ValueError(
                    "chance outcomes must be finite, nonnegative, nonempty, and sum to one"
                )
            return fsum(
                probability
                * self._traverse_full_tree(
                    self.game.next_state(state, action),
                    reach_zero,
                    reach_one,
                    chance_reach * probability,
                    update_player=update_player,
                    batch=batch,
                )
                for action, probability in outcomes
            )
        if player not in (0, 1):
            raise ValueError("CFR current_player must be 0, 1, or None for chance")

        actions = self.game.legal_actions(state)
        information_set = self.game.information_set(state)
        node = self._node(player, information_set, actions)
        strategy = node.strategy()
        action_values: list[float] = []
        for action, probability in zip(actions, strategy):
            next_zero = reach_zero * probability if player == 0 else reach_zero
            next_one = reach_one * probability if player == 1 else reach_one
            action_values.append(
                self._traverse_full_tree(
                    self.game.next_state(state, action),
                    next_zero,
                    next_one,
                    chance_reach,
                    update_player=update_player,
                    batch=batch,
                )
            )
        node_value = fsum(
            probability * value for probability, value in zip(strategy, action_values)
        )
        if player == update_player:
            own_reach = reach_zero if player == 0 else reach_one
            opponent_reach = reach_one if player == 0 else reach_zero
            sign = 1.0 if player == 0 else -1.0
            key = (player, information_set)
            batch._add(
                batch.regrets,
                key,
                tuple(
                    chance_reach
                    * opponent_reach
                    * sign
                    * (action_value - node_value)
                    for action_value in action_values
                ),
            )
            batch._add(
                batch.strategy,
                key,
                tuple(chance_reach * own_reach * probability for probability in strategy),
            )
            batch.visits[key] = batch.visits.get(key, 0) + 1
        return node_value


class CFRTrainer(RegretMinimizationTrainer):
    """Backward-compatible Vanilla CFR facade over the composable trainer."""

    def __init__(self, game: ExtensiveFormGame[State]) -> None:
        super().__init__(
            game,
            algorithm_id="vanilla_cfr",
            traversal_policy=FullTreeTraversal(),
            regret_update_policy=VanillaRegretUpdate(),
            average_strategy_policy=UniformAverageStrategy(),
            seed=None,
        )


class RootChanceSamplingTraversal:
    """Compatibility traversal that samples only the initial chance event."""

    policy_id = "root_chance_sampling"
    update_schedule = "alternating_players"

    def __init__(self, *, seed: int) -> None:
        self._rng = random.Random(seed)

    def run_iteration(
        self, trainer: RegretMinimizationTrainer, root: State, iteration: int
    ) -> None:
        outcomes = trainer.game.chance_outcomes(root)
        total_probability = fsum(probability for _, probability in outcomes)
        if (
            trainer.game.current_player(root) is not None
            or not outcomes
            or len({action for action, _ in outcomes}) != len(outcomes)
            or any(
                not isfinite(probability) or probability < 0
                for _, probability in outcomes
            )
            or abs(total_probability - 1.0) > 1e-9
        ):
            raise ValueError(
                "chance-sampling CFR requires a valid chance node at the root"
            )
        for update_player in (0, 1):
            selected = _sample_weighted(self._rng, outcomes)
            sampled_state = trainer.game.next_state(root, selected)
            batch = _CFRBatch()
            trainer._traverse_full_tree(
                sampled_state,
                1.0,
                1.0,
                1.0,
                update_player=update_player,
                batch=batch,
            )
            trainer._apply_batch(batch, iteration=iteration)


def _sample_weighted(
    rng: random.Random, weighted_actions: tuple[tuple[Action, float], ...]
) -> Action:
    target = rng.random()
    cumulative = 0.0
    for action, probability in weighted_actions:
        cumulative += probability
        if target <= cumulative:
            return action
    return weighted_actions[-1][0]


class ExternalSamplingTraversal:
    """External-sampling MCCFR for chance nodes anywhere in a sequential tree.

    On each player update, all actions of that player are traversed while chance
    and opponent actions are sampled from their current distributions. The
    simple-average policy is accumulated at opponent nodes, matching the
    standard two-player external-sampling algorithm.
    """

    policy_id = "external_sampling"
    update_schedule = "alternating_players"

    def __init__(self, *, seed: int) -> None:
        self._rng = random.Random(seed)

    def run_iteration(
        self, trainer: RegretMinimizationTrainer, root: State, iteration: int
    ) -> None:
        self._traverse(
            trainer,
            root,
            update_player=0,
            sampled_opponent_actions={},
            iteration=iteration,
        )
        self._traverse(
            trainer,
            root,
            update_player=1,
            sampled_opponent_actions={},
            iteration=iteration,
        )

    def _traverse(
        self,
        trainer: RegretMinimizationTrainer,
        state: State,
        *,
        update_player: int,
        sampled_opponent_actions: dict[tuple[int, InformationSet], Action],
        iteration: int,
    ) -> float:
        if trainer.game.is_terminal(state):
            utility = trainer.game.utility_player_zero(state)
            if not isfinite(utility):
                raise ValueError("terminal CFR utility must be finite")
            return utility if update_player == 0 else -utility

        player = trainer.game.current_player(state)
        if player is None:
            outcomes = trainer.game.chance_outcomes(state)
            total_probability = fsum(probability for _, probability in outcomes)
            if (
                not outcomes
                or len({action for action, _ in outcomes}) != len(outcomes)
                or any(
                    not isfinite(probability) or probability < 0
                    for _, probability in outcomes
                )
                or abs(total_probability - 1.0) > 1e-9
            ):
                raise ValueError(
                    "chance outcomes must be finite, nonnegative, nonempty, and sum to one"
                )
            selected = _sample_weighted(self._rng, outcomes)
            return self._traverse(
                trainer,
                trainer.game.next_state(state, selected),
                update_player=update_player,
                sampled_opponent_actions=sampled_opponent_actions,
                iteration=iteration,
            )
        if player not in (0, 1):
            raise ValueError("MCCFR current_player must be 0, 1, or None for chance")

        actions = trainer.game.legal_actions(state)
        information_set = trainer.game.information_set(state)
        node = trainer._node(player, information_set, actions)
        node.visits += 1
        strategy = node.strategy()
        if player != update_player:
            for index, probability in enumerate(strategy):
                node.strategy_sum[index] = trainer.average_strategy_policy.apply(
                    node.strategy_sum[index], probability, iteration=iteration
                )
            sample_key = (player, information_set)
            if sample_key in sampled_opponent_actions:
                selected = sampled_opponent_actions[sample_key]
            else:
                selected = _sample_weighted(self._rng, tuple(zip(actions, strategy)))
                sampled_opponent_actions[sample_key] = selected
            return self._traverse(
                trainer,
                trainer.game.next_state(state, selected),
                update_player=update_player,
                sampled_opponent_actions=sampled_opponent_actions,
                iteration=iteration,
            )

        action_values = [
            self._traverse(
                trainer,
                trainer.game.next_state(state, action),
                update_player=update_player,
                sampled_opponent_actions=sampled_opponent_actions,
                iteration=iteration,
            )
            for action in actions
        ]
        node_value = sum(
            probability * value for probability, value in zip(strategy, action_values)
        )
        for index, action_value in enumerate(action_values):
            node.regrets[index] = trainer.regret_update_policy.apply(
                node.regrets[index], action_value - node_value, iteration=iteration
            )
        return node_value


class ChanceSamplingCFRTrainer(RegretMinimizationTrainer):
    """Backward-compatible root-chance-sampling Vanilla CFR facade."""

    def __init__(self, game: ExtensiveFormGame[State], *, seed: int = 0) -> None:
        super().__init__(
            game,
            algorithm_id="root_chance_sampling_cfr",
            traversal_policy=RootChanceSamplingTraversal(seed=seed),
            regret_update_policy=VanillaRegretUpdate(),
            average_strategy_policy=UniformAverageStrategy(),
            seed=seed,
        )


class ExternalSamplingCFRTrainer(RegretMinimizationTrainer):
    """Backward-compatible external-sampling MCCFR facade."""

    def __init__(self, game: ExtensiveFormGame[State], *, seed: int = 0) -> None:
        super().__init__(
            game,
            algorithm_id="external_sampling_mccfr",
            traversal_policy=ExternalSamplingTraversal(seed=seed),
            regret_update_policy=VanillaRegretUpdate(),
            average_strategy_policy=UniformAverageStrategy(),
            seed=seed,
        )


class CFRPlusTrainer(RegretMinimizationTrainer):
    """Full-tree CFR+ using RM+ and linear average-strategy weighting."""

    def __init__(self, game: ExtensiveFormGame[State]) -> None:
        super().__init__(
            game,
            algorithm_id="cfr_plus",
            traversal_policy=FullTreeTraversal(),
            regret_update_policy=RegretMatchingPlusUpdate(),
            average_strategy_policy=LinearAverageStrategy(),
            seed=None,
        )


class DCFRTrainer(RegretMinimizationTrainer):
    """Full-tree discounted CFR with explicit alpha, beta, and gamma."""

    def __init__(
        self,
        game: ExtensiveFormGame[State],
        *,
        alpha: float = 1.5,
        beta: float = 0.0,
        gamma: float = 2.0,
    ) -> None:
        if not isfinite(gamma) or gamma < 0:
            raise ValueError("DCFR gamma must be finite and nonnegative")
        super().__init__(
            game,
            algorithm_id="dcfr",
            traversal_policy=FullTreeTraversal(),
            regret_update_policy=DiscountedRegretUpdate(alpha=alpha, beta=beta),
            average_strategy_policy=DiscountedAverageStrategy(gamma=gamma),
            seed=None,
        )


def create_regret_minimization_trainer(
    game: ExtensiveFormGame[State],
    algorithm_id: str,
    *,
    parameters: Mapping[str, float] | None = None,
    seed: int = 0,
) -> RegretMinimizationTrainer:
    """Build a validated composition from the public algorithm registry."""

    supplied = dict(parameters or {})
    if any(not isinstance(value, (int, float)) for value in supplied.values()):
        raise ValueError("algorithm parameters must be numeric")
    if any(not isfinite(float(value)) for value in supplied.values()):
        raise ValueError("algorithm parameters must be finite")
    if algorithm_id == "vanilla_cfr":
        if supplied:
            raise ValueError("vanilla_cfr does not accept algorithm parameters")
        return CFRTrainer(game)
    if algorithm_id == "cfr_plus":
        if supplied:
            raise ValueError("cfr_plus does not accept algorithm parameters")
        return CFRPlusTrainer(game)
    if algorithm_id == "dcfr":
        unknown = set(supplied) - {"alpha", "beta", "gamma"}
        if unknown:
            raise ValueError(f"unknown DCFR parameters: {sorted(unknown)!r}")
        return DCFRTrainer(
            game,
            alpha=float(supplied.get("alpha", 1.5)),
            beta=float(supplied.get("beta", 0.0)),
            gamma=float(supplied.get("gamma", 2.0)),
        )
    if algorithm_id == "external_sampling_mccfr":
        if supplied:
            raise ValueError(
                "external_sampling_mccfr does not accept algorithm parameters"
            )
        if not isinstance(seed, int) or isinstance(seed, bool):
            raise ValueError("external-sampling seed must be an integer")
        return ExternalSamplingCFRTrainer(game, seed=seed)
    raise ValueError(f"unknown regret-minimization algorithm ID: {algorithm_id!r}")


@dataclass(frozen=True, slots=True)
class CFRThresholds:
    min_iterations: int = 10_000
    min_information_sets: int = 1
    min_visits_per_information_set: int = 1
    max_average_positive_regret: float = 0.01
    max_exploitability: float = 0.01
    probability_tolerance: float = 1e-9

    def __post_init__(self) -> None:
        if self.min_iterations <= 0 or self.min_information_sets <= 0:
            raise ValueError("CFR minimums must be positive")
        if self.min_visits_per_information_set <= 0:
            raise ValueError("CFR visit minimum must be positive")
        if (
            not isfinite(self.max_average_positive_regret)
            or not isfinite(self.max_exploitability)
            or self.max_average_positive_regret < 0
            or self.max_exploitability < 0
        ):
            raise ValueError("CFR error thresholds cannot be negative")
        if not isfinite(self.probability_tolerance) or self.probability_tolerance <= 0:
            raise ValueError("CFR probability tolerance must be finite and positive")


@dataclass(frozen=True, slots=True)
class CFRGameProperties:
    """Explicit domain assumptions required by this CFR certification path."""

    players: int
    finite: bool
    zero_sum_or_constant_sum: bool
    perfect_recall: bool

    @property
    def supported(self) -> bool:
        return (
            self.players == 2
            and self.finite
            and self.zero_sum_or_constant_sum
            and self.perfect_recall
        )


@dataclass(frozen=True, slots=True)
class EquilibriumEvaluation:
    """Independent two-player deviation gains with unambiguous metric names."""

    player_0_deviation_gain: float
    player_1_deviation_gain: float

    @property
    def nash_conv(self) -> float:
        return self.player_0_deviation_gain + self.player_1_deviation_gain

    @property
    def exploitability(self) -> float:
        return self.nash_conv / 2

    @property
    def maximum_unilateral_deviation_gain(self) -> float:
        return max(self.player_0_deviation_gain, self.player_1_deviation_gain)

    def to_report(self) -> dict[str, float]:
        """Return the versioned cross-project metric vocabulary."""

        return {
            "nash_conv": self.nash_conv,
            "exploitability": self.exploitability,
            "player_0_deviation_gain": self.player_0_deviation_gain,
            "player_1_deviation_gain": self.player_1_deviation_gain,
            "maximum_unilateral_deviation_gain": (
                self.maximum_unilateral_deviation_gain
            ),
        }


@dataclass(frozen=True, slots=True)
class CFRGateReport:
    passed: bool
    failures: tuple[str, ...]
    iterations: int
    information_sets: int
    minimum_visits: int
    maximum_average_positive_regret: float
    evaluation: EquilibriumEvaluation | None

    @property
    def nash_conv(self) -> float | None:
        return None if self.evaluation is None else self.evaluation.nash_conv

    @property
    def exploitability(self) -> float | None:
        return None if self.evaluation is None else self.evaluation.exploitability

    @property
    def player_0_deviation_gain(self) -> float | None:
        return (
            None
            if self.evaluation is None
            else self.evaluation.player_0_deviation_gain
        )

    @property
    def player_1_deviation_gain(self) -> float | None:
        return (
            None
            if self.evaluation is None
            else self.evaluation.player_1_deviation_gain
        )

    @property
    def maximum_unilateral_deviation_gain(self) -> float | None:
        return (
            None
            if self.evaluation is None
            else self.evaluation.maximum_unilateral_deviation_gain
        )

    def require_passed(self) -> None:
        """Prevent a policy from being activated when any evidence gate failed."""

        if not self.passed:
            raise CFRGateFailure(self.failures)


class CFRGateFailure(RuntimeError):
    def __init__(self, failures: tuple[str, ...]) -> None:
        self.failures = failures
        super().__init__("CFR policy failed certification: " + ", ".join(failures))


@dataclass(slots=True)
class CFRCertificationGate:
    """Uniform promotion gate: training diagnostics plus an independent oracle."""

    thresholds: CFRThresholds = field(default_factory=CFRThresholds)

    def evaluate(
        self,
        result: CFRResult,
        *,
        evaluation: EquilibriumEvaluation | None,
        required_information_sets: frozenset[
            tuple[int, InformationSet]
        ] = frozenset(),
        exact_information_sets: bool = False,
        game_properties: CFRGameProperties | None = None,
    ) -> CFRGateReport:
        failures: list[str] = []
        policy_keys = set(result.policy)
        visit_keys = set(result.information_set_visits)
        visit_values = tuple(result.information_set_visits.values())
        visits_valid = (
            policy_keys == visit_keys
            and all(
                isinstance(value, int) and not isinstance(value, bool) and value >= 0
                for value in visit_values
            )
        )
        minimum_visits = min(visit_values, default=0) if visits_valid else 0
        regrets = tuple(result.average_positive_regret)
        regrets_valid = (
            len(regrets) == 2
            and all(isfinite(value) and value >= 0 for value in regrets)
        )
        maximum_regret = max(regrets, default=float("nan"))
        if game_properties is None:
            failures.append("game_properties_required")
        elif not game_properties.supported:
            failures.append("unsupported_game_properties")
        if result.iterations < self.thresholds.min_iterations:
            failures.append("insufficient_iterations")
        if result.information_set_count < self.thresholds.min_information_sets:
            failures.append("insufficient_information_sets")
        if not required_information_sets.issubset(result.policy):
            failures.append("missing_required_information_sets")
        if exact_information_sets and policy_keys != set(required_information_sets):
            failures.append("unexpected_information_sets")
        if not visits_valid:
            failures.append("invalid_information_set_visits")
        if minimum_visits < self.thresholds.min_visits_per_information_set:
            failures.append("insufficient_information_set_visits")
        if not regrets_valid:
            failures.append("invalid_regret_diagnostic")
        elif maximum_regret > self.thresholds.max_average_positive_regret:
            failures.append("average_positive_regret_above_threshold")
        gains = (
            ()
            if evaluation is None
            else (
                evaluation.player_0_deviation_gain,
                evaluation.player_1_deviation_gain,
            )
        )
        if evaluation is None or any(not isfinite(gain) for gain in gains):
            failures.append("independent_exploitability_required")
        elif any(gain < -self.thresholds.probability_tolerance for gain in gains):
            failures.append("invalid_exploitability")
        elif evaluation.exploitability > self.thresholds.max_exploitability:
            failures.append("exploitability_above_threshold")
        for distribution in result.policy.values():
            values = tuple(distribution.values())
            if (
                not values
                or any(not isfinite(value) or value < 0 for value in values)
                or abs(sum(values) - 1.0) > self.thresholds.probability_tolerance
            ):
                failures.append("invalid_policy_distribution")
                break
        return CFRGateReport(
            passed=not failures,
            failures=tuple(failures),
            iterations=result.iterations,
            information_sets=result.information_set_count,
            minimum_visits=minimum_visits,
            maximum_average_positive_regret=maximum_regret,
            evaluation=evaluation,
        )
