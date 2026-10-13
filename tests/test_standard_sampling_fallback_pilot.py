import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PILOT = ROOT / "research/results/standard_sampling_fallback_pilot_2026-10-13.json"


def test_pilot_is_labeled_noncertifying_and_excluded_from_confirmation():
    pilot = json.loads(PILOT.read_text())
    confirmation = json.loads(
        (
            ROOT
            / "configs/standard_sampling_fallback_confirmation_2026-10-13.json"
        ).read_text()
    )
    assert pilot["status"] == "exploratory_pilot_not_certification"
    assert pilot["thresholds_selected_from_this_pilot"] is False
    assert set(pilot["seeds_excluded_from_confirmation"]).isdisjoint(
        confirmation["confirmation_seeds"]
    )
    assert pilot["seeds_excluded_from_confirmation"] == (
        confirmation["pilot_seeds_must_be_excluded"]
    )
