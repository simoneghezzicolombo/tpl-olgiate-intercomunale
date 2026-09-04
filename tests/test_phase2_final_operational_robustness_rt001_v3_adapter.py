import csv
import gzip
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.phase2_run_final_operational_robustness_rt001_v3 import (
    materialise_compatibility_inputs,
    parse_vehicle_id,
)


def _write_csv(path: Path, fields, rows):
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def _write_gz(path: Path, fields, rows):
    with gzip.open(path, "wt", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def test_vehicle_id_parser_is_label_invariant():
    assert parse_vehicle_id("V1", field="x") == 1
    assert parse_vehicle_id("VEHICLE_17", field="x") == 17
    assert parse_vehicle_id("23", field="x") == 23
    with pytest.raises(ValueError):
        parse_vehicle_id("bus-A", field="x")


def test_adapter_uses_selected_timetable_as_exact_unit_and_never_leaks_open_route_endpoint(tmp_path):
    tables = tmp_path / "tables.csv"
    contexts = tmp_path / "contexts.csv.gz"
    trips = tmp_path / "trips.csv.gz"
    routes = tmp_path / "routes.csv"

    table_rows = [{
        "selected_timetable_id": "T1", "stage_d_input_id": "D1", "scenario_id": "S1",
        "topology_family": "CORE", "span_start_min": "330", "span_end_min": "900",
        "public_route_ids_json": '["Rclosed","Ropen"]', "explicit_public_trip_count": "2",
        "exact_fleet_recovery5": "1", "exact_fleet_recovery10": "1", "exact_fleet_recovery15": "1",
    }]
    _write_csv(tables, list(table_rows[0]), table_rows)

    context_rows = [{
        "plan_context_id": "m20pct|P1", "selected_timetable_id": "T1", "stage_d_input_id": "D1",
    }]
    _write_gz(contexts, list(context_rows[0]), context_rows)

    trip_rows = [
        {
            "selected_timetable_id": "T1", "route_id": "Rclosed", "trip_ordinal": "0",
            "departure_min": "400", "public_service_end_min": "430", "vehicle_return_hub_min": "430",
            "vehicle_id_recovery5": "V1", "vehicle_id_recovery10": "V1", "vehicle_id_recovery15": "V1",
        },
        {
            "selected_timetable_id": "T1", "route_id": "Ropen", "trip_ordinal": "0",
            "departure_min": "410", "public_service_end_min": "440", "vehicle_return_hub_min": "450",
            "vehicle_id_recovery5": "V1", "vehicle_id_recovery10": "V1", "vehicle_id_recovery15": "V1",
        },
    ]
    _write_gz(trips, list(trip_rows[0]), trip_rows)

    route_rows = [
        {"route_id": "Rclosed", "bus_to_rail_passenger_event_supported": "true"},
        {"route_id": "Ropen", "bus_to_rail_passenger_event_supported": "false"},
    ]
    _write_csv(routes, list(route_rows[0]), route_rows)

    args = SimpleNamespace(
        stage_d_timetables=tables,
        stage_d_contexts=contexts,
        stage_d_trips=trips,
        route_input=routes,
    )
    validation = {
        "unique_selected_exact_timetable_count": 1,
        "stage_c_plan_context_count": 1,
        "selected_exact_trip_row_count": 2,
    }
    summary_path, trip_path, table_index, context_count = materialise_compatibility_inputs(
        args, tmp_path / "normalized", validation
    )
    assert set(table_index) == {"T1"}
    assert context_count == 1

    with gzip.open(summary_path, "rt", encoding="utf-8", newline="") as f:
        summary = list(csv.DictReader(f))
    assert summary[0]["stage_d_input_id"] == "T1"

    with gzip.open(trip_path, "rt", encoding="utf-8", newline="") as f:
        normalized = {r["route_id"]: r for r in csv.DictReader(f)}
    assert normalized["Rclosed"]["stage_d_input_id"] == "T1"
    assert normalized["Rclosed"]["public_hub_return_min"] == "430"
    assert normalized["Ropen"]["public_hub_return_min"] == ""
    assert normalized["Ropen"]["vehicle_hub_return_min"] == "450"
    for recovery in (5, 10, 15):
        assert normalized["Rclosed"][f"vehicle_block_recovery{recovery}"] == "1"
        assert normalized["Ropen"][f"vehicle_block_recovery{recovery}"] == "1"
