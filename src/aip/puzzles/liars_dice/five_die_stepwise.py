"""Five-die stepwise Liar's Dice adapter and independent histogram oracle."""

from __future__ import annotations

from dataclasses import dataclass
from math import factorial, fsum, isfinite
from typing import Hashable, Mapping

from aip.core import ExternalSamplingCFRTrainer
from aip.core.evaluation import ActionValueReport, StrategyProfile


Bid = tuple[int, int]
LiarAction = str | Bid
Histogram = tuple[int, int, int, int, int, int]
FACES = tuple(range(1, 7))
BIDS: tuple[Bid, ...] = tuple(
    (quantity, face) for quantity in range(1, 11) for face in FACES
)
OPENING_BIDS: tuple[Bid, ...] = tuple((1, face) for face in FACES)


def _histograms(total: int, bins: int = 6) -> tuple[Histogram, ...]:
    result = []

    def build(prefix: tuple[int, ...], left: int) -> None:
        if len(prefix) == bins - 1:
            result.append(prefix + (left,))
            return
        for count in range(left + 1):
            build(prefix + (count,), left - count)

    build((), total)
    return tuple(result)  # type: ignore[return-value]


HISTOGRAMS = _histograms(5)


def _histogram_probability(histogram: Histogram) -> float:
    arrangements = factorial(5)
    for count in histogram:
        arrangements //= factorial(count)
    return arrangements / (6**5)


HISTOGRAM_OUTCOMES: tuple[tuple[Histogram, float], ...] = tuple(
    (histogram, _histogram_probability(histogram)) for histogram in HISTOGRAMS
)
HISTOGRAM_PROBABILITIES = tuple(probability for _, probability in HISTOGRAM_OUTCOMES)


@dataclass(frozen=True, slots=True)
class FiveDieStepwiseState:
    hands: tuple[Histogram, ...] = ()
    bids: tuple[Bid, ...] = ()
    challenger: int | None = None


class FiveDieStepwiseLiarGame:
    """Frozen two-player five-die, wild-one, next-bid-only research variant."""

    RULES_ID = "five_die_liar_two_player_stepwise_v1"

    def initial_state(self) -> FiveDieStepwiseState:
        return FiveDieStepwiseState()

    def is_terminal(self, state: FiveDieStepwiseState) -> bool:
        return state.challenger is not None

    def utility_player_zero(self, state: FiveDieStepwiseState) -> float:
        if len(state.hands) != 2 or state.challenger is None or not state.bids:
            raise ValueError("utility requires two hands and a challenged bid")
        quantity, face = state.bids[-1]
        face_index = face - 1
        matches = sum(hand[face_index] for hand in state.hands)
        if face != 1:
            matches += sum(hand[0] for hand in state.hands)
        bidder = 1 - state.challenger
        winner = bidder if matches >= quantity else state.challenger
        return 1.0 if winner == 0 else -1.0

    def current_player(self, state: FiveDieStepwiseState) -> int | None:
        if len(state.hands) < 2 or self.is_terminal(state):
            return None
        return len(state.bids) % 2

    def chance_outcomes(
        self, state: FiveDieStepwiseState
    ) -> tuple[tuple[Hashable, float], ...]:
        if len(state.hands) < 2 and not self.is_terminal(state):
            return HISTOGRAM_OUTCOMES
        return ()

    def legal_actions(self, state: FiveDieStepwiseState) -> tuple[LiarAction, ...]:
        if len(state.hands) != 2 or self.is_terminal(state):
            return ()
        if not state.bids:
            return OPENING_BIDS
        index = BIDS.index(state.bids[-1])
        if index == len(BIDS) - 1:
            return ("challenge",)
        return "challenge", BIDS[index + 1]

    def information_set(self, state: FiveDieStepwiseState) -> Hashable:
        player = self.current_player(state)
        if player is None:
            raise ValueError("chance and terminal states have no information set")
        return state.hands[player], state.bids

    def next_state(
        self, state: FiveDieStepwiseState, action: Hashable
    ) -> FiveDieStepwiseState:
        if len(state.hands) < 2:
            if action not in HISTOGRAMS:
                raise ValueError("chance action must be a five-die histogram")
            return FiveDieStepwiseState(state.hands + (action,))  # type: ignore[arg-type]
        if action not in self.legal_actions(state):
            raise ValueError(f"illegal five-die stepwise action: {action!r}")
        if action == "challenge":
            return FiveDieStepwiseState(
                state.hands, state.bids, challenger=self.current_player(state)
            )
        assert isinstance(action, tuple)
        return FiveDieStepwiseState(state.hands, state.bids + (action,))


