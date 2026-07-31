from __future__ import annotations

import argparse

from aip.puzzles.hats.formatting import format_solution as format_hat_solution
from aip.puzzles.hats.solver import HatSolver
from aip.puzzles.pirates.formatting import format_solution
from aip.puzzles.pirates.models import PirateRules, VoteThreshold
from aip.puzzles.pirates.solver import PirateSolver


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="aip", description="Asymmetric Information Puzzles")
    subparsers = parser.add_subparsers(dest="puzzle", required=True)
    pirates = subparsers.add_parser("pirates", help="solve the pirate gold puzzle")
    pirates.add_argument("--pirates", type=int, default=5, help="number of pirates")
    pirates.add_argument("--gold", type=int, default=100, help="total indivisible gold coins")
    pirates.add_argument(
        "--strict-majority",
        action="store_true",
        help="require more than half of all votes (default: an exact tie passes)",
    )
    pirates.add_argument(
        "--accept-equal",
        action="store_true",
        help="a voter accepts when both outcomes give equal survival and gold",
    )
    hats = subparsers.add_parser("hats", help="solve the public coloured-hat puzzle")
    hats.add_argument("--colors", required=True, help="actual hats, e.g. BBBRR")
    hats.add_argument("--target", default="B", help="publicly announced colour")
    hats.add_argument("--other", default="R", help="the other possible colour")
    hats.add_argument("--max-rounds", type=int, default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.puzzle == "pirates":
        threshold = (
            VoteThreshold.STRICT_MAJORITY
            if args.strict_majority
            else VoteThreshold.HALF_OR_MORE
        )
        rules = PirateRules(threshold=threshold, accept_equal_gold=args.accept_equal)
        solution = PirateSolver(rules).solve(args.pirates, args.gold)
        print(format_solution(solution))
    elif args.puzzle == "hats":
        solution = HatSolver().solve(args.colors, args.target, args.other, args.max_rounds)
        print(format_hat_solution(solution))
    return 0
