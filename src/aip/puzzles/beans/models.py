from __future__ import annotations

from dataclasses import dataclass

from aip.core.information import InformationSet


@dataclass(frozen=True, slots=True)
class BeanRules:
    player_count: int = 5
    min_take: int = 1
    max_take: int = 3
    last_taker_loses: bool = True

    def __post_init__(self) -> None:
        if self.player_count < 2:
            raise ValueError("player_count must be at least 2")
        if self.min_take < 1 or self.max_take < self.min_take:
            raise ValueError("take range must satisfy 1 <= min_take <= max_take")
        if not self.last_taker_loses:
            raise ValueError("only the extreme-risk last-taker-loses rule is supported")


@dataclass(frozen=True, slots=True)
class BeanState:
    beans: int
    turn: int


@dataclass(frozen=True, slots=True)
class CountAnalysis:
    beans: int
    safe_actions: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class ActionRisk:
    action: int
    safe_counts: tuple[int, ...]
    unsafe_counts: tuple[int, ...]

    @property
    def worst_case_safe(self) -> bool:
        return not self.unsafe_counts


@dataclass(frozen=True, slots=True)
class BeanSolution:
    minimum_beans: int
    maximum_beans: int
    rules: BeanRules
    information_set: InformationSet[BeanState]
    analyses: tuple[CountAnalysis, ...]
    action_risks: tuple[ActionRisk, ...]
    robust_actions: tuple[int, ...]
    recommended_action: int

    @property
    def has_zero_risk_action(self) -> bool:
        return bool(self.robust_actions)
