from __future__ import annotations

from aip.puzzles.auctions.coordination import CoordinationOutcome


def format_coordination(outcome: CoordinationOutcome) -> str:
    lines = [
        "Public-bid leadership and convention selection",
        f"Raw highest bidder: player {outcome.raw_high_bid_leader} at "
        f"{outcome.raw_high_bid}",
        f"Maximum rational leadership bid under configured private leadership value: "
        f"{outcome.maximum_rational_leadership_bid:.2f}",
        f"Raw leadership bid rational under that value: {outcome.raw_leader_bid_is_rational}",
        f"Median ideal price: {outcome.median_ideal_price:g}",
        f"Pairwise-majority equilibrium price: {outcome.equilibrium_price}",
        f"Majority-recognized leader: player {outcome.majority_recognized_leader}",
        f"Total burned in leadership contest: {outcome.leadership_contest_cost}",
        "",
        "Proposal comparison:",
        "  price  first-choice support  payoff/supporter  group surplus  viable",
    ]
    for vote in outcome.votes:
        lines.append(
            f"  {vote.price:5d} {vote.first_choice_support:20d} "
            f"{vote.expected_payoff_per_supporter:17.2f} "
            f"{vote.group_surplus:14.2f} {str(vote.economically_viable):>7s}"
        )
    lines.extend(["", outcome.explanation])
    return "\n".join(lines)
