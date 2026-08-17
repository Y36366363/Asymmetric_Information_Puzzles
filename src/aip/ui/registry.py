from __future__ import annotations

import random
import threading
import uuid
from dataclasses import dataclass
from itertools import combinations
from math import comb
from typing import Callable, Protocol

from aip.puzzles.cases.models import CLASSROOM_BANKER, CaseGameRules, RiskPreferences
from aip.puzzles.cases.solver import CaseGameAnalyzer
from aip.puzzles.mastermind.models import CodeRules
from aip.puzzles.mastermind.solver import MastermindSolver
from aip.puzzles.battleship.models import FleetRules, ShipPlacement, ShotOutcome
from aip.puzzles.battleship.solver import HiddenFleetBoard, ProbabilityDensityAI
from aip.puzzles.hidden_pursuit.models import EDGES, NODE_POSITIONS, HiddenPursuitRules
from aip.puzzles.hidden_pursuit.solver import PursuitState
from aip.puzzles.love_letter.solver import CARD_COUNTS, CARD_NAMES, LoveLetterGame
from aip.puzzles.investment import InvestmentTournament
from aip.puzzles.guess_who import DEFAULT_QUESTIONS, DEFAULT_ROSTER, GuessWhoSolver
from aip.puzzles.goofspiel import GoofspielSolver
from aip.puzzles.kuhn_poker import equilibrium_policy
from aip.puzzles.pirates.models import PirateRules
from aip.puzzles.pirates.solver import PirateSolver
from aip.puzzles.worm.solver import WormSolver


def _whole_int(value: object, label: str) -> int:
    try:
        number = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{label} must be a whole number") from error
    if not number.is_integer():
        raise ValueError(f"{label} must be a whole number")
    return int(number)


class PlayableSession(Protocol):
    def snapshot(self) -> dict[str, object]: ...

    def act(self, action: str, payload: dict[str, object]) -> dict[str, object]: ...


@dataclass(frozen=True, slots=True)
class GameDescriptor:
    game_id: str
    title: str
    summary: str
    player_mode: str
    available: bool = True

    def as_dict(self) -> dict[str, object]:
        return {
            "id": self.game_id,
            "title": self.title,
            "summary": self.summary,
            "playerMode": self.player_mode,
            "available": self.available,
        }


SessionFactory = Callable[[dict[str, object]], PlayableSession]


def validate_public_state(
    state: object, *, expected_game_id: str | None = None
) -> dict[str, object]:
    """Validate the small cross-game contract consumed by every UI runtime."""

    if not isinstance(state, dict):
        raise ValueError("playable session snapshots must be objects")
    game_id = state.get("gameId")
    if not isinstance(game_id, str) or not game_id:
        raise ValueError("playable session snapshots need a non-empty gameId")
    if expected_game_id is not None and game_id != expected_game_id:
        raise ValueError(
            f"session returned gameId {game_id!r}; expected {expected_game_id!r}"
        )
    phase = state.get("phase")
    if not isinstance(phase, str) or not phase:
        raise ValueError("playable session snapshots need a non-empty phase")
    legal_actions = state.get("legalActions")
    if (
        not isinstance(legal_actions, list)
        or any(not isinstance(action, str) or not action for action in legal_actions)
        or len(legal_actions) != len(set(legal_actions))
    ):
        raise ValueError("playable session snapshots need unique string legalActions")
    return state

GAME_DISPLAY_ORDER = {
    "cases": 1,
    "blackjack": 2,
    "restricted-rps": 3,
    "mastermind": 4,
    "guess-who": 5,
    "hidden-pursuit": 6,
    "battleship": 7,
    "e-card": 8,
    "pirates": 9,
    "love-letter": 10,
    "investment": 11,
    "kuhn-poker": 12,
    "liars-dice": 13,
    "goofspiel": 14,
    "worm": 15,
    "auction": 16,
}


class GameRegistry:
    """Maps stable game identifiers to isolated playable session factories."""

    def __init__(self) -> None:
        self._entries: dict[str, tuple[GameDescriptor, SessionFactory]] = {}

    def register(self, descriptor: GameDescriptor, factory: SessionFactory) -> None:
        if descriptor.game_id in self._entries:
            raise ValueError(f"duplicate game id: {descriptor.game_id}")
        self._entries[descriptor.game_id] = (descriptor, factory)

    def list_games(self) -> tuple[GameDescriptor, ...]:
        descriptors = (descriptor for descriptor, _factory in self._entries.values())
        return tuple(sorted(descriptors, key=lambda item: GAME_DISPLAY_ORDER.get(item.game_id, 999)))

    def create(self, game_id: str, options: dict[str, object]) -> PlayableSession:
        try:
            descriptor, factory = self._entries[game_id]
        except KeyError as error:
            raise ValueError(f"unknown game: {game_id}") from error
        if not descriptor.available:
            raise ValueError(f"game is not playable yet: {game_id}")
        return factory(options)


class LocalGameService:
    """Thread-safe in-memory session facade used by the HTTP layer and tests."""

    def __init__(self, registry: GameRegistry, max_sessions: int = 256) -> None:
        if max_sessions < 1:
            raise ValueError("max_sessions must be positive")
        self.registry = registry
        self.max_sessions = max_sessions
        self._sessions: dict[str, tuple[str, PlayableSession]] = {}
        self._lock = threading.RLock()

    def games(self) -> list[dict[str, object]]:
        return [game.as_dict() for game in self.registry.list_games()]

    def create_session(
        self, game_id: str, options: dict[str, object] | None = None
    ) -> dict[str, object]:
        session = self.registry.create(game_id, options or {})
        state = validate_public_state(session.snapshot(), expected_game_id=game_id)
        session_id = uuid.uuid4().hex
        with self._lock:
            while len(self._sessions) >= self.max_sessions:
                self._sessions.pop(next(iter(self._sessions)))
            self._sessions[session_id] = (game_id, session)
        return {"sessionId": session_id, "state": state}

    def snapshot(self, session_id: str) -> dict[str, object]:
        with self._lock:
            game_id, session = self._get(session_id)
            return validate_public_state(session.snapshot(), expected_game_id=game_id)

    def act(
        self, session_id: str, action: str, payload: dict[str, object] | None = None
    ) -> dict[str, object]:
        with self._lock:
            game_id, session = self._get(session_id)
            return validate_public_state(
                session.act(action, payload or {}), expected_game_id=game_id
            )

    def _get(self, session_id: str) -> tuple[str, PlayableSession]:
        try:
            entry = self._sessions.pop(session_id)
        except KeyError as error:
            raise ValueError("unknown or expired session") from error
        self._sessions[session_id] = entry
        return entry


class CaseGameSession:
    """Human-driven 26-case game; hidden values never enter public snapshots."""

    def __init__(self, options: dict[str, object]) -> None:
        self.rules = CaseGameRules()
        self.analyzer = CaseGameAnalyzer()
        self.risk = RiskPreferences(self._optional_float(options, "riskTolerance"))
        self.seed = int(options.get("seed", random.SystemRandom().randrange(2**32)))
        self._rng = random.Random(self.seed)
        values = list(self.rules.prizes)
        self._rng.shuffle(values)
        self._values = dict(zip(range(1, len(values) + 1), values))
        self.chosen_case: int | None = None
        self.opened: dict[int, float] = {}
        self.round_index = 0
        self.opened_this_round = 0
        self.phase = "choose"
        self.current_offer: float | None = None
        self.payout: float | None = None
        self.result: dict[str, object] | None = None
        self.history: list[dict[str, object]] = []

    @staticmethod
    def _optional_float(options: dict[str, object], key: str) -> float | None:
        value = options.get(key)
        if value is None or value == "":
            return None
        return float(value)

    def act(self, action: str, payload: dict[str, object]) -> dict[str, object]:
        if action == "choose_case":
            self._choose_case(int(payload.get("caseId", 0)))
        elif action == "open_case":
            self._open_case(int(payload.get("caseId", 0)))
        elif action == "deal":
            self._deal()
        elif action == "no_deal":
            self._no_deal()
        else:
            raise ValueError(f"unknown action: {action}")
        return self.snapshot()

    def _choose_case(self, case_id: int) -> None:
        if self.phase != "choose" or case_id not in self._values:
            raise ValueError("choose one unopened case at the start of the game")
        self.chosen_case = case_id
        self.phase = "opening"
        self.history.append({"kind": "choose", "caseId": case_id})

    def _open_case(self, case_id: int) -> None:
        if self.phase != "opening":
            raise ValueError("cases can only be opened during the opening phase")
        if case_id not in self._values or case_id == self.chosen_case or case_id in self.opened:
            raise ValueError("that case cannot be opened")
        value = self._values[case_id]
        self.opened[case_id] = value
        self.opened_this_round += 1
        self.history.append({"kind": "reveal", "caseId": case_id, "value": value})
        target = self.rules.cases_opened_per_round[self.round_index]
        if self.opened_this_round == target:
            remaining = self._remaining_values()
            self.current_offer = self.analyzer.make_offer(
                remaining, self.round_index, CLASSROOM_BANKER, self._rng
            )
            self.phase = "offer"
            self.history.append(
                {
                    "kind": "offer",
                    "round": self.round_index + 1,
                    "value": self.current_offer,
                }
            )

    def _deal(self) -> None:
        if self.phase != "offer" or self.current_offer is None:
            raise ValueError("there is no offer to accept")
        self.payout = self.current_offer
        self.phase = "finished"
        self.result = {"kind": "deal", "payout": self.payout, "offer": self.current_offer}
        self.history.append({"kind": "deal", "value": self.payout})

    def _no_deal(self) -> None:
        if self.phase != "offer":
            raise ValueError("there is no offer to reject")
        self.history.append({"kind": "no_deal", "round": self.round_index + 1})
        if len(self._remaining_values()) == 1:
            self.payout = self._values[self.chosen_case]  # type: ignore[index]
            self.phase = "finished"
            self.result = {"kind": "kept_case", "payout": self.payout, "chosenCase": self.chosen_case}
            self.history.append({"kind": "case_payout", "caseId": self.chosen_case, "value": self.payout})
            return
        self.round_index += 1
        self.opened_this_round = 0
        self.current_offer = None
        self.phase = "opening"

    def _remaining_values(self) -> tuple[float, ...]:
        return tuple(
            value for case_id, value in self._values.items() if case_id not in self.opened
        )

    def snapshot(self) -> dict[str, object]:
        cases = []
        for case_id in self._values:
            status = "opened" if case_id in self.opened else "closed"
            if case_id == self.chosen_case:
                status = "chosen"
            case: dict[str, object] = {"id": case_id, "status": status}
            if case_id in self.opened:
                case["value"] = self.opened[case_id]
            if self.phase == "finished" and case_id == self.chosen_case:
                case["value"] = self._values[case_id]
            cases.append(case)

        metrics = None
        if self.phase == "offer" and self.current_offer is not None:
            analysis = self.analyzer.analyze_offer(
                self._remaining_values(), self.current_offer, self.risk
            )
            metrics = {
                "expectedValue": analysis.expected_value,
                "standardDeviation": analysis.standard_deviation,
                "certaintyEquivalent": analysis.certainty_equivalent,
                "offerRatio": analysis.offer_to_expected_value,
                "chanceToBeatOffer": analysis.probability_case_beats_offer,
                "reservationRecommendation": analysis.reservation_recommendation,
            }

        target = (
            self.rules.cases_opened_per_round[self.round_index]
            if self.phase in {"opening", "offer"}
            else 0
        )
        remaining_prizes = sorted(self._remaining_values())
        return {
            "gameId": "cases",
            "phase": self.phase,
            "round": self.round_index + 1,
            "chosenCase": self.chosen_case,
            "cases": cases,
            "prizeBoard": [
                {"value": value, "remaining": value in remaining_prizes}
                for value in self.rules.prizes
            ],
            "openTarget": target,
            "openedThisRound": self.opened_this_round,
            "opensRemaining": max(0, target - self.opened_this_round),
            "offer": self.current_offer,
            "isFinalOffer": self.phase == "offer" and len(remaining_prizes) == 1,
            "metrics": metrics,
            "payout": self.payout,
            "result": dict(self.result) if self.result else None,
            "history": list(self.history),
            "riskTolerance": self.risk.risk_tolerance,
            "legalActions": {
                "choose": ["choose_case"],
                "opening": ["open_case"],
                "offer": ["deal", "no_deal"],
                "finished": [],
            }[self.phase],
        }


