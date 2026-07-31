"""Information-set primitives for imperfect-information puzzles.

The pirate puzzle is a perfect-information game and therefore does not need
these types directly.  Hat, bean, and future puzzle modules can use them to
group states that a player cannot distinguish from their observations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Generic, Hashable, Mapping, TypeVar

StateT = TypeVar("StateT")
PlayerId = Hashable


@dataclass(frozen=True, slots=True)
class Observation:
    """One fact observed by a player or publicly by all players."""

    name: str
    value: object
    is_public: bool = False
    timestamp: int | None = None


@dataclass(frozen=True, slots=True)
class InformationSet(Generic[StateT]):
    """States a player considers possible at one decision point.

    ``possible_states`` supports explicit finite puzzles. ``beliefs`` is an
    optional probability distribution for later Bayesian extensions. Public
    history is stored separately because public announcements are what drive
    common-knowledge updates in puzzles such as the coloured-hat village.
    """

    key: str
    player_id: PlayerId
    possible_states: tuple[StateT, ...]
    observations: tuple[Observation, ...] = ()
    public_history: tuple[Observation, ...] = ()
    beliefs: Mapping[StateT, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.possible_states:
            raise ValueError("an information set must contain at least one state")
        if self.beliefs:
            unknown = set(self.beliefs).difference(self.possible_states)
            if unknown:
                raise ValueError("beliefs contain states outside possible_states")
            total = sum(self.beliefs.values())
            if abs(total - 1.0) > 1e-9:
                raise ValueError("belief probabilities must sum to 1")
            if any(probability < 0 for probability in self.beliefs.values()):
                raise ValueError("belief probabilities cannot be negative")

    def update(
        self,
        observation: Observation,
        compatible: Callable[[StateT, Observation], bool],
    ) -> "InformationSet[StateT]":
        """Return the posterior information set after a deterministic fact.

        ``compatible(state, observation)`` keeps domain logic out of the core.
        """

        remaining = tuple(
            state for state in self.possible_states if compatible(state, observation)
        )
        if not remaining:
            raise ValueError("observation eliminates every possible state")
        return InformationSet(
            key=f"{self.key}@{len(self.observations) + len(self.public_history) + 1}",
            player_id=self.player_id,
            possible_states=remaining,
            observations=self.observations + (() if observation.is_public else (observation,)),
            public_history=self.public_history + ((observation,) if observation.is_public else ()),
        )
