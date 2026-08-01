"""Common-knowledge solver for the village eye-colour puzzle."""

from __future__ import annotations

from aip.core.information import InformationSet, Observation
from aip.puzzles.eyes.models import EyeRules, EyeSolution, EyeWorld, ReasoningDay


class EyeVillageSolver:
    """Solve the classic induction without enumerating 2**population worlds.

    Everyone sees everybody else's eye colour, cannot see their own, reasons
    perfectly, and observes each previous night's actions. The public statement
    that at least one target-colour person exists supplies the common-knowledge
    base case required by the induction.
    """

    def __init__(self, rules: EyeRules | None = None) -> None:
        self.rules = rules or EyeRules()

    def solve(self, target_count: int, other_count: int) -> EyeSolution:
        if target_count < 0 or other_count < 0:
            raise ValueError("population counts cannot be negative")
        if target_count + other_count < 1:
            raise ValueError("the village must contain at least one person")

        target = self.rules.target_color
        if target_count == 0:
            return EyeSolution(
                target_count,
                other_count,
                self.rules,
                (),
                None,
                f"No one has {target} eyes, so no one is subject to the rule.",
            )
        if not self.rules.public_announcement:
            return EyeSolution(
                target_count,
                other_count,
                self.rules,
                (),
                None,
                "The fact was not made public knowledge, so the induction has no "
                "shared base case and no synchronized action day is guaranteed.",
            )

        history: tuple[Observation, ...] = (
            Observation(
                "public_announcement",
                f"at least one person has {target} eyes",
                is_public=True,
                timestamp=0,
            ),
        )
        actual = EyeWorld(target_count, other_count)
        counterfactual = EyeWorld(target_count - 1, other_count + 1)
        days: list[ReasoningDay] = []

        for day in range(1, target_count + 1):
            knows = day == target_count
            worlds = (actual,) if knows else (counterfactual, actual)
            own_colors = (target,) if knows else (
                self.rules.other_color,
                target,
            )
            info = InformationSet(
                key=f"eyes-{target_count}-{other_count}-day-{day}",
                player_id=f"representative-{target}-eyed-person",
                possible_states=worlds,
                observations=(
                    Observation(
                        "visible_counts",
                        {
                            target: target_count - 1,
                            self.rules.other_color: other_count,
                        },
                        is_public=False,
                        timestamp=day,
                    ),
                ),
                public_history=history,
            )
            event = (
                f"all {target_count} {target}-eyed people know and "
                f"{self.rules.action_description} that night"
                if knows
                else "nobody acts that night; another lower-count world is eliminated"
            )
            days.append(ReasoningDay(day, own_colors, info, event, knows))
            if not knows:
                history = history + (
                    Observation(
                        "night_result",
                        "nobody acted",
                        is_public=True,
                        timestamp=day,
                    ),
                )

        conclusion = (
            f"All {target_count} {target}-eyed people determine their colour on day "
            f"{target_count} and simultaneously {self.rules.action_description} that "
            f"night. People with {self.rules.other_color} eyes never become subject "
            "to the rule."
        )
        return EyeSolution(
            target_count,
            other_count,
            self.rules,
            tuple(days),
            target_count,
            conclusion,
        )
