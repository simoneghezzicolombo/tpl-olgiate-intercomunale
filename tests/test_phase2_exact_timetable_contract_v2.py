import math

from src.phase2_exact_timetable_contract_v2 import route_phase_cell_values_contract
from src.phase2_exact_timetable_optimizer_v2 import (
    RouteInput,
    TransferProfile,
    best_continuous_quality_target,
)


def test_bus_to_rail_excludes_public_returns_after_declared_span_end():
    profile = TransferProfile("MID", 2.0, 4.0, 1.5, 12.0)
    route = RouteInput(
        route_id="LOOP",
        public_runtime_min=20.0,
        cycle_runtime_min=20.0,
        public_service_starts_at_hub=True,
        public_service_returns_to_hub=True,
        vehicle_closure_added=False,
        rail_to_bus_passenger_event_supported=True,
        bus_to_rail_passenger_event_supported=True,
    )
    rail_index = {
        direction: {
            "arrivals": (300.0, 330.0, 360.0),
            "departures": (326.0, 356.0, 420.0),
        }
        for direction in ("LECCO", "MILANO")
    }

    cells = route_phase_cell_values_contract(
        route,
        phase=0,
        headway=30,
        span_start=300,
        span_end=361,
        rail_index=rail_index,
        profiles=(profile,),
    )

    # Departures are 300, 330, 360. Public returns are 320, 350, 380,
    # but 380 is outside the declared end-exclusive hub-event span.
    expected = []
    for public_return in (320.0, 350.0):
        matched = best_continuous_quality_target(
            rail_index["LECCO"]["departures"], public_return, profile
        )
        assert matched is not None
        expected.append(matched[1])
    expected_b2r = math.fsum(expected) / len(expected)

    # Cell order with one profile is R2B/B2R for LECCO, then R2B/B2R for MILANO.
    assert abs(cells[1] - expected_b2r) < 1e-15
    assert abs(cells[3] - expected_b2r) < 1e-15

    out_of_span = best_continuous_quality_target(
        rail_index["LECCO"]["departures"], 380.0, profile
    )
    assert out_of_span is not None
    incorrect_if_380_were_included = math.fsum([*expected, out_of_span[1]]) / 3
    assert abs(cells[1] - incorrect_if_380_were_included) > 1e-6
