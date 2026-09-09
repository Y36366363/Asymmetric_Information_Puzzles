#!/usr/bin/env python3
"""Train, independently certify, and export the one-die Liar's Dice policy."""

from __future__ import annotations

import argparse
from pathlib import Path

from aip.puzzles.liars_dice import (
    certify_one_die_liar_cfr,
    save_one_die_liar_policy,
    train_one_die_liar_cfr,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "src/aip/puzzles/liars_dice/one_die_cfr_policy.json"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--iterations", type=int, default=20_000)
    parser.add_argument("--seed", type=int, default=20260908)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    result = train_one_die_liar_cfr(args.iterations, seed=args.seed)
    report = certify_one_die_liar_cfr(result)
    report.require_passed()
    save_one_die_liar_policy(result, args.output, certification=report)
    print(
        f"wrote {args.output} (epsilon={report.exploitability:.8f}, "
        f"information_sets={report.information_sets})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
