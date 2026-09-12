"""Immutable extensive-form Love Letter model and independent audit tools."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, replace
from functools import lru_cache
from math import isfinite
from typing import Hashable, Mapping

from aip.core import (
    CFRCertificationGate,
    CFRGame,
    CFRGameProperties,
    CFRGateReport,
    CFRResult,
    CFRThresholds,
)
from aip.puzzles.love_letter.solver import CARD_COUNTS, Play


CardCounts = tuple[int, ...]
PublicEvent = tuple[Hashable, ...]
PrivateEvent = tuple[Hashable, ...]


def _counts(cards: tuple[int, ...] | list[int]) -> CardCounts:
    counter = Counter(cards)
    return tuple(counter[value] for value in range(1, 9))


def _remove(counts: CardCounts, card: int) -> CardCounts:
    if not 1 <= card <= 8 or counts[card - 1] <= 0:
        raise ValueError(f"card {card} is unavailable")
    mutable = list(counts)
    mutable[card - 1] -= 1
    return tuple(mutable)


def _add_private(
    histories: tuple[tuple[PrivateEvent, ...], tuple[PrivateEvent, ...]],
    player: int,
    event: PrivateEvent,
) -> tuple[tuple[PrivateEvent, ...], tuple[PrivateEvent, ...]]:
    mutable = [histories[0], histories[1]]
    mutable[player] = mutable[player] + (event,)
    return mutable[0], mutable[1]


@dataclass(frozen=True, slots=True)
class LoveLetterState:
    stage: str = "root"
    remaining: CardCounts = (0,) * 8
    burn: int | None = None
    face_up: tuple[int, ...] = ()
    hands: tuple[tuple[int, ...], tuple[int, ...]] = ((), ())
    actor: int = 0
    protected: tuple[bool, bool] = (False, False)
    discard_totals: tuple[int, int] = (0, 0)
    public_history: tuple[PublicEvent, ...] = ()
    private_history: tuple[tuple[PrivateEvent, ...], tuple[PrivateEvent, ...]] = (
        (),
        (),
    )
    setup_face_up_left: int = 0
    setup_deal_player: int = 0
    pending_target: int | None = None
    winner: int | None = None


@dataclass(frozen=True, slots=True)
class ExtensiveFormAudit:
    histories: int
    chance_histories: int
    decision_histories: int
    terminal_histories: int
    information_sets: int
    hidden_information_sets: int
    maximum_depth: int
    failures: tuple[str, ...]

    @property
    def passed(self) -> bool:
        return not self.failures


class LoveLetterCFRGame(CFRGame[LoveLetterState]):
    """Complete two-player single-round rules with explicit chance and recall.

    The default root represents the full 16-card round. ``late_round_subgame``
    returns a smaller, completely enumerable imperfect-information endgame using
    the same transition and information-set implementation.
    """

    def __init__(
        self,
        root_outcomes: tuple[tuple[LoveLetterState, float], ...] | None = None,
    ) -> None:
        self._root_outcomes = root_outcomes

    @classmethod
    def late_round_subgame(cls) -> LoveLetterCFRGame:
        """Four-card river: Guard, Priest, Baron, Handmaid remain hidden.

        One card is held by each player and two remain in draw order. Every one
        of the 24 hidden arrangements is equally likely. Player zero draws and
        acts first. This is a closed subgame certificate, not a full-round one.
        """

        cards = (1, 2, 3, 4)
        worlds: list[tuple[LoveLetterState, float]] = []
        for first in cards:
            for second in cards:
                if second == first:
                    continue
                for draw in cards:
                    if draw in (first, second):
                        continue
                    last = next(
                        card for card in cards if card not in (first, second, draw)
                    )
                    private = (
                        (("initial_hand", first),),
                        (("initial_hand", second),),
                    )
                    worlds.append(
                        (
                            LoveLetterState(
                                stage="draw",
                                remaining=_counts([draw, last]),
                                burn=8,
                                face_up=(5, 5, 6, 7),
                                hands=((first,), (second,)),
                                actor=0,
                                private_history=private,
                            ),
                            1 / 24,
                        )
                    )
        return cls(tuple(worlds))

    def initial_state(self) -> LoveLetterState:
        if self._root_outcomes is not None:
            return LoveLetterState(stage="root")
        return LoveLetterState(
            stage="setup_burn",
            remaining=tuple(CARD_COUNTS[value] for value in range(1, 9)),
            setup_face_up_left=3,
        )

    def is_terminal(self, state: LoveLetterState) -> bool:
        return state.stage == "terminal"

    def utility_player_zero(self, state: LoveLetterState) -> float:
        if not self.is_terminal(state):
            raise ValueError("Love Letter utility is defined only at terminal states")
        if state.winner is None:
            return 0.0
        return 1.0 if state.winner == 0 else -1.0

    def current_player(self, state: LoveLetterState) -> int | None:
        return state.actor if state.stage == "play" else None

    def chance_outcomes(
        self, state: LoveLetterState
    ) -> tuple[tuple[Hashable, float], ...]:
        if state.stage == "root" and self._root_outcomes is not None:
            return tuple((index, probability) for index, (_, probability) in enumerate(self._root_outcomes))
        if state.stage not in {
            "setup_burn",
            "setup_face_up",
            "setup_deal",
            "draw",
            "prince_draw",
        }:
            return ()
        total = sum(state.remaining)
        if total <= 0:
            return ()
        return tuple(
            (card, count / total)
            for card, count in enumerate(state.remaining, start=1)
            if count
        )

    def legal_actions(self, state: LoveLetterState) -> tuple[Play, ...]:
        if state.stage != "play":
            return ()
        actor = state.actor
        opponent = 1 - actor
        hand = state.hands[actor]
        legal_cards = (
            (7,)
            if 7 in hand and (5 in hand or 6 in hand)
            else tuple(sorted(set(hand)))
        )
        actions: list[Play] = []
        for card in legal_cards:
            if card == 1:
                actions.extend(
                    Play(card, "ai" if opponent else "player", guess)
                    for guess in range(2, 9)
                )
            elif card in {2, 3, 6}:
                actions.append(Play(card, "ai" if opponent else "player"))
            elif card == 5:
                actions.append(Play(card, "ai" if actor else "player"))
                if not state.protected[opponent]:
                    actions.append(Play(card, "ai" if opponent else "player"))
            else:
                actions.append(Play(card))
        return tuple(actions)

    def information_set(self, state: LoveLetterState) -> Hashable:
        if state.stage != "play":
            raise ValueError("only Love Letter decision states have information sets")
        actor = state.actor
        return (
            actor,
            state.face_up,
            state.hands[actor],
            state.protected,
            sum(state.remaining),
            state.discard_totals,
            state.public_history,
            state.private_history[actor],
        )

    def hidden_world(self, state: LoveLetterState, player: int) -> Hashable:
        """Return variables deliberately excluded from ``information_set``."""

        return (
            state.remaining,
            state.burn,
            state.hands[1 - player],
            state.private_history[1 - player],
        )

    def next_state(self, state: LoveLetterState, action: Hashable) -> LoveLetterState:
        if state.stage == "root" and self._root_outcomes is not None:
            if not isinstance(action, int) or not 0 <= action < len(self._root_outcomes):
                raise ValueError("invalid Love Letter root world")
            return self._root_outcomes[action][0]
        if state.stage in {
            "setup_burn",
            "setup_face_up",
            "setup_deal",
            "draw",
            "prince_draw",
        }:
            if not isinstance(action, int):
                raise ValueError("Love Letter chance actions must be cards")
            return self._chance_transition(state, action)
        if state.stage != "play" or not isinstance(action, Play):
            raise ValueError("invalid Love Letter transition")
        if action not in self.legal_actions(state):
            raise ValueError(f"illegal Love Letter action: {action!r}")
        return self._play_transition(state, action)

    def _chance_transition(
        self, state: LoveLetterState, card: int
    ) -> LoveLetterState:
        remaining = _remove(state.remaining, card)
        if state.stage == "setup_burn":
            return replace(
                state,
                stage="setup_face_up",
                remaining=remaining,
                burn=card,
            )
        if state.stage == "setup_face_up":
            left = state.setup_face_up_left - 1
            return replace(
                state,
                stage="setup_deal" if left == 0 else "setup_face_up",
                remaining=remaining,
                face_up=tuple(sorted(state.face_up + (card,))),
                setup_face_up_left=left,
            )
        if state.stage == "setup_deal":
            player = state.setup_deal_player
            hands = [state.hands[0], state.hands[1]]
            hands[player] = (card,)
            histories = _add_private(
                state.private_history, player, ("initial_hand", card)
            )
            next_player = player + 1
            return replace(
                state,
                stage="draw" if next_player == 2 else "setup_deal",
                remaining=remaining,
                hands=(hands[0], hands[1]),
                private_history=histories,
                setup_deal_player=next_player,
                actor=0,
            )
        target = state.actor if state.stage == "draw" else state.pending_target
        assert target in (0, 1)
        hands = [state.hands[0], state.hands[1]]
        hands[target] = tuple(sorted(hands[target] + (card,)))
        histories = _add_private(
            state.private_history, target, ("draw", len(state.public_history), card)
        )
        if state.stage == "draw":
            protected = list(state.protected)
            protected[target] = False
            return replace(
                state,
                stage="play",
                remaining=remaining,
                hands=(hands[0], hands[1]),
                protected=(protected[0], protected[1]),
                private_history=histories,
            )
        resumed = replace(
            state,
            remaining=remaining,
            hands=(hands[0], hands[1]),
            private_history=histories,
            pending_target=None,
        )
        return self._advance_after_play(resumed)

    def _play_transition(
        self, state: LoveLetterState, play: Play
    ) -> LoveLetterState:
        actor = state.actor
        opponent = 1 - actor
        hands = [state.hands[0], state.hands[1]]
        mutable_hand = list(hands[actor])
        mutable_hand.remove(play.card)
        hands[actor] = tuple(mutable_hand)
        totals = list(state.discard_totals)
        totals[actor] += play.card
        histories = _add_private(
            state.private_history,
            actor,
            ("action", len(state.public_history), play.card, play.target, play.guess),
        )
        event: PublicEvent = (actor, play.card, play.target, play.guess, "none")
        updated = replace(
            state,
            hands=(hands[0], hands[1]),
            discard_totals=(totals[0], totals[1]),
            private_history=histories,
        )

        if play.card == 1 and not state.protected[opponent]:
            hit = state.hands[opponent][0] == play.guess
            event = (actor, play.card, play.target, play.guess, "hit" if hit else "miss")
            if hit:
                return self._terminal(updated, actor, event)
        elif play.card == 2 and not state.protected[opponent]:
            histories = _add_private(
                updated.private_history,
                actor,
                ("priest", len(state.public_history), state.hands[opponent][0]),
            )
            updated = replace(updated, private_history=histories)
            event = (actor, play.card, play.target, None, "seen")
        elif play.card == 3 and not state.protected[opponent]:
            mine, theirs = updated.hands[actor][0], updated.hands[opponent][0]
            if mine != theirs:
                winner = actor if mine > theirs else opponent
                event = (actor, play.card, play.target, None, "baron_loss")
                return self._terminal(updated, winner, event)
            event = (actor, play.card, play.target, None, "baron_tie")
        elif play.card == 4:
            protected = list(updated.protected)
            protected[actor] = True
            updated = replace(updated, protected=(protected[0], protected[1]))
            event = (actor, play.card, None, None, "protected")
        elif play.card == 5:
            target = actor if play.target == ("ai" if actor else "player") else opponent
            discarded = updated.hands[target][0]
            hands = [updated.hands[0], updated.hands[1]]
            hands[target] = ()
            totals = list(updated.discard_totals)
            totals[target] += discarded
            event = (actor, play.card, play.target, None, "prince_discard", discarded)
            updated = replace(
                updated,
                hands=(hands[0], hands[1]),
                discard_totals=(totals[0], totals[1]),
            )
            if discarded == 8:
                return self._terminal(updated, 1 - target, event)
            updated = replace(
                updated,
                public_history=updated.public_history + (event,),
                stage="prince_draw",
                pending_target=target,
            )
            if sum(updated.remaining) == 0:
                assert updated.burn is not None
                hands = [updated.hands[0], updated.hands[1]]
                hands[target] = (updated.burn,)
                histories = _add_private(
                    updated.private_history,
                    target,
                    ("burn_replacement", len(updated.public_history), updated.burn),
                )
                return self._advance_after_play(
                    replace(
                        updated,
                        hands=(hands[0], hands[1]),
                        private_history=histories,
                        pending_target=None,
                    )
                )
            return updated
        elif play.card == 6 and not state.protected[opponent]:
            hands = [updated.hands[0], updated.hands[1]]
            hands[actor], hands[opponent] = hands[opponent], hands[actor]
            histories = _add_private(
                updated.private_history,
                actor,
                ("king_received", len(state.public_history), hands[actor][0]),
            )
            histories = _add_private(
                histories,
                opponent,
                ("king_received", len(state.public_history), hands[opponent][0]),
            )
            updated = replace(
                updated,
                hands=(hands[0], hands[1]),
                private_history=histories,
            )
            event = (actor, play.card, play.target, None, "traded")
        elif play.card == 8:
            event = (actor, play.card, None, None, "princess")
            return self._terminal(updated, opponent, event)

        updated = replace(
            updated, public_history=updated.public_history + (event,)
        )
        return self._advance_after_play(updated)

    def _advance_after_play(self, state: LoveLetterState) -> LoveLetterState:
        if sum(state.remaining) == 0:
            first, second = state.hands[0][0], state.hands[1][0]
            if first != second:
                winner = 0 if first > second else 1
            elif state.discard_totals[0] != state.discard_totals[1]:
                winner = 0 if state.discard_totals[0] > state.discard_totals[1] else 1
            else:
                winner = None
            return replace(state, stage="terminal", winner=winner)
        return replace(state, stage="draw", actor=1 - state.actor)

    @staticmethod
    def _terminal(
        state: LoveLetterState, winner: int, event: PublicEvent
    ) -> LoveLetterState:
        return replace(
            state,
            stage="terminal",
            winner=winner,
            public_history=state.public_history + (event,),
        )


def audit_complete_tree(
    game: LoveLetterCFRGame, *, maximum_histories: int = 1_000_000
) -> ExtensiveFormAudit:
    """Exhaust every history, validating chance, actions, and information sets."""

    action_tables: dict[tuple[int, Hashable], tuple[Play, ...]] = {}
    hidden_worlds: dict[tuple[int, Hashable], set[Hashable]] = defaultdict(set)
    failures: set[str] = set()
    counts = {"histories": 0, "chance": 0, "decision": 0, "terminal": 0}
    maximum_depth = 0

    def traverse(state: LoveLetterState, depth: int) -> None:
        nonlocal maximum_depth
        counts["histories"] += 1
        maximum_depth = max(maximum_depth, depth)
        if counts["histories"] > maximum_histories:
            raise OverflowError(
                f"complete tree exceeds {maximum_histories} histories"
            )
        if game.is_terminal(state):
            counts["terminal"] += 1
            if not isfinite(game.utility_player_zero(state)):
                failures.add("nonfinite_terminal_utility")
            return
        player = game.current_player(state)
        if player is None:
            counts["chance"] += 1
            outcomes = game.chance_outcomes(state)
            if (
                not outcomes
                or len({action for action, _ in outcomes}) != len(outcomes)
                or any(not isfinite(probability) or probability <= 0 for _, probability in outcomes)
                or abs(sum(probability for _, probability in outcomes) - 1) > 1e-9
            ):
                failures.add("invalid_chance_distribution")
                return
            for action, _ in outcomes:
                traverse(game.next_state(state, action), depth + 1)
            return
        counts["decision"] += 1
        actions = game.legal_actions(state)
        if not actions or len(set(actions)) != len(actions):
            failures.add("invalid_legal_actions")
            return
        information_set = game.information_set(state)
        key = (player, information_set)
        previous = action_tables.setdefault(key, actions)
        if previous != actions:
            failures.add("inconsistent_information_set_actions")
        hidden_worlds[key].add(game.hidden_world(state, player))
        for action in actions:
            traverse(game.next_state(state, action), depth + 1)

    traverse(game.initial_state(), 0)
    return ExtensiveFormAudit(
        histories=counts["histories"],
        chance_histories=counts["chance"],
        decision_histories=counts["decision"],
        terminal_histories=counts["terminal"],
        information_sets=len(action_tables),
        hidden_information_sets=sum(len(worlds) > 1 for worlds in hidden_worlds.values()),
        maximum_depth=maximum_depth,
        failures=tuple(sorted(failures)),
    )


def complete_information_set_actions(
    game: LoveLetterCFRGame, *, maximum_histories: int = 1_000_000
) -> Mapping[tuple[int, Hashable], tuple[Play, ...]]:
    """Return every information set/action table after exhaustive traversal."""

    tables: dict[tuple[int, Hashable], tuple[Play, ...]] = {}
    histories = 0

    def traverse(state: LoveLetterState) -> None:
        nonlocal histories
        histories += 1
        if histories > maximum_histories:
            raise OverflowError(
                f"complete tree exceeds {maximum_histories} histories"
            )
        if game.is_terminal(state):
            return
        player = game.current_player(state)
        if player is None:
            for action, _ in game.chance_outcomes(state):
                traverse(game.next_state(state, action))
            return
        actions = game.legal_actions(state)
        key = (player, game.information_set(state))
        previous = tables.setdefault(key, actions)
        if previous != actions:
            raise ValueError("inconsistent Love Letter information-set actions")
        for action in actions:
            traverse(game.next_state(state, action))

    traverse(game.initial_state())
    return tables


def independent_best_response_value(
    game: LoveLetterCFRGame,
    policy: Mapping[tuple[int, Hashable], Mapping[Hashable, float]],
    hero: int,
) -> float:
    """Exact pure best response to a fixed opponent policy on an enumerated tree."""

    if hero not in (0, 1):
        raise ValueError("Love Letter best response player must be 0 or 1")
    members: dict[Hashable, dict[LoveLetterState, float]] = defaultdict(
        lambda: defaultdict(float)
    )

    def collect(state: LoveLetterState, counterfactual_reach: float) -> None:
        if game.is_terminal(state):
            return
        player = game.current_player(state)
        if player is None:
            for action, probability in game.chance_outcomes(state):
                collect(game.next_state(state, action), counterfactual_reach * probability)
            return
        information_set = game.information_set(state)
        actions = game.legal_actions(state)
        if player == hero:
            members[information_set][state] += counterfactual_reach
            for action in actions:
                collect(game.next_state(state, action), counterfactual_reach)
            return
        distribution = policy[(player, information_set)]
        for action in actions:
            collect(
                game.next_state(state, action),
                counterfactual_reach * float(distribution[action]),
            )

    collect(game.initial_state(), 1.0)
    chosen: dict[Hashable, Play] = {}

    @lru_cache(maxsize=None)
    def value(state: LoveLetterState) -> float:
        if game.is_terminal(state):
            utility = game.utility_player_zero(state)
            return utility if hero == 0 else -utility
        player = game.current_player(state)
        if player is None:
            return sum(
                probability * value(game.next_state(state, action))
                for action, probability in game.chance_outcomes(state)
            )
        information_set = game.information_set(state)
        actions = game.legal_actions(state)
        if player != hero:
            distribution = policy[(player, information_set)]
            return sum(
                float(distribution[action]) * value(game.next_state(state, action))
                for action in actions
            )
        if information_set not in chosen:
            chosen[information_set] = max(
                actions,
                key=lambda action: sum(
                    reach * value(game.next_state(member, action))
                    for member, reach in members[information_set].items()
                ),
            )
        return value(game.next_state(state, chosen[information_set]))

    return value(game.initial_state())


def love_letter_subgame_exploitability(
    game: LoveLetterCFRGame, result: CFRResult
) -> float:
    """Return half NashConv from independent exhaustive best responses."""

    return (
        independent_best_response_value(game, result.policy, 0)
        + independent_best_response_value(game, result.policy, 1)
    ) / 2


def certify_love_letter_subgame(
    game: LoveLetterCFRGame,
    result: CFRResult,
    thresholds: CFRThresholds | None = None,
) -> CFRGateReport:
    """Certify only the enumerable four-card Love Letter research subgame."""

    required = frozenset(complete_information_set_actions(game))
    gate = CFRCertificationGate(
        thresholds
        or CFRThresholds(
            min_iterations=20_000,
            min_information_sets=len(required),
            min_visits_per_information_set=1_000,
            max_average_positive_regret=0.015,
            max_exploitability=0.001,
        )
    )
    return gate.evaluate(
        result,
        exploitability=love_letter_subgame_exploitability(game, result),
        required_information_sets=required,
        exact_information_sets=True,
        game_properties=CFRGameProperties(
            players=2,
            finite=True,
            zero_sum_or_constant_sum=True,
            perfect_recall=True,
        ),
    )
