from __future__ import annotations

import random
from dataclasses import dataclass
from itertools import combinations, product
from statistics import mean
from typing import Mapping

from aip.core.information import InformationSet, Observation


CATEGORIES = ("suspect", "room", "method")
DEFAULT_CARDS = {
    "suspect": ("alden", "bria", "cyra", "dax"),
    "room": ("atrium", "gallery", "library", "observatory"),
    "method": ("lantern", "letter_opener", "rope", "vial"),
}


@dataclass(frozen=True, slots=True)
class Suggestion:
    suspect: str
    room: str
    method: str

    @property
    def cards(self) -> frozenset[str]:
        return frozenset((self.suspect, self.room, self.method))


@dataclass(frozen=True, slots=True)
class Response:
    """What the detective learns after making one suggestion."""

    passed_players: tuple[int, ...]
    responder: int | None
    shown_card: str | None


@dataclass(frozen=True, slots=True)
class CaseWorld:
    secret: tuple[str, str, str]
    hands: tuple[frozenset[str], frozenset[str], frozenset[str]]


@dataclass(frozen=True, slots=True)
class SuggestionScore:
    suggestion: Suggestion
    expected_remaining_secrets: float
    worst_remaining_secrets: int
    expected_remaining_worlds: float
    possible_responses: int


@dataclass(frozen=True, slots=True)
class MysteryRun:
    seed: int
    strategy: str
    suggestions: int
    total_turns: int
    solved: bool
    candidate_trace: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class StrategySummary:
    strategy: str
    games: int
    solved_rate: float
    mean_suggestions: float
    mean_total_turns: float
    worst_suggestions: int


