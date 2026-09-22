"""Regression gates for deciding when to expand the transfer benchmark."""

import json
from pathlib import Path

import pytest

from aip.benchmark.liar_transfer import (
    build_oracle_probes,
    compare_probe_oracles,
    opponent_reach_mass,
    select_profile_invariant_probes,
)
from aip.puzzles.liars_dice import load_one_die_liar_policy, solve_one_die_liar_exact


ROOT = Path(__file__).resolve().parents[1]


def test_selected_liar_probes_expose_profile_sensitive_label():
    _, exact = solve_one_die_liar_exact()
    frozen = load_one_die_liar_policy(
        ROOT / "src/aip/puzzles/liars_dice/one_die_cfr_policy.json"
    )
    audit = compare_probe_oracles(
        build_oracle_probes(),
        {"exact": exact.policy, "frozen": frozen.policy},
    )
    assert audit["profileInvariantProbes"] == 11
    assert audit["unstableProbeIds"] == ["liar-probe-02"]
    assert audit["allProbeLabelsInvariant"] is False


def test_oracle_comparison_rejects_single_profile():
    _, exact = solve_one_die_liar_exact()
    with pytest.raises(ValueError, match="at least two profiles"):
        compare_probe_oracles(build_oracle_probes(), {"exact": exact.policy})


def test_consensus_selector_builds_balanced_reachable_thirty_probe_panel():
    _, exact = solve_one_die_liar_exact()
    frozen = load_one_die_liar_policy(
        ROOT / "src/aip/puzzles/liars_dice/one_die_cfr_policy.json"
    )
    profiles = {"exact": exact.policy, "frozen": frozen.policy}
    probes, audit = select_profile_invariant_probes(profiles)
    assert len(probes) == 30
    assert audit["challengeOptimal"] == 15
    assert audit["raiseOptimal"] == 15
    assert audit["playerOneRaiseProbes"] == 5
    assert audit["allSelectedProfileInvariant"] is True
    assert all(
        opponent_reach_mass(profile, probe.player, probe.bids) > 0
        for profile in profiles.values()
        for probe in probes
    )


def test_frozen_methodology_audit_fails_closed_before_game_expansion():
    artifact = json.loads((
        ROOT / "research/results/transfer_methodology_audit_2026-09-22.json"
    ).read_text(encoding="utf-8"))
    gates = artifact["methodGates"]
    assert gates["liar_run_complete"] is True
    assert gates["provider_token_counts_exact"] is True
    assert gates["all_selected_probe_labels_profile_invariant"] is False
    assert gates["same_game_positive_control_detectably_better"] is False
    assert gates["abstract_transfer_replicated_across_targets"] is False
    assert artifact["decision"]["nextStep"] == (
        "optimize_current_method_before_expanding_primary_game_count"
    )
    assert artifact["nextProfileInvariantPanel"]["selectedProbeCount"] == 30
    assert artifact["nextProfileInvariantPanel"]["allSelectedProfileInvariant"] is True
    candidates = {
        item["game"]: item["readiness"]
        for item in artifact["horizontalCandidateAssessment"]
    }
    assert candidates["goofspiel-four-card"] == (
        "best_next_horizontal_target_after_method_gates"
    )
    assert candidates["full-love-letter"] == "blocked"
