import csv
import gzip
from pathlib import Path

import pytest

from scripts.phase2_build_s8_robust_opportunity_surface_v2 import (
    PINNED_SOURCE_COMMIT,
    load_envelope_subset,
    strict_bool,
)


REQUIRED = [
    "scenario_id", "uniform_headway_min", "span_id", "public_route_count",
    "public_complete_match_route_count", "public_complete_match_route_share",
    "public_all_routes_have_some_complete_match_phase", "public_any_route_has_some_complete_match_phase",
    "public_roundtrip_route_count", "public_roundtrip_complete_match_route_count",
    "public_roundtrip_complete_match_route_share", "public_roundtrip_best_complete_gap_min_min",
    "public_roundtrip_best_complete_gap_min_max", "public_roundtrip_worst_complete_gap_min_min",
    "public_roundtrip_worst_complete_gap_min_max", "public_rail_to_bus_only_route_count",
    "public_rail_to_bus_only_complete_match_route_count", "public_rail_to_bus_only_complete_match_route_share",
    "public_rail_to_bus_only_best_complete_gap_min_min", "public_rail_to_bus_only_best_complete_gap_min_max",
    "public_rail_to_bus_only_worst_complete_gap_min_min", "public_rail_to_bus_only_worst_complete_gap_min_max",
    "worker_direction_weight_reference", "demand_weight_semantics", "route_weighting_applied",
    "worker_reference_assigned_to_routes", "cross_route_phase_selected", "passenger_utility_calculated",
    "full_gjt_calculated", "topology_ranked", "service_policy_selected",
]


def sample(**overrides):
    row = {field: "0" for field in REQUIRED}
    row.update({
        "scenario_id": "S1",
        "uniform_headway_min": "30",
        "span_id": "CORE_0600_2200",
        "public_route_count": "2",
        "public_complete_match_route_count": "2",
        "public_complete_match_route_share": "1.0",
        "public_all_routes_have_some_complete_match_phase": "true",
        "public_any_route_has_some_complete_match_phase": "true",
        "worker_direction_weight_reference": "1882.0",
        "demand_weight_semantics": "DIRECTION_WEIGHT_ONLY_NOT_ROUTE_DEMAND_NOT_MODAL_SHARE",
        "route_weighting_applied": "false",
        "worker_reference_assigned_to_routes": "false",
        "cross_route_phase_selected": "false",
        "passenger_utility_calculated": "false",
        "full_gjt_calculated": "false",
        "topology_ranked": "false",
        "service_policy_selected": "false",
    })
    row.update(overrides)
    return row


def write_gz(path: Path, rows):
    with gzip.open(path, "wt", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REQUIRED, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def test_pinned_commit_is_immutable_sha():
    assert len(PINNED_SOURCE_COMMIT) == 40
    int(PINNED_SOURCE_COMMIT, 16)


def test_strict_bool_is_fail_closed():
    assert strict_bool("true", field="x") is True
    assert strict_bool("false", field="x") is False
    with pytest.raises(ValueError):
        strict_bool("yes", field="x")


def test_subset_accepts_unweighted_unselected_evidence(tmp_path):
    path = tmp_path / "env.csv.gz"
    write_gz(path, [sample()])
    key = ("S1", 30, "CORE_0600_2200")
    out = load_envelope_subset(path, {key})
    assert set(out) == {key}


def test_subset_rejects_route_weighting_or_phase_selection(tmp_path):
    for field in ("route_weighting_applied", "worker_reference_assigned_to_routes", "cross_route_phase_selected"):
        path = tmp_path / f"{field}.csv.gz"
        write_gz(path, [sample(**{field: "true"})])
        with pytest.raises(ValueError):
            load_envelope_subset(path, {("S1", 30, "CORE_0600_2200")})


def test_subset_rejects_missing_stage_c_key(tmp_path):
    path = tmp_path / "env.csv.gz"
    write_gz(path, [sample()])
    with pytest.raises(ValueError):
        load_envelope_subset(path, {("S2", 30, "CORE_0600_2200")})
