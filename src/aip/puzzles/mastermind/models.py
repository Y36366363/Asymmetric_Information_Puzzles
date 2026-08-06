from __future__ import annotations

from dataclasses import dataclass
from math import perm


@dataclass(frozen=True, slots=True)
class CodeRules:
    """Rules for a decimal Bulls-and-Cows code with no repeated digits."""

    length: int = 4
    symbols: tuple[int, ...] = tuple(range(10))
    max_attempts: int = 10

    def __post_init__(self) -> None:
        if not 2 <= self.length <= len(self.symbols):
            raise ValueError("length must fit within the available symbols")
        if len(set(self.symbols)) != len(self.symbols):
            raise ValueError("symbols must be unique")
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be positive")

    @property
    def world_count(self) -> int:
        return perm(len(self.symbols), self.length)

    def validate_guess(self, guess: tuple[int, ...]) -> None:
        if len(guess) != self.length:
            raise ValueError(f"guess must contain exactly {self.length} digits")
        if len(set(guess)) != self.length:
            raise ValueError("digits may not repeat")
        if any(value not in self.symbols for value in guess):
            raise ValueError("every digit must be between 0 and 9")


@dataclass(frozen=True, slots=True)
class CodeFeedback:
    exact: int
    misplaced: int

    def as_tuple(self) -> tuple[int, int]:
        return self.exact, self.misplaced
