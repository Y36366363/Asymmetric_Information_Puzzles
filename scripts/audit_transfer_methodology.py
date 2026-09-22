#!/usr/bin/env python3
"""Audit whether AIP is ready to expand its cross-game transfer benchmark."""

from __future__ import annotations

import json
import math
import random
from pathlib import Path
from statistics import mean, stdev

from aip.benchmark import evaluate_goofspiel_policy
from aip.benchmark.liar_transfer import (
    ARMS,
    SEED,
    build_oracle_probes,
    compare_probe_oracles,
    opponent_reach_mass,
    select_profile_invariant_probes,
)
from aip.core import create_regret_minimization_trainer, run_independent_evaluation
from aip.puzzles.liars_dice import (
    OneDieLiarDiceCFRGame,
    OneDieLiarIndependentEvaluator,
    load_one_die_liar_policy,
    solve_one_die_liar_exact,
)


ROOT = Path(__file__).resolve().parents[1]
LIAR_DIR = ROOT / "research/results/liar_transfer_confirmatory_2026-09-21"
GUESS_DIR = ROOT / "research/results/focused_transfer_2026-09-20"
DESTINATION = ROOT / "research/results/transfer_methodology_audit_2026-09-22.json"


def load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def compact_equilibrium_report(name: str, profile) -> dict[str, object]:
    report = run_independent_evaluation(
        OneDieLiarIndependentEvaluator(),
        profile,
        maximum_exploitability=1.0,
    )
    return {
        "name": name,
        "profileFingerprint": report.profile_fingerprint,
        "expectedValueToPlayer0": report.expected_value_to_player_0,
        "nashConv": report.nash_conv,
        "exploitability": report.exploitability,
        "maximumUnilateralDeviationGain": report.maximum_unilateral_deviation_gain,
    }


def clustered_differences(plan, rows, arm: str, allowed: set[str] | None = None):
    by_cell = {
        (row["probeId"], row["arm"], row["repeat"]): row for row in rows
    }
    output = []
    for probe in plan["probes"]:
        probe_id = probe["id"]
        if allowed is not None and probe_id not in allowed:
            continue
        output.append(mean(
            float(by_cell[(probe_id, arm, repeat)]["penalizedActionRegret"])
            - float(by_cell[(probe_id, "no_memory", repeat)]["penalizedActionRegret"])
            for repeat in range(1, plan["repeats"] + 1)
        ))
    return output


def interval(values: list[float]) -> list[float]:
    rng = random.Random(SEED)
    estimates = sorted(
        mean(rng.choices(values, k=len(values))) for _ in range(10_000)
    )
    return [estimates[249], estimates[9749]]


def sensitivity_analysis(plan, rows, stable_ids: set[str]) -> dict[str, object]:
    contrasts = {}
    for arm in ARMS[1:]:
        values = clustered_differences(plan, rows, arm, stable_ids)
        lower, upper = interval(values)
        contrasts[arm] = {
            "independentProbeClusters": len(values),
            "meanDifference": mean(values),
            "clusterBootstrap95": [lower, upper],
            "interpretation": (
                "benefit" if upper < 0 else "harm" if lower > 0 else "inconclusive"
            ),
        }
    return {
        "scope": "post-hoc robustness check excluding profile-sensitive oracle labels",
        "notReplacementForPreregisteredPrimary": True,
        "retainedProbeIds": sorted(stable_ids),
        "contrastsVersusNoMemory": contrasts,
    }


def planning_diagnostics(plan, rows) -> dict[str, object]:
    diagnostics = {}
    for arm in ARMS[1:]:
        values = clustered_differences(plan, rows, arm)
        spread = stdev(values)
        minimum_effect = 0.25
        approximate_probes = math.ceil(
            (1.96 + 0.8416) ** 2 * spread ** 2 / minimum_effect ** 2
        )
        diagnostics[arm] = {
            "observedIndependentProbeClusters": len(values),
            "clusterMeanDifference": mean(values),
            "clusterStandardDeviation": spread,
            "approximateProbesFor80PercentPowerAtAbsoluteEffect0_25": max(2, approximate_probes),
            "warning": (
                "Normal approximation based on this exploratory sample; use only for "
                "planning and preregister a simulation-based calculation before inference."
            ),
        }
    return diagnostics