class WormGameSession:
    """Playable hidden-worm search with a public belief-state companion."""

    def __init__(self, options: dict[str, object]) -> None:
        self.hole_count = _whole_int(options.get("holes", 5), "holes")
        if self.hole_count < 2 or self.hole_count > 12:
            raise ValueError("holes must be between 2 and 12")
        self._caught_hole: int | None = None
        self.possible_positions = set(range(1, self.hole_count + 1))
        self.turn = 0
        self.phase = "playing"
        self.history: list[dict[str, object]] = []
        self.strategy = WormSolver().solve(self.hole_count).checks
        self.followed_strategy = True

    def act(self, action: str, payload: dict[str, object]) -> dict[str, object]:
        if action != "check_hole":
            raise ValueError(f"unknown action: {action}")
        self._check_hole(_whole_int(payload.get("holeId", 0), "holeId"))
        return self.snapshot()

    def _check_hole(self, hole_id: int) -> None:
        if self.phase != "playing":
            raise ValueError("the worm has already been caught")
        if hole_id < 1 or hole_id > self.hole_count:
            raise ValueError("hole is outside the board")
        suggested = self.strategy[self.turn] if self.turn < len(self.strategy) else None
        self.followed_strategy = self.followed_strategy and hole_id == suggested
        self.turn += 1
        guaranteed_capture = self.possible_positions.issubset({hole_id})
        if guaranteed_capture:
            self.phase = "finished"
            self.possible_positions = {hole_id}
            self._caught_hole = hole_id
            self.history.append(
                {
                    "turn": self.turn,
                    "holeId": hole_id,
                    "result": "caught",
                    "guaranteed": guaranteed_capture,
                }
            )
            return

        self.history.append({"turn": self.turn, "holeId": hole_id, "result": "miss"})
        self.possible_positions = self._after_miss(
            self.possible_positions, hole_id, self.hole_count
        )

    @staticmethod
    def _after_miss(
        positions: set[int], checked: int, hole_count: int
    ) -> set[int]:
        destinations: set[int] = set()
        for position in positions.difference({checked}):
            if position > 1:
                destinations.add(position - 1)
            if position < hole_count:
                destinations.add(position + 1)
        return destinations

    def snapshot(self) -> dict[str, object]:
        next_suggestion = None
        if (
            self.phase == "playing"
            and self.followed_strategy
            and self.turn < len(self.strategy)
        ):
            next_suggestion = self.strategy[self.turn]
        return {
            "gameId": "worm",
            "mode": "adversarial",
            "phase": self.phase,
            "turn": self.turn,
            "holes": [
                {
                    "id": hole_id,
                    "possible": hole_id in self.possible_positions,
                    "worm": self.phase == "finished" and hole_id == self._caught_hole,
                }
                for hole_id in range(1, self.hole_count + 1)
            ],
            "possiblePositions": sorted(self.possible_positions),
            "strategy": list(self.strategy),
            "followedStrategy": self.followed_strategy,
            "suggestedHole": next_suggestion,
            "history": list(self.history),
            "legalActions": ["check_hole"] if self.phase == "playing" else [],
        }


class PirateGameSession:
    """One human proposal against backward-induction pirate voters."""

    def __init__(self, options: dict[str, object]) -> None:
        self.pirate_count = _whole_int(options.get("pirates", 5), "pirates")
        self.total_gold = _whole_int(options.get("gold", 100), "gold")
        if self.pirate_count < 1 or self.pirate_count > 12:
            raise ValueError("pirates must be between 1 and 12")
        if self.total_gold < 0 or self.total_gold > 10_000:
            raise ValueError("gold must be between 0 and 10000")
        self.rules = PirateRules()
        self.solution = PirateSolver(self.rules).solve(
            self.pirate_count, self.total_gold
        )
        self.phase = "proposing"
        self.proposal: tuple[int, ...] | None = None
        self.votes: list[dict[str, object]] = []
        self.passed: bool | None = None
        self.realized_allocation: tuple[int, ...] | None = None
        self.realized_alive: tuple[bool, ...] | None = None

    def act(self, action: str, payload: dict[str, object]) -> dict[str, object]:
        if action != "submit_proposal":
            raise ValueError(f"unknown action: {action}")
        raw_allocation = payload.get("allocation")
        if not isinstance(raw_allocation, list):
            raise ValueError("allocation must be a list")
        parsed: list[int] = []
        for value in raw_allocation:
            number = float(value)
            if not number.is_integer():
                raise ValueError("gold allocations must be whole coins")
            parsed.append(int(number))
        self._submit(tuple(parsed))
        return self.snapshot()

    def _submit(self, allocation: tuple[int, ...]) -> None:
        if self.phase != "proposing":
            raise ValueError("the council has already voted")
        if len(allocation) != self.pirate_count:
            raise ValueError("allocation length must equal pirate count")
        if any(value < 0 for value in allocation):
            raise ValueError("gold allocations cannot be negative")
        if sum(allocation) != self.total_gold:
            raise ValueError("the proposal must allocate every gold coin")

        names = self.solution.pirate_names
        continuation = (
            self.solution.rounds[-2] if self.pirate_count > 1 else None
        )
        votes: list[dict[str, object]] = []
        for index, (name, offered) in enumerate(zip(names, allocation)):
            if index == 0:
                supports = True
                rejection_alive = False
                rejection_gold = 0
                reason_code = "proposer"
            else:
                rejection_alive = continuation.alive[index - 1]  # type: ignore[union-attr]
                rejection_gold = continuation.allocation[index - 1]  # type: ignore[union-attr]
                if not rejection_alive:
                    supports = True
                    reason_code = "survival"
                elif offered > rejection_gold:
                    supports = True
                    reason_code = "more_gold"
                elif offered == rejection_gold and self.rules.accept_equal_gold:
                    supports = True
                    reason_code = "equal_accepted"
                elif offered == rejection_gold:
                    supports = False
                    reason_code = "equal_rejected"
                else:
                    supports = False
                    reason_code = "less_gold"
            votes.append(
                {
                    "pirate": name,
                    "offered": offered,
                    "supports": supports,
                    "rejectionAlive": rejection_alive,
                    "rejectionGold": rejection_gold,
                    "reasonCode": reason_code,
                }
            )

        required = self.rules.votes_required(self.pirate_count)
        self.proposal = allocation
        self.votes = votes
        self.passed = sum(bool(vote["supports"]) for vote in votes) >= required
        if self.passed:
            self.realized_allocation = allocation
            self.realized_alive = tuple(True for _ in names)
        else:
            self.realized_allocation = (
                (0,) if continuation is None else (0,) + continuation.allocation
            )
            self.realized_alive = (
                (False,) if continuation is None else (False,) + continuation.alive
            )
        self.phase = "finished"

    def snapshot(self) -> dict[str, object]:
        optimal = self.solution.final_round.allocation
        return {
            "gameId": "pirates",
            "phase": self.phase,
            "pirateCount": self.pirate_count,
            "totalGold": self.total_gold,
            "votesRequired": self.rules.votes_required(self.pirate_count),
            "pirates": [
                {"id": index, "name": name, "isProposer": index == 0}
                for index, name in enumerate(self.solution.pirate_names)
            ],
            "proposal": list(self.proposal) if self.proposal is not None else None,
            "votes": list(self.votes),
            "yesVotes": sum(bool(vote["supports"]) for vote in self.votes),
            "passed": self.passed,
            "realizedAllocation": (
                list(self.realized_allocation)
                if self.realized_allocation is not None
                else None
            ),
            "realizedAlive": (
                list(self.realized_alive) if self.realized_alive is not None else None
            ),
            "optimalAllocation": list(optimal) if self.phase == "finished" else None,
            "matchesOptimal": self.proposal == optimal if self.proposal is not None else None,
            "legalActions": ["submit_proposal"] if self.phase == "proposing" else [],
        }


class KuhnPokerSession:
    """A short repeated poker match with private cards and a mixed-strategy AI."""

    CARDS = ("J", "Q", "K")
    EQUILIBRIUM = equilibrium_policy()

    def __init__(self, options: dict[str, object]) -> None:
        self.seed = int(options.get("seed", random.SystemRandom().randrange(2**32)))
        self._rng = random.Random(self.seed)
        self.hand_number = 0
        self.player_score = 0
        self.ai_score = 0
        self.player_card = ""
        self.ai_card = ""
        self.player_is_first = True
        self.phase = "playing"
        self.history: list[dict[str, str]] = []
        self.legal_actions: list[str] = []
        self.result: dict[str, object] | None = None
        self.pot = 2
        self._start_hand()

    def act(self, action: str, payload: dict[str, object]) -> dict[str, object]:
        del payload
        if action == "next_hand":
            if self.phase != "finished":
                raise ValueError("finish the current hand first")
            self._start_hand()
        elif action in self.legal_actions and self.phase == "playing":
            self._player_action(action)
        else:
            raise ValueError(f"illegal action: {action}")
        return self.snapshot()

    def _start_hand(self) -> None:
        self.hand_number += 1
        cards = list(self.CARDS)
        self._rng.shuffle(cards)
        self.player_card, self.ai_card = cards[:2]
        self.player_is_first = self.hand_number % 2 == 1
        self.phase = "playing"
        self.history = []
        self.result = None
        self.pot = 2
        if self.player_is_first:
            self.legal_actions = ["check", "bet"]
        else:
            self.legal_actions = []
            self._ai_opening_action()

    def _player_action(self, action: str) -> None:
        self.history.append({"actor": "player", "action": action})
        if action == "fold":
            self._finish("ai", 1, "player_folded")
            return
        if action == "call":
            self.pot = 4
            self._showdown(2, "bet_called")
            return
        if action == "bet":
            self.pot = 3
            self.legal_actions = []
            self._ai_facing_bet()
            return

        # Player checked. A second check ends the hand; otherwise the AI may bet.
        if self.history[0]["actor"] == "ai":
            self._showdown(1, "both_checked")
            return
        self.legal_actions = []
        self._ai_after_player_check()

    def _ai_opening_action(self) -> None:
        should_bet = self._rng.random() < float(
            self.EQUILIBRIUM.first_open_bet[self.ai_card]
        )
        action = "bet" if should_bet else "check"
        self.history.append({"actor": "ai", "action": action})
        if action == "bet":
            self.pot = 3
            self.legal_actions = ["fold", "call"]
        else:
            self.legal_actions = ["check", "bet"]

    def _ai_after_player_check(self) -> None:
        should_bet = self._rng.random() < float(
            self.EQUILIBRIUM.second_bet_after_check[self.ai_card]
        )
        action = "bet" if should_bet else "check"
        self.history.append({"actor": "ai", "action": action})
        if action == "bet":
            self.pot = 3
            self.legal_actions = ["fold", "call"]
        else:
            self._showdown(1, "both_checked")

    def _ai_facing_bet(self) -> None:
        # The two Q information sets are not interchangeable.  As first seat,
        # after check-bet, equilibrium calls 2/3; as second seat versus an
        # opening bet it calls 1/3.
        call_table = (
            self.EQUILIBRIUM.second_call_open_bet
            if self.player_is_first
            else self.EQUILIBRIUM.first_call_after_check_bet
        )
        should_call = self._rng.random() < float(call_table[self.ai_card])
        action = "call" if should_call else "fold"
        self.history.append({"actor": "ai", "action": action})
        if action == "fold":
            self._finish("player", 1, "ai_folded")
        else:
            self.pot = 4
            self._showdown(2, "bet_called")

    def _showdown(self, stakes: int, reason: str) -> None:
        winner = (
            "player"
            if self.CARDS.index(self.player_card) > self.CARDS.index(self.ai_card)
            else "ai"
        )
        self._finish(winner, stakes, reason)

    def _finish(self, winner: str, stakes: int, reason: str) -> None:
        player_delta = stakes if winner == "player" else -stakes
        self.player_score += player_delta
        self.ai_score -= player_delta
        ai_bet = any(
            item["actor"] == "ai" and item["action"] == "bet"
            for item in self.history
        )
        self.result = {
            "winner": winner,
            "playerDelta": player_delta,
            "reason": reason,
            "aiBluffed": ai_bet and self.ai_card == "J",
        }
        self.phase = "finished"
        self.legal_actions = ["next_hand"]

    def snapshot(self) -> dict[str, object]:
        public_history = [dict(item) for item in self.history]
        possible_ai_cards = [card for card in self.CARDS if card != self.player_card]
        return {
            "gameId": "kuhn-poker",
            "phase": self.phase,
            "handNumber": self.hand_number,
            "playerCard": self.player_card,
            "aiCard": self.ai_card if self.phase == "finished" else None,
            "playerIsFirst": self.player_is_first,
            "pot": self.pot,
            "playerScore": self.player_score,
            "aiScore": self.ai_score,
            "legalActions": list(self.legal_actions),
            "history": public_history,
            "result": self.result,
            "strategyScope": "exact_three_card_kuhn_equilibrium_alpha_one_third",
            "informationSet": {
                "privateCard": self.player_card,
                "publicHistory": public_history,
                "possibleOpponentCards": possible_ai_cards,
            },
        }


