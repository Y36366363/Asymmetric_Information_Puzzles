"""Observation semantics for simultaneous Goofspiel commitments."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations

from aip.core.game_spec import (
    GameSpecObservationSlice,
    ObservationStateRecord,
    generate_observation_invariance_contract,
)


@dataclass(frozen=True, slots=True)
class GoofspielCommitmentState:
    """One simultaneous round represented as sequential hidden commitments."""

    player_0_cards: tuple[int, ...]
    player_1_cards: tuple[int, ...]
    remaining_prizes: tuple[int, ...]
    current_prize: int | None = None
    pending_player_0_card: int | None = None
    player_1_card: int | None = None

    @property
    def stage(self) -> str:
        if self.current_prize is None:
            return "reveal_prize"
        if self.pending_player_0_card is None:
            return "player_0_commit"
        if self.player_1_card is None:
            return "player_1_commit"
        return "terminal"


def goofspiel_observation_spec() -> GameSpecObservationSlice:
    return GameSpecObservationSlice(
        spec_id="four_card_goofspiel_hidden_commitment_v1",
        player_count=2,
        public_fields=(
            "stage",
            "player_0_cards",
            "player_1_cards",
            "remaining_prizes",
            "current_prize",
        ),
        private_fields_by_player=(("pending_player_0_card",), ()),
    )


def _state_record(
    state: GoofspielCommitmentState, player: int
) -> ObservationStateRecord[GoofspielCommitmentState]:
    return ObservationStateRecord.from_mapping(
        state,
        player,
        {
            "stage": state.stage,
            "player_0_cards": state.player_0_cards,
            "player_1_cards": state.player_1_cards,
            "remaining_prizes": state.remaining_prizes,
            "current_prize": state.current_prize,
            "pending_player_0_card": state.pending_player_0_card,
        },
    )


class GoofspielCommitmentGame:
    """Four-card one-round slice with a hidden first commitment."""

    cards = (1, 2, 3, 4)

    def __init__(self, *, leak_player_0_commitment: bool = False) -> None:
        self.leak_player_0_commitment = leak_player_0_commitment
        self.observation_spec = goofspiel_observation_spec()

    def initial_state(self) -> GoofspielCommitmentState:
        return GoofspielCommitmentState(self.cards, self.cards, self.cards)

    def is_terminal(self, state: GoofspielCommitmentState) -> bool:
        return state.stage == "terminal"

    def utility_player_zero(self, state: GoofspielCommitmentState) -> float:
        if not self.is_terminal(state):
            raise ValueError("utility is defined only at terminal states")
        assert state.current_prize is not None
        assert state.pending_player_0_card is not None
        assert state.player_1_card is not None
        if state.pending_player_0_card > state.player_1_card:
            return float(state.current_prize)
        if state.pending_player_0_card < state.player_1_card:
            return float(-state.current_prize)
        return 0.0

    def current_player(self, state: GoofspielCommitmentState) -> int | None:
        if state.stage == "player_0_commit":
            return 0
        if state.stage == "player_1_commit":
            return 1
        return None

    def chance_outcomes(
        self, state: GoofspielCommitmentState
    ) -> tuple[tuple[int, float], ...]:
        if state.stage != "reveal_prize":
            return ()
        probability = 1.0 / len(state.remaining_prizes)
        return tuple((prize, probability) for prize in state.remaining_prizes)

    def legal_actions(self, state: GoofspielCommitmentState) -> tuple[int, ...]:
        player = self.current_player(state)
        if player == 0:
            return state.player_0_cards
        if player == 1:
            return state.player_1_cards
        return ()

    def information_set(self, state: GoofspielCommitmentState):
        player = self.current_player(state)
        if player not in (0, 1):
            raise ValueError("information sets exist only at decision states")
        projection = self.observation_spec.project(
            _state_record(state, player).field_mapping(), player
        )
        if player == 1 and self.leak_player_0_commitment:
            return projection + (
                ("pending_player_0_card", state.pending_player_0_card),
            )
        return projection

    def next_state(
        self, state: GoofspielCommitmentState, action: int
    ) -> GoofspielCommitmentState:
        if state.stage == "reveal_prize":
            if action not in state.remaining_prizes:
                raise ValueError("invalid prize outcome")
            return GoofspielCommitmentState(
                state.player_0_cards,
                state.player_1_cards,
                state.remaining_prizes,
                current_prize=action,
            )
        if state.stage == "player_0_commit":
            if action not in state.player_0_cards:
                raise ValueError("invalid player 0 card")
            return GoofspielCommitmentState(
                state.player_0_cards,
                state.player_1_cards,
                state.remaining_prizes,
                state.current_prize,
                pending_player_0_card=action,
            )
        if state.stage == "player_1_commit":
            if action not in state.player_1_cards:
                raise ValueError("invalid player 1 card")
            return GoofspielCommitmentState(
                state.player_0_cards,
                state.player_1_cards,
                state.remaining_prizes,
                state.current_prize,
                state.pending_player_0_card,
                player_1_card=action,
            )
        raise ValueError("terminal states have no successors")


def goofspiel_observation_records(
    card_count: int = 4,
) -> tuple[ObservationStateRecord[GoofspielCommitmentState], ...]:
    """Enumerate all public inventory shapes with a meaningful hidden choice."""

    if card_count != 4:
        raise ValueError("the frozen semantic transfer uses exactly four cards")
    cards = tuple(range(1, card_count + 1))
    records = []
    for remaining_count in range(card_count, 1, -1):
        for player_0_cards in combinations(cards, remaining_count):
            for player_1_cards in combinations(cards, remaining_count):
                for remaining_prizes in combinations(cards, remaining_count):
                    for current_prize in remaining_prizes:
                        for pending_card in player_0_cards:
                            state = GoofspielCommitmentState(
                                player_0_cards,
                                player_1_cards,
                                remaining_prizes,
                                current_prize,
                                pending_player_0_card=pending_card,
                            )
                            records.append(_state_record(state, 1))
    return tuple(records)


def generated_goofspiel_observation_contract():
    return generate_observation_invariance_contract(
        goofspiel_observation_spec(), goofspiel_observation_records()
    )
