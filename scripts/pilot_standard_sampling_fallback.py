"""Exploratory pilot for standard external-sampling zero-weight fallback.

Pilot seeds are permanently excluded from any later confirmatory experiment.
"""

from __future__ import annotations

import json
from pathlib import Path

from aip.core import CoverageAwareExternalSamplingCFRTrainer, ExternalSamplingCFRTrainer
from aip.puzzles.kuhn_poker import KuhnCFRGame, evaluate_kuhn_cfr
from aip.puzzles.liars_dice import (
    OneDieLiarDiceCFRGame,
    OneDieLiarIndependentEvaluator,
    OneDieLiarState,
    required_one_die_information_sets,
)


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "research/results/standard_sampling_fallback_pilot_2026-10-13.json"
SEEDS = (2026101301, 2026101302, 2026101303)


def _initialize_one_die(trainer) -> None:
    for player, information_set in sorted(required_one_die_information_sets(), key=repr):
        own_die, bids = information_set
        dice = (own_die, 1) if player == 0 else (1, own_die)
        actions = trainer.game.legal_actions(OneDieLiarState(dice, bids))
        trainer.initialize_information_set(player, information_set, actions)


def _one_die_evaluation(result):
    evaluator = OneDieLiarIndependentEvaluator()
    return evaluator.exploitability(result.policy)


def _run(game_factory, evaluator, iterations: int, seed: int, initialize=None):
    candidate_trainer = CoverageAwareExternalSamplingCFRTrainer(
        game_factory(), seed=seed
    )
    legacy_trainer = ExternalSamplingCFRTrainer(game_factory(), seed=seed)
    if initialize:
        initialize(candidate_trainer)
        initialize(legacy_trainer)
    candidate = candidate_trainer.train(iterations)
    legacy = legacy_trainer.train(iterations)
    fallback = sum(candidate.average_strategy_fallback_used.values())
    return {
        "seed": seed,
        "iterations": iterations,
        "candidate_exploitability": evaluator(candidate),
        "legacy_exploitability": evaluator(legacy),
        "fallback_information_sets": fallback,
        "information_sets": len(candidate.policy),
        "fallback_fraction": fallback / len(candidate.policy),
        "trace_parity": (
            candidate.information_set_visits == legacy.information_set_visits
            and candidate.average_positive_regret == legacy.average_positive_regret
            and candidate.average_strategy_observations
            == legacy.average_strategy_observations
            and candidate.average_strategy_observation_weight
            == legacy.average_strategy_observation_weight
        ),
    }


def main() -> int:
    kuhn = [
        _run(
            KuhnCFRGame,
            lambda result: evaluate_kuhn_cfr(result).exploitability,
            20_000,
            seed,
        )
        for seed in SEEDS
    ]
    one_die = [
        _run(
            OneDieLiarDiceCFRGame,
            _one_die_evaluation,
            30_000,
            seed,
            _initialize_one_die,
        )
        for seed in SEEDS
    ]
    artifact = {
        "status": "exploratory_pilot_not_certification",
        "algorithm_id": "coverage_aware_external_sampling_mccfr_v1",
        "seeds_excluded_from_confirmation": list(SEEDS),
        "games": {
            "canonical_kuhn_poker": kuhn,
            "one_die_stepwise_liars_dice": one_die,
        },
        "thresholds_selected_from_this_pilot": False,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(artifact, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(OUTPUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
