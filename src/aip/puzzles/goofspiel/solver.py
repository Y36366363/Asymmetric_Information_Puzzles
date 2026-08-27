from __future__ import annotations

import random
from dataclasses import dataclass
from fractions import Fraction
from functools import lru_cache
from itertools import combinations
from statistics import mean


@dataclass(frozen=True, slots=True)
class MatrixSolution:
    value: Fraction
    row_strategy: tuple[Fraction, ...]
    column_strategy: tuple[Fraction, ...]


@dataclass(frozen=True, slots=True)
class GoofspielRun:
    seed: int
    player_policy: str
    player_score: int
    ai_score: int

    @property
    def difference(self) -> int:
        return self.player_score - self.ai_score


@dataclass(frozen=True, slots=True)
class PolicySummary:
    policy: str
    games: int
    player_mean_difference: float
    player_win_rate: float
    draw_rate: float


def _solve_linear(matrix: list[list[Fraction]], vector: list[Fraction]) -> list[Fraction] | None:
    size = len(vector)
    augmented = [row[:] + [value] for row, value in zip(matrix, vector)]
    for column in range(size):
        pivot = next((row for row in range(column, size) if augmented[row][column]), None)
        if pivot is None:
            return None
        augmented[column], augmented[pivot] = augmented[pivot], augmented[column]
        divisor = augmented[column][column]
        augmented[column] = [value / divisor for value in augmented[column]]
        for row in range(size):
            if row == column:
                continue
            factor = augmented[row][column]
            if factor:
                augmented[row] = [
                    value - factor * pivot_value
                    for value, pivot_value in zip(augmented[row], augmented[column])
                ]
    return [augmented[index][-1] for index in range(size)]


def solve_zero_sum_matrix(payoffs: tuple[tuple[Fraction, ...], ...]) -> MatrixSolution:
    """Solve a small zero-sum matrix by exact LP-vertex enumeration."""
    row_count = len(payoffs)
    column_count = len(payoffs[0]) if payoffs else 0
    if not row_count or not column_count or any(len(row) != column_count for row in payoffs):
        raise ValueError("payoff matrix must be non-empty and rectangular")
    best_row: tuple[Fraction, tuple[Fraction, ...]] | None = None
    # Variables are row probabilities followed by guaranteed value v.  A
    # vertex combines sum(p)=1 with m active non-negativity/payoff constraints.
    for active in combinations(range(row_count + column_count), row_count):
        equations = [[Fraction(1)] * row_count + [Fraction(0)]]
        targets = [Fraction(1)]
        for constraint in active:
            if constraint < row_count:
                equation = [Fraction(0)] * (row_count + 1)
                equation[constraint] = Fraction(1)
            else:
                column = constraint - row_count
                equation = [payoffs[row][column] for row in range(row_count)] + [Fraction(-1)]
            equations.append(equation)
            targets.append(Fraction(0))
        result = _solve_linear(equations, targets)
        if result is None:
            continue
        probabilities, value = tuple(result[:-1]), result[-1]
        if any(probability < 0 for probability in probabilities):
            continue
        column_returns = [
            sum(probabilities[row] * payoffs[row][column] for row in range(row_count))
            for column in range(column_count)
        ]
        if min(column_returns) < value:
            continue
        if best_row is None or value > best_row[0]:
            best_row = (value, probabilities)

    best_column: tuple[Fraction, tuple[Fraction, ...]] | None = None
    # The dual minimizes v with q>=0, sum(q)=1, and every row payoff <=v.
    for active in combinations(range(column_count + row_count), column_count):
        equations = [[Fraction(1)] * column_count + [Fraction(0)]]
        targets = [Fraction(1)]
        for constraint in active:
            if constraint < column_count:
                equation = [Fraction(0)] * (column_count + 1)
                equation[constraint] = Fraction(1)
            else:
                row = constraint - column_count
                equation = list(payoffs[row]) + [Fraction(-1)]
            equations.append(equation)
            targets.append(Fraction(0))
        result = _solve_linear(equations, targets)
        if result is None:
            continue
        probabilities, value = tuple(result[:-1]), result[-1]
        if any(probability < 0 for probability in probabilities):
            continue
        row_returns = [
            sum(payoffs[row][column] * probabilities[column] for column in range(column_count))
            for row in range(row_count)
        ]
        if max(row_returns) > value:
            continue
        if best_column is None or value < best_column[0]:
            best_column = (value, probabilities)

    if best_row is None or best_column is None or best_row[0] != best_column[0]:
        raise RuntimeError("LP vertex enumeration found no zero-sum equilibrium")
    return MatrixSolution(best_row[0], best_row[1], best_column[1])