def required_five_die_information_sets() -> frozenset[tuple[int, Hashable]]:
    histories: set[tuple[Bid, ...]] = {()}
    for opening in OPENING_BIDS:
        history = (opening,)
        histories.add(history)
        for next_bid in BIDS[BIDS.index(opening) + 1 :]:
            history += (next_bid,)
            histories.add(history)
    return frozenset(
        (len(history) % 2, (histogram, history))
        for history in histories
        for histogram in HISTOGRAMS
    )


def complete_five_die_policy(
    sampled_policy: StrategyProfile,
) -> dict[tuple[int, Hashable], dict[Hashable, float]]:
    """Complete an MCCFR candidate uniformly at unvisited information sets."""

    game = FiveDieStepwiseLiarGame()
    completed = {}
    for key in required_five_die_information_sets():
        player, (histogram, bids) = key
        opponent = HISTOGRAMS[0]
        hands = (histogram, opponent) if player == 0 else (opponent, histogram)
        actions = game.legal_actions(FiveDieStepwiseState(hands, bids))
        observed = sampled_policy.get(key)
        if observed is None:
            completed[key] = {action: 1 / len(actions) for action in actions}
        else:
            if set(observed) != set(actions):
                raise ValueError("sampled policy has inconsistent legal actions")
            completed[key] = {
                action: float(observed[action]) for action in actions
            }
    extras = set(sampled_policy) - set(completed)
    if extras:
        raise ValueError("sampled policy contains unknown information sets")
    return completed


def train_five_die_external_sampling(
    iterations: int, *, seed: int = 20261008
):
    return ExternalSamplingCFRTrainer(
        FiveDieStepwiseLiarGame(), seed=seed
    ).train(iterations)


def _validate_profile(profile: StrategyProfile) -> None:
    required = required_five_die_information_sets()
    if set(profile) != set(required):
        raise ValueError("five-die profile must cover every audited information set")
    game = FiveDieStepwiseLiarGame()
    for key in required:
        player, (histogram, bids) = key
        other = HISTOGRAMS[0]
        hands = (histogram, other) if player == 0 else (other, histogram)
        actions = game.legal_actions(FiveDieStepwiseState(hands, bids))
        distribution = profile[key]
        probabilities = tuple(float(distribution[action]) for action in actions)
        if (
            set(distribution) != set(actions)
            or any(not isfinite(value) or value < 0 for value in probabilities)
            or abs(fsum(probabilities) - 1.0) > 1e-9
        ):
            raise ValueError("invalid five-die behavioral distribution")


def _terminal_hero_utility(
    hero: int,
    own_hand: Histogram,
    opponent_hand: Histogram,
    bid: Bid,
    challenger: int,
) -> float:
    hands = (
        (own_hand, opponent_hand)
        if hero == 0
        else (opponent_hand, own_hand)
    )
    utility = FiveDieStepwiseLiarGame().utility_player_zero(
        FiveDieStepwiseState(hands, (bid,), challenger=challenger)
    )
    return utility if hero == 0 else -utility


