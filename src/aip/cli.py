from __future__ import annotations

import argparse

from aip.puzzles.beans.formatting import format_solution as format_bean_solution
from aip.puzzles.beans.models import BeanRules
from aip.puzzles.beans.solver import BeanSolver
from aip.puzzles.hats.formatting import format_solution as format_hat_solution
from aip.puzzles.hats.solver import HatSolver
from aip.puzzles.pirates.formatting import format_solution
from aip.puzzles.pirates.models import PirateRules, VoteThreshold
from aip.puzzles.pirates.solver import PirateSolver
from aip.puzzles.worm.formatting import format_solution as format_worm_solution
from aip.puzzles.worm.solver import WormSolver


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
    beans = subparsers.add_parser("beans", help="solve robust sequential bean taking")
    beans.add_argument("--min-beans", type=int, required=True)
    beans.add_argument("--max-beans", type=int, required=True)
    beans.add_argument("--players", type=int, default=5)
    beans.add_argument("--min-take", type=int, default=1)
    beans.add_argument("--max-take", type=int, default=3)
    worm = subparsers.add_parser("worm", help="find a guaranteed moving-worm search")
    worm.add_argument("--holes", type=int, default=5)
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
    elif args.puzzle == "beans":
        rules = BeanRules(args.players, args.min_take, args.max_take)
        solution = BeanSolver(rules).solve(args.min_beans, args.max_beans)
        print(format_bean_solution(solution))
    elif args.puzzle == "worm":
        print(format_worm_solution(WormSolver().solve(args.holes)))
    return 0
