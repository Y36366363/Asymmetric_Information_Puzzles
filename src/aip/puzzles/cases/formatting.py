from __future__ import annotations

from aip.puzzles.cases.models import CaseGameResult, CaseSimulationSummary


def format_case_game(
    result: CaseGameResult, summary: CaseSimulationSummary | None = None
) -> str:
    lines = ["26-case deal-or-no-deal simulation", ""]
    for round_ in result.rounds:
        analysis = round_.analysis
        lines.extend(
            [
                f"Round {round_.round_number}: revealed "
                + ", ".join(f"{value:,.2f}" for value in round_.revealed),
                f"  remaining={len(round_.remaining)}, offer={round_.offer:,.2f}, "
                f"EV={analysis.expected_value:,.2f}, CE={analysis.certainty_equivalent:,.2f}",
                f"  offer/EV={analysis.offer_to_expected_value:.2%}, "
                f"P(case > offer)={analysis.probability_case_beats_offer:.2%}, "
                f"reservation rule={analysis.reservation_recommendation}",
            ]
        )
    lines.extend(
        [
            "",
            f"Chosen case contained {result.player_case_value:,.2f}; payout={result.payout:,.2f}; "
            + (
                f"deal in round {result.accepted_round}"
                if result.accepted_round is not None
                else "no deal through the final case"
            ),
            "The CE comparison is a transparent reservation rule, not a full early-round "
            "Bellman solution; future offers can add option value.",
        ]
    )
    if summary is not None:
        mean_round = (
            f"{summary.mean_accepted_round:.2f}"
            if summary.mean_accepted_round is not None
            else "n/a"
        )
        lines.extend(
            [
                "",
                f"Monte Carlo ({summary.trials} trials): mean payout={summary.mean_payout:,.2f}, "
                f"mean case={summary.mean_case_value:,.2f}, deal rate={summary.deal_rate:.2%}, "
                f"mean deal round={mean_round}",
            ]
        )
    return "\n".join(lines)
