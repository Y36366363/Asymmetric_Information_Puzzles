from __future__ import annotations

import argparse

from aip.puzzles.beans.formatting import format_solution as format_bean_solution
from aip.puzzles.beans.models import BeanRules
from aip.puzzles.beans.solver import BeanSolver
from aip.puzzles.eyes.formatting import format_solution as format_eye_solution
from aip.puzzles.eyes.models import EyeRules
from aip.puzzles.eyes.solver import EyeVillageSolver
from aip.puzzles.hats.formatting import format_solution as format_hat_solution
from aip.puzzles.hats.solver import HatSolver
from aip.puzzles.pirates.formatting import format_solution
from aip.puzzles.pirates.models import PirateRules, VoteThreshold
from aip.puzzles.pirates.solver import PirateSolver
from aip.puzzles.prisoners.formatting import format_simulation
from aip.puzzles.prisoners.models import DeclarationGoal, InitialLight
from aip.puzzles.prisoners.solver import PrisonerLightSolver
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
    eyes = subparsers.add_parser("eyes", help="solve the village eye-colour puzzle")
    eyes.add_argument("--target-count", type=int, required=True)
    eyes.add_argument("--other-count", type=int, default=0)
    eyes.add_argument("--target-color", default="white")
    eyes.add_argument("--other-color", default="black")
    eyes.add_argument(
        "--no-public-announcement",
        action="store_true",
        help="remove the common-knowledge announcement",
    )
    prisoners = subparsers.add_parser(
        "prisoners", help="solve and simulate the prisoners-and-light puzzle"
    )
    prisoners.add_argument("--count", type=int, default=100)
    prisoners.add_argument(
        "--initial", choices=[state.value for state in InitialLight], default="off"
    )
    prisoners.add_argument(
        "--goal",
        choices=[goal.value for goal in DeclarationGoal],
        default=DeclarationGoal.TURNED_ON.value,
    )
    prisoners.add_argument(
        "--actual-initial-on",
        action="store_true",
        help="simulation state when --initial unknown",
    )
    prisoners.add_argument("--seed", type=int, default=42)
    prisoners.add_argument("--max-days", type=int, default=1_000_000)
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
    elif args.puzzle == "eyes":
        rules = EyeRules(
            target_color=args.target_color,
            other_color=args.other_color,
            public_announcement=not args.no_public_announcement,
        )
        solution = EyeVillageSolver(rules).solve(args.target_count, args.other_count)
        print(format_eye_solution(solution))
    elif args.puzzle == "prisoners":
        solver = PrisonerLightSolver()
        plan = solver.create_plan(args.count, args.initial, args.goal)
        result = solver.simulate(
            plan,
            seed=args.seed,
            max_days=args.max_days,
            actual_initial_on=args.actual_initial_on,
        )
        print(format_simulation(result))
    return 0
