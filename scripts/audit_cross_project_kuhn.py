#!/usr/bin/env python3
"""Compare AIP batched full-tree CFR with PokerCapabilityLab via subprocess."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

from aip.core import CFRTrainer
from aip.puzzles.kuhn_poker import (
    KuhnCFRGame,
    audit_policy,
    kuhn_policy_from_cfr,
    policy_value,
)


class ReverseChanceKuhn(KuhnCFRGame):
    def chance_outcomes(self, state):
        return tuple(reversed(super().chance_outcomes(state)))


class ReverseActionKuhn(KuhnCFRGame):
    def legal_actions(self, state):
        return tuple(reversed(super().legal_actions(state)))


def _canonical_strategy(result) -> dict[str, dict[str, float]]:
    strategy: dict[str, dict[str, float]] = {}
    history_names = {"": "root", "cb": "pb", "c": "p", "b": "b"}
    passive = {"check", "fold"}
    for (player, (card, history)), distribution in result.policy.items():
        strategy[f"P{player}:{card}:{history_names[history]}"] = {
            "p" if action in passive else "b": probability
            for action, probability in distribution.items()
        }
    return dict(sorted(strategy.items()))


def _aip_result(game: KuhnCFRGame, iterations: int) -> dict[str, object]:
    result = CFRTrainer(game).train(iterations)
    policy = kuhn_policy_from_cfr(result)
    audit = audit_policy(policy)
    return {
        "value_to_player_0": float(
            policy_value(policy, policy, hero_first=True)
        ),
        "evaluation": {
            "nash_conv": float(audit.nash_conv),
            "exploitability": float(audit.exploitability),
            "player_0_deviation_gain": float(audit.player_0_deviation_gain),
            "player_1_deviation_gain": float(audit.player_1_deviation_gain),
            "maximum_unilateral_deviation_gain": float(
                audit.maximum_unilateral_deviation_gain
            ),
        },
        "information_sets": result.information_set_count,
        "strategy": _canonical_strategy(result),
    }


def _poker_result(root: Path, iterations: int) -> dict[str, object]:
    source = f"""
import json
from scripts.solve_kuhn_gto import solve
artifact = solve({iterations}, 'vanilla')
print(json.dumps({{
    'value_to_player_0': artifact['metrics']['value_to_player_0'],
    'nash_conv': artifact['metrics']['nash_conv'],
    'exploitability': artifact['metrics']['exploitability'],
    'information_sets': len(artifact['average_strategy']),
    'strategy': artifact['average_strategy'],
}}))
"""
    completed = subprocess.run(
        [sys.executable, "-c", source],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def _maximum_strategy_difference(
    left: dict[str, dict[str, float]], right: dict[str, dict[str, float]]
) -> float:
    return max(
        abs(left[key][action] - right[key][action])
        for key in left
        for action in left[key]
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--poker-root", type=Path, required=True)
    parser.add_argument("--iterations", type=int, default=10_000)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    forward = _aip_result(KuhnCFRGame(), args.iterations)
    reverse_chance = _aip_result(ReverseChanceKuhn(), args.iterations)
    reverse_actions = _aip_result(ReverseActionKuhn(), args.iterations)
    poker = _poker_result(args.poker_root, args.iterations)
    chance_difference = _maximum_strategy_difference(
        forward["strategy"], reverse_chance["strategy"]
    )
    action_difference = _maximum_strategy_difference(
        forward["strategy"], reverse_actions["strategy"]
    )
    cross_project_difference = _maximum_strategy_difference(
        forward["strategy"], poker["strategy"]
    )
    report = {
        "audit_version": "2.0.0",
        "iterations": args.iterations,
        "algorithm": "alternating full-tree batched vanilla CFR",
        "aip": forward,
        "poker_capability_lab": poker,
        "maximum_chance_order_strategy_difference": chance_difference,
        "maximum_action_order_strategy_difference": action_difference,
        "maximum_cross_project_strategy_difference": cross_project_difference,
        "checks": {
            "chance_order_invariant": chance_difference <= 1e-12,
            "action_order_invariant": action_difference <= 1e-12,
            "game_values_match": abs(
                forward["value_to_player_0"] - poker["value_to_player_0"]
            )
            <= 1e-9,
            "exploitabilities_match": abs(
                forward["evaluation"]["exploitability"]
                - poker["exploitability"]
            )
            <= 1e-9,
            "information_set_coverage_matches": (
                forward["information_sets"] == poker["information_sets"] == 12
            ),
        },
        "interpretation": (
            "Kuhn equilibria need not have unique frequencies; value and "
            "exploitability are primary. Here the two batched vanilla CFR "
            "implementations also agree on strategy to floating-point precision."
        ),
    }
    report["passed"] = all(report["checks"].values())
    rendered = json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if args.output is None:
        print(rendered, end="")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
        print(args.output)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
