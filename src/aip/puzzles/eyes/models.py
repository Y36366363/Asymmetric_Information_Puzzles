from __future__ import annotations

from dataclasses import dataclass

from aip.core.information import InformationSet


@dataclass(frozen=True, slots=True)
class EyeRules:
    target_color: str = "white"
    other_color: str = "black"
    action_description: str = "die by suicide"
    public_announcement: bool = True

    def __post_init__(self) -> None:
        if not self.target_color or not self.other_color or not self.action_description:
            raise ValueError("eye-colour names and action description must be non-empty")
        if self.target_color == self.other_color:
            raise ValueError("the two eye colours must be distinct")


@dataclass(frozen=True, slots=True)
class EyeWorld:
    target_count: int
    other_count: int


@dataclass(frozen=True, slots=True)
class ReasoningDay:
    day: int
    possible_own_colors: tuple[str, ...]
    information_set: InformationSet[EyeWorld]
    public_event: str
    target_group_knows: bool


@dataclass(frozen=True, slots=True)
class EyeSolution:
    target_count: int
    other_count: int
    rules: EyeRules
    days: tuple[ReasoningDay, ...]
    action_day: int | None
    conclusion: str

    @property
    def target_people_act(self) -> bool:
        return self.action_day is not None
