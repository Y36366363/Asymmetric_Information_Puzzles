"""Solver-selection and compression audits for finite strategic games."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class EquilibriumMethod(str, Enum):
    EXACT_MATRIX = "exact_matrix"
    SEQUENCE_FORM = "sequence_form_lp"
    VANILLA_CFR = "vanilla_cfr"
    CFR_PLUS = "cfr_plus"
    DCFR = "dcfr"
    EXTERNAL_SAMPLING_MCCFR = "external_sampling_mccfr"
    UNSUPPORTED = "unsupported_by_two_player_zero_sum_pipeline"


@dataclass(frozen=True, slots=True)
class StoppingTimeStructure:
    horizon: int
    fixed_private_information_at_start: bool
    no_new_private_information: bool
    forced_continuation_before_stop: bool
    payoff_depends_only_on_stopping_times: bool


@dataclass(frozen=True, slots=True)
class StoppingTimeAudit:
    compressible: bool
    failures: tuple[str, ...]
    matrix_shape: tuple[int, int] | None


def audit_stopping_time_compression(
    structure: StoppingTimeStructure,
) -> StoppingTimeAudit:
    failures: list[str] = []
    if structure.horizon <= 0:
        failures.append("invalid_horizon")
    if not structure.fixed_private_information_at_start:
        failures.append("private_information_not_fixed_at_start")
    if not structure.no_new_private_information:
        failures.append("new_private_information_arrives")
    if not structure.forced_continuation_before_stop:
        failures.append("strategic_actions_exist_before_stopping")
    if not structure.payoff_depends_only_on_stopping_times:
        failures.append("payoff_requires_more_than_stopping_times")
    return StoppingTimeAudit(
        compressible=not failures,
        failures=tuple(failures),
        matrix_shape=(structure.horizon, structure.horizon) if not failures else None,
    )


@dataclass(frozen=True, slots=True)
class EquilibriumGameStructure:
    players: int
    finite: bool
    zero_sum_or_constant_sum: bool
    perfect_recall: bool
    chance_after_initial_state: bool
    stopping_time: StoppingTimeStructure | None = None
    exact_tree_is_small: bool = False
    estimated_full_tree_nodes: int | None = None
    full_tree_node_budget: int | None = None

    def __post_init__(self) -> None:
        if (
            self.estimated_full_tree_nodes is not None
            and self.estimated_full_tree_nodes <= 0
        ):
            raise ValueError("estimated full-tree nodes must be positive")
        if (
            self.full_tree_node_budget is not None
            and self.full_tree_node_budget <= 0
        ):
            raise ValueError("full-tree node budget must be positive")


@dataclass(frozen=True, slots=True)
class SolverRecommendation:
    eligible_for_gto_pipeline: bool
    primary: EquilibriumMethod
    cross_check: EquilibriumMethod | None
    reasons: tuple[str, ...]


def recommend_equilibrium_solver(
    structure: EquilibriumGameStructure,
) -> SolverRecommendation:
    unsupported: list[str] = []
    if structure.players != 2:
        unsupported.append("requires_two_players")
    if not structure.finite:
        unsupported.append("requires_finite_game")
    if not structure.zero_sum_or_constant_sum:
        unsupported.append("requires_zero_or_constant_sum")
    if not structure.perfect_recall:
        unsupported.append("requires_perfect_recall_or_a_separate_abstraction_proof")
    if unsupported:
        return SolverRecommendation(
            False, EquilibriumMethod.UNSUPPORTED, None, tuple(unsupported)
        )

    if structure.stopping_time is not None:
        audit = audit_stopping_time_compression(structure.stopping_time)
        if audit.compressible:
            return SolverRecommendation(
                True,
                EquilibriumMethod.EXACT_MATRIX,
                EquilibriumMethod.VANILLA_CFR,
                ("complete_stopping_time_matrix_available",),
            )
    if structure.exact_tree_is_small:
        return SolverRecommendation(
            True,
            EquilibriumMethod.SEQUENCE_FORM,
            EquilibriumMethod.VANILLA_CFR,
            ("small_perfect_recall_extensive_form",),
        )
    full_tree_cost_known = (
        structure.estimated_full_tree_nodes is not None
        and structure.full_tree_node_budget is not None
    )
    full_tree_fits = (
        full_tree_cost_known
        and structure.estimated_full_tree_nodes <= structure.full_tree_node_budget
    )
    if full_tree_cost_known and not full_tree_fits:
        return SolverRecommendation(
            True,
            EquilibriumMethod.EXTERNAL_SAMPLING_MCCFR,
            EquilibriumMethod.DCFR,
            ("estimated_full_tree_cost_exceeds_resource_budget",),
        )
    if structure.chance_after_initial_state and full_tree_fits:
        return SolverRecommendation(
            True,
            EquilibriumMethod.DCFR,
            EquilibriumMethod.EXTERNAL_SAMPLING_MCCFR,
            (
                "later_chance_supported_by_full_tree_traversal",
                "estimated_full_tree_cost_within_resource_budget",
            ),
        )
    if structure.chance_after_initial_state:
        return SolverRecommendation(
            True,
            EquilibriumMethod.EXTERNAL_SAMPLING_MCCFR,
            EquilibriumMethod.SEQUENCE_FORM,
            (
                "later_chance_supported_by_both_full_tree_and_sampling",
                "full_tree_cost_or_resource_budget_not_established",
            ),
        )
    return SolverRecommendation(
        True,
        EquilibriumMethod.VANILLA_CFR,
        EquilibriumMethod.SEQUENCE_FORM,
        ("finite_two_player_zero_sum_extensive_form",),
    )
