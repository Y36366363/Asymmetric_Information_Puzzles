"""Independent full-tree oracle for small perfect-recall games."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from functools import lru_cache
from math import fsum, isfinite
from typing import Generic, Hashable, Mapping, TypeVar

from aip.core.cfr import ExtensiveFormGame
from aip.core.evaluation import (
    ActionValueReport,
    StrategyProfile,
    strategy_profile_fingerprint,
)


State = TypeVar("State", bound=Hashable)
Action = Hashable
InformationSet = Hashable


@dataclass(frozen=True, slots=True)
class FullTreeGameAudit:
    """Structural evidence collected without consulting a trained strategy."""

    histories: int
    terminal_histories: int
    chance_histories: int
    decision_histories: int
    information_sets: int
    maximum_depth: int
    failures: tuple[str, ...]

    @property
    def passed(self) -> bool:
        return not self.failures

    def to_artifact(self) -> dict[str, object]:
        return {
            "histories": self.histories,
            "terminal_histories": self.terminal_histories,
            "chance_histories": self.chance_histories,
            "decision_histories": self.decision_histories,
            "information_sets": self.information_sets,
            "maximum_depth": self.maximum_depth,
            "perfect_recall": "imperfect_recall" not in self.failures,
            "passed": self.passed,
            "failures": list(self.failures),
        }


def audit_small_extensive_form(
    game: ExtensiveFormGame[State], *, maximum_histories: int = 1_000_000
) -> FullTreeGameAudit:
    """Exhaust a game and verify the assumptions required by the exact oracle.

    Perfect recall is checked by requiring every member of an information set to
    have the same sequence of that player's earlier information sets and actions.
    This catches absent-minded or forgotten-action adapters before certification.
    """

    if maximum_histories <= 0:
        raise ValueError("maximum histories must be positive")
    counts = {"histories": 0, "terminal": 0, "chance": 0, "decision": 0}
    maximum_depth = 0
    failures: set[str] = set()
    action_tables: dict[tuple[int, InformationSet], tuple[Action, ...]] = {}
    recall_sequences: dict[
        tuple[int, InformationSet], tuple[tuple[InformationSet, Action], ...]
    ] = {}

    def traverse(
        state: State,
        depth: int,
        own_histories: tuple[
            tuple[tuple[InformationSet, Action], ...],
            tuple[tuple[InformationSet, Action], ...],
        ],
        ancestors: frozenset[State],
    ) -> None:
        nonlocal maximum_depth
        counts["histories"] += 1
        if counts["histories"] > maximum_histories:
            raise OverflowError(
                f"complete tree exceeds {maximum_histories} histories"
            )
        maximum_depth = max(maximum_depth, depth)
        try:
            if state in ancestors:
                failures.add("cyclic_game_graph")
                return
            next_ancestors = ancestors | {state}
        except TypeError as error:
            raise TypeError("full-tree evaluator requires hashable states") from error

        if game.is_terminal(state):
            counts["terminal"] += 1
            utility = game.utility_player_zero(state)
            if not isfinite(utility):
                failures.add("nonfinite_terminal_utility")
            return

        player = game.current_player(state)
        if player is None:
            counts["chance"] += 1
            outcomes = game.chance_outcomes(state)
            probabilities = tuple(probability for _, probability in outcomes)
            if (
                not outcomes
                or len({action for action, _ in outcomes}) != len(outcomes)
                or any(
                    not isfinite(probability) or probability < 0
                    for probability in probabilities
                )
                or abs(fsum(probabilities) - 1.0) > 1e-9
            ):
                failures.add("invalid_chance_distribution")
                return
            for action, _ in outcomes:
                traverse(
                    game.next_state(state, action),
                    depth + 1,
                    own_histories,
                    next_ancestors,
                )
            return

        counts["decision"] += 1
        if player not in (0, 1):
            failures.add("invalid_current_player")
            return
        actions = game.legal_actions(state)
        if not actions:
            failures.add("empty_legal_actions")
            return
        if len(set(actions)) != len(actions):
            failures.add("duplicate_legal_actions")
            return
        information_set = game.information_set(state)
        key = (player, information_set)
        previous_actions = action_tables.setdefault(key, actions)
        if previous_actions != actions:
            failures.add("inconsistent_information_set_actions")
            return
        previous_recall = recall_sequences.setdefault(key, own_histories[player])
        if previous_recall != own_histories[player]:
            failures.add("imperfect_recall")
        for action in actions:
            updated = list(own_histories)
            updated[player] = own_histories[player] + ((information_set, action),)
            traverse(
                game.next_state(state, action),
                depth + 1,
                (updated[0], updated[1]),
                next_ancestors,
            )

    traverse(game.initial_state(), 0, ((), ()), frozenset())
    return FullTreeGameAudit(
        histories=counts["histories"],
        terminal_histories=counts["terminal"],
        chance_histories=counts["chance"],
        decision_histories=counts["decision"],
        information_sets=len(action_tables),
        maximum_depth=maximum_depth,
        failures=tuple(sorted(failures)),
    )


class FullTreeBestResponseEvaluator(Generic[State]):
    """Exact evaluator shared by small two-player zero-sum game adapters.

    The implementation enumerates chance and opponent play and optimizes one
    deterministic action per hero information set. It never reads trainer
    regrets, visits, or convergence diagnostics.
    """

    def __init__(
        self,
        game: ExtensiveFormGame[State],
        *,
        evaluator_id: str,
        maximum_histories: int = 1_000_000,
    ) -> None:
        if not evaluator_id:
            raise ValueError("evaluator id must be nonempty")
        self.game = game
        self.evaluator_id = evaluator_id
        self.maximum_histories = maximum_histories
        self.audit = audit_small_extensive_form(
            game, maximum_histories=maximum_histories
        )
        if not self.audit.passed:
            raise ValueError(
                "game failed independent full-tree audit: "
                + ", ".join(self.audit.failures)
            )
        self._action_tables = self._collect_action_tables()
        self._value_cache: dict[str, float] = {}
        self._response_cache: dict[
            tuple[str, int],
            tuple[float, dict[tuple[int, InformationSet], dict[Action, float]]],
        ] = {}

    def _collect_action_tables(
        self,
    ) -> dict[tuple[int, InformationSet], tuple[Action, ...]]:
        tables: dict[tuple[int, InformationSet], tuple[Action, ...]] = {}
        histories = 0

        def traverse(state: State) -> None:
            nonlocal histories
            histories += 1
            if histories > self.maximum_histories:
                raise OverflowError(
                    f"complete tree exceeds {self.maximum_histories} histories"
                )
            if self.game.is_terminal(state):
                return
            player = self.game.current_player(state)
            if player is None:
                for action, _ in self.game.chance_outcomes(state):
                    traverse(self.game.next_state(state, action))
                return
            actions = self.game.legal_actions(state)
            tables.setdefault((player, self.game.information_set(state)), actions)
            for action in actions:
                traverse(self.game.next_state(state, action))

        traverse(self.game.initial_state())
        return tables

    def _validate_profile(self, profile: StrategyProfile) -> None:
        if set(profile) != set(self._action_tables):
            raise ValueError(
                "strategy profile must cover exactly the audited information sets"
            )
        for key, actions in self._action_tables.items():
            distribution = profile[key]
            if set(distribution) != set(actions):
                raise ValueError(
                    f"strategy actions do not match information set {key!r}"
                )
            probabilities = tuple(float(distribution[action]) for action in actions)
            if (
                any(not isfinite(value) or value < 0 for value in probabilities)
                or abs(fsum(probabilities) - 1.0) > 1e-9
            ):
                raise ValueError(
                    "strategy probabilities must be finite, nonnegative, and sum to one"
                )

    def expected_value(self, profile: StrategyProfile) -> float:
        self._validate_profile(profile)
        fingerprint = strategy_profile_fingerprint(profile)
        cached = self._value_cache.get(fingerprint)
        if cached is not None:
            return cached

        @lru_cache(maxsize=None)
        def value(state: State) -> float:
            if self.game.is_terminal(state):
                return self.game.utility_player_zero(state)
            player = self.game.current_player(state)
            if player is None:
                return fsum(
                    probability * value(self.game.next_state(state, action))
                    for action, probability in self.game.chance_outcomes(state)
                )
            actions = self.game.legal_actions(state)
            distribution = profile[(player, self.game.information_set(state))]
            return fsum(
                float(distribution[action])
                * value(self.game.next_state(state, action))
                for action in actions
            )

        result = value(self.game.initial_state())
        self._value_cache[fingerprint] = result
        return result

    def _best_response(
        self, profile: StrategyProfile, hero: int
    ) -> tuple[float, dict[tuple[int, InformationSet], dict[Action, float]]]:
        if hero not in (0, 1):
            raise ValueError("best-response player must be zero or one")
        self._validate_profile(profile)
        cache_key = (strategy_profile_fingerprint(profile), hero)
        cached = self._response_cache.get(cache_key)
        if cached is not None:
            return cached
        members: dict[InformationSet, dict[State, float]] = defaultdict(
            lambda: defaultdict(float)
        )

        def collect(state: State, counterfactual_reach: float) -> None:
            if self.game.is_terminal(state):
                return
            player = self.game.current_player(state)
            if player is None:
                for action, probability in self.game.chance_outcomes(state):
                    collect(
                        self.game.next_state(state, action),
                        counterfactual_reach * probability,
                    )
                return
            information_set = self.game.information_set(state)
            actions = self.game.legal_actions(state)
            if player == hero:
                members[information_set][state] += counterfactual_reach
                for action in actions:
                    collect(self.game.next_state(state, action), counterfactual_reach)
                return
            distribution = profile[(player, information_set)]
            for action in actions:
                collect(
                    self.game.next_state(state, action),
                    counterfactual_reach * float(distribution[action]),
                )

        collect(self.game.initial_state(), 1.0)
        chosen: dict[InformationSet, Action] = {}

        @lru_cache(maxsize=None)
        def value(state: State) -> float:
            if self.game.is_terminal(state):
                utility = self.game.utility_player_zero(state)
                return utility if hero == 0 else -utility
            player = self.game.current_player(state)
            if player is None:
                return fsum(
                    probability * value(self.game.next_state(state, action))
                    for action, probability in self.game.chance_outcomes(state)
                )
            information_set = self.game.information_set(state)
            actions = self.game.legal_actions(state)
            if player != hero:
                distribution = profile[(player, information_set)]
                return fsum(
                    float(distribution[action])
                    * value(self.game.next_state(state, action))
                    for action in actions
                )
            if information_set not in chosen:
                chosen[information_set] = max(
                    actions,
                    key=lambda action: fsum(
                        reach * value(self.game.next_state(member, action))
                        for member, reach in members[information_set].items()
                    ),
                )
            return value(self.game.next_state(state, chosen[information_set]))

        root_value = value(self.game.initial_state())
        action_values: dict[tuple[int, InformationSet], dict[Action, float]] = {}
        for information_set, states in members.items():
            actions = self._action_tables[(hero, information_set)]
            reach = fsum(states.values())
            action_values[(hero, information_set)] = {
                action: (
                    fsum(
                        weight * value(self.game.next_state(state, action))
                        for state, weight in states.items()
                    )
                    / reach
                    if reach > 0
                    else 0.0
                )
                for action in actions
            }
        result = (root_value, action_values)
        self._response_cache[cache_key] = result
        return result

    def best_response(self, profile: StrategyProfile, player: int) -> float:
        return self._best_response(profile, player)[0]

    def nash_conv(self, profile: StrategyProfile) -> float:
        return self.best_response(profile, 0) + self.best_response(profile, 1)

    def exploitability(self, profile: StrategyProfile) -> float:
        return self.nash_conv(profile) / 2.0

    def action_values(self, profile: StrategyProfile) -> ActionValueReport:
        combined = {
            **self._best_response(profile, 0)[1],
            **self._best_response(profile, 1)[1],
        }
        return {key: dict(values) for key, values in combined.items()}