class ECardSession:
    """Repeated asymmetric card duels with simultaneous hidden choices."""

    SPECIAL_COUNTER = {"emperor": "slave", "slave": "emperor"}

    def __init__(self, options: dict[str, object]) -> None:
        self.seed = int(options.get("seed", random.SystemRandom().randrange(2**32)))
        self._rng = random.Random(self.seed)
        self.round_number = 0
        self.player_score = 0
        self.ai_score = 0
        self.phase = "playing"
        self.player_role = "emperor"
        self.ai_role = "slave"
        self.player_hand: list[str] = []
        self.ai_hand: list[str] = []
        self.history: list[dict[str, object]] = []
        self.last_reveal: dict[str, object] | None = None
        self.result: dict[str, object] | None = None
        self.player_special_timings: list[int] = []
        self._start_round()

    def act(self, action: str, payload: dict[str, object]) -> dict[str, object]:
        if action == "next_round":
            if self.phase != "finished":
                raise ValueError("finish the current round first")
            self._start_round()
        elif action == "play_card":
            self._play_card(str(payload.get("card", "")))
        else:
            raise ValueError(f"unknown action: {action}")
        return self.snapshot()

    def _start_round(self) -> None:
        self.round_number += 1
        self.player_role = "emperor" if self.round_number % 2 == 1 else "slave"
        self.ai_role = self.SPECIAL_COUNTER[self.player_role]
        self.player_hand = [self.player_role] + ["citizen"] * 4
        self.ai_hand = [self.ai_role] + ["citizen"] * 4
        self.phase = "playing"
        self.history = []
        self.last_reveal = None
        self.result = None

    def _play_card(self, card: str) -> None:
        if self.phase != "playing":
            raise ValueError("the round has already ended")
        if card not in self.player_hand:
            raise ValueError("that card is not available in your hand")

        duel = len(self.history) + 1
        ai_card, special_probability = self._choose_ai_card()
        self.player_hand.remove(card)
        self.ai_hand.remove(ai_card)
        outcome = self._outcome(card, ai_card)
        reveal = {
            "duel": duel,
            "playerCard": card,
            "aiCard": ai_card,
            "outcome": outcome,
            "aiSpecialProbability": special_probability,
        }
        self.history.append(reveal)
        self.last_reveal = reveal

        if card == self.player_role:
            self.player_special_timings.append(duel)
        if outcome == "draw":
            if not self.player_hand:
                raise RuntimeError("an E-Card round cannot exhaust without a winner")
            return

        winner_role = self.player_role if outcome == "player" else self.ai_role
        points = 5 if winner_role == "slave" else 1
        if outcome == "player":
            self.player_score += points
        else:
            self.ai_score += points
        self.result = {
            "winner": outcome,
            "winnerRole": winner_role,
            "points": points,
            "decisiveDuel": duel,
        }
        self.phase = "finished"

    def _choose_ai_card(self) -> tuple[str, float]:
        special = self.ai_role
        if special not in self.ai_hand:
            return "citizen", 0.0
        citizen_count = self.ai_hand.count("citizen")
        if citizen_count == 0:
            return special, 1.0

        cards_left = len(self.ai_hand)
        average_timing = (
            sum(self.player_special_timings) / len(self.player_special_timings)
            if self.player_special_timings
            else 3.0
        )
        learned_early_bias = max(-0.08, min(0.08, (3.0 - average_timing) * 0.04))
        probability = min(0.78, 1 / cards_left + learned_early_bias)
        if self._rng.random() < probability:
            return special, probability
        return "citizen", probability

    @staticmethod
    def _outcome(player_card: str, ai_card: str) -> str:
        if player_card == ai_card:
            return "draw"
        wins_against = {
            "emperor": "citizen",
            "citizen": "slave",
            "slave": "emperor",
        }
        return "player" if wins_against[player_card] == ai_card else "ai"

    def snapshot(self) -> dict[str, object]:
        visible_history = [dict(item) for item in self.history]
        opponent_possible = sorted(set(self.ai_hand))
        return {
            "gameId": "e-card",
            "phase": self.phase,
            "roundNumber": self.round_number,
            "duelNumber": len(self.history) + (0 if self.phase == "finished" else 1),
            "playerRole": self.player_role,
            "aiRole": self.ai_role,
            "playerHand": [
                {"card": card, "count": self.player_hand.count(card)}
                for card in dict.fromkeys(self.player_hand)
            ],
            "opponentCardsLeft": len(self.ai_hand),
            "playerScore": self.player_score,
            "aiScore": self.ai_score,
            "history": visible_history,
            "lastReveal": dict(self.last_reveal) if self.last_reveal else None,
            "result": dict(self.result) if self.result else None,
            "legalActions": ["play_card"] if self.phase == "playing" else ["next_round"],
            "informationSet": {
                "privateHand": list(self.player_hand),
                "publicHistory": visible_history,
                "possibleOpponentCards": opponent_possible,
                "opponentCardsLeft": len(self.ai_hand),
            },
        }


class RestrictedRPSSession:
    """Finite-inventory RPS with a minimax baseline and bounded exploitation."""

    MOVES = ("rock", "paper", "scissors")
    BEATS = {"rock": "scissors", "paper": "rock", "scissors": "paper"}

    def __init__(self, options: dict[str, object]) -> None:
        self.copies = _whole_int(options.get("copies", 3), "copies")
        if self.copies < 1 or self.copies > 8:
            raise ValueError("copies must be between 1 and 8")
        self.seed = int(options.get("seed", random.SystemRandom().randrange(2**32)))
        self._rng = random.Random(self.seed)
        self.player_inventory: dict[str, int] = {}
        self.ai_inventory: dict[str, int] = {}
        self.player_history: dict[str, int] = {}
        self.round_number = 0
        self.player_score = 0
        self.ai_score = 0
        self.draws = 0
        self.phase = "playing"
        self.history: list[dict[str, object]] = []
        self.last_analysis: dict[str, object] | None = None
        self._minimax_cache: dict[
            tuple[tuple[int, ...], tuple[int, ...]],
            tuple[float, tuple[float, ...], tuple[float, ...]],
        ] = {}
        self._reset_match()

    def act(self, action: str, payload: dict[str, object]) -> dict[str, object]:
        if action == "play_move":
            self._play(str(payload.get("move", "")))
        elif action == "new_match":
            if self.phase != "finished":
                raise ValueError("finish the current match first")
            self._reset_match()
        else:
            raise ValueError(f"unknown action: {action}")
        return self.snapshot()

    def _reset_match(self) -> None:
        self.player_inventory = {move: self.copies for move in self.MOVES}
        self.ai_inventory = {move: self.copies for move in self.MOVES}
        self.player_history = {move: 0 for move in self.MOVES}
        self.round_number = 0
        self.player_score = 0
        self.ai_score = 0
        self.draws = 0
        self.phase = "playing"
        self.history = []
        self.last_analysis = None

    def _play(self, player_move: str) -> None:
        if self.phase != "playing":
            raise ValueError("the match has already ended")
        if self.player_inventory.get(player_move, 0) <= 0:
            raise ValueError("that move has no cards remaining")

        strategy = self._ai_strategy()
        ai_move = self._sample(strategy["finalDistribution"])
        self.player_inventory[player_move] -= 1
        self.ai_inventory[ai_move] -= 1
        self.player_history[player_move] += 1
        self.round_number += 1

        if player_move == ai_move:
            outcome = "draw"
            self.draws += 1
        elif self.BEATS[player_move] == ai_move:
            outcome = "player"
            self.player_score += 1
        else:
            outcome = "ai"
            self.ai_score += 1
        entry = {
            "round": self.round_number,
            "playerMove": player_move,
            "aiMove": ai_move,
            "outcome": outcome,
            "analysis": strategy,
        }
        self.history.append(entry)
        self.last_analysis = strategy
        if sum(self.player_inventory.values()) == 0:
            self.phase = "finished"

    def _ai_strategy(self) -> dict[str, object]:
        ai_counts = tuple(self.ai_inventory[move] for move in self.MOVES)
        player_counts = tuple(self.player_inventory[move] for move in self.MOVES)
        value, ai_minimax, player_minimax = self._solve_minimax(
            ai_counts, player_counts
        )
        equilibrium = dict(zip(self.MOVES, ai_minimax))
        observations = sum(self.player_history.values())
        empirical = {
            move: (self.player_history[move] + 1) / (observations + 3)
            for move in self.MOVES
        }
        player_remaining = sum(self.player_inventory.values())
        inventory_prior = {
            move: self.player_inventory[move] / player_remaining for move in self.MOVES
        }
        prediction = {
            move: 0.55 * inventory_prior[move] + 0.45 * empirical[move]
            for move in self.MOVES
        }
        best_response = max(
            (move for move in self.MOVES if self.ai_inventory[move] > 0),
            key=lambda candidate: sum(
                prediction[player_move]
                * self._payoff(candidate, player_move)
                for player_move in self.MOVES
            ),
        )
        exploit_weight = min(0.32, observations * 0.045)
        final = {
            move: (1 - exploit_weight) * equilibrium[move]
            + (exploit_weight if move == best_response else 0)
            for move in self.MOVES
        }
        return {
            "equilibriumDistribution": equilibrium,
            "playerMinimaxDistribution": dict(zip(self.MOVES, player_minimax)),
            "minimaxValue": value,
            "predictedPlayerDistribution": prediction,
            "bestResponse": best_response,
            "exploitWeight": exploit_weight,
            "finalDistribution": final,
        }

    def _solve_minimax(
        self, ai_counts: tuple[int, ...], player_counts: tuple[int, ...]
    ) -> tuple[float, tuple[float, ...], tuple[float, ...]]:
        key = (ai_counts, player_counts)
        if key in self._minimax_cache:
            return self._minimax_cache[key]
        if sum(ai_counts) == 0:
            result = (0.0, (0.0, 0.0, 0.0), (0.0, 0.0, 0.0))
            self._minimax_cache[key] = result
            return result

        ai_actions = [index for index, count in enumerate(ai_counts) if count]
        player_actions = [
            index for index, count in enumerate(player_counts) if count
        ]
        matrix: list[list[float]] = []
        for ai_index in ai_actions:
            row: list[float] = []
            for player_index in player_actions:
                next_ai = list(ai_counts)
                next_player = list(player_counts)
                next_ai[ai_index] -= 1
                next_player[player_index] -= 1
                continuation = self._solve_minimax(
                    tuple(next_ai), tuple(next_player)
                )[0]
                immediate = self._payoff(
                    self.MOVES[ai_index], self.MOVES[player_index]
                )
                row.append(immediate + continuation)
            matrix.append(row)

        value, row_mix, column_mix = self._solve_matrix_game(matrix)
        ai_full = [0.0, 0.0, 0.0]
        player_full = [0.0, 0.0, 0.0]
        for local, global_index in enumerate(ai_actions):
            ai_full[global_index] = row_mix[local]
        for local, global_index in enumerate(player_actions):
            player_full[global_index] = column_mix[local]
        result = (value, tuple(ai_full), tuple(player_full))
        self._minimax_cache[key] = result
        return result

    @classmethod
    def _solve_matrix_game(
        cls, matrix: list[list[float]]
    ) -> tuple[float, tuple[float, ...], tuple[float, ...]]:
        rows = len(matrix)
        columns = len(matrix[0])
        tolerance = 1e-7
        for size in range(1, min(rows, columns) + 1):
            for row_support in combinations(range(rows), size):
                for column_support in combinations(range(columns), size):
                    row_system = [
                        [1.0] * size + [0.0]
                    ] + [
                        [matrix[row][column] for row in row_support] + [-1.0]
                        for column in column_support
                    ]
                    column_system = [
                        [1.0] * size + [0.0]
                    ] + [
                        [matrix[row][column] for column in column_support] + [-1.0]
                        for row in row_support
                    ]
                    row_solution = cls._linear_solve(
                        row_system, [1.0] + [0.0] * size
                    )
                    column_solution = cls._linear_solve(
                        column_system, [1.0] + [0.0] * size
                    )
                    if row_solution is None or column_solution is None:
                        continue
                    row_probabilities = row_solution[:size]
                    column_probabilities = column_solution[:size]
                    value = (row_solution[-1] + column_solution[-1]) / 2
                    if min(row_probabilities + column_probabilities) < -tolerance:
                        continue
                    row_mix = [0.0] * rows
                    column_mix = [0.0] * columns
                    for index, probability in zip(row_support, row_probabilities):
                        row_mix[index] = max(0.0, probability)
                    for index, probability in zip(
                        column_support, column_probabilities
                    ):
                        column_mix[index] = max(0.0, probability)
                    guaranteed = [
                        sum(row_mix[row] * matrix[row][column] for row in range(rows))
                        for column in range(columns)
                    ]
                    capped = [
                        sum(matrix[row][column] * column_mix[column] for column in range(columns))
                        for row in range(rows)
                    ]
                    if min(guaranteed) < value - tolerance:
                        continue
                    if max(capped) > value + tolerance:
                        continue
                    return value, tuple(row_mix), tuple(column_mix)
        raise RuntimeError("unable to solve restricted RPS matrix game")

    @staticmethod
    def _linear_solve(
        coefficients: list[list[float]], values: list[float]
    ) -> list[float] | None:
        size = len(values)
        augmented = [row[:] + [value] for row, value in zip(coefficients, values)]
        for column in range(size):
            pivot = max(range(column, size), key=lambda row: abs(augmented[row][column]))
            if abs(augmented[pivot][column]) < 1e-10:
                return None
            augmented[column], augmented[pivot] = augmented[pivot], augmented[column]
            divisor = augmented[column][column]
            augmented[column] = [value / divisor for value in augmented[column]]
            for row in range(size):
                if row == column:
                    continue
                factor = augmented[row][column]
                augmented[row] = [
                    current - factor * pivot_value
                    for current, pivot_value in zip(
                        augmented[row], augmented[column]
                    )
                ]
        return [augmented[index][-1] for index in range(size)]

    def _sample(self, distribution: object) -> str:
        probabilities = distribution
        if not isinstance(probabilities, dict):
            raise TypeError("distribution must be a mapping")
        target = self._rng.random()
        cumulative = 0.0
        for move in self.MOVES:
            cumulative += float(probabilities.get(move, 0.0))
            if target <= cumulative and self.ai_inventory[move] > 0:
                return move
        return next(move for move in reversed(self.MOVES) if self.ai_inventory[move] > 0)

    @classmethod
    def _payoff(cls, ai_move: str, player_move: str) -> int:
        if ai_move == player_move:
            return 0
        return 1 if cls.BEATS[ai_move] == player_move else -1

    def snapshot(self) -> dict[str, object]:
        rounds_total = self.copies * len(self.MOVES)
        ai_counts = tuple(self.ai_inventory[move] for move in self.MOVES)
        player_counts = tuple(self.player_inventory[move] for move in self.MOVES)
        _value, _ai_strategy, player_strategy = self._solve_minimax(
            ai_counts, player_counts
        )
        recommendation = dict(zip(self.MOVES, player_strategy))
        public_history = [dict(entry) for entry in self.history]
        post_match_review = None
        if self.phase == "finished":
            selected_probabilities = [
                float(entry["analysis"]["playerMinimaxDistribution"][entry["playerMove"]])
                for entry in self.history
            ]
            move_counts = {
                move: sum(entry["playerMove"] == move for entry in self.history)
                for move in self.MOVES
            }
            highest_count = max(move_counts.values())
            post_match_review = {
                "scoreDifference": self.player_score - self.ai_score,
                "equilibriumSupportedRounds": sum(
                    probability > 1e-9 for probability in selected_probabilities
                ),
                "averageChosenProbability": sum(selected_probabilities)
                / len(selected_probabilities),
                "mostUsedMoves": [
                    move for move, count in move_counts.items() if count == highest_count
                ],
                "moveCounts": move_counts,
                "maxExploitWeight": max(
                    float(entry["analysis"]["exploitWeight"])
                    for entry in self.history
                ),
            }
        return {
            "gameId": "restricted-rps",
            "phase": self.phase,
            "roundNumber": self.round_number,
            "roundsTotal": rounds_total,
            "playerInventory": dict(self.player_inventory),
            "aiInventory": dict(self.ai_inventory),
            "playerScore": self.player_score,
            "aiScore": self.ai_score,
            "draws": self.draws,
            "history": public_history,
            "lastAnalysis": self.last_analysis,
            "postMatchReview": post_match_review,
            "equilibriumRecommendation": recommendation,
            "legalActions": ["play_move"] if self.phase == "playing" else ["new_match"],
            "informationSet": {
                "privateChoice": None,
                "publicHistory": public_history,
                "knownInventories": {
                    "player": dict(self.player_inventory),
                    "ai": dict(self.ai_inventory),
                },
            },
        }


