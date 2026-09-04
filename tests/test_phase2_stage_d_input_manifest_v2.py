import csv
import gzip
import json

import pytest

from scripts.phase2_build_stage_d_input_manifest_v2 import (
    _json_sorted,
    load_s8_opportunity,
    load_scenario_mapping,
    stable_input_id,
)


def write_gzip_csv(path, rows):
    fields = list(rows[0])
    with gzip.open(path, "wt", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def opp_row(plan="P1", klass="ALL_PUBLIC_ROUTES_HAVE_SOME_COMPLETE_MATCH_PHASE"):
    return {
        "plan_id": plan,
        "scenario_id": "S1",
        "uniform_headway_min": "30",
        "span_id": "CORE_0600_2200",
        "s8_opportunity_class": klass,
        "s8_public_complete_match_route_count": "2",
        "s8_public_complete_match_route_share": "1.0",
        "s8_public_all_routes_have_some_complete_match_phase": "true",
        "s8_public_any_route_has_some_complete_match_phase": "true",
        "s8_roundtrip_best_complete_gap_min_min": "3.0",
        "s8_roundtrip_best_complete_gap_min_max": "5.0",
        "s8_roundtrip_worst_complete_gap_min_min": "10.0",
        "s8_roundtrip_worst_complete_gap_min_max": "12.0",
        "s8_rail_to_bus_only_best_complete_gap_min_min": "",
        "s8_rail_to_bus_only_best_complete_gap_min_max": "",
        "s8_rail_to_bus_only_worst_complete_gap_min_min": "",
        "s8_rail_to_bus_only_worst_complete_gap_min_max": "",
    }


def test_stage_d_input_id_is_deterministic_and_context_sensitive():
    a = stable_input_id("S1", 30, "CORE_0600_2200")
    b = stable_input_id("S1", 30, "CORE_0600_2200")
    c = stable_input_id("S1", 20, "CORE_0600_2200")
    d = stable_input_id("S2", 30, "CORE_0600_2200")
    assert a == b
    assert a != c
    assert a != d
    assert a.startswith("D4I2_")


def test_sorted_json_preserves_unique_context_members():
    assert _json_sorted(["reference", "m10pct", "reference"]) == '["m10pct","reference"]'
    assert _json_sorted([365, 260, 365]) == '[260,365]'


def test_s8_plan_duplicates_collapse_only_when_scenario_timing_evidence_is_identical(tmp_path):
    p = tmp_path / "opp.csv.gz"
    write_gzip_csv(p, [opp_row("P1"), opp_row("P2")])
    out = load_s8_opportunity(p)
    assert list(out) == [("S1", 30, "CORE_0600_2200")]


def test_s8_plan_duplicates_fail_closed_when_same_timing_key_disagrees(tmp_path):
    p = tmp_path / "opp.csv.gz"
    write_gzip_csv(p, [
        opp_row("P1"),
        opp_row("P2", "NO_PUBLIC_ROUTE_HAS_COMPLETE_MATCH_PHASE"),
    ])
    with pytest.raises(ValueError, match="differs within same scenario/timing key"):
        load_s8_opportunity(p)


def test_scenario_mapping_selects_only_requested_scenarios_without_cross_scenario_dedup(tmp_path):
    p = tmp_path / "mapping.csv.gz"
    rows = [
        {"scenario_id": "S1", "topology_family": "A", "public_route_ids_json": json.dumps(["R1", "R2"]), "extension_route_ids_json": "[]"},
        {"scenario_id": "S2", "topology_family": "B", "public_route_ids_json": json.dumps(["R1", "R2"]), "extension_route_ids_json": "[]"},
        {"scenario_id": "S3", "topology_family": "C", "public_route_ids_json": json.dumps(["R3"]), "extension_route_ids_json": "[]"},
    ]
    write_gzip_csv(p, rows)
    out = load_scenario_mapping(p, {"S1", "S2"})
    assert set(out) == {"S1", "S2"}
    assert out["S1"][1] == ["R1", "R2"]
    assert out["S2"][1] == ["R1", "R2"]
    assert out["S1"][0] != out["S2"][0]


def test_scenario_mapping_fails_if_requested_scenario_missing(tmp_path):
    p = tmp_path / "mapping.csv.gz"
    rows = [
        {"scenario_id": "S1", "topology_family": "A", "public_route_ids_json": json.dumps(["R1"]), "extension_route_ids_json": "[]"},
    ]
    write_gzip_csv(p, rows)
    with pytest.raises(ValueError, match="missing 1 Stage-D scenarios"):
        load_scenario_mapping(p, {"S1", "S2"})
