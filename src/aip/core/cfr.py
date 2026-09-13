"""Reusable tabular CFR engine and evidence gate for finite two-player games."""

from __future__ import annotations

from dataclasses import dataclass, field
from math import fsum, isfinite
import random
from typing import Hashable, Mapping, Protocol, TypeVar


State = TypeVar("State")
Action = Hashable
InformationSet = Hashable


class CFRGame(Protocol[State]):
    """Adapter boundary for finite, two-player, zero-sum extensive-form games."""

    def initial_state(self) -> State: ...

    def is_terminal(self, state: State) -> bool: ...

    def utility_player_zero(self, state: State) -> float: ...

    def current_player(self, state: State) -> int | None: ...

    def chance_outcomes(self, state: State) -> tuple[tuple[Action, float], ...]: ...

    def legal_actions(self, state: State) -> tuple[Action, ...]: ...

    def information_set(self, state: State) -> InformationSet: ...

    def next_state(self, state: State, action: Action) -> State: ...


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
class CFRResult:
    iterations: int
    policy: Mapping[tuple[int, InformationSet], Mapping[Action, float]]
    information_set_visits: Mapping[tuple[int, InformationSet], int]
    average_positive_regret: tuple[float, float]

    @property
    def information_set_count(self) -> int:
        return len(self.policy)


class CFRTrainer:
    """Batched full-tree vanilla CFR with alternating player updates.

    Each player traversal reads one fixed regret-matching strategy. Regret and
    average-strategy deltas from every chance outcome are committed together
    only after that complete traversal, making deterministic results independent
    of chance and action enumeration order (up to floating-point roundoff).
    """

    def __init__(self, game: CFRGame[State]) -> None:
        self.game = game
        self._nodes: dict[tuple[int, InformationSet], _Node] = {}
        self.iterations = 0

    def train(self, iterations: int) -> CFRResult:
        if iterations <= 0:
            raise ValueError("CFR iterations must be positive")
        root = self.game.initial_state()
        for _ in range(iterations):
            for update_player in (0, 1):
                batch = _CFRBatch()
                self._traverse(
                    root,
                    1.0,
                    1.0,
                    1.0,
                    update_player=update_player,
                    batch=batch,
                )
                self._apply_batch(batch)
            self.iterations += 1
        return self.result()

    def _apply_batch(self, batch: _CFRBatch) -> None:
        for key, deltas in batch.regrets.items():
            node = self._nodes[key]
            for index, delta in enumerate(deltas):
                node.regrets[index] += delta
        for key, deltas in batch.strategy.items():
            node = self._nodes[key]
            for index, delta in enumerate(deltas):
                node.strategy_sum[index] += delta
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

    def _traverse(
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
                * self._traverse(
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
                self._traverse(
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


class ChanceSamplingCFRTrainer(CFRTrainer):
    """CFR variant that samples root chance while traversing every player action."""

    def __init__(self, game: CFRGame[State], *, seed: int = 0) -> None:
        super().__init__(game)
        self._rng = random.Random(seed)

    def train(self, iterations: int) -> CFRResult:
        if iterations <= 0:
            raise ValueError("CFR iterations must be positive")
        root = self.game.initial_state()
        outcomes = self.game.chance_outcomes(root)
        total_probability = sum(probability for _, probability in outcomes)
        if (
            self.game.current_player(root) is not None
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
        for _ in range(iterations):
            for update_player in (0, 1):
                target = self._rng.random()
                cumulative = 0.0
                selected = outcomes[-1][0]
                for action, probability in outcomes:
                    cumulative += probability
                    if target <= cumulative:
                        selected = action
                        break
                sampled_state = self.game.next_state(root, selected)
                batch = _CFRBatch()
                self._traverse(
                    sampled_state,
                    1.0,
                    1.0,
                    1.0,
                    update_player=update_player,
                    batch=batch,
                )
                self._apply_batch(batch)
            self.iterations += 1
        return self.result()


class ExternalSamplingCFRTrainer(CFRTrainer):
    """External-sampling MCCFR for chance nodes anywhere in a sequential tree.

    On each player update, all actions of that player are traversed while chance
    and opponent actions are sampled from their current distributions. The
    simple-average policy is accumulated at opponent nodes, matching the
    standard two-player external-sampling algorithm.
    """

    def __init__(self, game: CFRGame[State], *, seed: int = 0) -> None:
        super().__init__(game)
        self._rng = random.Random(seed)

    def train(self, iterations: int) -> CFRResult:
        if iterations <= 0:
            raise ValueError("MCCFR iterations must be positive")
        root = self.game.initial_state()
        for _ in range(iterations):
            self._traverse_external(root, update_player=0, sampled_opponent_actions={})
            self._traverse_external(root, update_player=1, sampled_opponent_actions={})
            self.iterations += 1
        return self.result()

    def _sample(self, weighted_actions: tuple[tuple[Action, float], ...]) -> Action:
        target = self._rng.random()
        cumulative = 0.0
        for action, probability in weighted_actions:
            cumulative += probability
            if target <= cumulative:
                return action
        return weighted_actions[-1][0]

    def _traverse_external(
        self,
        state: State,
        *,
        update_player: int,
        sampled_opponent_actions: dict[tuple[int, InformationSet], Action],
    ) -> float:
        if self.game.is_terminal(state):
            utility = self.game.utility_player_zero(state)
            if not isfinite(utility):
                raise ValueError("terminal CFR utility must be finite")
            return utility if update_player == 0 else -utility

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
            selected = self._sample(outcomes)
            return self._traverse_external(
                self.game.next_state(state, selected),
                update_player=update_player,
                sampled_opponent_actions=sampled_opponent_actions,
            )
        if player not in (0, 1):
            raise ValueError("MCCFR current_player must be 0, 1, or None for chance")

        actions = self.game.legal_actions(state)
        information_set = self.game.information_set(state)
        node = self._node(player, information_set, actions)
        node.visits += 1
        strategy = node.strategy()
        if player != update_player:
            for index, probability in enumerate(strategy):
                node.strategy_sum[index] += probability
            sample_key = (player, information_set)
            if sample_key in sampled_opponent_actions:
                selected = sampled_opponent_actions[sample_key]
            else:
                selected = self._sample(tuple(zip(actions, strategy)))
                sampled_opponent_actions[sample_key] = selected
            return self._traverse_external(
                self.game.next_state(state, selected),
                update_player=update_player,
                sampled_opponent_actions=sampled_opponent_actions,
            )

        action_values = [
            self._traverse_external(
                self.game.next_state(state, action),
                update_player=update_player,
                sampled_opponent_actions=sampled_opponent_actions,
            )
            for action in actions
        ]
        node_value = sum(
            probability * value for probability, value in zip(strategy, action_values)
        )
        for index, action_value in enumerate(action_values):
            node.regrets[index] += action_value - node_value
        return node_value


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
