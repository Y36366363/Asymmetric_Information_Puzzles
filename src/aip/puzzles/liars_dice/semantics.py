"""Trusted visibility contracts for the reduced one-die Liar's Dice game."""

from __future__ import annotations

from itertools import combinations

from aip.core.semantic_audit import ObservationInvarianceCase

from .cfr import BIDS, FACES, OPENING_BIDS, OneDieLiarState


def one_die_private_die_invariance_cases(
) -> tuple[ObservationInvarianceCase[OneDieLiarState], ...]:
    """Pair states that differ only in the acting player's unseen opponent die."""

    public_histories: list[tuple[tuple[int, int], ...]] = [()]
    for opening_index in range(len(OPENING_BIDS)):
        for final_index in range(opening_index, len(BIDS)):
            public_histories.append(BIDS[opening_index : final_index + 1])

    cases = []
    for bids in public_histories:
        player = len(bids) % 2
        bid_label = "root" if not bids else "-".join(
            f"{quantity}x{face}" for quantity, face in bids
        )
        for own_die in FACES:
            for left_opponent, right_opponent in combinations(FACES, 2):
                left_dice = (
                    (own_die, left_opponent)
                    if player == 0
                    else (left_opponent, own_die)
                )
                right_dice = (
                    (own_die, right_opponent)
                    if player == 0
                    else (right_opponent, own_die)
                )
                cases.append(
                    ObservationInvarianceCase(
                        case_id=(
                            f"p{player}:own{own_die}:{bid_label}:"
                            f"opp{left_opponent}-{right_opponent}"
                        ),
                        left_state=OneDieLiarState(left_dice, bids),
                        right_state=OneDieLiarState(right_dice, bids),
                    )
                )
    return tuple(cases)
