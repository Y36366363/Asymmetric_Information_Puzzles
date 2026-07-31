from __future__ import annotations

from dataclasses import dataclass

from aip.core.information import InformationSet

HatWorld = tuple[str, ...]


@dataclass(frozen=True, slots=True)
class HatRound:
    number: int
    possible_world_count: int
    knowers: tuple[int, ...]
    information_sets: tuple[InformationSet[HatWorld], ...]
    public_event: str


@dataclass(frozen=True, slots=True)
class HatSolution:
    actual_world: HatWorld
    target_color: str
    rounds: tuple[HatRound, ...]

    @property
    def discovery_round(self) -> int | None:
        for round_ in self.rounds:
            if round_.knowers:
                return round_.number
        return None
