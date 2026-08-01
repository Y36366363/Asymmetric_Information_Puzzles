from __future__ import annotations

from aip.puzzles.prisoners.analysis import TimingAnalysis


def format_timing_analysis(analysis: TimingAnalysis) -> str:
    def probability(value: float) -> str:
        if value >= 1.0 - 1e-12:
            return "≈100%*"
        return f"{value:.6%}"

    lines = [
        f"Timing analysis: N={analysis.prisoner_count}, known-off, visit goal",
        f"Expected day everyone has physically visited: {analysis.expected_visit_day:.2f}",
        f"Expected safe declaration day (single counter): {analysis.expected_proof_day:.2f}",
        "",
        "Day-by-day probabilities:",
        "  day | everyone visited | counter has proof",
    ]
    for point in analysis.points:
        lines.append(
            f"  {point.day:5d} | {probability(point.everyone_visited):>15} | "
            f"{probability(point.counter_has_proof):>17}"
        )
    lines.append("  * Rounded numerically; no finite blind deadline is literally 100%.")
    lines.extend(["", "Confidence thresholds:"])
    for item in analysis.confidence_days:
        lines.append(
            f"  {item.confidence:7.3%}: visited by day {item.visit_day}; "
            f"single-counter proof by day {item.proof_day}"
        )
    lines.extend(
        [
            "",
            "Illustrative risky-deadline policy:",
            f"  false declaration cost={analysis.false_declaration_cost:g}, "
            f"wait cost/day={analysis.daily_wait_cost:g}",
            f"  minimum expected cost at day {analysis.illustrative_deadline}, "
            f"where P(all visited)={analysis.illustrative_deadline_probability:.8%}",
            "  This is not a universal optimum: changing the death/wait cost changes the day.",
        ]
    )
    if analysis.monte_carlo:
        simulation = analysis.monte_carlo
        lines.extend(
            [
                "",
                f"Monte Carlo check ({simulation.trials} trials):",
                f"  mean physical coverage day={simulation.mean_visit_day:.2f}",
                f"  mean single-counter proof day={simulation.mean_proof_day:.2f}",
            ]
        )
    return "\n".join(lines)