class GoofspielSolver:
    """Exact dynamic equilibrium for a shuffled-prize, small-deck Goofspiel."""

    PLAYER_POLICIES = ("equilibrium", "random", "match_prize", "high_card")

    def __init__(self, card_count: int = 4) -> None:
        if card_count < 2 or card_count > 5:
            raise ValueError("exact Goofspiel supports between two and five cards")
        self.card_count = card_count
        self.cards = tuple(range(1, card_count + 1))

    @lru_cache(maxsize=None)
    def state_value(
        self,
        player_cards: tuple[int, ...],
        ai_cards: tuple[int, ...],
        prizes: tuple[int, ...],
    ) -> Fraction:
        if not prizes:
            return Fraction(0)
        return sum(
            self.round_solution(player_cards, ai_cards, prizes, prize).value
            for prize in prizes
        ) / len(prizes)

    @lru_cache(maxsize=None)
    def round_solution(
        self,
        player_cards: tuple[int, ...],
        ai_cards: tuple[int, ...],
        prizes: tuple[int, ...],
        current_prize: int,
    ) -> MatrixSolution:
        if current_prize not in prizes:
            raise ValueError("current prize must remain in the prize set")
        next_prizes = tuple(value for value in prizes if value != current_prize)
        matrix = []
        for player_bid in player_cards:
            row = []
            next_player = tuple(value for value in player_cards if value != player_bid)
            for ai_bid in ai_cards:
                next_ai = tuple(value for value in ai_cards if value != ai_bid)
                immediate = current_prize if player_bid > ai_bid else -current_prize if player_bid < ai_bid else 0
                continuation = self.state_value(next_player, next_ai, next_prizes)
                row.append(Fraction(immediate) + continuation)
            matrix.append(tuple(row))
        return solve_zero_sum_matrix(tuple(matrix))

    @staticmethod
    def _sample(cards: tuple[int, ...], probabilities: tuple[Fraction, ...], rng: random.Random) -> int:
        draw = rng.random()
        cumulative = 0.0
        for card, probability in zip(cards, probabilities):
            cumulative += float(probability)
            if draw < cumulative:
                return card
        return cards[-1]

    def choose_player_bid(
        self,
        policy: str,
        player_cards: tuple[int, ...],
        ai_cards: tuple[int, ...],
        prizes: tuple[int, ...],
        current_prize: int,
        rng: random.Random,
    ) -> int:
        if policy not in self.PLAYER_POLICIES:
            raise ValueError(f"unknown Goofspiel player policy: {policy}")
        if policy == "random":
            return rng.choice(player_cards)
        if policy == "match_prize":
            return min(player_cards, key=lambda card: (abs(card - current_prize), card))
        if policy == "high_card":
            return max(player_cards)
        solution = self.round_solution(player_cards, ai_cards, prizes, current_prize)
        return self._sample(player_cards, solution.row_strategy, rng)

    @staticmethod
    def match_prize_bid(cards: tuple[int, ...], current_prize: int) -> int:
        """Return the intuitive closest-to-prize bid, breaking ties downward."""
        if not cards:
            raise ValueError("at least one bid card must remain")
        return min(cards, key=lambda card: (abs(card - current_prize), card))

    @lru_cache(maxsize=None)
    def best_response_value_against_match_prize(
        self,
        player_cards: tuple[int, ...],
        ai_cards: tuple[int, ...],
        prizes: tuple[int, ...],
    ) -> Fraction:
        """Exact player value against the deterministic match-prize heuristic."""
        if not prizes:
            return Fraction(0)
        return sum(
            self._best_response_round_value(
                player_cards, ai_cards, prizes, current_prize
            )
            for current_prize in prizes
        ) / len(prizes)

    def _best_response_round_value(
        self,
        player_cards: tuple[int, ...],
        ai_cards: tuple[int, ...],
        prizes: tuple[int, ...],
        current_prize: int,
    ) -> Fraction:
        ai_bid = self.match_prize_bid(ai_cards, current_prize)
        next_ai = tuple(card for card in ai_cards if card != ai_bid)
        next_prizes = tuple(prize for prize in prizes if prize != current_prize)
        returns = []
        for player_bid in player_cards:
            immediate = (
                current_prize
                if player_bid > ai_bid
                else -current_prize
                if player_bid < ai_bid
                else 0
            )
            next_player = tuple(card for card in player_cards if card != player_bid)
            returns.append(
                Fraction(immediate)
                + self.best_response_value_against_match_prize(
                    next_player, next_ai, next_prizes
                )
            )
        return max(returns)

    def play(self, seed: int, player_policy: str = "equilibrium") -> GoofspielRun:
        rng = random.Random(seed)
        prizes = list(self.cards)
        rng.shuffle(prizes)
        player_cards = self.cards
        ai_cards = self.cards
        player_score = 0
        ai_score = 0
        for current_prize in prizes:
            remaining_prizes = tuple(sorted(prizes[prizes.index(current_prize):]))
            solution = self.round_solution(player_cards, ai_cards, remaining_prizes, current_prize)
            player_bid = self.choose_player_bid(
                player_policy,
                player_cards,
                ai_cards,
                remaining_prizes,
                current_prize,
                rng,
            )
            ai_bid = self._sample(ai_cards, solution.column_strategy, rng)
            if player_bid > ai_bid:
                player_score += current_prize
            elif ai_bid > player_bid:
                ai_score += current_prize
            player_cards = tuple(value for value in player_cards if value != player_bid)
            ai_cards = tuple(value for value in ai_cards if value != ai_bid)
        return GoofspielRun(seed, player_policy, player_score, ai_score)

    def compare(self, games: int = 1000, seed: int = 0) -> tuple[PolicySummary, ...]:
        if games < 1:
            raise ValueError("games must be positive")
        summaries = []
        for policy in self.PLAYER_POLICIES:
            runs = [self.play(seed + index, policy) for index in range(games)]
            summaries.append(
                PolicySummary(
                    policy=policy,
                    games=games,
                    player_mean_difference=mean(run.difference for run in runs),
                    player_win_rate=sum(run.difference > 0 for run in runs) / games,
                    draw_rate=sum(run.difference == 0 for run in runs) / games,
                )
            )
        return tuple(summaries)
