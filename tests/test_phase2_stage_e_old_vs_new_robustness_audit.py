from __future__ import annotations

import csv
import gzip
import importlib.util
from pathlib import Path

MODULE_PATH = Path(__file__).parents[1] / "scripts" / "phase2_audit_stage_e_old_vs_new_robustness.py"
spec = importlib.util.spec_from_file_location("audit", MODULE_PATH)
audit = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(audit)


def test_semantic_identity_is_route_order_invariant_when_phase_mapping_is_same():
    a = {
        "scenario_id": "S",
        "topology_family": "T",
        "uniform_headway_min": "20",
        "span_start_min": "360",
        "span_end_min": "1320",
        "public_route_ids_json": '["R1","R2"]',
        "selected_phase_vector_json": "[3,7]",
    }
    b = dict(a)
    b["public_route_ids_json"] = '["R2","R1"]'
    b["selected_phase_vector_json"] = "[7,3]"
    assert audit.semantic_hash(a) == audit.semantic_hash(b)


def test_semantic_identity_changes_when_phase_mapping_changes():
    a = {
        "scenario_id": "S", "topology_family": "T", "uniform_headway_min": "20",
        "span_start_min": "360", "span_end_min": "1320",
        "public_route_ids_json": '["R1","R2"]', "selected_phase_vector_json": "[3,7]",
    }
    b = dict(a)
    b["selected_phase_vector_json"] = "[4,7]"
    assert audit.semantic_hash(a) != audit.semantic_hash(b)


def test_span_rule_is_start_inclusive_end_exclusive():
    assert audit.in_service_span(360.0, 360.0, 1320.0)
    assert audit.in_service_span(1319.999, 360.0, 1320.0)
    assert not audit.in_service_span(1320.0, 360.0, 1320.0)
    assert not audit.in_service_span(359.999, 360.0, 1320.0)


def test_metric_equality_is_numeric_but_blank_sensitive():
    assert audit.metric_equal("1", "1.000000000")
    assert audit.metric_equal("true", "TRUE")
    assert not audit.metric_equal("", "0")
    assert not audit.metric_equal("1", "1.1")


def test_split_detection_is_context_to_multiple_timetable_identity(tmp_path):
    path = tmp_path / "contexts.csv.gz"
    fields = ["plan_context_id", "stage_d_input_id", "selected_timetable_id", "budget_suffix", "calendar_id", "selected_phase_vector_json"]
    with gzip.open(path, "wt", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerow({"plan_context_id":"c1","stage_d_input_id":"d1","selected_timetable_id":"t1","budget_suffix":"b1","calendar_id":"cal1","selected_phase_vector_json":"[0]"})
        writer.writerow({"plan_context_id":"c2","stage_d_input_id":"d1","selected_timetable_id":"t2","budget_suffix":"b2","calendar_id":"cal2","selected_phase_vector_json":"[1]"})
        writer.writerow({"plan_context_id":"c3","stage_d_input_id":"d2","selected_timetable_id":"t3","budget_suffix":"b1","calendar_id":"cal1","selected_phase_vector_json":"[0]"})
    tids, contexts, split, count = audit.load_split_contexts(path)
    assert split == {"d1"}
    assert tids["d1"] == {"t1", "t2"}
    assert len(contexts["d1"]) == 2
    assert count == 3


def test_connection_scan_counts_out_of_span_legacy_rows(tmp_path):
    path = tmp_path / "connections.csv.gz"
    fields = [
        "stage_d_input_id", "route_id", "connection_type", "direction", "profile_id",
        "source_time_min", "technical_return_used_as_passenger_service", "planned_connection_exists",
        "sensitivity_results_json",
    ]
    payload = '{"0.000000000":{"planned_connection_exists":true,"planned_connection_retained":true},"5.000000000":{"planned_connection_exists":true,"planned_connection_retained":false}}'
    with gzip.open(path, "wt", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerow({
            "stage_d_input_id":"d1", "route_id":"r1", "connection_type":"BUS_TO_RAIL",
            "direction":"MILANO", "profile_id":"P", "source_time_min":"100.000000",
            "technical_return_used_as_passenger_service":"false", "planned_connection_exists":"true",
            "sensitivity_results_json":payload,
        })
    tables = {"d1":{"span_start_min":"0", "span_end_min":"100"}}
    events = {("d1","r1","100.000000"):{
        "stage_e_connection_row_count":0, "stage_e_planned_connection_row_count":0,
        "profile_direction_counts":audit.Counter(), "misses_by_runtime_stress":audit.Counter(),
    }}
    result = audit.scan_connection_audit(path, identity_field="stage_d_input_id", tables=tables, raw_outspan=events)
    assert result["direct_out_of_span_bus_to_rail_row_count"] == 1
    assert events[("d1","r1","100.000000")]["stage_e_connection_row_count"] == 1
    assert events[("d1","r1","100.000000")]["misses_by_runtime_stress"]["5.000000000"] == 1
