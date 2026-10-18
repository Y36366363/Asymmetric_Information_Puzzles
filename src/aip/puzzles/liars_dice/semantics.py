"""Trusted visibility contracts for the reduced one-die Liar's Dice game."""

from __future__ import annotations

from itertools import combinations

from aip.core.game_spec import (
    GameSpecObservationSlice,
    ObservationStateRecord,
    generate_observation_invariance_contract,
)
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


def one_die_observation_spec() -> GameSpecObservationSlice:
    """Return the declarative visibility slice for one-die decision states."""

    return GameSpecObservationSlice(
        spec_id="one_die_liar_observation_v1",
        player_count=2,
        public_fields=("bids",),
        private_fields_by_player=(("die_0",), ("die_1",)),
    )


def one_die_observation_records(
) -> tuple[ObservationStateRecord[OneDieLiarState], ...]:
    """Enumerate the same decision worlds used by the manual reference."""

    public_histories: list[tuple[tuple[int, int], ...]] = [()]
    for opening_index in range(len(OPENING_BIDS)):
        for final_index in range(opening_index, len(BIDS)):
            public_histories.append(BIDS[opening_index : final_index + 1])

    records = []
    for bids in public_histories:
        player = len(bids) % 2
        for own_die in FACES:
            for opponent_die in FACES:
                dice = (
                    (own_die, opponent_die)
                    if player == 0
                    else (opponent_die, own_die)
                )
                state = OneDieLiarState(dice, bids)
                records.append(
                    ObservationStateRecord.from_mapping(
                        state,
                        player,
                        {"bids": bids, "die_0": dice[0], "die_1": dice[1]},
                    )
                )
    return tuple(records)


def generated_one_die_observation_contract():
    """Generate one-die invariance pairs solely from declared visibility."""

    return generate_observation_invariance_contract(
        one_die_observation_spec(), one_die_observation_records()
    )
