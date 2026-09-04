import pytest

from scripts.phase2_run_final_operational_robustness_rt001_v3 import (
    parse_vehicle_id,
    prepare_engine_inputs,
)


def validation():
    return {"recovery_values_evaluated_not_selected": [5, 10, 15]}


def timetable(*, routes='["R_OPEN"]', fleet5="1", fleet10="1", fleet15="1"):
    return [{
        "selected_timetable_id": "T1",
        "stage_d_input_id": "D1",
        "scenario_id": "S1",
        "topology_family": "TEST",
        "public_route_ids_json": routes,
        "explicit_public_trip_count": "1",
        "span_start_min": "330",
        "span_end_min": "1440",
        "exact_fleet_recovery5": fleet5,
        "exact_fleet_recovery10": fleet10,
        "exact_fleet_recovery15": fleet15,
    }]


def trip(*, route="R_OPEN", parent="D1", v5="V1", v10="V1", v15="V1"):
    return [{
        "selected_timetable_id": "T1",
        "stage_d_input_id": parent,
        "route_id": route,
        "trip_ordinal": "0",
        "departure_min": "360",
        "public_service_end_min": "380",
        "vehicle_return_hub_min": "390",
        "vehicle_id_recovery5": v5,
        "vehicle_id_recovery10": v10,
        "vehicle_id_recovery15": v15,
    }]


def semantics(*, returns=False):
    return {
        "R_OPEN" if not returns else "R_CLOSED": {
            "public_service_returns_to_hub": returns,
            "bus_to_rail_passenger_event_supported": returns,
            "vehicle_closure_added": not returns,
            "rail_to_bus_passenger_event_supported": True,
        }
    }


def test_vehicle_ids_are_canonical_and_zero_based_in_engine():
    assert parse_vehicle_id("V1") == 0
    assert parse_vehicle_id("V4") == 3
    for bad in ("1", "V0", "V-1", "vehicle1", ""):
        with pytest.raises(ValueError):
            parse_vehicle_id(bad)


def test_open_route_public_service_end_never_becomes_passenger_hub_return():
    summaries, trips, parents, recoveries = prepare_engine_inputs(
        validation=validation(), timetable_rows=timetable(), trip_rows=trip(), route_semantics=semantics(returns=False)
    )
    exact = trips["T1"][0]
    assert exact.public_hub_return_min is None
    assert exact.vehicle_hub_return_min == 390
    assert exact.passenger_returns_to_hub is False
    assert parents == {"T1": "D1"}
    assert recoveries == (5, 10, 15)
    assert summaries["T1"]["stage_d_input_id"] == "T1"
    assert summaries["T1"]["original_stage_d_input_id"] == "D1"


def test_closed_route_public_service_end_is_passenger_hub_return():
    tables = timetable(routes='["R_CLOSED"]')
    rows = trip(route="R_CLOSED")
    route_semantics = semantics(returns=True)
    _, trips, _, _ = prepare_engine_inputs(
        validation=validation(), timetable_rows=tables, trip_rows=rows, route_semantics=route_semantics
    )
    exact = trips["T1"][0]
    assert exact.public_hub_return_min == 380
    assert exact.passenger_returns_to_hub is True


def test_vehicle_id_partition_must_reproduce_declared_exact_fleet():
    with pytest.raises(ValueError, match="vehicle IDs do not reproduce exact fleet"):
        prepare_engine_inputs(
            validation=validation(), timetable_rows=timetable(fleet5="2"), trip_rows=trip(), route_semantics=semantics(returns=False)
        )


def test_trip_parent_stage_d_identity_must_match_timetable():
    with pytest.raises(ValueError, match="parent Stage-D identity mismatch"):
        prepare_engine_inputs(
            validation=validation(), timetable_rows=timetable(), trip_rows=trip(parent="D2"), route_semantics=semantics(returns=False)
        )


def test_route_semantics_must_keep_technical_closure_out_of_passenger_return():
    bad = {
        "R_OPEN": {
            "public_service_returns_to_hub": False,
            "bus_to_rail_passenger_event_supported": True,
            "vehicle_closure_added": True,
            "rail_to_bus_passenger_event_supported": True,
        }
    }
    with pytest.raises(ValueError, match="passenger-return route semantics conflict"):
        prepare_engine_inputs(
            validation=validation(), timetable_rows=timetable(), trip_rows=trip(), route_semantics=bad
        )