class BlackjackSession:
    """Six-deck S17 blackjack lab with a rule-scoped basic-strategy AI."""

    RANKS = ("A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K")

    def __init__(self, options: dict[str, object]) -> None:
        self.seed = int(options.get("seed", random.SystemRandom().randrange(2**32)))
        self._rng = random.Random(self.seed)
        self.shoe: list[str] = []
        self.player_hand: list[str] = []
        self.dealer_hand: list[str] = []
        self.phase = "player_turn"
        self.round_number = 0
        self.bet_multiplier = 1
        self.bankroll = 0.0
        self.wins = 0
        self.losses = 0
        self.pushes = 0
        self.decisions = 0
        self.basic_strategy_matches = 0
        self.history: list[dict[str, object]] = []
        self.result: dict[str, object] | None = None
        self._build_shoe()
        self._start_round()

    def act(self, action: str, payload: dict[str, object]) -> dict[str, object]:
        del payload
        if action == "new_round":
            if self.phase != "finished":
                raise ValueError("finish the current hand first")
            self._start_round()
        elif action == "ai_play":
            if self.phase != "player_turn":
                raise ValueError("there is no player decision to automate")
            self._player_action(self._recommendation(), used_ai=True)
        elif action in {"hit", "stand", "double"}:
            self._player_action(action, used_ai=False)
        else:
            raise ValueError(f"unknown action: {action}")
        return self.snapshot()

    def _build_shoe(self) -> None:
        self.shoe = [rank for rank in self.RANKS for _ in range(4 * 6)]
        self._rng.shuffle(self.shoe)

    def _draw(self) -> str:
        return self.shoe.pop()

    def _start_round(self) -> None:
        if len(self.shoe) < 52:
            self._build_shoe()
        self.round_number += 1
        self.bet_multiplier = 1
        self.player_hand = [self._draw()]
        self.dealer_hand = [self._draw()]
        self.player_hand.append(self._draw())
        self.dealer_hand.append(self._draw())
        self.phase = "player_turn"
        self.history = []
        self.result = None
        player_blackjack = self._is_blackjack(self.player_hand)
        dealer_blackjack = self._is_blackjack(self.dealer_hand)
        if player_blackjack or dealer_blackjack:
            if player_blackjack and dealer_blackjack:
                self._finish("push", 0.0, "both_blackjack")
            elif player_blackjack:
                self._finish("player", 1.5, "player_blackjack")
            else:
                self._finish("dealer", -1.0, "dealer_blackjack")

    def _player_action(self, action: str, *, used_ai: bool) -> None:
        if self.phase != "player_turn":
            raise ValueError("the player hand is not awaiting an action")
        legal = self._legal_actions()
        if action not in legal:
            raise ValueError(f"illegal blackjack action: {action}")
        recommendation = self._recommendation()
        self.decisions += 1
        matched = action == recommendation
        if matched:
            self.basic_strategy_matches += 1
        self.history.append(
            {
                "actor": "ai" if used_ai else "player",
                "action": action,
                "recommended": recommendation,
                "matched": matched,
                "totalBefore": self._hand_value(self.player_hand)[0],
            }
        )
        if action == "hit":
            self.player_hand.append(self._draw())
            total, _soft = self._hand_value(self.player_hand)
            if total > 21:
                self._finish("dealer", -float(self.bet_multiplier), "player_bust")
            elif total == 21:
                self._resolve_dealer()
        elif action == "double":
            self.bet_multiplier = 2
            self.player_hand.append(self._draw())
            if self._hand_value(self.player_hand)[0] > 21:
                self._finish("dealer", -2.0, "player_bust")
            else:
                self._resolve_dealer()
        else:
            self._resolve_dealer()

    def _resolve_dealer(self) -> None:
        self.phase = "dealer_turn"
        while True:
            total, _soft = self._hand_value(self.dealer_hand)
            if total >= 17:
                break
            card = self._draw()
            self.dealer_hand.append(card)
            self.history.append(
                {
                    "actor": "dealer",
                    "action": "hit",
                    "card": card,
                    "total": self._hand_value(self.dealer_hand)[0],
                }
            )
        player_total = self._hand_value(self.player_hand)[0]
        dealer_total = self._hand_value(self.dealer_hand)[0]
        stake = float(self.bet_multiplier)
        if dealer_total > 21 or player_total > dealer_total:
            self._finish("player", stake, "dealer_bust" if dealer_total > 21 else "higher_total")
        elif player_total < dealer_total:
            self._finish("dealer", -stake, "lower_total")
        else:
            self._finish("push", 0.0, "equal_total")

    def _finish(self, winner: str, delta: float, reason: str) -> None:
        self.phase = "finished"
        self.bankroll += delta
        if winner == "player":
            self.wins += 1
        elif winner == "dealer":
            self.losses += 1
        else:
            self.pushes += 1
        self.result = {"winner": winner, "delta": delta, "reason": reason}

    def _legal_actions(self) -> list[str]:
        actions = ["hit", "stand"]
        if len(self.player_hand) == 2:
            actions.append("double")
        return actions

    def _recommendation(self) -> str:
        total, soft = self._hand_value(self.player_hand)
        dealer = self._dealer_value(self.dealer_hand[0])
        can_double = len(self.player_hand) == 2

        if soft:
            if total >= 19:
                recommendation = "stand"
            elif total == 18:
                if 3 <= dealer <= 6:
                    recommendation = "double"
                elif dealer in {2, 7, 8}:
                    recommendation = "stand"
                else:
                    recommendation = "hit"
            elif total == 17:
                recommendation = "double" if 3 <= dealer <= 6 else "hit"
            elif total in {15, 16}:
                recommendation = "double" if 4 <= dealer <= 6 else "hit"
            elif total in {13, 14}:
                recommendation = "double" if 5 <= dealer <= 6 else "hit"
            else:
                recommendation = "hit"
        else:
            if total >= 17:
                recommendation = "stand"
            elif 13 <= total <= 16:
                recommendation = "stand" if 2 <= dealer <= 6 else "hit"
            elif total == 12:
                recommendation = "stand" if 4 <= dealer <= 6 else "hit"
            elif total == 11:
                recommendation = "double" if dealer <= 10 else "hit"
            elif total == 10:
                recommendation = "double" if 2 <= dealer <= 9 else "hit"
            elif total == 9:
                recommendation = "double" if 3 <= dealer <= 6 else "hit"
            else:
                recommendation = "hit"
        if recommendation == "double" and not can_double:
            return "hit"
        return recommendation

    @staticmethod
    def _dealer_value(card: str) -> int:
        if card == "A":
            return 11
        if card in {"10", "J", "Q", "K"}:
            return 10
        return int(card)

    @classmethod
    def _hand_value(cls, cards: list[str]) -> tuple[int, bool]:
        total = 0
        aces = 0
        for card in cards:
            if card == "A":
                aces += 1
                total += 11
            elif card in {"10", "J", "Q", "K"}:
                total += 10
            else:
                total += int(card)
        while total > 21 and aces:
            total -= 10
            aces -= 1
        return total, aces > 0

    @classmethod
    def _is_blackjack(cls, cards: list[str]) -> bool:
        return len(cards) == 2 and cls._hand_value(cards)[0] == 21

    def snapshot(self) -> dict[str, object]:
        player_total, player_soft = self._hand_value(self.player_hand)
        dealer_visible = [self.dealer_hand[0]]
        if self.phase == "finished":
            dealer_visible = list(self.dealer_hand)
        dealer_total = self._hand_value(self.dealer_hand)[0] if self.phase == "finished" else None
        accuracy = self.basic_strategy_matches / self.decisions if self.decisions else None
        return {
            "gameId": "blackjack",
            "phase": self.phase,
            "roundNumber": self.round_number,
            "playerHand": list(self.player_hand),
            "playerTotal": player_total,
            "playerSoft": player_soft,
            "dealerHand": dealer_visible,
            "dealerTotal": dealer_total,
            "dealerHoleHidden": self.phase != "finished",
            "shoeRemaining": len(self.shoe),
            "betMultiplier": self.bet_multiplier,
            "bankroll": self.bankroll,
            "wins": self.wins,
            "losses": self.losses,
            "pushes": self.pushes,
            "legalActions": (
                self._legal_actions()
                if self.phase == "player_turn"
                else (["new_round"] if self.phase == "finished" else [])
            ),
            "recommendation": self._recommendation() if self.phase == "player_turn" else None,
            "strategyAccuracy": accuracy,
            "decisions": self.decisions,
            "history": [dict(item) for item in self.history],
            "result": dict(self.result) if self.result else None,
            "rules": {
                "decks": 6,
                "dealerStandsSoft17": True,
                "blackjackPayout": 1.5,
                "split": False,
                "surrender": False,
                "insurance": False,
            },
            "strategyScope": "six_deck_s17_no_split_no_surrender_no_counting",
            "informationSet": {
                "privateHand": list(self.player_hand),
                "publicDealerUpcard": self.dealer_hand[0],
                "hiddenDealerHole": True if self.phase != "finished" else self.dealer_hand[1],
                "shoeRemaining": len(self.shoe),
            },
        }


