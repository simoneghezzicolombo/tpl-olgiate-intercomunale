#!/usr/bin/env python3
"""Targeted semantic red-team for Alpha exact feeder-to-S8 set bounds.

The audit is intentionally tiny. It exercises the already-certified passenger
span rule with a closed public route whose last trip departs in span but returns
to the hub after the declared service end. Such a physical/public return must not
become a BUS->RAIL passenger event under the certified [start,end) contract.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from scripts.phase2_build_gjt_set_bounds_exact_v3 import build_anchor_components
from src.phase2_gjt_set_bounds_exact_v3 import (
    HUB_ANCHOR,
    RailDeparture,
    SensitivityCase,
    build_public_to_hub_occurrences,
)

STATUS_FAIL = "FAIL_PHASE2_GJT_BOUNDS_TARGETED_REVIEW_A"
CONTRACT = "PHASE2_GJT_BOUNDS_TARGETED_PASSENGER_SPAN_REVIEW_A"


def detect_out_of_span_leak() -> dict[str, object]:
    # Certified semantic fixture: public route is HUB -> A -> HUB. The trip
    # departs inside the service span but its public return occurs after span_end.
    span_start = 0.0
    span_end = 60.0
    trip_departure = 50.0
    anchors = (HUB_ANCHOR, "anchor:A", HUB_ANCHOR)
    runtime = {
        (HUB_ANCHOR, "anchor:A"): 10.0,
        ("anchor:A", HUB_ANCHOR): 10.0,
    }
    occurrences = build_public_to_hub_occurrences(
        anchors,
        runtime,
        bus_to_rail_passenger_event_supported=True,
    )
    case = SensitivityCase(
        case_id="LOW_SW2",
        station_transfer_walk_min=2.0,
        bus_ivt_weight=1.0,
        walk_weight=1.5,
        wait_weight=1.5,
        transfer_penalty_min=2.0,
        bound_side="LOW",
    )
    rail = {
        "MILANO": (
            RailDeparture(event_id="TRAIN_75", direction="MILANO", departure_min=75.0),
        )
    }
    components = build_anchor_components(
        timetable_route_departures={"R_CLOSED": (trip_departure,)},
        route_occurrences={"R_CLOSED": occurrences},
        rail_departures=rail,
        case=case,
        direction="MILANO",
    )
    component = components.get("anchor:A")
    reconstructed_return = None if component is None else float(component["bus_hub_arrival_min"])
    return {
        "span_start_min": span_start,
        "span_end_min": span_end,
        "trip_departure_min": trip_departure,
        "reconstructed_public_hub_return_min": reconstructed_return,
        "return_is_out_of_span": reconstructed_return is not None and reconstructed_return >= span_end,
        "passenger_component_was_created": component is not None,
        "out_of_span_passenger_return_leak_detected": (
            component is not None and reconstructed_return is not None and reconstructed_return >= span_end
        ),
        "component": component,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--validation", type=Path, required=True)
    args = parser.parse_args()

    fixture = detect_out_of_span_leak()
    leak = bool(fixture["out_of_span_passenger_return_leak_detected"])
    payload = {
        "status": STATUS_FAIL if leak else "PASS_PHASE2_GJT_BOUNDS_TARGETED_REVIEW_A",
        "contract": CONTRACT,
        "certification_pass": not leak,
        "frozen_alpha_commit": "0916cc2c1ecc00f0919d33809e9e8d4473e2f8cc",
        "out_of_span_public_return_leak_detected": leak,
        "certified_passenger_span_rule": "START_INCLUSIVE_END_EXCLUSIVE_[span_start,span_end)",
        "fixture": fixture,
        "required_fix": (
            "Carry certified Stage-D public_service_end_min or span_end_min into BUS_TO_RAIL event construction "
            "and reject any public hub return >= span_end_min."
        ),
        "other_review_findings": {
            "historical_half_headway_wait_reused": False,
            "municipal_od_downscaled": False,
            "resident_population_used_as_demand": False,
            "rail_direction_conditioned_separately": True,
            "technical_vehicle_closure_used_as_passenger_return": False,
            "six_case_sensitivity_reduction_design_blocked": False,
        },
        "decision_boundary": "TARGETED_FAIL_ONLY_NO_RANKING_NO_NEW_PHASE2_BLOCKER",
    }
    args.validation.parent.mkdir(parents=True, exist_ok=True)
    args.validation.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))

    # A green CI run means the red-team correctly detected the frozen-commit bug.
    if not leak:
        raise SystemExit("Frozen Alpha commit no longer reproduces the expected leak; audit fixture must be revisited")


if __name__ == "__main__":
    main()
