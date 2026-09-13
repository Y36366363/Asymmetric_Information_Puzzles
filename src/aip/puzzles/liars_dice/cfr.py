"""CFR adapter for the tractable one-die stepwise-bidding Liar's Dice variant."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import json
from pathlib import Path
from typing import Hashable, Mapping

from aip.core.cfr import (
    CFRCertificationGate,
    CFRGateReport,
    CFRGameProperties,
    CFRResult,
    CFRThresholds,
    ChanceSamplingCFRTrainer,
    EquilibriumEvaluation,
)


Bid = tuple[int, int]
LiarAction = str | Bid
FACES = tuple(range(1, 7))
BIDS: tuple[Bid, ...] = tuple(
    (quantity, face) for quantity in (1, 2) for face in FACES
)
OPENING_BIDS: tuple[Bid, ...] = tuple((1, face) for face in FACES)


@dataclass(frozen=True, slots=True)
class OneDieLiarState:
    dice: tuple[int, int] | None = None
    bids: tuple[Bid, ...] = ()
    challenger: int | None = None


class OneDieLiarDiceCFRGame:
    """One die each with a deliberately reduced, auditable raise rule.

    Ones are wild for faces 2--6. The opener chooses a quantity-one bid. Later
    players challenge or advance exactly one step on the quantity/face ladder.
    This is a separate reduced mode, not the existing five-die ruleset.
    """

    def initial_state(self) -> OneDieLiarState:
        return OneDieLiarState()

    def is_terminal(self, state: OneDieLiarState) -> bool:
        return state.challenger is not None

    def utility_player_zero(self, state: OneDieLiarState) -> float:
        if state.challenger is None or state.dice is None or not state.bids:
            raise ValueError("utility is defined only after a bid is challenged")
        quantity, face = state.bids[-1]
        matches = sum(
            die == face or (face != 1 and die == 1) for die in state.dice
        )
        bidder = 1 - state.challenger
        winner = bidder if matches >= quantity else state.challenger
        return 1.0 if winner == 0 else -1.0

    def current_player(self, state: OneDieLiarState) -> int | None:
        if state.dice is None or self.is_terminal(state):
            return None
        return len(state.bids) % 2

    def chance_outcomes(
        self, state: OneDieLiarState
    ) -> tuple[tuple[Hashable, float], ...]:
        if state.dice is not None:
            return ()
        return tuple(((first, second), 1 / 36) for first in FACES for second in FACES)

    def legal_actions(self, state: OneDieLiarState) -> tuple[LiarAction, ...]:
        if state.dice is None or self.is_terminal(state):
            return ()
        if not state.bids:
            return OPENING_BIDS
        index = BIDS.index(state.bids[-1])
        return ("challenge",) if index == len(BIDS) - 1 else (
            "challenge",
            BIDS[index + 1],
        )

    def information_set(self, state: OneDieLiarState) -> Hashable:
        player = self.current_player(state)
        if player is None or state.dice is None:
            raise ValueError("chance and terminal states have no player information set")
        return state.dice[player], state.bids

    def next_state(
        self, state: OneDieLiarState, action: LiarAction
    ) -> OneDieLiarState:
        if state.dice is None:
            if not isinstance(action, tuple) or len(action) != 2:
                raise ValueError("chance action must deal one die to each player")
            return OneDieLiarState((int(action[0]), int(action[1])))
        if action not in self.legal_actions(state):
            raise ValueError(f"illegal one-die Liar's Dice action: {action!r}")
        if action == "challenge":
            return OneDieLiarState(
                state.dice, state.bids, challenger=self.current_player(state)
            )
        assert isinstance(action, tuple)
        return OneDieLiarState(state.dice, state.bids + (action,))


def train_one_die_liar_cfr(
    iterations: int = 20_000, *, seed: int = 20260908
) -> CFRResult:
    return ChanceSamplingCFRTrainer(
        OneDieLiarDiceCFRGame(), seed=seed
    ).train(iterations)


def save_one_die_liar_policy(
    result: CFRResult,
    destination: Path,
    *,
    certification: CFRGateReport,
) -> None:
    """Write a deterministic, runtime-loadable CFR artifact."""

    records = []
    for (player, information_set), distribution in sorted(
        result.policy.items(), key=lambda item: repr(item[0])
    ):
        die, bids = information_set
        records.append({
            "player": player,
            "die": die,
            "bids": [list(bid) for bid in bids],
            "distribution": [
                {
                    "action": action if action == "challenge" else list(action),
                    "probability": probability,
                }
                for action, probability in distribution.items()
            ],
            "visits": result.information_set_visits[(player, information_set)],
        })
    payload = {
        "schemaVersion": 1,
        "game": "one_die_stepwise_liars_dice",
        "iterations": result.iterations,
        "averagePositiveRegret": list(result.average_positive_regret),
        "certification": {
            "passed": certification.passed,
            "failures": list(certification.failures),
            "evaluation": (
                certification.evaluation.to_report()
                if certification.evaluation is not None
                else None
            ),
        },
        "policy": records,
    }
    destination.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def load_one_die_liar_policy(source: Path) -> CFRResult:
    payload = json.loads(source.read_text(encoding="utf-8"))
    if payload.get("schemaVersion") != 1 or payload.get("game") != "one_die_stepwise_liars_dice":
        raise ValueError("unsupported one-die Liar's Dice CFR artifact")
    certification = payload.get("certification", {})
    if not certification.get("passed") or certification.get("failures"):
        raise ValueError("one-die Liar's Dice artifact is not certified")
    policy = {}
    visits = {}
    for record in payload["policy"]:
        information_set = (
            int(record["die"]),
            tuple(tuple(int(value) for value in bid) for bid in record["bids"]),
        )
        key = (int(record["player"]), information_set)
        if key in policy:
            raise ValueError("duplicate information set in CFR artifact")
        distribution = {}
        for item in record["distribution"]:
            raw_action = item["action"]
            action = (
                "challenge"
                if raw_action == "challenge"
                else tuple(int(value) for value in raw_action)
            )
            distribution[action] = float(item["probability"])
        policy[key] = distribution
        visits[key] = int(record["visits"])
    regrets = tuple(float(value) for value in payload["averagePositiveRegret"])
    if len(regrets) != 2:
        raise ValueError("CFR artifact must contain two player regret diagnostics")
    return CFRResult(
        iterations=int(payload["iterations"]),
        policy=policy,
        information_set_visits=visits,
        average_positive_regret=(regrets[0], regrets[1]),
    )


def _best_response_value(
    policy: Mapping[tuple[int, Hashable], Mapping[Hashable, float]], hero: int
) -> float:
    """Exactly traverse one player's best response to the fixed opponent."""

    game = OneDieLiarDiceCFRGame()

    def value_for_own_die(own_die: int) -> float:
        def transition_value(
            bids: tuple[Bid, ...], weights: tuple[float, ...], action: LiarAction
        ) -> float:
            actor = len(bids) % 2
            if action == "challenge":
                total = 0.0
                for opponent_die, weight in zip(FACES, weights):
                    dice = (
                        (own_die, opponent_die)
                        if hero == 0
                        else (opponent_die, own_die)
                    )
                    terminal = OneDieLiarState(dice, bids, challenger=actor)
                    utility = game.utility_player_zero(terminal)
                    total += weight * (utility if hero == 0 else -utility)
                return total
            assert isinstance(action, tuple)
            return recurse(bids + (action,), weights)

        @lru_cache(maxsize=None)
        def recurse(bids: tuple[Bid, ...], weights: tuple[float, ...]) -> float:
            representative_dice = (
                (own_die, 1) if hero == 0 else (1, own_die)
            )
            state = OneDieLiarState(representative_dice, bids)
            actor = game.current_player(state)
            actions = game.legal_actions(state)
            if actor == hero:
                return max(transition_value(bids, weights, action) for action in actions)
            total = 0.0
            for action in actions:
                next_weights = tuple(
                    weight * float(policy[(actor, (die, bids))][action])
                    for die, weight in zip(FACES, weights)
                )
                total += transition_value(bids, next_weights, action)
            return total

        return recurse((), tuple(1 / 6 for _ in FACES))

    return sum(value_for_own_die(die) for die in FACES) / 6


