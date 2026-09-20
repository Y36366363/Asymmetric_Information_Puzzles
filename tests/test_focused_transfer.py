"""Regression checks for the frozen source-to-target transfer experiment."""

import copy
from pathlib import Path

import pytest

from aip.benchmark.focused_transfer import (
    ARMS,
    MEMORY_CHARACTERS,
    analyze_results,
    make_preregistration,
    memory_prompt,
    validate_preregistration,
)


SOURCES = (
    Path("research/results/love_letter_liar_algorithm_audit_2026-09-19.json"),
    Path("research/results/one_die_liar_exact_2026-09-18.json"),
)


def test_four_conditions_have_equal_instruction_block_length_and_no_target_leakage():
    plan = make_preregistration(SOURCES)
    validate_preregistration(plan)
    assert set(plan["memoryPrompts"]) == set(ARMS)
    assert {len(memory_prompt(arm)) for arm in ARMS} == {MEMORY_CHARACTERS}
    assert len(plan["cellOrder"]) == 32
    for arm in ("surface_experience", "abstract_memory"):
        assert "guess who" not in memory_prompt(arm).lower()
        assert "ada" not in memory_prompt(arm).lower()


def test_preregistration_rejects_changed_prompt_state_and_schedule():
    plan = make_preregistration(SOURCES)
    changed = copy.deepcopy(plan)
    changed["memoryPrompts"]["abstract_memory"] = memory_prompt("no_memory")
    with pytest.raises(ValueError, match="memory prompt"):
        validate_preregistration(changed)
    changed = copy.deepcopy(plan)
    changed["probes"][0]["publicStateSha256"] = "0" * 64
    with pytest.raises(ValueError, match="target state"):
        validate_preregistration(changed)
    changed = copy.deepcopy(plan)
    changed["cellOrder"][0] = changed["cellOrder"][1]
    with pytest.raises(ValueError, match="complete and unique"):
        validate_preregistration(changed)


def test_primary_analysis_is_paired_and_failures_are_included():
    plan = make_preregistration(SOURCES)
    rows = [
        {
            "probeId": probe["id"],
            "arm": arm,
            "status": "valid",
            "penalizedRegretTurns": 0.25,
            "beliefBrier": None,
            "totalTokens": 10,
        }
        for probe in plan["probes"]
        for arm in ARMS
    ]
    first = next(row for row in rows if row["arm"] == "abstract_memory")
    first["status"] = "failed"
    first["penalizedRegretTurns"] = plan["probes"][0]["failurePenaltyTurns"]
    report = analyze_results(plan, rows)
    assert report["summaries"]["abstract_memory"]["validDecisions"] == 7
    assert report["contrastsVersusNoMemory"]["abstract_memory"]["meanDifferenceTurns"] > 0
    assert report["contrastsVersusNoMemory"]["same_game"]["interpretation"] == "inconclusive"
    with pytest.raises(ValueError, match="incomplete"):
        analyze_results(plan, rows[:-1])
