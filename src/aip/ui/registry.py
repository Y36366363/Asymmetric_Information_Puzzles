from __future__ import annotations

import random
import threading
import uuid
from dataclasses import dataclass
from typing import Callable, Protocol

from aip.puzzles.cases.models import CLASSROOM_BANKER, CaseGameRules, RiskPreferences
from aip.puzzles.cases.solver import CaseGameAnalyzer
from aip.puzzles.pirates.models import PirateRules
from aip.puzzles.pirates.solver import PirateSolver
from aip.puzzles.worm.solver import WormSolver


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


class GameRegistry:
    """Maps stable game identifiers to isolated playable session factories."""

    def __init__(self) -> None:
        self._entries: dict[str, tuple[GameDescriptor, SessionFactory]] = {}

    def register(self, descriptor: GameDescriptor, factory: SessionFactory) -> None:
        if descriptor.game_id in self._entries:
            raise ValueError(f"duplicate game id: {descriptor.game_id}")
        self._entries[descriptor.game_id] = (descriptor, factory)

    def list_games(self) -> tuple[GameDescriptor, ...]:
        return tuple(descriptor for descriptor, _factory in self._entries.values())

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

    def __init__(self, registry: GameRegistry) -> None:
        self.registry = registry
        self._sessions: dict[str, PlayableSession] = {}
        self._lock = threading.RLock()

    def games(self) -> list[dict[str, object]]:
        return [game.as_dict() for game in self.registry.list_games()]

    def create_session(
        self, game_id: str, options: dict[str, object] | None = None
    ) -> dict[str, object]:
        session = self.registry.create(game_id, options or {})
        session_id = uuid.uuid4().hex
        with self._lock:
            self._sessions[session_id] = session
        return {"sessionId": session_id, "state": session.snapshot()}

    def snapshot(self, session_id: str) -> dict[str, object]:
        with self._lock:
            return self._get(session_id).snapshot()

    def act(
        self, session_id: str, action: str, payload: dict[str, object] | None = None
    ) -> dict[str, object]:
        with self._lock:
            return self._get(session_id).act(action, payload or {})

    def _get(self, session_id: str) -> PlayableSession:
        try:
            return self._sessions[session_id]
        except KeyError as error:
            raise ValueError("unknown or expired session") from error


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
        self.history.append({"kind": "deal", "value": self.payout})

    def _no_deal(self) -> None:
        if self.phase != "offer":
            raise ValueError("there is no offer to reject")
        self.history.append({"kind": "no_deal", "round": self.round_index + 1})
        if len(self._remaining_values()) == 1:
            self.payout = self._values[self.chosen_case]  # type: ignore[index]
            self.phase = "finished"
            self.history.append({"kind": "case_payout", "value": self.payout})
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
            "metrics": metrics,
            "payout": self.payout,
            "history": list(self.history),
            "riskTolerance": self.risk.risk_tolerance,
        }


class WormGameSession:
    """Playable hidden-worm search with a public belief-state companion."""

    def __init__(self, options: dict[str, object]) -> None:
        self.hole_count = int(options.get("holes", 5))
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
        self._check_hole(int(payload.get("holeId", 0)))
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
        }


class PirateGameSession:
    """One human proposal against backward-induction pirate voters."""

    def __init__(self, options: dict[str, object]) -> None:
        self.pirate_count = int(options.get("pirates", 5))
        self.total_gold = int(options.get("gold", 100))
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
        self._submit(tuple(int(value) for value in raw_allocation))
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
        }


class KuhnPokerSession:
    """A short repeated poker match with private cards and a mixed-strategy AI."""

    CARDS = ("J", "Q", "K")

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
        should_bet = self.ai_card == "K" or (
            self.ai_card == "J" and self._rng.random() < 1 / 3
        )
        action = "bet" if should_bet else "check"
        self.history.append({"actor": "ai", "action": action})
        if action == "bet":
            self.pot = 3
            self.legal_actions = ["fold", "call"]
        else:
            self.legal_actions = ["check", "bet"]

    def _ai_after_player_check(self) -> None:
        should_bet = self.ai_card == "K" or (
            self.ai_card == "J" and self._rng.random() < 1 / 3
        )
        action = "bet" if should_bet else "check"
        self.history.append({"actor": "ai", "action": action})
        if action == "bet":
            self.pot = 3
            self.legal_actions = ["fold", "call"]
        else:
            self._showdown(1, "both_checked")

    def _ai_facing_bet(self) -> None:
        should_call = self.ai_card == "K" or (
            self.ai_card == "Q" and self._rng.random() < 1 / 3
        )
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
            "informationSet": {
                "privateCard": self.player_card,
                "publicHistory": public_history,
                "possibleOpponentCards": possible_ai_cards,
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
    for descriptor in (
        GameDescriptor(
            "liars-dice",
            "骗子骰子",
            "隐藏手牌、公开叫价与诈唬识别。",
            "本地多人 · 即将开放",
            False,
        ),
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
