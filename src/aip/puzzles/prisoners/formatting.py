from __future__ import annotations

from aip.puzzles.prisoners.models import PrisonerPlan, SimulationResult


def format_plan(plan: PrisonerPlan) -> str:
    n = plan.prisoner_count
    return "\n".join(
        [
            f"Prisoners and light: N={n}, initial light={plan.initial_light.value}",
            f"Declaration goal: everyone has {plan.goal.value}",
            "Pre-agreement: prisoner 0 is the designated counter.",
            f"Each of prisoners 1..{n - 1} turns the light on only when it is off, "
            f"and does so at most {plan.signals_per_non_counter} time(s).",
            "The counter turns every on light off and increments a private count.",
            f"The counter declares after count={plan.declaration_count}.",
            "Safety proof: " + plan.safety_argument,
            "Timing: safe always; completion has probability 1 under fair random "
            "selection, but there is no finite worst-case day bound.",
        ]
    )


def format_simulation(result: SimulationResult, tail: int = 10) -> str:
    lines = [format_plan(result.plan), "", "Simulation:"]
    for record in result.records[-tail:]:
        lines.append(
            f"  Day {record.day}: prisoner {record.prisoner_id}; {record.action}; "
            f"light={'on' if record.light_after else 'off'}; count={record.counter_value}"
        )
    if len(result.records) > tail:
        lines.insert(-tail, f"  ... {len(result.records) - tail} earlier day(s) omitted ...")
    if result.completed:
        lines.append(
            f"Declared safely on day {result.declaration_day}: "
            f"{'yes' if result.declaration_was_safe else 'NO'}"
        )
    else:
        lines.append(f"No declaration within {len(result.records)} simulated days.")
    return "\n".join(lines)
