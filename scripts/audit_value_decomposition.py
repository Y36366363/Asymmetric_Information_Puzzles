#!/usr/bin/env python3
"""Audit the shared value-decomposition interface on Liar and Goofspiel."""

from __future__ import annotations

import json
from pathlib import Path

from aip.benchmark.goofspiel import (
    GoofspielValueDecompositionOracle,
    build_goofspiel_oracle_probes,
)
from aip.benchmark.liar_transfer import (
    LiarValueDecompositionOracle,
    build_consensus_reference_profiles,
    select_profile_invariant_probes,
)
from aip.benchmark.love_letter import (
    LoveLetterValueDecompositionOracle,
    love_letter_action_id,
)
from aip.benchmark.value_decomposition import score_value_decomposition
from aip.core import CFRGameProperties, compile_sequence_form, solve_sequence_form
from aip.puzzles.love_letter import LoveLetterCFRGame, LoveLetterIndependentEvaluator


OUTPUT = Path("research/results/value_decomposition_audit_2026-09-25.json")


def _summary(probes, oracle, expected_values):
    rows = []
    for probe in probes:
        reference = oracle.decompose(probe)
        self_score = score_value_decomposition(reference, reference)
        reconstruction = max(
            abs(reference.total_action_values[action] - float(value))
            for action, value in expected_values(probe).items()
        )
        rows.append({
            "probeId": probe.probe_id,
            "chosenActionId": reference.chosen_action_id,
            "posteriorStates": len(reference.posterior),
            "actions": len(reference.total_action_values),
            "maximumAdditivityResidual": reference.maximum_additivity_residual,
            "maximumTotalValueReconstructionError": reconstruction,
            "selfScore": self_score.to_artifact(),
            "decomposition": reference.to_artifact(),
        })
    return {
        "oracleId": oracle.oracle_id,
        "probes": len(rows),
        "maximumAdditivityResidual": max(
            row["maximumAdditivityResidual"] for row in rows
        ),
        "maximumTotalValueReconstructionError": max(
            row["maximumTotalValueReconstructionError"] for row in rows
        ),
        "allSelfScoresWithinTolerance": all(
            row["selfScore"]["posteriorBrier"] <= 1e-12
            and row["selfScore"]["immediateValueMae"] <= 1e-12
            and row["selfScore"]["continuationValueMae"] <= 1e-12
            and row["selfScore"]["totalValueMae"] <= 1e-12
            and row["selfScore"]["finalActionRegret"] <= 1e-12
            and row["selfScore"]["optimalActionAgreement"]
            for row in rows
        ),
        "rows": rows,
    }


def build_report():
    liar_probes, liar_audit = select_profile_invariant_probes(
        build_consensus_reference_profiles(), count=30
    )
    goofspiel_probes = build_goofspiel_oracle_probes()
    liar = _summary(
        liar_probes,
        LiarValueDecompositionOracle(),
        lambda probe: probe.exact_action_values,
    )
    goofspiel = _summary(
        goofspiel_probes,
        GoofspielValueDecompositionOracle(),
        lambda probe: probe.exact_action_values,
    )
    love_game = LoveLetterCFRGame.late_round_subgame()
    love_solution = solve_sequence_form(
        compile_sequence_form(
            love_game,
            game_properties=CFRGameProperties(2, True, True, True),
            sparse=True,
        ),
        backend="scipy_highs",
    )
    love_values = LoveLetterIndependentEvaluator(love_game).action_values(
        love_solution.policy
    )
    love_panel = LoveLetterValueDecompositionOracle(love_game).decompose_all(
        love_solution.policy
    )
    love_rows = []
    for key, reference in love_panel.decompositions.items():
        self_score = score_value_decomposition(reference, reference)
        expected = {
            love_letter_action_id(action): value
            for action, value in love_values[key].items()
        }
        reconstruction = max(
            abs(reference.total_action_values[action] - expected[action])
            for action in expected
        )
        love_rows.append({
            "informationSet": repr(key),
            "posteriorStates": len(reference.posterior),
            "actions": len(reference.total_action_values),
            "maximumAdditivityResidual": reference.maximum_additivity_residual,
            "maximumTotalValueReconstructionError": reconstruction,
            "selfScore": self_score.to_artifact(),
        })
    love = {
        "oracleId": LoveLetterValueDecompositionOracle.oracle_id,
        "totalInformationSets": love_panel.total_information_sets,
        "scoredReachableInformationSets": len(love_panel.decompositions),
        "zeroReachInformationSets": len(love_panel.zero_reach_information_sets),
        "zeroReachInformationSetKeys": [
            repr(key) for key in love_panel.zero_reach_information_sets
        ],
        "maximumAdditivityResidual": max(
            row["maximumAdditivityResidual"] for row in love_rows
        ),
        "maximumTotalValueReconstructionError": max(
            row["maximumTotalValueReconstructionError"] for row in love_rows
        ),
        "allSelfScoresWithinTolerance": all(
            row["selfScore"]["posteriorBrier"] <= 1e-12
            and row["selfScore"]["finalActionRegret"] <= 1e-12
            and row["selfScore"]["optimalActionAgreement"]
            for row in love_rows
        ),
        "exactActionValueInformationSets": len(love_values),
        "rows": love_rows,
    }
    passed = (
        liar["allSelfScoresWithinTolerance"]
        and goofspiel["allSelfScoresWithinTolerance"]
        and liar["maximumTotalValueReconstructionError"] < 1e-12
        and goofspiel["maximumTotalValueReconstructionError"] < 1e-12
        and liar["maximumAdditivityResidual"] < 1e-12
        and goofspiel["maximumAdditivityResidual"] < 1e-12
        and love["allSelfScoresWithinTolerance"]
        and love["maximumTotalValueReconstructionError"] < 1e-12
        and love["maximumAdditivityResidual"] < 1e-12
        and love["scoredReachableInformationSets"] + love["zeroReachInformationSets"]
        == love["totalInformationSets"]
    )
    return {
        "schemaVersion": "aip-value-decomposition-audit-v1",
        "date": "2026-09-25",
        "updatedDate": "2026-09-26",
        "pipeline": [
            "posterior",
            "immediate_action_values",
            "continuation_action_values",
            "total_action_values",
            "final_action",
        ],
        "games": {
            "one-die-liars-dice": liar,
            "goofspiel-four-card": goofspiel,
            "love-letter-four-card-subgame": love,
        },
        "liarPanelAudit": liar_audit,
        "passed": passed,
        "claimRestrictions": {
            "modelEvaluated": False,
            "runtimePolicyChanged": False,
            "fullLoveLetterCertified": False,
            "decompositionCorrectnessImpliesGto": False,
        },
    }


def main() -> int:
    report = build_report()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "output": str(OUTPUT),
        "passed": report["passed"],
        "games": {
            game: {
                "scoredStates": summary.get(
                    "probes", summary.get("scoredReachableInformationSets")
                ),
                "maximumAdditivityResidual": summary["maximumAdditivityResidual"],
                "maximumTotalValueReconstructionError": summary["maximumTotalValueReconstructionError"],
            }
            for game, summary in report["games"].items()
        },
    }, indent=2, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
