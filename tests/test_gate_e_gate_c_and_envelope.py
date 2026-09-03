from pathlib import Path
import csv
import json
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.gate_e_gate_c_baseline import build_baseline  # noqa: E402
from src.operating_envelope import (  # noqa: E402
    cycle_slack_min,
    maximum_cycle_min_for_headway,
    maximum_pure_running_min_for_headway,
    max_symmetric_daily_cycles_each_direction_for_budget,
    max_symmetric_route_km_for_budget,
    max_total_directional_cycles_year_for_budget,
    theoretical_regular_headway_min,
)
from src.service_math import ServiceMathError  # noqa: E402


def c_bus(service_date="2026-09-03"):
    return {
        "gate": "C", "source_class": "OFFICIAL_OPERATOR_PRIMARY_TIMETABLE_PDFS",
        "service_date": service_date,
        "routes": [
            {"route_id": "D184", "active_timetable_columns": 2, "valid_from": "2026-06-09",
             "valid_to": "2026-09-13", "epistemic_status": "RECONSTRUCTED_FROM_OFFICIAL_PRIMARY_TIMETABLE",
             "notes_detected": {"brivio_bridge_cantu_deviation": False}},
            {"route_id": "D185", "active_timetable_columns": 3, "valid_from": "2026-06-09",
             "valid_to": "2026-09-13", "epistemic_status": "RECONSTRUCTED_FROM_OFFICIAL_PRIMARY_TIMETABLE",
             "notes_detected": {"brivio_bridge_cantu_deviation": True}},
        ],
    }


def c_rail(service_date="2026-09-03"):
    return {
        "gate": "C", "source_type": "LIVE_OFFICIAL_GTFS", "service_date": service_date,
        "route_ids_resolved_for_s8": ["S8"],
        "station": {"stop_id": "S01514", "stop_name": "Olgiate-Calco-Brivio"},
        "active_s8_trips_count": 4, "active_s8_station_events_count": 4,
        "feed_service_span": {"start": "2026-07-26", "end": "2026-12-12"},
    }


def test_gate_c_baseline_is_single_date_and_never_annualized():
    rows = build_baseline(c_bus(), c_rail(), gate_c_commit="abc123", bus_artifact="bus.json", rail_artifact="rail.json")
    assert len(rows) == 4
    assert all(row["annualization_status"] == "FORBIDDEN_FROM_SINGLE_DATE_BASELINE" for row in rows)
    assert all("FUTURE_SERVICE_PLAN" in row["future_plan_status"] or "CONNECTION_CONTEXT_ONLY" in row["future_plan_status"] for row in rows)


def test_gate_c_baseline_derives_bus_sum_without_calling_it_cycles():
    rows = build_baseline(c_bus(), c_rail(), gate_c_commit="abc123", bus_artifact="bus.json", rail_artifact="rail.json")
    total = next(row for row in rows if row["service_id"] == "D184+D185")
    assert total["value"] == 5
    assert total["metric"] == "active_timetable_columns_sum"
    assert "cycle" not in total["metric"]


def test_gate_c_baseline_propagates_temporary_bridge_context():
    rows = build_baseline(c_bus(), c_rail(), gate_c_commit="abc123", bus_artifact="bus.json", rail_artifact="rail.json")
    d185 = next(row for row in rows if row["service_id"] == "D185")
    assert d185["context_warning"] == "BRIVIO_BRIDGE_CANTU_DEVIATION_ACTIVE_IN_SOURCE"


def test_gate_c_baseline_requires_matching_service_date():
    with pytest.raises(ServiceMathError, match="service dates differ"):
        build_baseline(c_bus(), c_rail("2026-09-04"), gate_c_commit="abc123", bus_artifact="bus.json", rail_artifact="rail.json")


def test_gate_c_baseline_requires_pass_lineage_commit():
    with pytest.raises(ServiceMathError, match="commit SHA"):
        build_baseline(c_bus(), c_rail(), gate_c_commit="", bus_artifact="bus.json", rail_artifact="rail.json")


