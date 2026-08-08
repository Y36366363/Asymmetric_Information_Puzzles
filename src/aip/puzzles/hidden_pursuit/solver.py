from __future__ import annotations

import random
from collections import deque
from dataclasses import dataclass, field
from statistics import mean

from .models import NODE_POSITIONS, HiddenPursuitRules, Transport, adjacency


GRAPH = adjacency()


def _distances(start: int) -> dict[int, int]:
    result = {start: 0}
    queue = deque([start])
    while queue:
        node = queue.popleft()
        for neighbor, _mode in GRAPH[node]:
            if neighbor not in result:
                result[neighbor] = result[node] + 1
                queue.append(neighbor)
    return result


DISTANCES = {node: _distances(node) for node in NODE_POSITIONS}


@dataclass(slots=True)
class PursuitState:
    rules: HiddenPursuitRules
    rng: random.Random
    fugitive_policy: str = "evasive-information"
    detectives: list[int] = field(init=False)
    fugitive: int = field(init=False)
    belief: set[int] = field(init=False)
    round_number: int = 1
    detective_index: int = 0
    phase: str = "detective_turn"
    winner: str | None = None
    last_transport: Transport | None = None
    last_reveal: int | None = None
    history: list[dict[str, object]] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.detectives = list(self.rules.detective_starts)
        candidates = sorted(set(NODE_POSITIONS) - set(self.detectives))
        self.fugitive = self.rng.choice(candidates)
        self.belief = set(candidates)

    def legal_detective_moves(self, index: int | None = None) -> tuple[int, ...]:
        target_index = self.detective_index if index is None else index
        occupied = self.detectives[1 - target_index]
        return tuple(
            node for node, _mode in GRAPH[self.detectives[target_index]] if node != occupied
        )

    def move_detective(self, destination: int) -> None:
        if self.phase != "detective_turn":
            raise ValueError("detectives can move only during their turn")
        if destination not in self.legal_detective_moves():
            raise ValueError("destination is not a legal detective move")
        actor = self.detective_index
        origin = self.detectives[actor]
        self.detectives[actor] = destination
        if destination == self.fugitive:
            self.phase = "finished"
            self.winner = "detectives"
            self.belief = {destination}
            self.history.append(
                {"round": self.round_number, "actor": actor, "from": origin,
                 "to": destination, "capture": True}
            )
            return
        self.belief.discard(destination)
        self.history.append(
            {"round": self.round_number, "actor": actor, "from": origin,
             "to": destination, "capture": False}
        )
        if actor == 0:
            self.detective_index = 1
        else:
            self.detective_index = 0
            self._move_fugitive()

    def _candidate_fugitive_moves(self) -> list[tuple[int, Transport]]:
        occupied = set(self.detectives)
        return [(node, mode) for node, mode in GRAPH[self.fugitive] if node not in occupied]

    def _belief_after(self, mode: Transport) -> set[int]:
        occupied = set(self.detectives)
        return {
            destination
            for origin in self.belief
            for destination, edge_mode in GRAPH[origin]
            if edge_mode == mode and destination not in occupied
        }

    def _choose_fugitive_move(self, candidates: list[tuple[int, Transport]]) -> tuple[int, Transport]:
        if self.fugitive_policy == "random":
            return self.rng.choice(candidates)
        if self.fugitive_policy not in {"distance", "evasive-information"}:
            raise ValueError(f"unknown fugitive policy: {self.fugitive_policy}")

        scored: list[tuple[float, int, Transport]] = []
        for destination, mode in candidates:
            distance = min(DISTANCES[destination][detective] for detective in self.detectives)
            exits = sum(node not in self.detectives for node, _edge_mode in GRAPH[destination])
            ambiguity = len(self._belief_after(mode))
            score = distance * 20 + exits
            if self.fugitive_policy == "evasive-information":
                score += ambiguity * 0.35
            scored.append((score, destination, mode))
        best_score = max(item[0] for item in scored)
        best = [(destination, mode) for score, destination, mode in scored if score == best_score]
        return self.rng.choice(best)

    def _move_fugitive(self) -> None:
        candidates = self._candidate_fugitive_moves()
        if not candidates:
            self.phase = "finished"
            self.winner = "detectives"
            self.belief = {self.fugitive}
            return
        origin = self.fugitive
        destination, mode = self._choose_fugitive_move(candidates)
        self.fugitive = destination
        self.last_transport = mode
        self.belief = self._belief_after(mode)
        revealed = self.round_number in self.rules.reveal_rounds
        if revealed:
            self.belief = {destination}
            self.last_reveal = destination
        self.history.append(
            {"round": self.round_number, "actor": "fugitive", "from": None,
             "to": destination if revealed else None, "transport": mode.value,
             "revealed": revealed}
        )
        if self.round_number >= self.rules.max_rounds:
            self.phase = "finished"
            self.winner = "fugitive"
            # The hidden location becomes public when the match ends, so the
            # post-game information set should match the revealed map marker.
            self.belief = {destination}
        else:
            self.round_number += 1


@dataclass(frozen=True, slots=True)
class SimulationResult:
    detective_policy: str
    fugitive_policy: str
    games: int
    capture_rate: float
    mean_capture_round: float | None


class HiddenPursuitSimulator:
    def __init__(self, rules: HiddenPursuitRules | None = None) -> None:
        self.rules = rules or HiddenPursuitRules()

    def _detective_move(self, state: PursuitState, policy: str, rng: random.Random) -> int:
        legal = state.legal_detective_moves()
        if policy == "random":
            return rng.choice(legal)
        if policy != "belief-pursuit":
            raise ValueError(f"unknown detective policy: {policy}")
        belief = state.belief
        scored = []
        for node in legal:
            hit_probability = 1 / len(belief) if node in belief else 0
            average_distance = mean(DISTANCES[node][candidate] for candidate in belief)
            scored.append((hit_probability * 100 - average_distance, -node, node))
        return max(scored)[2]

    def play(
        self,
        detective_policy: str,
        fugitive_policy: str,
        seed: int,
    ) -> tuple[str, int]:
        rng = random.Random(seed)
        state = PursuitState(self.rules, rng, fugitive_policy)
        while state.phase != "finished":
            move = self._detective_move(state, detective_policy, rng)
            state.move_detective(move)
        return state.winner or "fugitive", state.round_number

    def compare(self, games: int = 500, seed: int = 20260808) -> tuple[SimulationResult, ...]:
        if games < 1:
            raise ValueError("games must be positive")
        results = []
        for detective_policy in ("random", "belief-pursuit"):
            for fugitive_policy in ("random", "distance", "evasive-information"):
                outcomes = [
                    self.play(detective_policy, fugitive_policy, seed + game)
                    for game in range(games)
                ]
                capture_rounds = [round_number for winner, round_number in outcomes if winner == "detectives"]
                results.append(
                    SimulationResult(
                        detective_policy,
                        fugitive_policy,
                        games,
                        round(len(capture_rounds) / games, 3),
                        round(mean(capture_rounds), 2) if capture_rounds else None,
                    )
                )
        return tuple(results)
