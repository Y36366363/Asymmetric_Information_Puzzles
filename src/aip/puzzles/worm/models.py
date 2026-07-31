from __future__ import annotations

from dataclasses import dataclass

from aip.core.information import InformationSet


@dataclass(frozen=True, slots=True)
class WormStep:
    number: int
    checked_hole: int
    information_set: InformationSet[int]
    possible_after_miss_and_move: tuple[int, ...]
    guarantees_capture: bool


@dataclass(frozen=True, slots=True)
class WormSolution:
    hole_count: int
    checks: tuple[int, ...]
    steps: tuple[WormStep, ...]

    @property
    def maximum_checks(self) -> int:
        return len(self.checks)
