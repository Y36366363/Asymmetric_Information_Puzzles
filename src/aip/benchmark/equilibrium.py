"""Exact equilibrium-backed metrics for the small Kuhn and Goofspiel models."""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from functools import lru_cache
from statistics import mean

from aip.puzzles.goofspiel import GoofspielSolver
from aip.puzzles.kuhn_poker import (
    KuhnPolicy,
    audit_policy,
    equilibrium_policy,
    game_value,
    policy_value,
)
from aip.puzzles.kuhn_poker.solver import CARDS


@dataclass(frozen=True, slots=True)
class KuhnEquilibriumMetrics:
    candidate_regret_first_seat: Fraction
    candidate_regret_second_seat: Fraction
    exploitability_when_candidate_first: Fraction
    exploitability_when_candidate_second: Fraction
    mean_information_set_tv_distance: Fraction
    equilibrium_support_violations: int

    @property
    def maximum_candidate_regret(self) -> Fraction:
        return max(self.candidate_regret_first_seat, self.candidate_regret_second_seat)

    @property
    def maximum_exploitability(self) -> Fraction:
        return max(
            self.exploitability_when_candidate_first,
            self.exploitability_when_candidate_second,
        )


def evaluate_kuhn_policy(policy: KuhnPolicy) -> KuhnEquilibriumMetrics:
    """Compare a complete behavior policy with the declared Kuhn equilibrium.

    Regret is the candidate's exact value loss against an equilibrium opponent.
    Exploitability is the exact best-response gain available to the opponent when
    the candidate occupies the other seat. These are different quantities.
    """

    reference = equilibrium_policy()
    tables = (
        (policy.first_open_bet, reference.first_open_bet),
        (policy.first_call_after_check_bet, reference.first_call_after_check_bet),
        (policy.second_bet_after_check, reference.second_bet_after_check),
        (policy.second_call_open_bet, reference.second_call_open_bet),
    )
    distances = tuple(
        abs(candidate[card] - equilibrium[card])
        for candidate, equilibrium in tables
        for card in CARDS
    )
    support_violations = sum(
        (equilibrium[card] == 0 and candidate[card] > 0)
        or (equilibrium[card] == 1 and candidate[card] < 1)
        for candidate, equilibrium in tables
        for card in CARDS
    )
    audit = audit_policy(policy)
    return KuhnEquilibriumMetrics(
        candidate_regret_first_seat=(
            game_value(True) - policy_value(policy, reference, hero_first=True)
        ),
        candidate_regret_second_seat=(
            game_value(False) - policy_value(policy, reference, hero_first=False)
        ),
        exploitability_when_candidate_first=audit.second_seat_exploitability,
        exploitability_when_candidate_second=audit.first_seat_exploitability,
        mean_information_set_tv_distance=sum(distances) / len(distances),
        equilibrium_support_violations=support_violations,
    )


@dataclass(frozen=True, slots=True)
class GoofspielEquilibriumMetrics:
    policy: str
    game_value: Fraction
    value_against_equilibrium: Fraction
    candidate_regret: Fraction
    value_against_best_response: Fraction
    exploitability: Fraction
    mean_root_tv_distance: Fraction


def _policy_distribution(
    solver: GoofspielSolver,
    policy: str,
    player_cards: tuple[int, ...],
    ai_cards: tuple[int, ...],
    prizes: tuple[int, ...],
    current_prize: int,
) -> tuple[Fraction, ...]:
    if policy == "equilibrium":
        return solver.round_solution(
            player_cards, ai_cards, prizes, current_prize
        ).row_strategy
    if policy == "random":
        return tuple(Fraction(1, len(player_cards)) for _ in player_cards)
    if policy == "match_prize":
        selected = solver.match_prize_bid(player_cards, current_prize)
    elif policy == "high_card":
        selected = max(player_cards)
    else:
        raise ValueError(f"unsupported exact Goofspiel policy: {policy}")
    return tuple(Fraction(card == selected) for card in player_cards)


def evaluate_goofspiel_policy(
    policy: str, *, card_count: int = 4
) -> GoofspielEquilibriumMetrics:
    """Compute exact regret and one-sided exploitability for a named row policy."""

    solver = GoofspielSolver(card_count)

    @lru_cache(maxsize=None)
    def versus_equilibrium(
        player_cards: tuple[int, ...],
        ai_cards: tuple[int, ...],
        prizes: tuple[int, ...],
    ) -> Fraction:
        if not prizes:
            return Fraction(0)
        total = Fraction(0)
        for prize in prizes:
            solution = solver.round_solution(player_cards, ai_cards, prizes, prize)
            row = _policy_distribution(
                solver, policy, player_cards, ai_cards, prizes, prize
            )
            next_prizes = tuple(value for value in prizes if value != prize)
            round_value = Fraction(0)
            for row_index, player_bid in enumerate(player_cards):
                next_player = tuple(card for card in player_cards if card != player_bid)
                for column_index, ai_bid in enumerate(ai_cards):
                    next_ai = tuple(card for card in ai_cards if card != ai_bid)
                    immediate = prize * ((player_bid > ai_bid) - (player_bid < ai_bid))
                    round_value += row[row_index] * solution.column_strategy[column_index] * (
                        immediate + versus_equilibrium(next_player, next_ai, next_prizes)
                    )
            total += round_value
        return total / len(prizes)

    @lru_cache(maxsize=None)
    def versus_best_response(
        player_cards: tuple[int, ...],
        ai_cards: tuple[int, ...],
        prizes: tuple[int, ...],
    ) -> Fraction:
        if not prizes:
            return Fraction(0)
        total = Fraction(0)
        for prize in prizes:
            row = _policy_distribution(
                solver, policy, player_cards, ai_cards, prizes, prize
            )
            next_prizes = tuple(value for value in prizes if value != prize)
            responses: list[Fraction] = []
            for ai_bid in ai_cards:
                next_ai = tuple(card for card in ai_cards if card != ai_bid)
                value = Fraction(0)
                for row_index, player_bid in enumerate(player_cards):
                    next_player = tuple(card for card in player_cards if card != player_bid)
                    immediate = prize * ((player_bid > ai_bid) - (player_bid < ai_bid))
                    value += row[row_index] * (
                        immediate
                        + versus_best_response(next_player, next_ai, next_prizes)
                    )
                responses.append(value)
            total += min(responses)
        return total / len(prizes)

    root = solver.cards
    game = solver.state_value(root, root, root)
    against_equilibrium = versus_equilibrium(root, root, root)
    against_best_response = versus_best_response(root, root, root)
    root_distances = []
    for prize in root:
        reference = solver.round_solution(root, root, root, prize).row_strategy
        candidate = _policy_distribution(solver, policy, root, root, root, prize)
        root_distances.append(
            sum(abs(left - right) for left, right in zip(candidate, reference)) / 2
        )
    return GoofspielEquilibriumMetrics(
        policy=policy,
        game_value=game,
        value_against_equilibrium=against_equilibrium,
        candidate_regret=game - against_equilibrium,
        value_against_best_response=against_best_response,
        exploitability=game - against_best_response,
        mean_root_tv_distance=sum(root_distances) / len(root_distances),
    )
