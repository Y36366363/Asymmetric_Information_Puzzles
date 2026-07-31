"""Minimax and interval-robust solver for sequential bean taking."""

from __future__ import annotations

from functools import lru_cache

from aip.core.information import InformationSet, Observation
from aip.puzzles.beans.models import (
    ActionRisk,
    BeanRules,
    BeanSolution,
    BeanState,
    CountAnalysis,
)


class BeanSolver:
    """Protect player 1 against a worst-case coalition of all other players.

    Player 1 chooses an initial action before the exact pile size is revealed,
    knowing only an inclusive interval. Later choices may use the visible
    remaining pile. Other players are treated adversarially, which deliberately
    implements extreme-risk avoidance rather than an average-case equilibrium.
    """

    def __init__(self, rules: BeanRules | None = None) -> None:
        self.rules = rules or BeanRules()

    def solve(self, minimum_beans: int, maximum_beans: int) -> BeanSolution:
        if minimum_beans < 1 or maximum_beans < minimum_beans:
            raise ValueError("bean interval must satisfy 1 <= minimum <= maximum")

        counts = tuple(range(minimum_beans, maximum_beans + 1))
        states = tuple(BeanState(beans, 0) for beans in counts)
        info = InformationSet(
            key=f"beans-{minimum_beans}-{maximum_beans}",
            player_id=1,
            possible_states=states,
            observations=(
                Observation("bean_range", (minimum_beans, maximum_beans), is_public=False),
            ),
        )
        common_actions = tuple(
            range(self.rules.min_take, min(self.rules.max_take, minimum_beans) + 1)
        )
        analyses = tuple(
            CountAnalysis(beans, self._safe_initial_actions(beans)) for beans in counts
        )
        risks = tuple(
            ActionRisk(
                action,
                tuple(beans for beans in counts if self._initial_action_is_safe(beans, action)),
                tuple(beans for beans in counts if not self._initial_action_is_safe(beans, action)),
            )
            for action in common_actions
        )
        robust = tuple(risk.action for risk in risks if risk.worst_case_safe)
        # Lexicographic risk policy: first minimise the number of losing worlds,
        # then take fewer beans to preserve future flexibility.
        recommended = min(risks, key=lambda risk: (len(risk.unsafe_counts), risk.action)).action
        return BeanSolution(
            minimum_beans,
            maximum_beans,
            self.rules,
            info,
            analyses,
            risks,
            robust,
            recommended,
        )

    def _safe_initial_actions(self, beans: int) -> tuple[int, ...]:
        return tuple(
            action
            for action in self._legal_actions(beans)
            if self._initial_action_is_safe(beans, action)
        )

    def _initial_action_is_safe(self, beans: int, action: int) -> bool:
        if action not in self._legal_actions(beans):
            return False
        if action == beans:
            return False  # player 1 takes the final bean and loses
        return self._hero_can_avoid_loss(beans - action, 1)

    @lru_cache(maxsize=None)
    def _hero_can_avoid_loss(self, beans: int, turn: int) -> bool:
        outcomes: list[bool] = []
        for action in self._legal_actions(beans):
            if action == beans:
                outcomes.append(turn != 0)
            else:
                outcomes.append(
                    self._hero_can_avoid_loss(
                        beans - action, (turn + 1) % self.rules.player_count
                    )
                )
        # Hero chooses any safe continuation; adversaries need only one line
        # that makes hero lose, hence every adversarial action must be safe.
        return any(outcomes) if turn == 0 else all(outcomes)

    def _legal_actions(self, beans: int) -> tuple[int, ...]:
        return tuple(
            action
            for action in range(self.rules.min_take, self.rules.max_take + 1)
            if action <= beans
        )