def test_gate_c_baseline_rejects_missing_core_bus_route():
    bus = c_bus(); bus["routes"] = bus["routes"][:1]
    with pytest.raises(ServiceMathError, match="D185"):
        build_baseline(bus, c_rail(), gate_c_commit="abc123", bus_artifact="bus.json", rail_artifact="rail.json")


def test_theoretical_headway_and_cycle_envelope_are_inverse():
    assert theoretical_regular_headway_min(120, 2) == 60
    assert maximum_cycle_min_for_headway(60, 2) == 120


def test_runtime_envelope_separates_dwell_and_recovery():
    assert maximum_pure_running_min_for_headway(60, 1, 4, 6) == 50
    assert maximum_pure_running_min_for_headway(30, 2, 4, 6) == 50


def test_runtime_envelope_can_explicitly_show_impossible_policy():
    assert maximum_pure_running_min_for_headway(5, 1, 4, 6) == -5


def test_cycle_slack_boundary_and_overrun():
    assert cycle_slack_min(60, 60, 1) == 0
    assert cycle_slack_min(60.01, 60, 1) == pytest.approx(-0.01)
    assert cycle_slack_min(59.99, 60, 1) == pytest.approx(0.01)


def test_budget_inverse_cycle_and_route_thresholds_are_consistent():
    budget = 1000
    route = 10
    assert max_total_directional_cycles_year_for_budget(budget, route) == 100
    assert max_symmetric_daily_cycles_each_direction_for_budget(budget, route, 10) == 5
    assert max_symmetric_route_km_for_budget(budget, 5, 10) == 10


def test_operating_envelope_rejects_nonpositive_inputs():
    with pytest.raises(ServiceMathError):
        maximum_cycle_min_for_headway(0, 1)
    with pytest.raises(ServiceMathError):
        max_symmetric_route_km_for_budget(1000, 0, 10)


def test_gate_c_baseline_cli_writes_no_annualized_metric(tmp_path):
    bus = tmp_path / "bus.json"; rail = tmp_path / "rail.json"; out = tmp_path / "out.csv"
    bus.write_text(json.dumps(c_bus()), encoding="utf-8")
    rail.write_text(json.dumps(c_rail()), encoding="utf-8")
    proc = subprocess.run([
        sys.executable, str(ROOT / "scripts/gate_e_gate_c_baseline.py"),
        "--bus-json", str(bus), "--rail-json", str(rail), "--gate-c-commit", "abc123", "--output", str(out),
    ], cwd=ROOT, text=True, capture_output=True)
    assert proc.returncode == 0, proc.stderr
    rows = list(csv.DictReader(out.open(encoding="utf-8")))
    assert rows and all(r["annualization_status"].startswith("FORBIDDEN") for r in rows)


def test_operating_envelope_cli_labels_every_policy_input_as_assumption(tmp_path):
    out = tmp_path / "envelope.csv"
    proc = subprocess.run([
        sys.executable, str(ROOT / "scripts/gate_e_operating_envelope.py"),
        "--headways", "60", "--vehicles-each-direction", "1", "--dwell-min", "4",
        "--recovery-min", "6", "--cycles-per-day-each-direction", "10", "--service-days", "300",
        "--output", str(out),
    ], cwd=ROOT, text=True, capture_output=True)
    assert proc.returncode == 0, proc.stderr
    row = next(csv.DictReader(out.open(encoding="utf-8")))
    assert row["result_status"] == "SENSITIVITY_ONLY_NOT_PROJECT_RESULT"
    assert row["headway_status"] == "ASSUMPTION"
    assert row["vehicle_policy_status"] == "ASSUMPTION"
    assert row["dwell_status"] == "ASSUMPTION"
    assert row["recovery_status"] == "ASSUMPTION"
    assert row["cycles_status"] == "ASSUMPTION"
    assert row["service_days_status"] == "ASSUMPTION"
