#!/usr/bin/env python3
"""Compare bounded Mastermind sampling budgets with an exact one-step reference."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from time import perf_counter
from typing import TypeVar

from aip.puzzles.mastermind import CodeFeedback, MastermindSolver

SampleItem = TypeVar("SampleItem")


def even_sample(
    values: tuple[SampleItem, ...], limit: int
) -> tuple[SampleItem, ...]:
    """Select a reproducible, evenly spaced subset without private solver APIs."""

    if len(values) <= limit:
        return values
    return tuple(values[index * len(values) // limit] for index in range(limit))


def policy_simulation(sample_budget: int, secret_count: int) -> dict[str, object]:
    solver = MastermindSolver(mid_size_global_sample=sample_budget)
    secrets = even_sample(solver.all_codes, secret_count)
    started = perf_counter()
    lengths: list[int] = []
    failures: list[list[int]] = []
    for secret in secrets:
        guesses = solver.solve(secret)
        lengths.append(len(guesses))
        if not guesses or guesses[-1] != secret:
            failures.append(list(secret))
    return {
        "midSizeGlobalSample": sample_budget,
        "secretCount": secret_count,
        "secretSelection": "deterministic_even_spacing",
        "solved": secret_count - len(failures),
        "failures": failures,
        "meanAttempts": sum(lengths) / len(lengths),
        "maximumAttempts": max(lengths),
        "attemptHistogram": {
            str(attempts): count
            for attempts, count in sorted(Counter(lengths).items())
        },
        "runtimeMs": (perf_counter() - started) * 1000,
    }


def opening_branch_audit(sample_budgets: tuple[int, ...]) -> dict[str, object]:
    reference = MastermindSolver()
    opening = (0, 1, 2, 3)
    feedbacks = sorted(
        {reference.feedback(opening, secret) for secret in reference.all_codes},
        key=lambda item: item.as_tuple(),
    )
    branches: list[dict[str, object]] = []
    for feedback in feedbacks:
        candidates = reference.filter_candidates(
            reference.all_codes, opening, feedback
        )
        if len(candidates) == 1:
            continue
        exact = reference.suggest_exact(candidates)
        policies: dict[str, object] = {}
        for budget in sample_budgets:
            bounded = MastermindSolver(
                mid_size_global_sample=budget
            ).suggest(candidates)
            policies[str(budget)] = {
                "guess": list(bounded.guess),
                "worstCaseRemaining": bounded.worst_case_remaining,
                "expectedRemaining": bounded.expected_remaining,
                "evaluatedGuesses": bounded.evaluated_guesses,
                "oneStepWorstCaseRegret": (
                    bounded.worst_case_remaining - exact.worst_case_remaining
                ),
                "oneStepExpectedDifference": (
                    bounded.expected_remaining - exact.expected_remaining
                ),
                "exactObjectiveAgreement": (
                    bounded.worst_case_remaining == exact.worst_case_remaining
                    and abs(
                        bounded.expected_remaining - exact.expected_remaining
                    )
                    < 1e-12
                ),
            }
        branches.append(
            {
                "feedback": {
                    "exact": feedback.exact,
                    "misplaced": feedback.misplaced,
                },
                "candidateCount": len(candidates),
                "exactOneStep": {
                    "guess": list(exact.guess),
                    "worstCaseRemaining": exact.worst_case_remaining,
                    "expectedRemaining": exact.expected_remaining,
                    "evaluatedGuesses": exact.evaluated_guesses,
                },
                "policies": policies,
            }
        )
    return {
        "openingGuess": list(opening),
        "nonterminalBranches": len(branches),
        "referenceScope": "exact_one_step_minimax_then_expected_partition",
        "branches": branches,
        "agreementByBudget": {
            str(budget): sum(
                bool(branch["policies"][str(budget)]["exactObjectiveAgreement"])
                for branch in branches
            )
            for budget in sample_budgets
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--secrets", type=int, default=200)
    parser.add_argument("--budgets", type=int, nargs="+", default=(360, 361))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not 1 <= args.secrets <= 5040:
        parser.error("--secrets must be between 1 and 5040")
    budgets = tuple(dict.fromkeys(args.budgets))
    if not budgets or any(budget < 1 for budget in budgets):
        parser.error("--budgets must contain positive integers")

    report = {
        "artifactSchemaVersion": "aip-mastermind-sampling-audit-v1",
        "rules": {
            "symbols": list(range(10)),
            "length": 4,
            "repeatedDigits": False,
            "worldCount": 5040,
        },
        "evidenceBoundary": {
            "candidateFiltering": "exact",
            "openingBranchReference": "exact_one_step_only",
            "fullPolicy": "strong_heuristic",
        },
        "simulations": [
            policy_simulation(budget, args.secrets) for budget in budgets
        ],
        "openingAudit": opening_branch_audit(budgets),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
