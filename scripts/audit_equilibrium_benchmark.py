#!/usr/bin/env python3
"""Export exact Kuhn and Goofspiel equilibrium metric sanity checks."""

from __future__ import annotations

import json
from dataclasses import asdict
from fractions import Fraction
from pathlib import Path

from aip.benchmark import evaluate_goofspiel_policy, evaluate_kuhn_policy
from aip.puzzles.kuhn_poker import equilibrium_policy, legacy_policy


def encode(value: object) -> object:
    if isinstance(value, Fraction):
        return {"exact": str(value), "decimal": float(value)}
    if isinstance(value, dict):
        return {key: encode(item) for key, item in value.items()}
    return value


def report() -> dict[str, object]:
    return {
        "date": "2026-09-04",
        "evidenceLevel": "equilibrium_backed",
        "kuhnPoker": {
            "equilibrium": encode(asdict(evaluate_kuhn_policy(equilibrium_policy()))),
            "legacy": encode(asdict(evaluate_kuhn_policy(legacy_policy()))),
            "scope": "complete three-card Kuhn behavior policies; exhaustive pure best responses",
        },
        "goofspiel": {
            policy: encode(asdict(evaluate_goofspiel_policy(policy)))
            for policy in ("equilibrium", "random", "match_prize", "high_card")
        },
        "claims": {
            "provedGlobalGameOptimality": False,
            "exactWithinDeclaredFiniteModels": True,
            "llmEvaluationExecuted": False,
            "liarsDiceOpponentShiftExecuted": False,
            "formalAblationExecuted": False,
        },
    }


def main() -> int:
    destination = Path("research/results/equilibrium_metrics_2026-09-04.json")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(report(), indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