class LiarDiceSession:
    """A two-player liar's-dice match with private dice and public bids."""

    def __init__(self, options: dict[str, object]) -> None:
        self.dice_per_player = _whole_int(options.get("dice", 5), "dice")
        if self.dice_per_player < 2 or self.dice_per_player > 8:
            raise ValueError("dice must be between 2 and 8")
        self.seed = int(options.get("seed", random.SystemRandom().randrange(2**32)))
        self._rng = random.Random(self.seed)
        self.player_score = 0
        self.ai_score = 0
        self.round_number = 0
        self._start_round()

    def _start_round(self) -> None:
        self.round_number += 1
        self.player_dice = sorted(self._roll(self.dice_per_player))
        self.ai_dice = sorted(self._roll(self.dice_per_player))
        self.current_bid: tuple[int, int] | None = None
        self.phase = "bidding"
        self.turn = "player"
        self.history: list[dict[str, object]] = []
        self.result: dict[str, object] | None = None

    def _roll(self, count: int) -> list[int]:
        return [self._rng.randint(1, 6) for _ in range(count)]

    def act(self, action: str, payload: dict[str, object]) -> dict[str, object]:
        if action == "new_round":
            if self.phase != "finished":
                raise ValueError("finish the current round first")
            self._start_round()
        elif action == "raise_bid":
            self._player_raise(
                _whole_int(payload.get("quantity", 0), "quantity"),
                _whole_int(payload.get("face", 0), "face"),
            )
        elif action == "challenge":
            self._player_challenge()
        else:
            raise ValueError(f"unknown liar's-dice action: {action}")
        return self.snapshot()

    @staticmethod
    def _is_higher(candidate: tuple[int, int], current: tuple[int, int] | None) -> bool:
        return current is None or candidate[0] > current[0] or (
            candidate[0] == current[0] and candidate[1] > current[1]
        )

    def _validate_bid(self, quantity: int, face: int) -> tuple[int, int]:
        bid = (quantity, face)
        if quantity < 1 or quantity > self.dice_per_player * 2 or face not in range(1, 7):
            raise ValueError("bid must use a face from 1 to 6 and fit the dice pool")
        if not self._is_higher(bid, self.current_bid):
            raise ValueError("a new bid must raise quantity, or raise the face at equal quantity")
        return bid

    def _player_raise(self, quantity: int, face: int) -> None:
        if self.phase != "bidding" or self.turn != "player":
            raise ValueError("it is not your bidding turn")
        bid = self._validate_bid(quantity, face)
        self.current_bid = bid
        self.history.append({"actor": "player", "action": "raise", "quantity": quantity, "face": face})
        self.turn = "ai"
        self._ai_response()

    def _player_challenge(self) -> None:
        if self.phase != "bidding" or self.turn != "player" or self.current_bid is None:
            raise ValueError("there is no bid to challenge")
        self.history.append({"actor": "player", "action": "challenge", "bid": list(self.current_bid)})
        self._resolve_challenge("player")

    def _claim_probability(self, bid: tuple[int, int], known_dice: list[int] | None = None) -> float:
        quantity, face = bid
        observer_dice = self.player_dice if known_dice is None else known_dice
        own = sum(value == face or (face != 1 and value == 1) for value in observer_dice)
        needed = quantity - own
        if needed <= 0:
            return 1.0
        probability = 1 / 6 if face == 1 else 1 / 3
        total = self.dice_per_player
        return sum(
            comb(total, k) * probability**k * (1 - probability) ** (total - k)
            for k in range(needed, total + 1)
        )

    def _ai_response(self) -> None:
        assert self.current_bid is not None
        confidence = self._claim_probability(self.current_bid, self.ai_dice)
        if confidence < 0.45 or self.current_bid[0] >= self.dice_per_player * 2:
            self.history.append({"actor": "ai", "action": "challenge", "bid": list(self.current_bid), "confidence": confidence})
            self._resolve_challenge("ai")
            return

        quantity, face = self.current_bid
        preferred = max(range(1, 7), key=lambda value: self.ai_dice.count(value) + (0 if value == 1 else self.ai_dice.count(1)))
        next_bid = (quantity + 1, preferred) if quantity < self.dice_per_player * 2 else (quantity, min(6, face + 1))
        if not self._is_higher(next_bid, self.current_bid) or next_bid[0] > self.dice_per_player * 2:
            self.history.append({"actor": "ai", "action": "challenge", "bid": list(self.current_bid), "confidence": confidence})
            self._resolve_challenge("ai")
            return
        self.current_bid = next_bid
        self.history.append({"actor": "ai", "action": "raise", "quantity": next_bid[0], "face": next_bid[1], "confidence": confidence})
        self.turn = "player"

    def _resolve_challenge(self, challenger: str) -> None:
        assert self.current_bid is not None
        quantity, face = self.current_bid
        count = sum(value == face or (face != 1 and value == 1) for value in self.player_dice + self.ai_dice)
        claim_true = count >= quantity
        challenger_lost = claim_true
        loser = challenger if challenger_lost else ("ai" if challenger == "player" else "player")
        winner = "ai" if loser == "player" else "player"
        if winner == "player":
            self.player_score += 1
        else:
            self.ai_score += 1
        self.result = {
            "challenger": challenger,
            "bid": [quantity, face],
            "actualCount": count,
            "claimTrue": claim_true,
            "winner": winner,
            "loser": loser,
        }
        self.phase = "finished"
        self.turn = "none"

    def snapshot(self) -> dict[str, object]:
        bid = list(self.current_bid) if self.current_bid is not None else None
        confidence = self._claim_probability(self.current_bid) if self.current_bid else None
        minimum = None if self.current_bid is None else {
            "quantity": self.current_bid[0] if self.current_bid[1] < 6 else self.current_bid[0] + 1,
            "face": self.current_bid[1] + 1 if self.current_bid[1] < 6 else 1,
        }
        return {
            "gameId": "liars-dice",
            "phase": self.phase,
            "roundNumber": self.round_number,
            "dicePerPlayer": self.dice_per_player,
            "playerDice": list(self.player_dice),
            "opponentDiceCount": len(self.ai_dice),
            "currentBid": bid,
            "minimumBid": minimum,
            "turn": self.turn,
            "playerScore": self.player_score,
            "aiScore": self.ai_score,
            "claimProbability": confidence,
            "history": list(self.history),
            "result": dict(self.result) if self.result else None,
            "legalActions": (["raise_bid", "challenge"] if self.phase == "bidding" and self.turn == "player" else ["new_round"] if self.phase == "finished" else []),
            "informationSet": {
                "privateHand": list(self.player_dice),
                "publicHistory": list(self.history),
                "opponentDiceCount": len(self.ai_dice),
                "claimProbability": confidence,
            },
        }


class MastermindSession:
    """Standard decimal Bulls and Cows with an explicit candidate information set."""

    def __init__(self, options: dict[str, object]) -> None:
        self.rules = CodeRules()
        self.solver = MastermindSolver(self.rules)
        self.seed = int(options.get("seed", random.SystemRandom().randrange(2**32)))
        self._rng = random.Random(self.seed)
        self.games_completed = 0
        self.games_solved = 0
        self.total_solved_attempts = 0
        self.best_attempts: int | None = None
        self._start_game()

    def _start_game(self) -> None:
        self.secret = self._rng.choice(self.solver.all_codes)
        self.candidates = self.solver.all_codes
        self.attempts: list[dict[str, object]] = []
        self.phase = "playing"
        self.result: dict[str, object] | None = None

    def act(self, action: str, payload: dict[str, object]) -> dict[str, object]:
        if action == "new_game":
            self._start_game()
            return self.snapshot()
        if action != "submit_guess" or self.phase != "playing":
            raise ValueError("submit a guess while the game is active")
        raw = payload.get("guess", [])
        guess = (
            tuple(_whole_int(value, "guess digit") for value in raw)
            if isinstance(raw, list)
            else ()
        )
        self.rules.validate_guess(guess)
        before = len(self.candidates)
        feedback = self.solver.feedback(guess, self.secret)
        self.candidates = self.solver.filter_candidates(
            self.candidates, guess, feedback
        )
        after = len(self.candidates)
        self.attempts.append(
            {
                "guess": list(guess),
                "exact": feedback.exact,
                "partial": feedback.misplaced,
                "beforeCandidates": before,
                "afterCandidates": after,
                "eliminated": before - after,
            }
        )
        if feedback.exact == self.rules.length:
            self.phase = "finished"
            self.result = {"won": True, "secret": list(self.secret), "attempts": len(self.attempts)}
            self.games_completed += 1
            self.games_solved += 1
            self.total_solved_attempts += len(self.attempts)
            self.best_attempts = (
                len(self.attempts)
                if self.best_attempts is None
                else min(self.best_attempts, len(self.attempts))
            )
        elif len(self.attempts) >= self.rules.max_attempts:
            self.phase = "finished"
            self.result = {"won": False, "secret": list(self.secret), "attempts": len(self.attempts)}
            self.games_completed += 1
        return self.snapshot()

    def snapshot(self) -> dict[str, object]:
        analysis = self.solver.suggest(self.candidates) if self.phase == "playing" else None
        return {
            "gameId": "mastermind", "phase": self.phase, "length": self.rules.length,
            "symbols": list(self.rules.symbols), "maxAttempts": self.rules.max_attempts,
            "attemptsUsed": len(self.attempts), "attempts": list(self.attempts),
            "candidateCount": len(self.candidates),
            "initialCandidateCount": self.rules.world_count,
            "suggestedGuess": list(analysis.guess) if analysis else None,
            "suggestionAnalysis": (
                {
                    "worstCaseRemaining": analysis.worst_case_remaining,
                    "expectedRemaining": analysis.expected_remaining,
                    "evaluatedGuesses": analysis.evaluated_guesses,
                    "exactSearch": analysis.exact_search,
                }
                if analysis
                else None
            ),
            "result": dict(self.result) if self.result else None,
            "legalActions": ["submit_guess"] if self.phase == "playing" else ["new_game"],
            "sessionStats": {
                "gamesCompleted": self.games_completed,
                "gamesSolved": self.games_solved,
                "averageSolvedAttempts": (
                    self.total_solved_attempts / self.games_solved
                    if self.games_solved
                    else None
                ),
                "bestAttempts": self.best_attempts,
            },
            "strategyScope": "bounded_one_step_minimax_then_expected_partition",
            "informationSet": {
                "candidateCount": len(self.candidates),
                "candidatePreview": [list(code) for code in self.candidates[:8]],
                "feedbackHistory": list(self.attempts),
            },
        }