def one_die_liar_exploitability(result: CFRResult) -> float:
    """Return epsilon = half NashConv from independent exact best responses."""

    return one_die_liar_evaluation(result).exploitability


def one_die_liar_evaluation(result: CFRResult) -> EquilibriumEvaluation:
    """Return exact deviation gains for both seats against the CFR profile."""

    best_zero = _best_response_value(result.policy, 0)
    best_one = _best_response_value(result.policy, 1)
    game = OneDieLiarDiceCFRGame()

    def profile_value(state: OneDieLiarState) -> float:
        if game.is_terminal(state):
            return game.utility_player_zero(state)
        player = game.current_player(state)
        if player is None:
            return sum(
                probability * profile_value(game.next_state(state, action))
                for action, probability in game.chance_outcomes(state)
            )
        distribution = result.policy[(player, game.information_set(state))]
        return sum(
            float(distribution[action]) * profile_value(game.next_state(state, action))
            for action in game.legal_actions(state)
        )

    value_zero = profile_value(game.initial_state())
    return EquilibriumEvaluation(
        player_0_deviation_gain=best_zero - value_zero,
        player_1_deviation_gain=best_one + value_zero,
    )


def required_one_die_information_sets() -> frozenset[tuple[int, Hashable]]:
    histories: set[tuple[Bid, ...]] = {()}
    for opening in OPENING_BIDS:
        history = (opening,)
        histories.add(history)
        for next_bid in BIDS[BIDS.index(opening) + 1 :]:
            history += (next_bid,)
            histories.add(history)
    return frozenset(
        (len(history) % 2, (die, history))
        for history in histories
        for die in FACES
    )


def certify_one_die_liar_cfr(
    result: CFRResult, thresholds: CFRThresholds | None = None
) -> CFRGateReport:
    required = required_one_die_information_sets()
    gate = CFRCertificationGate(
        thresholds
        or CFRThresholds(
            min_iterations=20_000,
            min_information_sets=len(required),
            min_visits_per_information_set=100,
            max_average_positive_regret=0.03,
            max_exploitability=0.01,
        )
    )
    return gate.evaluate(
        result,
        evaluation=one_die_liar_evaluation(result),
        required_information_sets=required,
        exact_information_sets=True,
        game_properties=CFRGameProperties(
            players=2,
            finite=True,
            zero_sum_or_constant_sum=True,
            perfect_recall=True,
        ),
    )
