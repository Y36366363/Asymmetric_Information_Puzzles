from __future__ import annotations

import random
import threading
import uuid
from dataclasses import dataclass
from typing import Callable, Protocol

from aip.puzzles.cases.models import CLASSROOM_BANKER, CaseGameRules, RiskPreferences
from aip.puzzles.cases.solver import CaseGameAnalyzer


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
    for descriptor in (
        GameDescriptor(
            "liars-dice",
            "骗子骰子",
            "隐藏手牌、公开叫价与诈唬识别。",
            "本地多人 · 即将开放",
            False,
        ),
        GameDescriptor(
            "pirates",
            "海盗议会",
            "扮演提案者，在有限金币与生死投票中组建联盟。",
            "人机博弈 · 即将开放",
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