class BattleshipGameSession:
    """Solo Battleship match with private fleets and probability-density AI."""

    FLEETS = {
        10: (5, 4, 3, 3, 2),
        12: (6, 5, 4, 3, 3, 2),
        15: (7, 6, 5, 4, 4, 3, 2),
    }

    def __init__(self, options: dict[str, object]) -> None:
        self.seed = int(options.get("seed", random.SystemRandom().randrange(2**32)))
        self._rng = random.Random(self.seed)
        self._configure(_whole_int(options.get("boardSize", 10), "boardSize"))

    def _configure(self, board_size: int) -> None:
        if board_size not in self.FLEETS:
            raise ValueError("boardSize must be 10, 12, or 15")
        self.rules = FleetRules(board_size, self.FLEETS[board_size])
        self._new_boards()

    def _new_boards(self) -> None:
        self.player_board = HiddenFleetBoard(self.rules, self._rng)
        self.enemy_board = HiddenFleetBoard(self.rules, self._rng)
        self.ai = ProbabilityDensityAI(self.rules, self._rng)
        self.advisor = ProbabilityDensityAI(self.rules, random.Random(self.seed ^ 0xA1B2C3))
        self.phase = "placement"
        self.turn = 0
        self.volley_number = 1
        self.player_shots_in_volley = 0
        self.winner: str | None = None
        self.history: list[dict[str, object]] = []
        self.last_ai_analysis: dict[str, object] | None = None

    def act(self, action: str, payload: dict[str, object]) -> dict[str, object]:
        if action == "randomize_fleet":
            if self.phase != "placement":
                raise ValueError("fleet placement is already locked")
            self.player_board = HiddenFleetBoard(self.rules, self._rng)
        elif action == "set_board_size":
            if self.phase != "placement":
                raise ValueError("board size can only change during placement")
            self._configure(_whole_int(payload.get("boardSize", 0), "boardSize"))
        elif action == "rotate_ship":
            if self.phase != "placement":
                raise ValueError("ships can only rotate during placement")
            self._rotate_ship(_whole_int(payload.get("shipId", -1), "shipId"))
        elif action == "start_battle":
            if self.phase != "placement":
                raise ValueError("battle has already started")
            self.phase = "player_turn"
        elif action == "fire":
            self._player_fire(
                (
                    _whole_int(payload.get("row", -1), "row"),
                    _whole_int(payload.get("column", -1), "column"),
                )
            )
        else:
            raise ValueError(f"unknown Battleship action: {action}")
        return self.snapshot()

    def _rotate_ship(self, ship_id: int) -> None:
        if ship_id < 0 or ship_id >= len(self.player_board.ships):
            raise ValueError("unknown ship")
        ship = self.player_board.ships[ship_id]
        horizontal = len({row for row, _column in ship.cells}) == 1
        anchor_row = min(row for row, _column in ship.cells)
        anchor_column = min(column for _row, column in ship.cells)
        occupied = set().union(
            *(item.cells for index, item in enumerate(self.player_board.ships) if index != ship_id)
        )
        candidates: list[frozenset[tuple[int, int]]] = []
        if horizontal:
            for row in range(self.rules.board_size - ship.length + 1):
                for column in range(self.rules.board_size):
                    cells = frozenset((row + offset, column) for offset in range(ship.length))
                    if cells.isdisjoint(occupied):
                        candidates.append(cells)
        else:
            for row in range(self.rules.board_size):
                for column in range(self.rules.board_size - ship.length + 1):
                    cells = frozenset((row, column + offset) for offset in range(ship.length))
                    if cells.isdisjoint(occupied):
                        candidates.append(cells)
        if not candidates:
            raise ValueError("no collision-free rotation is available")
        cells = min(
            candidates,
            key=lambda item: abs(min(row for row, _column in item) - anchor_row)
            + abs(min(column for _row, column in item) - anchor_column),
        )
        ships = list(self.player_board.ships)
        ships[ship_id] = ShipPlacement(ship.length, cells)
        self.player_board.ships = tuple(ships)

    def _player_fire(self, cell: tuple[int, int]) -> None:
        if self.phase != "player_turn":
            raise ValueError("fire only when the battle is active")
        player_outcome = self.enemy_board.fire(cell)
        self.advisor.observe(player_outcome)
        self.turn += 1
        event: dict[str, object] = {
            "turn": self.turn,
            "volley": self.volley_number,
            "playerShot": self._outcome_payload(player_outcome),
            "aiShot": None,
            "aiShots": [],
        }
        if self.enemy_board.all_sunk:
            self.phase = "finished"
            self.winner = "player"
            self.history.append(event)
            return
        self.player_shots_in_volley += 1
        if self.player_shots_in_volley < self.salvo_size:
            self.history.append(event)
            return

        ai_shots: list[dict[str, object]] = []
        ai_analyses: list[dict[str, object]] = []
        for _shot in range(self.salvo_size):
            ai_cell = self.ai.choose()
            analysis = {
                **getattr(self.ai, "last_analysis", {}),
                "chosenCell": list(ai_cell),
            }
            ai_outcome = self.player_board.fire(ai_cell)
            self.ai.observe(ai_outcome)
            ai_shots.append(self._outcome_payload(ai_outcome))
            ai_analyses.append(analysis)
            if self.player_board.all_sunk:
                self.phase = "finished"
                self.winner = "ai"
                break
        event["aiShot"] = ai_shots[0] if ai_shots else None
        event["aiShots"] = ai_shots
        self.last_ai_analysis = {
            **ai_analyses[-1],
            "volleyShots": ai_analyses,
        }
        self.history.append(event)
        self.player_shots_in_volley = 0
        self.volley_number += 1

    @staticmethod
    def _outcome_payload(outcome: ShotOutcome) -> dict[str, object]:
        return {
            "cell": list(outcome.cell),
            "hit": outcome.hit,
            "sunk": outcome.sunk,
            "sunkLength": outcome.sunk_length,
        }

    @staticmethod
    def _remaining_ships(board: HiddenFleetBoard) -> list[int]:
        return [ship.length for ship in board.ships if not ship.cells.issubset(board.hits)]

    def _board_payload(self, board: HiddenFleetBoard, reveal_fleet: bool) -> list[dict[str, object]]:
        size = self.rules.board_size
        cells: list[dict[str, object]] = []
        for row in range(size):
            for column in range(size):
                cell = (row, column)
                ship_id = next((index for index, item in enumerate(board.ships) if cell in item.cells), None)
                ship = board.ships[ship_id] if ship_id is not None else None
                sunk = bool(ship and ship.cells.issubset(board.hits))
                cells.append(
                    {
                        "row": row,
                        "column": column,
                        "shot": cell in board.shots,
                        "hit": cell in board.hits,
                        "sunk": sunk,
                        "ship": bool(ship) if reveal_fleet else bool(sunk),
                        "shipId": ship_id if reveal_fleet or sunk else None,
                    }
                )
        return cells

    def snapshot(self) -> dict[str, object]:
        scores, candidate_count = self.advisor.density_scores()
        available_scores = scores or {(0, 0): 0}
        peak = max(available_scores.values())
        suggested = min(cell for cell, score in available_scores.items() if score == peak)
        finished = self.phase == "finished"
        return {
            "gameId": "battleship",
            "phase": self.phase,
            "turn": self.turn,
            "volleyNumber": self.volley_number,
            "salvoSize": self.salvo_size,
            "shotsRemainingInVolley": (
                self.salvo_size - self.player_shots_in_volley
                if self.phase == "player_turn"
                else 0
            ),
            "winner": self.winner,
            "boardSize": self.rules.board_size,
            "boardSizes": list(self.FLEETS),
            "shipLengths": list(self.rules.ship_lengths),
            "fleet": [
                {
                    "id": index,
                    "length": ship.length,
                    "orientation": (
                        "horizontal" if len({row for row, _column in ship.cells}) == 1 else "vertical"
                    ),
                }
                for index, ship in enumerate(self.player_board.ships)
            ],
            "playerBoard": self._board_payload(self.player_board, True),
            "enemyBoard": self._board_payload(self.enemy_board, finished),
            "playerShipsRemaining": self._remaining_ships(self.player_board),
            "enemyShipsRemaining": self._remaining_ships(self.enemy_board),
            "suggestedShot": list(suggested) if self.phase == "player_turn" else None,
            "candidatePlacementCount": candidate_count,
            "lastAiAnalysis": dict(self.last_ai_analysis) if self.last_ai_analysis else None,
            "history": list(self.history),
            "strategyScope": (
                "cluster-consistent one-step placement density on 10x10/12x12; "
                "tail-protected legacy density on 15x15; not a full-fleet posterior optimum"
            ),
            "legalActions": (
                ["randomize_fleet", "set_board_size", "rotate_ship", "start_battle"]
                if self.phase == "placement"
                else ["fire"]
                if self.phase == "player_turn"
                else []
            ),
            "informationSet": {
                "misses": [list(cell) for cell in sorted(self.advisor.misses)],
                "unresolvedHits": [list(cell) for cell in sorted(self.advisor.unresolved_hits)],
                "sunkCells": [list(cell) for cell in sorted(self.advisor.sunk_cells)],
                "remainingShipLengths": list(self.advisor.remaining_lengths),
                "candidatePlacementCount": candidate_count,
                "confirmedEnemyHits": len(self.advisor.unresolved_hits)
                + len(self.advisor.sunk_cells),
                "enemySegmentsTotal": sum(self.rules.ship_lengths),
                "searchedCells": len(self.advisor.shots),
                "boardCells": self.rules.board_size**2,
            },
        }

    @property
    def salvo_size(self) -> int:
        return 2 if self.rules.board_size == 15 else 1


