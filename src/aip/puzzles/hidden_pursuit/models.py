from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Transport(StrEnum):
    TAXI = "taxi"
    BUS = "bus"


NODE_POSITIONS: dict[int, tuple[int, int]] = {
    1: (8, 14), 2: (28, 9), 3: (50, 8), 4: (72, 12), 5: (91, 20),
    6: (16, 37), 7: (38, 31), 8: (61, 34), 9: (82, 40),
    10: (7, 61), 11: (29, 57), 12: (51, 60), 13: (74, 63), 14: (93, 58),
    15: (19, 84), 16: (43, 89), 17: (69, 86), 18: (92, 82),
}


_TAXI = (
    (1, 2), (1, 6), (2, 3), (2, 6), (2, 7), (3, 4), (3, 7), (3, 8),
    (4, 5), (4, 8), (4, 9), (5, 9), (6, 7), (6, 10), (6, 11),
    (7, 8), (7, 11), (7, 12), (8, 9), (8, 12), (8, 13), (9, 13), (9, 14),
    (10, 11), (10, 15), (11, 12), (11, 15), (11, 16), (12, 13), (12, 16),
    (12, 17), (13, 14), (13, 17), (13, 18), (14, 18), (15, 16), (16, 17),
    (17, 18),
)

_BUS = (
    (1, 7), (2, 8), (3, 9), (4, 7), (5, 8), (6, 12), (7, 13),
    (8, 14), (9, 12), (10, 16), (11, 17), (12, 18), (13, 16), (14, 17),
)

EDGES: tuple[tuple[int, int, Transport], ...] = tuple(
    (left, right, Transport.TAXI) for left, right in _TAXI
) + tuple((left, right, Transport.BUS) for left, right in _BUS)


@dataclass(frozen=True, slots=True)
class HiddenPursuitRules:
    max_rounds: int = 12
    reveal_rounds: tuple[int, ...] = (3, 6, 9)
    detective_starts: tuple[int, int] = (1, 18)

    def __post_init__(self) -> None:
        nodes = set(NODE_POSITIONS)
        if self.max_rounds < 1:
            raise ValueError("max_rounds must be positive")
        if len(set(self.detective_starts)) != 2 or any(
            node not in nodes for node in self.detective_starts
        ):
            raise ValueError("detectives need two distinct valid starts")
        if any(round_number < 1 or round_number > self.max_rounds for round_number in self.reveal_rounds):
            raise ValueError("reveal rounds must fit within the match")


def adjacency() -> dict[int, tuple[tuple[int, Transport], ...]]:
    result: dict[int, list[tuple[int, Transport]]] = {
        node: [] for node in NODE_POSITIONS
    }
    for left, right, mode in EDGES:
        result[left].append((right, mode))
        result[right].append((left, mode))
    return {node: tuple(sorted(neighbors)) for node, neighbors in result.items()}
