from __future__ import annotations

import argparse

from aip.puzzles.auctions.formatting import format_analysis as format_auction_analysis
from aip.puzzles.auctions.coordination import (
    LeadershipCandidate,
    PublicPriceCoordinationSolver,
)
from aip.puzzles.auctions.coordination_formatting import format_coordination
from aip.puzzles.auctions.models import AuctionMode, AuctionRules
from aip.puzzles.auctions.solver import AllPayAuctionAnalyzer
from aip.puzzles.beans.formatting import format_solution as format_bean_solution
from aip.puzzles.beans.models import BeanRules
from aip.puzzles.beans.solver import BeanSolver
from aip.puzzles.cases.formatting import format_case_game
from aip.puzzles.cases.models import CLASSROOM_BANKER, CaseGameRules, RiskPreferences
from aip.puzzles.cases.solver import CaseGameAnalyzer
from aip.puzzles.eyes.formatting import format_solution as format_eye_solution
from aip.puzzles.eyes.models import EyeRules
from aip.puzzles.eyes.solver import EyeVillageSolver
from aip.puzzles.hats.formatting import format_solution as format_hat_solution
from aip.puzzles.hats.solver import HatSolver
from aip.puzzles.liars_dice.formatting import format_liars_dice
from aip.puzzles.liars_dice.models import DiceBid, LiarsDiceRules
from aip.puzzles.liars_dice.solver import LiarsDiceAnalyzer
from aip.puzzles.pirates.formatting import format_solution
from aip.puzzles.pirates.models import PirateRules, VoteThreshold
from aip.puzzles.pirates.solver import PirateSolver
from aip.puzzles.prisoners.formatting import format_simulation
from aip.puzzles.prisoners.analysis import PrisonerTimingAnalyzer
from aip.puzzles.prisoners.analysis_formatting import format_timing_analysis
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
    prisoner_analysis = subparsers.add_parser(
        "prisoners-analysis", help="analyze coverage and proof timing"
    )
    prisoner_analysis.add_argument("--count", type=int, default=100)
    prisoner_analysis.add_argument("--max-days", type=int, default=30_000)
    prisoner_analysis.add_argument("--trials", type=int, default=2_000)
    prisoner_analysis.add_argument("--seed", type=int, default=42)
    prisoner_analysis.add_argument("--false-cost", type=float, default=1_000_000)
    prisoner_analysis.add_argument("--daily-cost", type=float, default=1.0)
    prisoner_analysis.add_argument(
        "--confidences",
        type=float,
        nargs="+",
        default=[0.5, 0.9, 0.95, 0.99, 0.999],
        help="target probabilities expressed between 0 and 1",
    )
    prisoner_analysis.add_argument(
        "--sample-days",
        type=int,
        nargs="+",
        default=None,
        help="days to include in the probability table",
    )
    auction = subparsers.add_parser("auction", help="analyze repeated all-pay auctions")
    auction.add_argument("--players", type=int, default=5)
    auction.add_argument("--rounds", type=int, default=10)
    auction.add_argument("--value", type=int, default=100)
    auction.add_argument("--budget", type=int, default=100)
    auction.add_argument("--trials", type=int, default=1_000)
    auction.add_argument("--seed", type=int, default=42)
    auction.add_argument(
        "--deviation-rate",
        type=float,
        default=0.02,
        help="per-player chance of breaking the price-1 tacit convention each round",
    )
    auction.add_argument("--social-supporters", type=int, default=None)
    auction.add_argument("--leader-bid", type=int, default=101)
    auction.add_argument("--social-deviation-rate", type=float, default=0.0)
    auction.add_argument(
        "--social-identity-hidden",
        action="store_true",
        help="prices reveal defection but cannot identify whom to expel",
    )
    auction.add_argument(
        "--modes",
        nargs="+",
        choices=[mode.value for mode in AuctionMode],
        default=[
            AuctionMode.NAIVE.value,
            AuctionMode.CAUTIOUS.value,
            AuctionMode.EQUILIBRIUM.value,
            AuctionMode.COOPERATIVE.value,
            AuctionMode.TACIT.value,
        ],
    )
    coordination = subparsers.add_parser(
        "auction-coordination", help="resolve public leadership and price conventions"
    )
    coordination.add_argument(
        "--candidate",
        nargs="+",
        required=True,
        metavar="PLAYER:BID:PRICE",
    )
    coordination.add_argument("--ideals", type=int, nargs="+", required=True)
    coordination.add_argument("--value", type=int, default=100)
    coordination.add_argument("--remaining-rounds", type=int, default=10)
    coordination.add_argument("--discount", type=float, default=0.9)
    coordination.add_argument("--leader-bonus", type=float, default=0.0)
    cases = subparsers.add_parser(
        "cases", help="simulate the 26-case banker-offer decision game"
    )
    cases.add_argument(
        "--risk-tolerance",
        type=float,
        default=None,
        help="CARA risk tolerance in prize units; omit for risk-neutral play",
    )
    cases.add_argument("--trials", type=int, default=1_000)
    cases.add_argument("--seed", type=int, default=42)
    dice = subparsers.add_parser(
        "liars-dice", help="analyze a Liar's Dice bid from a private hand"
    )
    dice.add_argument("--players", type=int, default=4)
    dice.add_argument("--dice-per-player", type=int, default=5)
    dice.add_argument("--sides", type=int, default=6)
    dice.add_argument("--hand", type=int, nargs="+", default=[1, 3, 3, 5, 6])
    dice.add_argument("--bid-quantity", type=int, default=9)
    dice.add_argument("--bid-face", type=int, default=3)
    dice.add_argument("--no-wild-ones", action="store_true")
    dice.add_argument("--honest-prior", type=float, default=0.7)
    dice.add_argument("--trials", type=int, default=100_000)
    dice.add_argument("--seed", type=int, default=42)
    play = subparsers.add_parser("play", help="start the local playable game lobby")
    play.add_argument("--host", default="127.0.0.1")
    play.add_argument("--port", type=int, default=8765)
    play.add_argument("--no-open", action="store_true")
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
    elif args.puzzle == "prisoners-analysis":
        options = {
            "max_days": args.max_days,
            "confidences": tuple(args.confidences),
            "false_declaration_cost": args.false_cost,
            "daily_wait_cost": args.daily_cost,
            "simulation_trials": args.trials,
            "seed": args.seed,
        }
        if args.sample_days is not None:
            options["sample_days"] = tuple(args.sample_days)
        analysis = PrisonerTimingAnalyzer().analyze(args.count, **options)
        print(format_timing_analysis(analysis))
    elif args.puzzle == "auction":
        rules = AuctionRules(
            player_count=args.players,
            rounds=args.rounds,
            prize_value=args.value,
            initial_budget=args.budget,
            tacit_deviation_probability=args.deviation_rate,
            social_supporters=args.social_supporters,
            social_identity_observable=not args.social_identity_hidden,
            social_leader_bid=args.leader_bid,
            social_deviation_probability=args.social_deviation_rate,
        )
        modes = tuple(AuctionMode(mode) for mode in args.modes)
        analysis = AllPayAuctionAnalyzer().analyze(
            rules, trials=args.trials, seed=args.seed, modes=modes
        )
        print(format_auction_analysis(analysis))
    elif args.puzzle == "auction-coordination":
        candidates = []
        for encoded in args.candidate:
            try:
                player, bid, price = (int(part) for part in encoded.split(":"))
            except ValueError as error:
                raise SystemExit(
                    f"invalid candidate {encoded!r}; expected PLAYER:BID:PRICE"
                ) from error
            candidates.append(LeadershipCandidate(player, bid, price))
        outcome = PublicPriceCoordinationSolver().solve(
            tuple(candidates),
            tuple(args.ideals),
            prize_value=args.value,
            remaining_rounds=args.remaining_rounds,
            discount_factor=args.discount,
            leadership_bonus_per_round=args.leader_bonus,
        )
        print(format_coordination(outcome))
    elif args.puzzle == "cases":
        analyzer = CaseGameAnalyzer()
        rules = CaseGameRules()
        preferences = RiskPreferences(args.risk_tolerance)
        result = analyzer.play(rules, CLASSROOM_BANKER, preferences, seed=args.seed)
        summary = analyzer.simulate(
            rules,
            CLASSROOM_BANKER,
            preferences,
            trials=args.trials,
            seed=args.seed,
        )
        print(format_case_game(result, summary))
    elif args.puzzle == "liars-dice":
        rules = LiarsDiceRules(
            player_count=args.players,
            dice_per_player=args.dice_per_player,
            sides=args.sides,
            wild_ones=not args.no_wild_ones,
        )
        hand = tuple(args.hand)
        bid = DiceBid(args.bid_quantity, args.bid_face)
        analyzer = LiarsDiceAnalyzer()
        analysis = analyzer.analyze_bid(hand, bid, rules)
        raises = analyzer.safest_raises(hand, bid, rules)
        check = analyzer.validate_probability(
            hand, bid, rules, trials=args.trials, seed=args.seed
        )
        beliefs = analyzer.infer_bidder_type(
            analysis.probability_bid_true, honest_prior=args.honest_prior
        )
        print(format_liars_dice(analysis, raises, check, beliefs))
    elif args.puzzle == "play":
        from aip.ui.server import serve

        serve(args.host, args.port, open_browser=not args.no_open)
    return 0
