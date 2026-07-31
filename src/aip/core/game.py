"""Small, dependency-free interfaces for dynamic puzzle solvers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, Iterable, Protocol, TypeVar

StateT = TypeVar("StateT")
ActionT = TypeVar("ActionT")
ResultT = TypeVar("ResultT")


@dataclass(frozen=True, slots=True)
class Transition(Generic[StateT, ActionT]):
    state: StateT
    action: ActionT
    next_state: StateT


class DynamicGame(Protocol[StateT, ActionT]):
    def legal_actions(self, state: StateT) -> Iterable[ActionT]: ...

    def transition(self, state: StateT, action: ActionT) -> StateT: ...

    def is_terminal(self, state: StateT) -> bool: ...


class GameSolver(Protocol[StateT, ResultT]):
    def solve(self, initial_state: StateT) -> ResultT: ...

