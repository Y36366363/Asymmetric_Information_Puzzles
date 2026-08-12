from __future__ import annotations

import random
from collections import Counter
from dataclasses import dataclass
from typing import Literal

Actor = Literal["player", "ai"]

CARD_NAMES = {
    1: "Guard",
    2: "Priest",
    3: "Baron",
    4: "Handmaid",
    5: "Prince",
    6: "King",
    7: "Countess",
    8: "Princess",
}
CARD_COUNTS = {1: 5, 2: 2, 3: 2, 4: 2, 5: 2, 6: 1, 7: 1, 8: 1}


@dataclass(frozen=True, slots=True)
class Play:
    card: int
    target: Actor | None = None
    guess: int | None = None


class LoveLetterGame:
    """Standard 16-card, two-player Love Letter match.

    Public state never contains the opponent's live hand.  The policy operates
    on remaining-card beliefs plus knowledge earned by Priest or King.
    """

    target_score = 4

    def __init__(self, rng: random.Random | None = None) -> None:
        self.rng = rng or random.Random()
        self.scores = {"player": 0, "ai": 0}
        self.round_number = 0
        self.games_completed = 0
        self.player_wins = 0
        self.start_round()

    @staticmethod
    def other(actor: Actor) -> Actor:
        return "ai" if actor == "player" else "player"

    def start_round(self) -> None:
        self.round_number += 1
        deck = [value for value, count in CARD_COUNTS.items() for _ in range(count)]
        self.rng.shuffle(deck)
        self.burned = deck.pop()
        self.face_up_removed = [deck.pop() for _ in range(3)]
        self.deck = deck
        self.hands: dict[Actor, list[int]] = {
            "player": [self.deck.pop()],
            "ai": [self.deck.pop()],
        }
        self.discards: dict[Actor, list[int]] = {"player": [], "ai": []}
        self.protected: dict[Actor, bool] = {"player": False, "ai": False}
        self.known_hand: dict[Actor, int | None] = {"player": None, "ai": None}
        self.eliminated: Actor | None = None
        self.round_winner: Actor | None = None
        self.round_reason: str | None = None
        self.history: list[dict[str, object]] = []
        self.phase = "player_turn"
        self._begin_turn("player")

    def _begin_turn(self, actor: Actor) -> None:
        self.protected[actor] = False
        if not self.deck:
            self._showdown()
            return
        self.hands[actor].append(self.deck.pop())
        self.phase = f"{actor}_turn"

    def legal_cards(self, actor: Actor) -> list[int]:
        hand = self.hands[actor]
        if 7 in hand and (5 in hand or 6 in hand):
            return [7]
        return sorted(set(hand))

    def legal_plays(self, actor: Actor) -> list[Play]:
        opponent = self.other(actor)
        plays: list[Play] = []
        for card in self.legal_cards(actor):
            if card == 1:
                plays.extend(Play(card, opponent, guess) for guess in range(2, 9))
            elif card in {2, 3, 6}:
                plays.append(Play(card, opponent))
            elif card == 5:
                plays.append(Play(card, actor))
                if not self.protected[opponent]:
                    plays.append(Play(card, opponent))
            else:
                plays.append(Play(card))
        return plays

    def belief(self, observer: Actor) -> Counter[int]:
        opponent = self.other(observer)
        known = self.known_hand[observer]
        if known is not None and known in self.hands[opponent]:
            return Counter({known: 1})
        counts = Counter(CARD_COUNTS)
        for card in self.face_up_removed + self.discards["player"] + self.discards["ai"] + self.hands[observer]:
            counts[card] -= 1
        return Counter({card: count for card, count in counts.items() if count > 0})

    def choose_play(self, actor: Actor, policy: str = "belief") -> Play:
        plays = self.legal_plays(actor)
        if policy == "random":
            return self.rng.choice(plays)
        belief = self.belief(actor)
        total = sum(belief.values()) or 1
        own_kept = lambda play: next(card for card in self.hands[actor] if card != play.card) if len(set(self.hands[actor])) > 1 else self.hands[actor][0]

        def score(play: Play) -> float:
            kept = own_kept(play)
            value = kept * 0.62
            if play.card == 1:
                value += 10.5 * belief[play.guess] / total
            elif play.card == 2:
                value += 2.1 if self.known_hand[actor] is None else 0.4
            elif play.card == 3:
                win = sum(count for card, count in belief.items() if kept > card) / total
                lose = sum(count for card, count in belief.items() if kept < card) / total
                value += 9.0 * win - 10.0 * lose
            elif play.card == 4:
                value += 3.2 + (1.2 if kept >= 6 else 0)
            elif play.card == 5:
                if play.target == self.other(actor):
                    value += 10.5 * belief[8] / total + 1.5 * belief[7] / total
                else:
                    value -= 3.0 + kept
            elif play.card == 6:
                expected = sum(card * count for card, count in belief.items()) / total
                value += expected - kept
            elif play.card == 7:
                value -= 0.3
            elif play.card == 8:
                value = -100
            return value

        return max(
            plays,
            key=lambda play: (
                score(play),
                -play.card,
                -(play.guess or 0),
                play.target == "ai",
            ),
        )

    def play(self, actor: Actor, play: Play) -> None:
        if self.phase != f"{actor}_turn":
            raise ValueError("it is not that player's turn")
        if play not in self.legal_plays(actor):
            raise ValueError("illegal Love Letter play")
        self.hands[actor].remove(play.card)
        self.discards[actor].append(play.card)
        opponent = self.other(actor)
        event: dict[str, object] = {
            "actor": actor,
            "card": play.card,
            "target": play.target,
            "guess": play.guess,
            "effect": "none",
        }

        if play.card == 1 and not self.protected[opponent]:
            if self.hands[opponent][0] == play.guess:
                event["effect"] = "guard_hit"
                self._eliminate(opponent, actor, "guard")
            else:
                event["effect"] = "guard_miss"
        elif play.card == 2 and not self.protected[opponent]:
            self.known_hand[actor] = self.hands[opponent][0]
            event["effect"] = "priest_seen"
        elif play.card == 3 and not self.protected[opponent]:
            mine, theirs = self.hands[actor][0], self.hands[opponent][0]
            if mine != theirs:
                loser = actor if mine < theirs else opponent
                event["effect"] = "baron_loss"
                self._eliminate(loser, self.other(loser), "baron")
            else:
                event["effect"] = "baron_tie"
        elif play.card == 4:
            self.protected[actor] = True
            event["effect"] = "protected"
        elif play.card == 5:
            target = play.target
            if target is not None:
                discarded = self.hands[target].pop()
                self.discards[target].append(discarded)
                event["effect"] = "prince_discard"
                event["discarded"] = discarded
                self.known_hand = {"player": None, "ai": None}
                if discarded == 8:
                    self._eliminate(target, self.other(target), "princess")
                else:
                    replacement = self.deck.pop() if self.deck else self.burned
                    self.hands[target].append(replacement)
        elif play.card == 6 and not self.protected[opponent]:
            self.hands[actor], self.hands[opponent] = self.hands[opponent], self.hands[actor]
            self.known_hand[actor] = self.hands[opponent][0]
            self.known_hand[opponent] = self.hands[actor][0]
            event["effect"] = "traded"
        elif play.card == 8:
            self._eliminate(actor, opponent, "princess")

        self.history.append(event)
        if self.phase in {"round_finished", "match_finished"}:
            return
        self.known_hand[opponent] = None
        if not self.deck:
            self._showdown()
            return
        self._begin_turn(opponent)

    def _eliminate(self, loser: Actor, winner: Actor, reason: str) -> None:
        self.eliminated = loser
        self._finish_round(winner, reason)

    def _showdown(self) -> None:
        player = self.hands["player"][0]
        ai = self.hands["ai"][0]
        if player == ai:
            player_total = sum(self.discards["player"])
            ai_total = sum(self.discards["ai"])
            if player_total == ai_total:
                winner: Actor = self.rng.choice(["player", "ai"])
            else:
                winner = "player" if player_total > ai_total else "ai"
            reason = "discard_tiebreak"
        else:
            winner = "player" if player > ai else "ai"
            reason = "showdown"
        self._finish_round(winner, reason)

    def _finish_round(self, winner: Actor, reason: str) -> None:
        self.round_winner = winner
        self.round_reason = reason
        self.scores[winner] += 1
        if self.scores[winner] >= self.target_score:
            self.phase = "match_finished"
            self.games_completed += 1
            if winner == "player":
                self.player_wins += 1
        else:
            self.phase = "round_finished"

    def player_action(self, card: int, target: str | None = None, guess: int | None = None) -> None:
        play = Play(card, target if target in {"player", "ai"} else None, guess)  # type: ignore[arg-type]
        self.play("player", play)
        if self.phase == "ai_turn":
            self.play("ai", self.choose_play("ai"))
