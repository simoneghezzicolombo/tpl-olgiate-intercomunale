import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from phase2_audit_rt031_line8_service_promise_v3 import build  # noqa: E402


SOURCE = ROOT / "outputs/phase2/rt031_line8_service_envelope_v3/envelope.json"


def test_inclusive_full_traversal_promise_math():
    result = build(json.loads(SOURCE.read_text(encoding="utf-8")))
    assert result["maximum_daily_full_traversals_each_direction_before_extras"] == 8
    assert result["uniform_departure_interval_hours_if_max_pairs_spread_across_16h"] == 2
    assert result["pairs_remaining_for_other_12h_under_cap_before_extras"] == 0
    scenarios = {row["scenario_id"]: row for row in result["scenarios"]}
    assert scenarios["H60_8H"]["within_cap_before_extras"]
    assert not scenarios["H60_10H"]["within_cap_before_extras"]
    assert scenarios["H60_16H"]["annual_full_traversal_km_before_extras"] == pytest.approx(217183.82816)
    assert result["decision_budget_km"] is None
    assert result["uncertainty_band_min"] is None
    assert not result["network_selected"]
    assert not result["primary_selection_authorised"]
    assert not result["runner_up_selection_authorised"]


def test_fails_closed_if_inclusive_variant_loses_retention():
    envelope = json.loads(SOURCE.read_text(encoding="utf-8"))
    next(row for row in envelope["variants"] if row["variant_id"] ==
         "FIVE_QUATTRO_STRADE_THEN_CARIPLO")[
             "current_exact_stop_ids_encountered_both_directions"] = 10
    with pytest.raises(ValueError, match="inclusive 11/11"):
        build(envelope)


def test_fails_closed_if_source_becomes_decisional():
    envelope = json.loads(SOURCE.read_text(encoding="utf-8"))
    envelope["primary_selection_authorised"] = True
    with pytest.raises(ValueError, match="unexpectedly authorises selection"):
        build(envelope)
