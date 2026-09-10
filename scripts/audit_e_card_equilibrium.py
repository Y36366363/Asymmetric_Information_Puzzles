#!/usr/bin/env python3
"""Compare exact matrix/sequence-form and shared-CFR E-Card solutions."""

from __future__ import annotations

import argparse

from aip.puzzles.e_card import (
    certify_e_card_cfr,
    e_card_cfr_value,
    solve_e_card_timing_game,
    train_e_card_cfr,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--iterations", type=int, default=10_000)
    args = parser.parse_args()

    exact = solve_e_card_timing_game()
    learned = train_e_card_cfr(args.iterations)
    report = certify_e_card_cfr(learned)
    print(f"exact_emperor_value={float(exact.emperor_value):.9f}")
    print(
        "exact_emperor_strategy="
        + ",".join(f"{float(value):.9f}" for value in exact.emperor_strategy)
    )
    print(
        "exact_slave_strategy="
        + ",".join(f"{float(value):.9f}" for value in exact.slave_strategy)
    )
    print(f"cfr_iterations={learned.iterations}")
    print(f"cfr_exploitability={report.exploitability:.9f}")
    print(f"cfr_emperor_value={e_card_cfr_value(learned):.9f}")
    print(f"cfr_max_average_positive_regret={report.maximum_average_positive_regret:.9f}")
    print(f"cfr_gate_passed={str(report.passed).lower()}")
    if not report.passed:
        print("cfr_failures=" + ",".join(report.failures))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
