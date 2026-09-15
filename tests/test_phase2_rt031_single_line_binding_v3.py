from copy import deepcopy

import pytest

from src.phase2_rt031_single_line_binding_v3 import (
    certify_single_public_line,
    eligible_h30_10h_candidates,
)


def candidate(identity="SL_1", ratios=None, *, within=True, retention=3):
    return {
        "candidate_line_id": identity,
        "physical_closed_walk_count": 1,
        "intended_public_route_identity_count": 1,
        "exact_access_ratios": ratios or ["2"] * 6,
        "retained_current_exact_stop_count": retention,
        "service_surface": [{
            "uniform_headway_min_per_movement": 30,
            "span_minutes": 600,
            "within_approved_reference_cap": within,
        }],
    }


def network():
    events = [{"event": {
        "event_id": identity,
        "pickup": pickup,
        "dropoff": dropoff,
        "passenger_through": through,
        "vehicle_through": vehicle,
    }} for identity, pickup, dropoff, through, vehicle in (
        ("depart", True, False, False, False),
        ("middle", True, True, True, True),
        ("arrive", False, True, False, False))]
    return {
        "service_relations_complete": True,
        "movement_assignment_complete": True,
        "payload": {
            "macro_incidence": [{"edge_id": "loop", "source_stop": "H",
                                  "target_stop": "H"}],
            "components": {"component": {
                "component": {"macro_edge_ids": ["loop"]},
                "events": events,
            }},
            "patterns": [{"pattern_id": "pattern", "component_id": "component",
                          "event_ids": ["depart", "middle", "arrive"]}],
            "movements": [{"movement_id": "movement", "component_id": "component",
                           "multiplicity": 1}],
        },
    }


def test_h30_context_uses_exact_access_and_does_not_filter_retention():
    rows = [candidate("low-retention", retention=1),
            candidate("high-retention", retention=11),
            candidate("worse", ["0"] * 6),
            candidate("over-cap", within=False)]
    got = eligible_h30_10h_candidates(rows, current_exact_ratios=["1"] * 6)
    assert [row["candidate_line_id"] for row in got] == [
        "high-retention", "low-retention"]


def test_single_line_certificate_keeps_route_movement_and_continuity_distinct():
    got = certify_single_public_line(network(), public_route_id="RT031_LINE")
    assert got["public_route_identity_count"] == 1
    assert got["cycle_seam_passenger_through"] is False
    assert got["vehicle_continuity_used_as_passenger_continuity"] is False
    assert got["ordered_service_event_ids"] == ["depart", "middle", "arrive"]


@pytest.mark.parametrize("mutation", ["two-components", "partial-pattern",
                                       "unknown-service", "seam-through"])
def test_false_single_line_guarantees_fail_closed(mutation):
    value = network()
    if mutation == "two-components":
        value["payload"]["components"]["other"] = deepcopy(
            value["payload"]["components"]["component"])
    if mutation == "partial-pattern":
        value["payload"]["patterns"][0]["event_ids"] = ["depart", "arrive"]
    if mutation == "unknown-service":
        value["payload"]["components"]["component"]["events"][1]["event"][
            "passenger_through"] = None
    if mutation == "seam-through":
        value["payload"]["components"]["component"]["events"][-1]["event"][
            "passenger_through"] = True
    with pytest.raises(ValueError):
        certify_single_public_line(value, public_route_id="RT031_LINE")