class GuessWhoGameSession:
    """Single-player identity deduction with an exact strategy oracle."""

    def __init__(self, options: dict[str, object]) -> None:
        self.seed = int(options.get("seed", random.SystemRandom().randrange(2**32)))
        self._rng = random.Random(self.seed)
        self.solver = GuessWhoSolver()
        self.max_turns = 8
        self.games_completed = 0
        self.games_won = 0
        self.total_winning_turns = 0
        self.best_turns: int | None = None
        self._questions = {question.id: question for question in DEFAULT_QUESTIONS}
        self._characters = {character.name: character for character in DEFAULT_ROSTER}
        self._start()

    def _start(self) -> None:
        self.secret = self._rng.choice(DEFAULT_ROSTER)
        self.candidates = list(DEFAULT_ROSTER)
        self.used_questions: set[str] = set()
        self.turns = 0
        self.phase = "playing"
        self.history: list[dict[str, object]] = []
        self.result: dict[str, object] | None = None

    def _finish(self, won: bool, reason: str) -> None:
        # The identity is revealed when the round ends, so the final public
        # information set contains exactly the secret character even on a loss.
        self.candidates = [self.secret]
        self.phase = "finished"
        self.result = {
            "won": won,
            "reason": reason,
            "secret": self.secret.name,
            "turns": self.turns,
        }
        self.games_completed += 1
        if won:
            self.games_won += 1
            self.total_winning_turns += self.turns
            self.best_turns = self.turns if self.best_turns is None else min(self.best_turns, self.turns)

    def _ask(self, question_id: str) -> None:
        if question_id not in self._questions:
            raise ValueError("unknown Guess Who question")
        if question_id in self.used_questions:
            raise ValueError("that question has already been asked")
        question = self._questions[question_id]
        yes_candidates = [character for character in self.candidates if question.matches(character)]
        no_candidates = [character for character in self.candidates if not question.matches(character)]
        if not yes_candidates or not no_candidates:
            raise ValueError("that question no longer separates the remaining characters")
        before = len(self.candidates)
        answer = question.matches(self.secret)
        self.candidates = yes_candidates if answer else no_candidates
        self.used_questions.add(question_id)
        self.turns += 1
        self.history.append(
            {
                "turn": self.turns,
                "action": "question",
                "questionId": question_id,
                "label": question.label,
                "answer": answer,
                "beforeCandidates": before,
                "afterCandidates": len(self.candidates),
            }
        )
        if self.turns >= self.max_turns:
            self._finish(False, "turn_limit")

    def _guess(self, name: str) -> None:
        character = self._characters.get(name)
        if character is None:
            raise ValueError("unknown Guess Who character")
        if character not in self.candidates:
            raise ValueError("that character has already been eliminated")
        before = len(self.candidates)
        correct = character == self.secret
        self.turns += 1
        if not correct:
            self.candidates.remove(character)
        self.history.append(
            {
                "turn": self.turns,
                "action": "guess",
                "character": name,
                "correct": correct,
                "beforeCandidates": before,
                "afterCandidates": len(self.candidates),
            }
        )
        if correct:
            self.candidates = [self.secret]
            self._finish(True, "correct_guess")
        elif self.turns >= self.max_turns:
            self._finish(False, "turn_limit")

    def act(self, action: str, payload: dict[str, object]) -> dict[str, object]:
        if action == "new_game":
            self._start()
            return self.snapshot()
        if self.phase != "playing":
            raise ValueError("start a new Guess Who game first")
        if action == "ask_question":
            self._ask(str(payload.get("questionId", "")))
        elif action == "guess_character":
            self._guess(str(payload.get("name", "")))
        else:
            raise ValueError(f"unknown Guess Who action: {action}")
        return self.snapshot()

    def _suggestion(self) -> dict[str, object] | None:
        if self.phase != "playing":
            return None
        if len(self.candidates) == 1:
            return {
                "type": "guess",
                "character": self.candidates[0].name,
                "projectedExpectedTurns": 1.0,
                "modelScope": "exact_fixed_roster_question_bank",
            }
        candidate_mask = self.solver.candidate_mask([character.name for character in self.candidates])
        remaining_mask = self.solver.remaining_question_mask(self.used_questions)
        question_index = self.solver.choose_question(
            "optimal_expected", candidate_mask, remaining_mask
        )
        question = self.solver.questions[question_index]
        score = next(
            item
            for item in self.solver.score_questions(candidate_mask, remaining_mask)
            if item.question.id == question.id
        )
        return {
            "type": "question",
            "questionId": question.id,
            "label": question.label,
            "yesCount": score.yes_count,
            "noCount": score.no_count,
            "worstRemaining": score.worst_remaining,
            "expectedRemaining": round(score.expected_remaining, 3),
            "projectedExpectedTurns": round(
                self.solver.exact_expected_questions(candidate_mask, remaining_mask) + 1,
                3,
            ),
            "modelScope": "exact_fixed_roster_question_bank",
        }

    def snapshot(self) -> dict[str, object]:
        candidate_names = {character.name for character in self.candidates}
        candidate_mask = self.solver.candidate_mask(list(candidate_names))
        remaining_mask = self.solver.remaining_question_mask(self.used_questions)
        scores = {item.question.id: item for item in self.solver.score_questions(candidate_mask, remaining_mask)}
        finished = self.phase == "finished"
        return {
            "gameId": "guess-who",
            "phase": self.phase,
            "turnsUsed": self.turns,
            "maxTurns": self.max_turns,
            "characters": [
                {
                    "name": character.name,
                    "hair": character.hair,
                    "glasses": character.glasses,
                    "hat": character.hat,
                    "facialHair": character.facial_hair,
                    "smiling": character.smiling,
                    "possible": character.name in candidate_names,
                    "secret": finished and character == self.secret,
                }
                for character in DEFAULT_ROSTER
            ],
            "questions": [
                {
                    "id": question.id,
                    "label": question.label,
                    "used": question.id in self.used_questions,
                    "informative": question.id in scores,
                    "yesCount": scores[question.id].yes_count if question.id in scores else 0,
                    "noCount": scores[question.id].no_count if question.id in scores else 0,
                }
                for question in DEFAULT_QUESTIONS
            ],
            "suggestion": self._suggestion(),
            "history": list(self.history),
            "result": dict(self.result) if self.result else None,
            "legalActions": ["ask_question", "guess_character"] if not finished else ["new_game"],
            "sessionStats": {
                "gamesCompleted": self.games_completed,
                "gamesWon": self.games_won,
                "averageWinningTurns": (
                    self.total_winning_turns / self.games_won if self.games_won else None
                ),
                "bestTurns": self.best_turns,
            },
            "informationSet": {
                "possibleNames": sorted(candidate_names),
                "possibleCount": len(candidate_names),
                "usedQuestionIds": sorted(self.used_questions),
                "publicHistory": list(self.history),
            },
        }


class HiddenPursuitGameSession:
    """Two-detective pursuit of a hidden, belief-aware fugitive."""

    def __init__(self, options: dict[str, object]) -> None:
        self.seed = int(options.get("seed", random.SystemRandom().randrange(2**32)))
        self._rng = random.Random(self.seed)
        self.rules = HiddenPursuitRules()
        self.games_completed = 0
        self.detective_wins = 0
        self._start()

    def _start(self) -> None:
        self.state = PursuitState(self.rules, self._rng, "evasive-information")
        self._recorded = False

    def act(self, action: str, payload: dict[str, object]) -> dict[str, object]:
        if action == "new_game":
            self._start()
            return self.snapshot()
        if action != "move_detective":
            raise ValueError(f"unknown Hidden Pursuit action: {action}")
        destination = _whole_int(payload.get("node", 0), "node")
        self.state.move_detective(destination)
        if self.state.phase == "finished" and not self._recorded:
            self.games_completed += 1
            if self.state.winner == "detectives":
                self.detective_wins += 1
            self._recorded = True
        return self.snapshot()

    def snapshot(self) -> dict[str, object]:
        state = self.state
        finished = state.phase == "finished"
        return {
            "gameId": "hidden-pursuit",
            "phase": state.phase,
            "round": state.round_number,
            "maxRounds": self.rules.max_rounds,
            "revealRounds": list(self.rules.reveal_rounds),
            "detectives": list(state.detectives),
            "currentDetective": state.detective_index,
            "legalMoves": list(state.legal_detective_moves()) if not finished else [],
            "belief": sorted(state.belief),
            "lastTransport": state.last_transport.value if state.last_transport else None,
            "lastReveal": state.last_reveal,
            "fugitivePosition": state.fugitive if finished else None,
            "winner": state.winner,
            "nodes": [
                {"id": node, "x": position[0], "y": position[1]}
                for node, position in NODE_POSITIONS.items()
            ],
            "edges": [
                {"from": left, "to": right, "transport": mode.value}
                for left, right, mode in EDGES
            ],
            "history": list(state.history),
            "legalActions": ["move_detective"] if not finished else ["new_game"],
            "sessionStats": {
                "gamesCompleted": self.games_completed,
                "detectiveWins": self.detective_wins,
            },
            "informationSet": {
                "possibleNodes": sorted(state.belief),
                "possibleCount": len(state.belief),
                "lastPublicTransport": state.last_transport.value if state.last_transport else None,
                "lastRevealedNode": state.last_reveal,
            },
        }


class LoveLetterGameSession:
    """Player-facing two-player Love Letter match with a belief-only AI."""

    def __init__(self, options: dict[str, object]) -> None:
        seed = int(options.get("seed", random.SystemRandom().randrange(2**32)))
        self.game = LoveLetterGame(random.Random(seed))

    def act(self, action: str, payload: dict[str, object]) -> dict[str, object]:
        if action == "play_card":
            card = _whole_int(payload.get("card", 0), "card")
            guess_value = payload.get("guess")
            guess = None if guess_value in {None, ""} else _whole_int(guess_value, "guess")
            self.game.player_action(card, str(payload.get("target", "ai")), guess)
        elif action == "next_round":
            if self.game.phase != "round_finished":
                raise ValueError("the current round is not finished")
            self.game.start_round()
        elif action == "new_match":
            self.game = LoveLetterGame(self.game.rng)
        else:
            raise ValueError(f"unknown Love Letter action: {action}")
        return self.snapshot()

    def _play_dict(self, play: object) -> dict[str, object]:
        return {
            "card": play.card,  # type: ignore[attr-defined]
            "target": play.target,  # type: ignore[attr-defined]
            "guess": play.guess,  # type: ignore[attr-defined]
        }

    def snapshot(self) -> dict[str, object]:
        game = self.game
        finished = game.phase in {"round_finished", "match_finished"}
        belief = game.belief("player")
        total = sum(belief.values())
        suggestion = game.choose_play("player") if game.phase == "player_turn" else None
        legal_actions = ["play_card"] if game.phase == "player_turn" else (["next_round"] if game.phase == "round_finished" else ["new_match"])
        return {
            "gameId": "love-letter", "phase": game.phase,
            "roundNumber": game.round_number, "targetScore": game.target_score,
            "scores": dict(game.scores), "playerHand": list(game.hands["player"]),
            "opponentCardCount": len(game.hands["ai"]),
            "opponentHand": list(game.hands["ai"]) if finished else None,
            "deckRemaining": len(game.deck), "faceUpRemoved": list(game.face_up_removed),
            "discards": {actor: list(cards) for actor, cards in game.discards.items()},
            "protected": dict(game.protected),
            "cardCatalog": [{"value": value, "name": CARD_NAMES[value], "count": CARD_COUNTS[value]} for value in CARD_NAMES],
            "legalCards": game.legal_cards("player") if game.phase == "player_turn" else [],
            "suggestedPlay": self._play_dict(suggestion) if suggestion else None,
            "history": [dict(item) for item in game.history],
            "roundResult": {"winner": game.round_winner, "reason": game.round_reason} if finished else None,
            "matchWinner": game.round_winner if game.phase == "match_finished" else None,
            "legalActions": legal_actions,
            "strategyScope": "remaining-card belief heuristic without hidden-hand access",
            "informationSet": {
                "possibleCards": [{"value": value, "count": count, "probability": count / total if total else 0.0} for value, count in sorted(belief.items())],
                "knownOpponentCard": game.known_hand["player"],
                "publicHistory": [dict(item) for item in game.history],
            },
        }