class FiveDieStepwiseIndependentEvaluator:
    """Exact best response over all 252 private histograms and 345 bid chains."""

    evaluator_id = "five_die_stepwise_histogram_best_response_v1"

    def __init__(self) -> None:
        self._profile_id: int | None = None
        self._value: float | None = None
        self._responses: dict[int, float] = {}
        self._action_values: dict[
            tuple[int, Hashable], dict[Hashable, float]
        ] = {}

    def _reset(self, profile: StrategyProfile) -> None:
        profile_id = id(profile)
        if self._profile_id != profile_id:
            _validate_profile(profile)
            self._profile_id = profile_id
            self._value = None
            self._responses = {}
            self._action_values = {}

    @staticmethod
    def _terminal_value(
        hero: int,
        own_hand: Histogram,
        weights: tuple[float, ...],
        bid: Bid,
        challenger: int,
    ) -> float:
        return fsum(
            weight
            * _terminal_hero_utility(
                hero, own_hand, opponent_hand, bid, challenger
            )
            for opponent_hand, weight in zip(HISTOGRAMS, weights)
        )

    def _value_for_hand(
        self,
        profile: StrategyProfile,
        hero: int,
        own_hand: Histogram,
        *,
        best_response: bool,
        record_actions: bool,
    ) -> float:
        def recurse(bids: tuple[Bid, ...], weights: tuple[float, ...]) -> float:
            actor = len(bids) % 2
            if not bids:
                actions: tuple[LiarAction, ...] = OPENING_BIDS
            else:
                index = BIDS.index(bids[-1])
                actions = (
                    ("challenge",)
                    if index == len(BIDS) - 1
                    else ("challenge", BIDS[index + 1])
                )

            def action_value(action: LiarAction) -> float:
                if action == "challenge":
                    return self._terminal_value(
                        hero, own_hand, weights, bids[-1], actor
                    )
                assert isinstance(action, tuple)
                return recurse(bids + (action,), weights)

            if actor == hero:
                values = {action: action_value(action) for action in actions}
                reach = fsum(weights)
                if record_actions:
                    self._action_values[(hero, (own_hand, bids))] = {
                        action: value / reach if reach > 0 else 0.0
                        for action, value in values.items()
                    }
                if best_response:
                    return max(values.values())
                distribution = profile[(actor, (own_hand, bids))]
                return fsum(
                    float(distribution[action]) * values[action]
                    for action in actions
                )

            total = 0.0
            for action in actions:
                next_weights = tuple(
                    weight
                    * float(profile[(actor, (opponent_hand, bids))][action])
                    for opponent_hand, weight in zip(HISTOGRAMS, weights)
                )
                if action == "challenge":
                    total += self._terminal_value(
                        hero, own_hand, next_weights, bids[-1], actor
                    )
                else:
                    assert isinstance(action, tuple)
                    total += recurse(bids + (action,), next_weights)
            return total

        initial_weights = HISTOGRAM_PROBABILITIES
        return recurse((), initial_weights)

    def expected_value(self, profile: StrategyProfile) -> float:
        self._reset(profile)
        if self._value is None:
            self._value = fsum(
                probability
                * self._value_for_hand(
                    profile,
                    0,
                    hand,
                    best_response=False,
                    record_actions=False,
                )
                for hand, probability in HISTOGRAM_OUTCOMES
            )
        return self._value

    def best_response(self, profile: StrategyProfile, player: int) -> float:
        if player not in (0, 1):
            raise ValueError("best-response player must be zero or one")
        self._reset(profile)
        if player not in self._responses:
            self._responses[player] = fsum(
                probability
                * self._value_for_hand(
                    profile,
                    player,
                    hand,
                    best_response=True,
                    record_actions=True,
                )
                for hand, probability in HISTOGRAM_OUTCOMES
            )
        return self._responses[player]

    def nash_conv(self, profile: StrategyProfile) -> float:
        return self.best_response(profile, 0) + self.best_response(profile, 1)

    def exploitability(self, profile: StrategyProfile) -> float:
        return self.nash_conv(profile) / 2

    def action_values(self, profile: StrategyProfile) -> ActionValueReport:
        self.best_response(profile, 0)
        self.best_response(profile, 1)
        return self._action_values
