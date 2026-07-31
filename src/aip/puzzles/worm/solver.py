"""Shortest guaranteed search for a worm forced to move every turn."""

from __future__ import annotations

from collections import deque

from aip.core.information import InformationSet, Observation
from aip.puzzles.worm.models import WormSolution, WormStep


class WormSolver:
    """Find a shortest open-loop checking sequence by belief-state search.

    If a check misses, the worm must move exactly one edge to an adjacent hole.
    Because a miss is the only observation, a strategy is a sequence: the next
    check is needed only on the branch where every earlier check missed.
    """

    def solve(self, hole_count: int = 5) -> WormSolution:
        if hole_count < 1:
            raise ValueError("hole_count must be at least 1")
        initial = frozenset(range(1, hole_count + 1))
        checks = self._shortest_sequence(initial, hole_count)
        belief = initial
        public_history: tuple[Observation, ...] = ()
        steps: list[WormStep] = []

        for number, checked in enumerate(checks, start=1):
            info = InformationSet(
                key=f"worm-{hole_count}-step-{number}",
                player_id="searcher",
                possible_states=tuple(sorted(belief)),
                public_history=public_history,
            )
            guarantees = belief.issubset({checked})
            after = frozenset() if guarantees else self._after_miss(belief, checked, hole_count)
            steps.append(
                WormStep(number, checked, info, tuple(sorted(after)), guarantees)
            )
            if guarantees:
                break
            miss = Observation(
                "check_result",
                f"worm not in hole {checked}",
                is_public=True,
                timestamp=number,
            )
            public_history = public_history + (miss,)
            belief = after
        return WormSolution(hole_count, checks, tuple(steps))

    def _shortest_sequence(
        self, initial: frozenset[int], hole_count: int
    ) -> tuple[int, ...]:
        queue: deque[tuple[frozenset[int], tuple[int, ...]]] = deque([(initial, ())])
        visited = {initial}
        while queue:
            belief, prefix = queue.popleft()
            for checked in range(1, hole_count + 1):
                candidate = prefix + (checked,)
                if belief.issubset({checked}):
                    return candidate
                after = self._after_miss(belief, checked, hole_count)
                if after not in visited:
                    visited.add(after)
                    queue.append((after, candidate))
        raise RuntimeError("no guaranteed capture sequence exists")

    @staticmethod
    def _after_miss(
        belief: frozenset[int], checked: int, hole_count: int
    ) -> frozenset[int]:
        destinations: set[int] = set()
        for hole in belief.difference({checked}):
            if hole > 1:
                destinations.add(hole - 1)
            if hole < hole_count:
                destinations.add(hole + 1)
        return frozenset(destinations)