def main() -> None:
    liar_plan = load_json(LIAR_DIR / "preregistration.json")
    liar_rows = load_json(LIAR_DIR / "trial_rows.json")["rows"]
    liar_report = load_json(LIAR_DIR / "report.json")
    guess_report = load_json(GUESS_DIR / "report_approved_network.json")

    _, exact = solve_one_die_liar_exact()
    frozen = load_one_die_liar_policy(
        ROOT / "src/aip/puzzles/liars_dice/one_die_cfr_policy.json"
    )
    dcfr = create_regret_minimization_trainer(
        OneDieLiarDiceCFRGame(), "dcfr"
    ).train(300)
    profiles = {
        "exact_sequence_form": exact.policy,
        "frozen_runtime_cfr": frozen.policy,
        "dcfr_300": dcfr.policy,
    }
    robustness = compare_probe_oracles(build_oracle_probes(), profiles)
    next_panel, next_panel_audit = select_profile_invariant_probes(profiles)
    stable_ids = {
        row["probeId"] for row in robustness["probes"] if row["profileInvariant"]
    }
    profile_reports = [
        compact_equilibrium_report(name, profile)
        for name, profile in profiles.items()
    ]

    same_game_interval = liar_report["analysis"]["contrastsVersusNoMemory"][
        "same_game"
    ]["pairedBootstrap95"]
    repeat_rates = {
        arm: liar_report["analysis"]["summaries"][arm]["repeatActionAgreementRate"]
        for arm in ARMS
    }
    guess_abstract = guess_report["analysis"]["contrastsVersusNoMemory"][
        "abstract_memory"
    ]
    liar_abstract = liar_report["analysis"]["contrastsVersusNoMemory"][
        "abstract_memory"
    ]
    gates = {
        "liar_run_complete": liar_report["runStatus"] == "complete",
        "all_liar_outputs_valid": liar_report["validDecisions"] == liar_report["completedCells"],
        "provider_token_counts_exact": liar_report["inputTokenMismatches"] == 0,
        "all_selected_probe_labels_profile_invariant": robustness["allProbeLabelsInvariant"],
        "same_game_positive_control_detectably_better": same_game_interval[1] < 0,
        "all_conditions_repeat_agreement_at_least_0_8": min(repeat_rates.values()) >= 0.8,
        "abstract_transfer_replicated_across_targets": (
            guess_abstract["interpretation"] == "benefit"
            and liar_abstract["interpretation"] == "benefit"
        ),
    }

    goofspiel = evaluate_goofspiel_policy("equilibrium")
    artifact = {
        "schemaVersion": "aip-transfer-methodology-audit-v1",
        "date": "2026-09-22",
        "inputs": {
            "guessWhoReport": str(GUESS_DIR / "report_approved_network.json"),
            "liarPlan": str(LIAR_DIR / "preregistration.json"),
            "liarRows": str(LIAR_DIR / "trial_rows.json"),
            "liarReport": str(LIAR_DIR / "report.json"),
        },
        "liarOracleProfileRobustness": {
            **robustness,
            "profileQuality": profile_reports,
            "gateRule": "Every selected probe must have the same best-action set across all accepted low-exploitability reference profiles.",
        },
        "profileInvariantSensitivity": sensitivity_analysis(
            liar_plan, liar_rows, stable_ids
        ),
        "nextProfileInvariantPanel": {
            "selectedProbes": [
                {
                    **probe.to_artifact(),
                    "opponentReachMassByProfile": {
                        name: opponent_reach_mass(
                            profile, probe.player, probe.bids
                        )
                        for name, profile in profiles.items()
                    },
                }
                for probe in next_panel
            ],
            "selectedProbeCount": next_panel_audit["selectedProbes"],
            "challengeOptimal": next_panel_audit["challengeOptimal"],
            "raiseOptimal": next_panel_audit["raiseOptimal"],
            "playerOneRaiseProbes": next_panel_audit["playerOneRaiseProbes"],
            "minimumActionValueGapAcrossProfiles": next_panel_audit[
                "minimumActionValueGap"
            ],
            "allSelectedProfileInvariant": next_panel_audit[
                "allSelectedProfileInvariant"
            ],
            "candidateProbesAudited": next_panel_audit["candidateAudit"][
                "totalProbes"
            ],
            "candidateProfileSensitiveProbes": next_panel_audit[
                "candidateAudit"
            ]["unstableProbeIds"],
        },
        "planningDiagnostics": planning_diagnostics(liar_plan, liar_rows),
        "methodGates": gates,
        "passedMethodGates": sum(gates.values()),
        "totalMethodGates": len(gates),
        "horizontalCandidateAssessment": [
            {
                "game": "goofspiel-four-card",
                "readiness": "best_next_horizontal_target_after_method_gates",
                "reason": "Exact dynamic equilibrium; simultaneous hidden commitment is structurally distinct from sequential Liar's Dice.",
                "exactValue": float(goofspiel.game_value),
                "exactOneSidedExploitability": float(goofspiel.exploitability),
                "missing": "completion adapter and profile-invariant per-state action-regret audit",
            },
            {
                "game": "kuhn-poker",
                "readiness": "ready_secondary_adversarial_target",
                "reason": "Exact sequence form and exhaustive best response already exist; useful bluffing replication but structurally closer to Liar's Dice.",
                "missing": "token-balanced completion adapter and equilibrium-family action-label robustness",
            },
            {
                "game": "single-round-e-card",
                "readiness": "solver_control_not_primary_agent_target",
                "reason": "Exact stopping-time matrix is valuable for algorithm comparison, but equilibrium action values are tied and provide little decision discrimination.",
            },
            {
                "game": "mastermind",
                "readiness": "secondary_only",
                "reason": "Belief filtering is exact but the current decision policy is heuristic, so it cannot support the same exact-regret primary endpoint.",
            },
            {
                "game": "full-love-letter",
                "readiness": "blocked",
                "reason": "Structural traversal and independent certification remain incomplete; four-card subgame may remain a source/control only.",
            },
        ],
        "decision": {
            "nextStep": "optimize_current_method_before_expanding_primary_game_count",
            "requiredBeforeExpansion": [
                "use the newly selected 30-probe profile-invariant panel",
                "redesign and independently pilot a same-game positive control that discriminates from no memory",
                "raise repeat stability above the preregistered threshold",
                "use at least 30 independent robust probes for an effect near 0.25, subject to simulation-based power analysis",
            ],
            "allowedParallelWork": (
                "Build a Goofspiel adapter and oracle audit without running a new efficacy experiment; keep E-Card as an exact solver control."
            ),
        },
    }
    DESTINATION.write_text(
        json.dumps(artifact, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "artifact": str(DESTINATION),
        "methodGates": gates,
        "unstableProbeIds": robustness["unstableProbeIds"],
        "decision": artifact["decision"],
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