class InvestmentGameSession:
    """Virtual-money elimination tournament with visible odds and calibrated probabilities."""

    def __init__(self, options: dict[str, object]) -> None:
        seed = int(options.get("seed", random.SystemRandom().randrange(2**32)))
        self.rng = random.Random(seed)
        self.game = InvestmentTournament(self.rng)

    def act(self, action: str, payload: dict[str, object]) -> dict[str, object]:
        if action == "invest":
            fraction = float(payload.get("fraction", 0))
            if not fraction.is_integer() and fraction not in {0.1, 0.25, 0.5, 0.75}:
                raise ValueError("choose one of the displayed stake fractions")
            if fraction not in {0.0, 0.1, 0.25, 0.5, 0.75}:
                raise ValueError("choose one of the displayed stake fractions")
            self.game.invest(str(payload.get("offerId", "")), fraction)
        elif action == "new_game":
            self.game = InvestmentTournament(self.rng)
        else:
            raise ValueError(f"unknown investment action: {action}")
        return self.snapshot()

    def snapshot(self) -> dict[str, object]:
        game = self.game
        player = next(item for item in game.contestants if item.id == "player")
        best = max(game.offers, key=lambda item: (item.expected_return, item.kelly))
        rank = next(index for index, item in enumerate(game.rankings, 1) if item.id == "player")
        return {
            "gameId": "investment",
            "phase": game.phase,
            "roundNumber": game.round_number,
            "maxRounds": game.max_rounds,
            "eliminationRounds": list(game.elimination_rounds),
            "playerRank": rank,
            "playerBankroll": player.bankroll,
            "offers": [
                {
                    "id": offer.id,
                    "netOdds": offer.net_odds,
                    "probability": offer.probability,
                    "expectedReturn": offer.expected_return,
                    "kellyFraction": offer.kelly,
                }
                for offer in game.offers
            ] if game.phase == "decision" else [],
            "rankings": [
                {"id": item.id, "name": item.name, "skill": item.skill, "bankroll": item.bankroll, "alive": item.alive}
                for item in game.rankings
            ],
            "lastRound": dict(game.history[-1]) if game.history else None,
            "winner": game.winner,
            "suggestion": {
                "offerId": best.id,
                "kellyFraction": best.kelly,
                "reason": "highest_expected_edge_then_log_growth",
            } if game.phase == "decision" else None,
            "legalActions": ["invest"] if game.phase == "decision" else ["new_game"],
            "strategyScope": "virtual bankroll; Kelly maximizes asymptotic log growth, not tournament survival or title probability",
            "informationSet": {
                "analystProbabilities": {offer.id: offer.probability for offer in game.offers},
                "opponentSkills": {item.id: item.skill for item in game.contestants if item.id != "player"},
                "privateOpponentChoices": True,
                "publicHistory": list(game.history),
            },
        }


_GOOFSPIEL_SOLVER = GoofspielSolver(4)


class GoofspielGameSession:
    """Four-round secret bidding against an exact dynamic-equilibrium AI."""

    def __init__(self, options: dict[str, object]) -> None:
        self.seed = int(options.get("seed", random.SystemRandom().randrange(2**32)))
        self.rng = random.Random(self.seed)
        self._start()

    def _start(self) -> None:
        self.prize_order = list(_GOOFSPIEL_SOLVER.cards)
        self.rng.shuffle(self.prize_order)
        self.player_cards = _GOOFSPIEL_SOLVER.cards
        self.ai_cards = _GOOFSPIEL_SOLVER.cards
        self.round_number = 1
        self.player_score = 0
        self.ai_score = 0
        self.phase = "bidding"
        self.history: list[dict[str, object]] = []

    @property
    def current_prize(self) -> int | None:
        if self.phase == "finished":
            return None
        return self.prize_order[self.round_number - 1]

    @property
    def remaining_prizes(self) -> tuple[int, ...]:
        return tuple(sorted(self.prize_order[self.round_number - 1:]))

    def _solution(self):
        current = self.current_prize
        if current is None:
            return None
        return _GOOFSPIEL_SOLVER.round_solution(
            self.player_cards,
            self.ai_cards,
            self.remaining_prizes,
            current,
        )

    def _sample_ai_bid(self, probabilities: tuple[object, ...]) -> int:
        target = self.rng.random()
        cumulative = 0.0
        for card, probability in zip(self.ai_cards, probabilities):
            cumulative += float(probability)
            if target < cumulative:
                return card
        return self.ai_cards[-1]

    def act(self, action: str, payload: dict[str, object]) -> dict[str, object]:
        if action == "new_match" and self.phase == "finished":
            self._start()
            return self.snapshot()
        if action != "bid" or self.phase != "bidding":
            raise ValueError(f"illegal Goofspiel action: {action}")
        player_bid = _whole_int(payload.get("card"), "bid card")
        if player_bid not in self.player_cards:
            raise ValueError("bid a card that remains in your hand")
        current_prize = self.current_prize
        solution = self._solution()
        assert current_prize is not None and solution is not None
        ai_bid = self._sample_ai_bid(solution.column_strategy)
        if player_bid > ai_bid:
            outcome = "player"
            self.player_score += current_prize
        elif ai_bid > player_bid:
            outcome = "ai"
            self.ai_score += current_prize
        else:
            outcome = "tie"
        self.history.append({
            "round": self.round_number,
            "prize": current_prize,
            "playerBid": player_bid,
            "aiBid": ai_bid,
            "outcome": outcome,
            "playerScore": self.player_score,
            "aiScore": self.ai_score,
            "equilibriumValue": float(solution.value),
            "aiDistribution": [
                {"card": card, "probability": float(probability)}
                for card, probability in zip(self.ai_cards, solution.column_strategy)
            ],
            "playerDistribution": [
                {"card": card, "probability": float(probability)}
                for card, probability in zip(self.player_cards, solution.row_strategy)
            ],
            "playerBidProbability": float(
                solution.row_strategy[self.player_cards.index(player_bid)]
            ),
        })
        self.player_cards = tuple(card for card in self.player_cards if card != player_bid)
        self.ai_cards = tuple(card for card in self.ai_cards if card != ai_bid)
        if self.round_number == len(self.prize_order):
            self.phase = "finished"
        else:
            self.round_number += 1
        return self.snapshot()

    def snapshot(self) -> dict[str, object]:
        solution = self._solution()
        advisor = [] if solution is None else [
            {"card": card, "probability": float(probability)}
            for card, probability in zip(self.player_cards, solution.row_strategy)
        ]
        recommended = (
            max(advisor, key=lambda item: (item["probability"], item["card"]))["card"]
            if advisor else None
        )
        winner = None
        if self.phase == "finished":
            winner = "player" if self.player_score > self.ai_score else "ai" if self.ai_score > self.player_score else "tie"
        post_match_review = None
        if self.phase == "finished":
            probabilities = [
                float(entry["playerBidProbability"]) for entry in self.history
            ]
            post_match_review = {
                "scoreDifference": self.player_score - self.ai_score,
                "equilibriumSupportedRounds": sum(
                    probability > 1e-9 for probability in probabilities
                ),
                "averageChosenProbability": sum(probabilities) / len(probabilities),
                "offSupportRounds": [
                    int(entry["round"])
                    for entry in self.history
                    if float(entry["playerBidProbability"]) <= 1e-9
                ],
                "lowFrequencyRounds": [
                    int(entry["round"])
                    for entry in self.history
                    if 0 < float(entry["playerBidProbability"]) < 0.1
                ],
            }
        return {
            "gameId": "goofspiel",
            "phase": self.phase,
            "roundNumber": self.round_number,
            "roundsTotal": len(self.prize_order),
            "currentPrize": self.current_prize,
            "playerCards": list(self.player_cards),
            "aiCards": list(self.ai_cards),
            "playerScore": self.player_score,
            "aiScore": self.ai_score,
            "history": [dict(item) for item in self.history],
            "lastRound": dict(self.history[-1]) if self.history else None,
            "winner": winner,
            "postMatchReview": post_match_review,
            "advisorDistribution": advisor,
            "recommendedBid": recommended,
            "futureValue": float(solution.value) if solution is not None else 0.0,
            "legalActions": ["bid"] if self.phase == "bidding" else ["new_match"],
            "strategyScope": "exact four-card shuffled-prize zero-sum equilibrium",
            "informationSet": {
                "currentPrize": self.current_prize,
                "playerRemaining": list(self.player_cards),
                "aiRemaining": list(self.ai_cards),
                "aiCurrentBidHidden": self.phase == "bidding",
                "unrevealedPrizeCount": len(self.remaining_prizes) - 1 if self.phase == "bidding" else 0,
                "publicHistory": [dict(item) for item in self.history],
            },
        }


def build_default_registry() -> GameRegistry:
    registry = GameRegistry()
    registry.register(
        GameDescriptor(
            "cases",
            "命运之箱",
            "从 26 个密封箱中保留一个，在不断缩小的风险中与银行家谈判。",
            "单人 · 决策与风险",
        ),
        CaseGameSession,
    )
    registry.register(
        GameDescriptor(
            "worm",
            "移动虫穴",
            "虫子每次失手后必向相邻洞移动；找出能保证抓住它的检查节奏。",
            "单人 · 隐藏状态追踪",
        ),
        WormGameSession,
    )
    registry.register(
        GameDescriptor(
            "pirates",
            "海盗议会",
            "亲自分配 100 枚金币，面对会做逆向归纳的理性海盗投票。",
            "单人 · 人机投票",
        ),
        PirateGameSession,
    )
    registry.register(
        GameDescriptor(
            "kuhn-poker",
            "库恩扑克",
            "只用三张牌与策略型 AI 对决：读取下注信号，决定诈唬、跟注或弃牌。",
            "单人 · 隐藏手牌与诈唬",
        ),
        KuhnPokerSession,
    )
    registry.register(
        GameDescriptor(
            "e-card",
            "E-Card 皇帝牌",
            "皇帝、市民与奴隶构成不对称循环；用隐藏出牌和高额弱者收益击败策略型 AI。",
            "单人 · 非对称混合策略",
        ),
        ECardSession,
    )
    registry.register(
        GameDescriptor(
            "restricted-rps",
            "限定猜拳实验室",
            "固定库存让每次出拳都消耗未来选择；对抗均衡随机化与会学习的策略型 AI。",
            "单人 · 资源约束与机制设计",
        ),
        RestrictedRPSSession,
    )
    registry.register(
        GameDescriptor(
            "blackjack",
            "21 点策略实验室",
            "在透明规则下对抗庄家，比较自己的决策与规则限定的最优基础策略。",
            "单人 · 概率决策与策略审计",
        ),
        BlackjackSession,
    )
    registry.register(
        GameDescriptor(
            "liars-dice",
            "骗子骰子",
            "隐藏手牌、公开叫价与质疑概率；用信息集判断何时加注，何时抓住 AI 的虚张声势。",
            "单人 · 隐藏骰子与公开信号",
        ),
        LiarDiceSession,
    )
    registry.register(
        GameDescriptor(
            "mastermind",
            "猜数字 · 密码破解",
            "从 5,040 个隐藏密码中推理答案，并比较自己的步数与 minimax 信息策略。",
            "单人 · 信息集搜索",
        ),
        MastermindSession,
    )
    registry.register(
        GameDescriptor(
            "battleship",
            "海战棋",
            "部署自己的舰队，在未知海域中搜索敌舰，并对抗概率热力图 AI。",
            "单人 · 隐藏部署与概率搜索",
        ),
        BattleshipGameSession,
    )
    registry.register(
        GameDescriptor(
            "guess-who",
            "猜猜我是谁",
            "通过公开的是非问题缩小 24 人候选集合，并与精确最优提问策略比较步数。",
            "单人 · 身份推理与信息分割",
        ),
        GuessWhoGameSession,
    )
    registry.register(
        GameDescriptor(
            "hidden-pursuit",
            "隐形追踪",
            "控制两名侦探围捕隐藏移动的目标；交通信号公开，但位置只会间歇暴露。",
            "单人 · 隐藏移动与信念追踪",
        ),
        HiddenPursuitGameSession,
    )
    registry.register(
        GameDescriptor(
            "love-letter",
            "情书决斗",
            "在 16 张角色牌中读取公开弃牌与隐蔽手牌，用推理、保护和点杀先赢得四轮。",
            "单人 · 手牌推断与风险控制",
        ),
        LoveLetterGameSession,
    )
    registry.register(
        GameDescriptor(
            "investment",
            "Kelly 生存投资赛",
            "在赔率与胜率之间选择，并管理仓位；每个淘汰点资金最低者离场，最终争夺第一。",
            "单人 · 增长率、风险与相对排名",
        ),
        InvestmentGameSession,
    )
    registry.register(
        GameDescriptor(
            "goofspiel",
            "秘密竞价",
            "奖牌逐轮揭晓，双方同时秘密打出唯一的竞价牌；用有限手牌对抗精确均衡 AI。",
            "单人 · 同时行动与秘密竞价",
        ),
        GoofspielGameSession,
    )
    for descriptor in (
        GameDescriptor(
            "auction",
            "百元全支付拍卖",
            "用公开价格争夺主导权，并观察联盟与背叛。",
            "本地多人 · 即将开放",
            False,
        ),
    ):
        registry.register(descriptor, lambda _options: CaseGameSession({}))
    return registry
