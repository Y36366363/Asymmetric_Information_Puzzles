"""Deterministic export boundary for regret-minimization solver artifacts."""

from __future__ import annotations

from collections.abc import Callable
import json
from math import isfinite
from pathlib import Path
from typing import Hashable

from aip.core.cfr import CFRResult, EquilibriumEvaluation


Encoder = Callable[[Hashable], object]


class CFRArtifactExporter:
    """Export solver state separately from its independent BR evaluation."""

    schema_version = "aip-regret-minimization-artifact-v1"

    def __init__(
        self,
        *,
        encode_information_set: Encoder = repr,
        encode_action: Encoder = repr,
    ) -> None:
        self._encode_information_set = encode_information_set
        self._encode_action = encode_action

    def build(
        self,
        result: CFRResult,
        *,
        game_id: str,
        independent_evaluation: EquilibriumEvaluation,
    ) -> dict[str, object]:
        if result.algorithm is None:
            raise ValueError("solver artifact requires algorithm metadata")
        if not game_id:
            raise ValueError("solver artifact requires a nonempty game ID")
        evaluation_report = independent_evaluation.to_report()
        if any(
            not isfinite(value) or value < 0 for value in evaluation_report.values()
        ):
            raise ValueError(
                "solver artifact requires finite, nonnegative independent evaluation"
            )
        if (
            result.convergence_trace
            and result.convergence_trace[-1].iteration == result.iterations
            and any(
                abs(
                    result.convergence_trace[-1].independent_evaluation[name] - value
                )
                > 1e-12
                for name, value in evaluation_report.items()
            )
        ):
            raise ValueError("final checkpoint and independent evaluation disagree")
        records = []
        for (player, information_set), distribution in sorted(
            result.policy.items(), key=lambda item: repr(item[0])
        ):
            records.append(
                {
                    "player": player,
                    "information_set": self._encode_information_set(information_set),
                    "actions": [
                        {
                            "action": self._encode_action(action),
                            "probability": probability,
                        }
                        for action, probability in distribution.items()
                    ],
                    "visits": result.information_set_visits[(player, information_set)],
                }
            )
        return {
            "schema_version": self.schema_version,
            "game_id": game_id,
            "algorithm": result.algorithm.to_artifact(),
            "iterations": result.iterations,
            "training_diagnostics": {
                "average_positive_regret": list(result.average_positive_regret),
                "not_an_exploitability_measure": True,
            },
            "independent_evaluation": evaluation_report,
            "convergence_trace": [
                checkpoint.to_artifact() for checkpoint in result.convergence_trace
            ],
            "policy": records,
        }

    def write(
        self,
        result: CFRResult,
        destination: Path,
        *,
        game_id: str,
        independent_evaluation: EquilibriumEvaluation,
    ) -> None:
        artifact = self.build(
            result,
            game_id=game_id,
            independent_evaluation=independent_evaluation,
        )
        destination.write_text(
            json.dumps(artifact, indent=2, sort_keys=True, allow_nan=False) + "\n",
            encoding="utf-8",
        )
