from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class InitialLight(str, Enum):
    OFF = "off"
    UNKNOWN = "unknown"


class DeclarationGoal(str, Enum):
    VISITED = "visited"
    TURNED_ON = "turned-on"


@dataclass(frozen=True, slots=True)
class PrisonerPlan:
    prisoner_count: int
    counter_id: int
    initial_light: InitialLight
    goal: DeclarationGoal
    signals_per_non_counter: int
    declaration_count: int
    almost_sure: bool
    finite_day_guarantee: bool
    safety_argument: str


@dataclass(frozen=True, slots=True)
class VisitRecord:
    day: int
    prisoner_id: int
    light_before: bool
    action: str
    light_after: bool
    counter_value: int
    declared: bool


@dataclass(frozen=True, slots=True)
class SimulationResult:
    plan: PrisonerPlan
    completed: bool
    declaration_day: int | None
    declaration_was_safe: bool | None
    visited_prisoners: tuple[int, ...]
    signal_counts: tuple[int, ...]
    records: tuple[VisitRecord, ...]
