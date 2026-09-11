"""Declared equilibrium-method profile for a complete Love Letter round."""

from aip.core import EquilibriumGameStructure, StoppingTimeStructure


def love_letter_equilibrium_structure() -> EquilibriumGameStructure:
    """Describe why Love Letter is extensive-form, not a timing matrix."""

    return EquilibriumGameStructure(
        players=2,
        finite=True,
        zero_sum_or_constant_sum=True,
        perfect_recall=True,
        chance_after_initial_state=True,
        stopping_time=StoppingTimeStructure(
            horizon=10,
            fixed_private_information_at_start=False,
            no_new_private_information=False,
            forced_continuation_before_stop=False,
            payoff_depends_only_on_stopping_times=False,
        ),
        exact_tree_is_small=False,
    )