class MysterySolver:
    """Enumerate hidden deals and plan suggestions by expected information.

    This deliberately small research model keeps the deduction structure of a
    classic manor mystery while avoiding branded names and map rules.  The
    responder reveals the alphabetically first matching card; because that
    policy is declared and deterministic, posterior filtering is exact.
    """

    def __init__(self, cards: Mapping[str, tuple[str, ...]] | None = None) -> None:
        source = cards or DEFAULT_CARDS
        if set(source) != set(CATEGORIES):
            raise ValueError(f"card categories must be {CATEGORIES}")
        if any(len(source[category]) != 4 for category in CATEGORIES):
            raise ValueError("the local exact prototype needs four cards per category")
        flattened = tuple(card for category in CATEGORIES for card in source[category])
        if len(set(flattened)) != len(flattened):
            raise ValueError("card ids must be unique across categories")
        self.cards = {category: tuple(source[category]) for category in CATEGORIES}
        self.all_cards = flattened
        self.card_order = {card: index for index, card in enumerate(flattened)}
        self.suggestions = tuple(
            Suggestion(suspect, room, method)
            for suspect, room, method in product(*(self.cards[item] for item in CATEGORIES))
        )

    def deal(self, seed: int) -> CaseWorld:
        rng = random.Random(seed)
        secret = tuple(rng.choice(self.cards[category]) for category in CATEGORIES)
        remaining = [card for card in self.all_cards if card not in secret]
        rng.shuffle(remaining)
        hands = (
            frozenset(remaining[0:3]),
            frozenset(remaining[3:6]),
            frozenset(remaining[6:9]),
        )
        return CaseWorld(secret, hands)

    def possible_worlds(self, detective_hand: frozenset[str]) -> tuple[CaseWorld, ...]:
        if len(detective_hand) != 3 or not detective_hand.issubset(self.all_cards):
            raise ValueError("the detective hand must contain three known cards")
        worlds = []
        secret_options = product(
            *(tuple(card for card in self.cards[category] if card not in detective_hand)
              for category in CATEGORIES)
        )
        for secret in secret_options:
            undealt = set(self.all_cards).difference(detective_hand, secret)
            for second_hand_tuple in combinations(sorted(undealt), 3):
                second_hand = frozenset(second_hand_tuple)
                third_hand = frozenset(undealt.difference(second_hand))
                worlds.append(CaseWorld(secret, (detective_hand, second_hand, third_hand)))
        return tuple(worlds)

    def initial_information_set(self, detective_hand: frozenset[str]) -> InformationSet[CaseWorld]:
        worlds = self.possible_worlds(detective_hand)
        return InformationSet(
            key="manor-mystery:start",
            player_id="detective",
            possible_states=worlds,
        )

    def response(self, world: CaseWorld, suggestion: Suggestion) -> Response:
        passed = []
        for player in (1, 2):
            matches = world.hands[player].intersection(suggestion.cards)
            if matches:
                shown = min(matches, key=self.card_order.__getitem__)
                return Response(tuple(passed), player, shown)
            passed.append(player)
        return Response(tuple(passed), None, None)

    def observe(
        self,
        information: InformationSet[CaseWorld],
        suggestion: Suggestion,
        response: Response,
    ) -> InformationSet[CaseWorld]:
        updated = information
        for player in response.passed_players:
            fact = Observation(
                name="player_passed",
                value=(player, suggestion),
                is_public=True,
                timestamp=len(updated.observations) + len(updated.public_history) + 1,
            )
            updated = updated.update(
                fact,
                lambda world, _observation, player=player: not world.hands[player].intersection(
                    suggestion.cards
                ),
            )
        if response.responder is not None and response.shown_card is not None:
            fact = Observation(
                name="card_shown",
                value=(response.responder, response.shown_card, suggestion),
                is_public=False,
                timestamp=len(updated.observations) + len(updated.public_history) + 1,
            )
            updated = updated.update(
                fact,
                lambda world, _observation: self.response(world, suggestion) == response,
            )
        return updated

    @staticmethod
    def remaining_secrets(information: InformationSet[CaseWorld]) -> frozenset[tuple[str, str, str]]:
        return frozenset(world.secret for world in information.possible_states)

    def score_suggestion(
        self,
        information: InformationSet[CaseWorld],
        suggestion: Suggestion,
    ) -> SuggestionScore:
        partitions: dict[Response, list[CaseWorld]] = {}
        for world in information.possible_states:
            partitions.setdefault(self.response(world, suggestion), []).append(world)
        total = len(information.possible_states)
        secret_counts = [len({world.secret for world in worlds}) for worlds in partitions.values()]
        expected_secrets = sum(
            len(worlds) / total * secret_count
            for worlds, secret_count in zip(partitions.values(), secret_counts)
        )
        expected_worlds = sum(len(worlds) * len(worlds) for worlds in partitions.values()) / total
        return SuggestionScore(
            suggestion=suggestion,
            expected_remaining_secrets=expected_secrets,
            worst_remaining_secrets=max(secret_counts),
            expected_remaining_worlds=expected_worlds,
            possible_responses=len(partitions),
        )

    def recommend(
        self,
        information: InformationSet[CaseWorld],
        used: frozenset[Suggestion] = frozenset(),
    ) -> SuggestionScore:
        candidates = [suggestion for suggestion in self.suggestions if suggestion not in used]
        if not candidates:
            raise ValueError("every suggestion has already been used")
        return min(
            (self.score_suggestion(information, suggestion) for suggestion in candidates),
            key=lambda item: (
                item.expected_remaining_secrets,
                item.worst_remaining_secrets,
                item.expected_remaining_worlds,
                item.suggestion.suspect,
                item.suggestion.room,
                item.suggestion.method,
            ),
        )

    def play(self, seed: int, strategy: str = "information", max_suggestions: int = 16) -> MysteryRun:
        if strategy not in {"information", "random"}:
            raise ValueError("strategy must be 'information' or 'random'")
        rng = random.Random(seed + 10_000)
        world = self.deal(seed)
        information = self.initial_information_set(world.hands[0])
        used: set[Suggestion] = set()
        trace = [len(self.remaining_secrets(information))]
        while len(self.remaining_secrets(information)) > 1 and len(used) < max_suggestions:
            available = [item for item in self.suggestions if item not in used]
            suggestion = (
                self.recommend(information, frozenset(used)).suggestion
                if strategy == "information"
                else rng.choice(available)
            )
            used.add(suggestion)
            information = self.observe(information, suggestion, self.response(world, suggestion))
            trace.append(len(self.remaining_secrets(information)))
        solved = self.remaining_secrets(information) == {world.secret}
        return MysteryRun(
            seed=seed,
            strategy=strategy,
            suggestions=len(used),
            total_turns=len(used) + (1 if solved else 0),
            solved=solved,
            candidate_trace=tuple(trace),
        )

    def compare(self, games: int = 100, seed: int = 0) -> tuple[StrategySummary, ...]:
        if games < 1:
            raise ValueError("games must be positive")
        summaries = []
        for strategy in ("information", "random"):
            runs = [self.play(seed + index, strategy) for index in range(games)]
            summaries.append(
                StrategySummary(
                    strategy=strategy,
                    games=games,
                    solved_rate=sum(run.solved for run in runs) / games,
                    mean_suggestions=mean(run.suggestions for run in runs),
                    mean_total_turns=mean(run.total_turns for run in runs),
                    worst_suggestions=max(run.suggestions for run in runs),
                )
            )
        return tuple(summaries)
