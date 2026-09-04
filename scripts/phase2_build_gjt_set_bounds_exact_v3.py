#!/usr/bin/env python3
"""Materialise exact fine-origin feeder-to-S8 set-identification bounds.

The output closes only the fine-origin spatial-identification gap. It does NOT
estimate expected daily passenger GJT because no empirical departure-time
weights exist. Municipal OD is never downscaled. Every population unit is an
unweighted admissible spatial state and the output reports extrema, not means.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import math
from pathlib import Path
from typing import Mapping, Sequence

from scripts.phase2_build_feeder_generalized_access_v2 import (
    build_anchor_walks,
    load_anchor_members,
    load_population,
    load_runtime_subset,
    load_walk_maps,
)
from src.phase2_gjt_set_bounds_exact_v3 import (
    HUB_ANCHOR,
    RAIL_DIRECTIONS,
    ItineraryWitness,
    RailDeparture,
    SensitivityCase,
    build_public_to_hub_occurrences,
    bus_generalized_cost,
    direct_walk_generalized_cost,
    first_feasible_rail_departure,
    reduced_sensitivity_cases,
    strict_bool,
)

STATUS = "PASS_PHASE2_EXACT_FEEDER_S8_SET_BOUNDS_V3"
CONTRACT = "PHASE2_EXACT_FEEDER_S8_SET_IDENTIFICATION_BOUNDS_V3"
EPS = 1e-9


def sha256_path(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv(path: Path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        yield from csv.DictReader(f)


def read_gzip_csv(path: Path):
    with gzip.open(path, "rt", encoding="utf-8-sig", newline="") as f:
        yield from csv.DictReader(f)


def deterministic_gzip_writer(path: Path, fields: Sequence[str]):
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = path.open("wb")
    gz = gzip.GzipFile(filename="", mode="wb", fileobj=raw, compresslevel=9, mtime=0)
    text = io.TextIOWrapper(gz, encoding="utf-8", newline="")
    writer = csv.DictWriter(text, fieldnames=list(fields), lineterminator="\n")
    writer.writeheader()
    return raw, text, writer


def validate_lineage(args) -> tuple[dict, dict, dict, dict]:
    stage_d = read_json(args.stage_d_validation)
    if stage_d.get("status") != "PASS_PHASE2_STAGE_D_EXACT_TIMETABLE_RT001_V3":
        raise ValueError("Stage D V3 is not certified")
    if stage_d.get("contract") != "PHASE2_BUDGET_LOSSLESS_EXHAUSTIVE_EXACT_CLOCKFACE_TIMETABLE_RT001_V3":
        raise ValueError("Unexpected Stage D V3 contract")
    if stage_d.get("technical_vehicle_closure_used_as_passenger_return") is not False:
        raise ValueError("Stage D permits technical closure as passenger return")
    if stage_d.get("passenger_return_events_restricted_to_declared_service_span") is not True:
        raise ValueError("Stage D passenger span semantics changed")
    if stage_d.get("passenger_weighting_applied") is not False or stage_d.get("worker_reference_used_for_phase_selection") is not False:
        raise ValueError("Stage D unexpectedly uses passenger/worker weighting")
    stage_hashes = {
        "timetable_output_sha256": sha256_path(args.stage_d_timetables),
        "trip_output_sha256": sha256_path(args.stage_d_trips),
        "route_inputs_sha256": sha256_path(args.route_input),
        "s8_events_sha256": sha256_path(args.s8_events),
        "path_matrix_sha256": sha256_path(args.path_matrix),
    }
    for key, actual in stage_hashes.items():
        if stage_d.get("lineage", {}).get(key) != actual:
            raise ValueError(f"Stage D lineage mismatch for {key}")

    feeder = read_json(args.feeder_validation)
    if feeder.get("status") != "PASS_FEEDER_GENERALIZED_ACCESS_V2_BUILD" or feeder.get("contract") != "PHASE2_PRE_PHASE_FEEDER_GENERALIZED_ACCESS_V2":
        raise ValueError("Feeder GFA V2 is not certified")
    for flag in ("municipal_work_od_downscaled", "resident_population_is_passenger_demand", "full_gjt_calculated"):
        if feeder.get(flag) is not False:
            raise ValueError(f"Feeder semantic boundary changed: {flag}")
    feeder_hashes = {
        "access_validation_sha256": sha256_path(args.access_validation),
        "population_units_sha256": sha256_path(args.population_units),
        "anchors_sha256": sha256_path(args.anchors),
        "proposed_catchments_sha256": sha256_path(args.proposed_catchments),
        "existing_catchments_sha256": sha256_path(args.existing_catchments),
        "path_matrix_sha256": sha256_path(args.path_matrix),
        "sensitivity_config_sha256": sha256_path(args.sensitivity_config),
    }
    for key, actual in feeder_hashes.items():
        if feeder.get("lineage", {}).get(key) != actual:
            raise ValueError(f"Feeder lineage mismatch for {key}")

    access = read_json(args.access_validation)
    if access.get("status") != "PASS_ACCESS_EQUITY_V2_BUILD" or access.get("contract") != "PHASE2_BUILDING_CATCHMENT_ACCESS_EQUITY_V2":
        raise ValueError("Access Equity V2 is not certified")
    bridge = access.get("hub_access_bridge", {})
    if bridge.get("status") != "VERIFIED_APPLIED" or bridge.get("rail_anchor_id") != HUB_ANCHOR:
        raise ValueError("Verified rail-hub pedestrian bridge unavailable")
    if bridge.get("bridge_type") != "PEDESTRIAN_ACCESS_ONLY":
        raise ValueError("Hub bridge semantics changed")

    sensitivity = read_json(args.sensitivity_config)
    if sensitivity.get("contract") != "PHASE2_FEEDER_GENERALIZED_ACCESS_SENSITIVITY_V2":
        raise ValueError("Unexpected feeder sensitivity contract")
    if sensitivity.get("status") != "ASSUMPTION_SENSITIVITY_NOT_EMPIRICAL_INTERVAL":
        raise ValueError("Sensitivity grid lost assumption semantics")
    if int(sensitivity.get("expected_full_factorial_case_count", -1)) != 243:
        raise ValueError("Expected certified 243-case sensitivity grid")
    return stage_d, feeder, access, sensitivity


def load_timetables(path: Path, expected_count: int) -> list[dict[str, object]]:
    rows = []
    seen = set()
    required = {
        "selected_timetable_id", "scenario_id", "topology_family", "uniform_headway_min",
        "span_id", "span_start_min", "span_end_min", "public_route_ids_json",
    }
    for row in read_csv(path):
        if not required <= set(row):
            raise ValueError("Stage D timetable schema mismatch")
        tid = str(row["selected_timetable_id"])
        if tid in seen:
            raise ValueError(f"Duplicate selected timetable {tid}")
        seen.add(tid)
        route_ids = json.loads(row["public_route_ids_json"])
        if not isinstance(route_ids, list) or not route_ids:
            raise ValueError(f"Invalid public route list for {tid}")
        rows.append({
            "selected_timetable_id": tid,
            "scenario_id": str(row["scenario_id"]),
            "topology_family": str(row["topology_family"]),
            "uniform_headway_min": int(row["uniform_headway_min"]),
            "span_id": str(row["span_id"]),
            "span_start_min": int(row["span_start_min"]),
            "span_end_min": int(row["span_end_min"]),
            "route_ids": tuple(str(v) for v in route_ids),
        })
    if len(rows) != expected_count:
        raise ValueError(f"Unexpected timetable count {len(rows)} != {expected_count}")
    return sorted(rows, key=lambda r: str(r["selected_timetable_id"]))


def load_trip_departures(path: Path, wanted_timetables: set[str], expected_count: int):
    out: dict[str, dict[str, list[float]]] = {}
    count = 0
    for row in read_gzip_csv(path):
        count += 1
        tid = str(row["selected_timetable_id"])
        if tid not in wanted_timetables:
            raise ValueError(f"Trip references unknown timetable {tid}")
        rid = str(row["route_id"])
        dep = float(row["departure_min"])
        if not math.isfinite(dep):
            raise ValueError("Non-finite exact trip departure")
        out.setdefault(tid, {}).setdefault(rid, []).append(dep)
    if count != expected_count:
        raise ValueError(f"Unexpected Stage D trip count {count} != {expected_count}")
    if set(out) != wanted_timetables:
        raise ValueError("At least one selected timetable has no exact trips")
    for by_route in out.values():
        for values in by_route.values():
            values.sort()
    return out


def load_route_inputs(path: Path, wanted_routes: set[str]):
    routes = {}
    for row in read_csv(path):
        rid = str(row["route_id"])
        if rid not in wanted_routes:
            continue
        if rid in routes:
            raise ValueError(f"Duplicate route input {rid}")
        anchors = tuple(str(v) for v in json.loads(row["anchors_json"]))
        if not anchors or anchors[0] != HUB_ANCHOR:
            raise ValueError(f"Route {rid} does not start at rail hub")
        starts = strict_bool(row["public_service_starts_at_hub"])
        returns = strict_bool(row["public_service_returns_to_hub"])
        closure = strict_bool(row["vehicle_closure_added"])
        b2r = strict_bool(row["bus_to_rail_passenger_event_supported"])
        if not starts or b2r != returns or closure == returns:
            raise ValueError(f"Passenger-return semantics inconsistent for {rid}")
        routes[rid] = {
            "anchors": anchors,
            "bus_to_rail_supported": b2r,
        }
    if set(routes) != wanted_routes:
        raise ValueError(f"Missing route inputs: {len(wanted_routes-set(routes))}")
    return routes


def load_rail_departures(path: Path):
    out: dict[str, list[RailDeparture]] = {d: [] for d in RAIL_DIRECTIONS}
    for row in read_csv(path):
        direction = str(row["direction"]).upper()
        if direction not in out:
            raise ValueError(f"Unexpected S8 direction {direction}")
        dep = RailDeparture(
            event_id=str(row["event_id"]),
            direction=direction,
            departure_min=float(row["departure_min"]),
        )
        dep.validate()
        out[direction].append(dep)
    for direction in out:
        out[direction].sort(key=lambda r: (r.departure_min, r.event_id))
        if len(out[direction]) != 37:
            raise ValueError(f"Expected 37 S8 events for {direction}, got {len(out[direction])}")
    return {k: tuple(v) for k, v in out.items()}


def build_anchor_components(
    *,
    timetable_route_departures: Mapping[str, Sequence[float]],
    route_occurrences: Mapping[str, Sequence],
    rail_departures: Mapping[str, Sequence[RailDeparture]],
    case: SensitivityCase,
    direction: str,
):
    """Best exact conditional feeder component for each public boarding anchor."""
    best: dict[str, dict[str, object]] = {}
    for rid, departures in timetable_route_departures.items():
        for occ in route_occurrences.get(rid, ()):
            for trip_departure in departures:
                bus_hub_arrival = float(trip_departure) + occ.next_public_hub_cumulative_min
                rail = first_feasible_rail_departure(
                    rail_departures[direction],
                    bus_hub_arrival_min=bus_hub_arrival,
                    station_transfer_walk_min=case.station_transfer_walk_min,
                )
                if rail is None:
                    continue
                component_cost, wait = bus_generalized_cost(
                    access_walk_min=0.0,
                    bus_ivt_min=occ.bus_ivt_to_hub_min,
                    bus_hub_arrival_min=bus_hub_arrival,
                    rail_departure_min=rail.departure_min,
                    case=case,
                )
                # access_walk=0 here; actual fine-origin access walk is added later.
                anchor = occ.anchor_id
                candidate = {
                    "base_cost": component_cost,
                    "route_id": rid,
                    "trip_departure_min": float(trip_departure),
                    "bus_hub_arrival_min": bus_hub_arrival,
                    "rail_event_id": rail.event_id,
                    "rail_departure_min": rail.departure_min,
                    "bus_ivt_min": occ.bus_ivt_to_hub_min,
                    "exact_transfer_wait_min": wait,
                }
                previous = best.get(anchor)
                key = (
                    component_cost,
                    rid,
                    float(trip_departure),
                    rail.departure_min,
                    rail.event_id,
                )
                if previous is None or key < previous["key"]:
                    candidate["key"] = key
                    best[anchor] = candidate
    return best


def unit_costs_for_case(
    *,
    unit_count: int,
    direct_hub_walks: Mapping[int, float],
    anchor_walks: Mapping[str, Mapping[int, float]],
    anchor_components: Mapping[str, Mapping[str, object]],
    case: SensitivityCase,
) -> list[float]:
    costs = [math.inf] * unit_count
    for idx, walk in direct_hub_walks.items():
        costs[idx] = direct_walk_generalized_cost(hub_walk_min=float(walk), case=case)
    for anchor, component in anchor_components.items():
        base = float(component["base_cost"])
        for idx, walk in anchor_walks.get(anchor, {}).items():
            value = base + case.walk_weight * float(walk)
            if value < costs[idx]:
                costs[idx] = value
    return costs


def unit_witness(
    *,
    unit_idx: int,
    direct_hub_walks: Mapping[int, float],
    anchor_walks: Mapping[str, Mapping[int, float]],
    anchor_components: Mapping[str, Mapping[str, object]],
    case: SensitivityCase,
) -> ItineraryWitness | None:
    best: tuple | None = None
    witness: ItineraryWitness | None = None
    if unit_idx in direct_hub_walks:
        walk = float(direct_hub_walks[unit_idx])
        cost = direct_walk_generalized_cost(hub_walk_min=walk, case=case)
        best = (cost, "DIRECT_WALK", "", "")
        witness = ItineraryWitness(
            mode="DIRECT_WALK",
            cost=cost,
            access_walk_min=walk,
            sensitivity_case_id=case.case_id,
        )
    for anchor, component in anchor_components.items():
        walk = anchor_walks.get(anchor, {}).get(unit_idx)
        if walk is None:
            continue
        cost = float(component["base_cost"]) + case.walk_weight * float(walk)
        key = (cost, "BUS_TO_RAIL", str(component["route_id"]), anchor)
        if best is None or key < best:
            best = key
            witness = ItineraryWitness(
                mode="BUS_TO_RAIL",
                cost=cost,
                anchor_id=anchor,
                route_id=str(component["route_id"]),
                trip_departure_min=float(component["trip_departure_min"]),
                bus_hub_arrival_min=float(component["bus_hub_arrival_min"]),
                rail_event_id=str(component["rail_event_id"]),
                rail_departure_min=float(component["rail_departure_min"]),
                access_walk_min=float(walk),
                bus_ivt_min=float(component["bus_ivt_min"]),
                station_transfer_walk_min=case.station_transfer_walk_min,
                exact_transfer_wait_min=float(component["exact_transfer_wait_min"]),
                sensitivity_case_id=case.case_id,
            )
    return witness


def fmt(value: float | None, digits: int = 9) -> str:
    return "" if value is None else f"{value:.{digits}f}"


def witness_fields(prefix: str, witness: ItineraryWitness | None) -> dict[str, object]:
    if witness is None:
        return {
            f"{prefix}_mode": "", f"{prefix}_anchor_id": "", f"{prefix}_route_id": "",
            f"{prefix}_trip_departure_min": "", f"{prefix}_bus_hub_arrival_min": "",
            f"{prefix}_rail_event_id": "", f"{prefix}_rail_departure_min": "",
            f"{prefix}_access_walk_min": "", f"{prefix}_bus_ivt_min": "",
            f"{prefix}_station_transfer_walk_min": "", f"{prefix}_exact_transfer_wait_min": "",
            f"{prefix}_sensitivity_case_id": "",
        }
    return {
        f"{prefix}_mode": witness.mode,
        f"{prefix}_anchor_id": witness.anchor_id,
        f"{prefix}_route_id": witness.route_id,
        f"{prefix}_trip_departure_min": fmt(witness.trip_departure_min),
        f"{prefix}_bus_hub_arrival_min": fmt(witness.bus_hub_arrival_min),
        f"{prefix}_rail_event_id": witness.rail_event_id,
        f"{prefix}_rail_departure_min": fmt(witness.rail_departure_min),
        f"{prefix}_access_walk_min": fmt(witness.access_walk_min),
        f"{prefix}_bus_ivt_min": fmt(witness.bus_ivt_min),
        f"{prefix}_station_transfer_walk_min": fmt(witness.station_transfer_walk_min),
        f"{prefix}_exact_transfer_wait_min": fmt(witness.exact_transfer_wait_min),
        f"{prefix}_sensitivity_case_id": witness.sensitivity_case_id,
    }


def main() -> int:
    p = argparse.ArgumentParser()
    for name in (
        "stage_d_validation", "stage_d_timetables", "stage_d_trips", "route_input", "s8_events",
        "feeder_validation", "access_validation", "population_units", "anchors", "proposed_catchments",
        "existing_catchments", "path_matrix", "sensitivity_config", "output", "validation_output",
    ):
        p.add_argument("--" + name.replace("_", "-"), dest=name, type=Path, required=True)
    args = p.parse_args()
    for name, path in vars(args).items():
        if name in {"output", "validation_output"}:
            continue
        if not path.is_file():
            raise FileNotFoundError(path)

    stage_d, feeder, access, sensitivity = validate_lineage(args)
    reduced_cases = reduced_sensitivity_cases(sensitivity["parameter_grid"])
    if len(reduced_cases) != 6:
        raise ValueError(f"Expected exact six-case reduction, got {len(reduced_cases)}")

    timetable_count = int(stage_d["unique_selected_exact_timetable_count"])
    timetables = load_timetables(args.stage_d_timetables, timetable_count)
    timetable_ids = {str(r["selected_timetable_id"]) for r in timetables}
    trips = load_trip_departures(
        args.stage_d_trips,
        timetable_ids,
        int(stage_d["selected_exact_trip_row_count"]),
    )
    wanted_routes = {rid for row in timetables for rid in row["route_ids"]}
    routes = load_route_inputs(args.route_input, wanted_routes)
    required_legs = {
        (a, b)
        for route in routes.values()
        for a, b in zip(route["anchors"][:-1], route["anchors"][1:])
    }
    runtime = load_runtime_subset(args.path_matrix, required_legs)
    route_occurrences = {
        rid: build_public_to_hub_occurrences(
            route["anchors"], runtime,
            bus_to_rail_passenger_event_supported=bool(route["bus_to_rail_supported"]),
        )
        for rid, route in routes.items()
    }
    wanted_anchors = {occ.anchor_id for values in route_occurrences.values() for occ in values}

    unit_ids, population_weights, municipalities, municipality_codes, unit_index = load_population(args.population_units)
    if len(unit_ids) != int(access["population_unit_count"]):
        raise ValueError("Population-unit count mismatch")
    # Population values are loaded only to verify certified catchment lineage.
    # They are never used as demand weights or worker-location capacities here.
    anchor_members, wanted_proposed, wanted_existing = load_anchor_members(args.anchors, wanted_anchors)
    hub_cluster = str(access["hub_access_bridge"]["physical_cluster_id"])
    proposed_walks, existing_walks = load_walk_maps(
        args.proposed_catchments,
        args.existing_catchments,
        wanted_proposed=wanted_proposed,
        wanted_existing=wanted_existing,
        hub_cluster_id=hub_cluster,
        unit_index=unit_index,
        weights=population_weights,
    )
    anchor_walks_raw = build_anchor_walks(anchor_members, proposed_walks, existing_walks)
    anchor_walks = {a: dict(v) for a, v in anchor_walks_raw.items()}
    direct_hub_walks = dict(existing_walks[hub_cluster])
    rail_departures = load_rail_departures(args.s8_events)

    muni_indices: dict[str, list[int]] = {}
    muni_code_by_name: dict[str, str] = {}
    for i, muni in enumerate(municipalities):
        muni_indices.setdefault(muni, []).append(i)
        muni_code_by_name[muni] = municipality_codes[muni]
    if len(muni_indices) != 5:
        raise ValueError(f"Expected five core municipalities, got {sorted(muni_indices)}")

    fields = [
        "selected_timetable_id", "scenario_id", "topology_family", "uniform_headway_min", "span_id",
        "origin_municipality_code", "origin_municipality", "rail_direction", "admissible_origin_unit_count",
        "full_grid_lower_conditional_cost_min", "full_grid_upper_conditional_cost_min", "upper_bound_unbounded",
        "unreachable_admissible_state_count", "lower_witness_population_unit_id", "upper_witness_population_unit_id",
        "unbounded_witness_population_unit_id", "unbounded_witness_sensitivity_case_id",
        "lower_mode", "lower_anchor_id", "lower_route_id", "lower_trip_departure_min", "lower_bus_hub_arrival_min",
        "lower_rail_event_id", "lower_rail_departure_min", "lower_access_walk_min", "lower_bus_ivt_min",
        "lower_station_transfer_walk_min", "lower_exact_transfer_wait_min", "lower_sensitivity_case_id",
        "upper_mode", "upper_anchor_id", "upper_route_id", "upper_trip_departure_min", "upper_bus_hub_arrival_min",
        "upper_rail_event_id", "upper_rail_departure_min", "upper_access_walk_min", "upper_bus_ivt_min",
        "upper_station_transfer_walk_min", "upper_exact_transfer_wait_min", "upper_sensitivity_case_id",
        "cost_semantics", "origin_bus_wait_imputed", "expected_daily_gjt_identified", "municipal_od_downscaled",
        "resident_population_used_as_demand", "rail_direction_inferred_from_destination", "ranking_or_pruning_authorized",
    ]
    raw, text, writer = deterministic_gzip_writer(args.output, fields)
    row_count = 0
    finite_upper_rows = 0
    unbounded_upper_rows = 0
    rows_with_no_finite_lower = 0
    timetable_with_no_public_bus_to_rail = 0
    direct_option_used_as_lower_witness = 0
    bus_option_used_as_lower_witness = 0
    try:
        for timetable in timetables:
            tid = str(timetable["selected_timetable_id"])
            by_route = trips[tid]
            if set(by_route) != set(timetable["route_ids"]):
                raise ValueError(f"Trip route set mismatch for {tid}")
            if all(not route_occurrences[rid] for rid in timetable["route_ids"]):
                timetable_with_no_public_bus_to_rail += 1
            for direction in RAIL_DIRECTIONS:
                case_costs: dict[str, list[float]] = {}
                case_components: dict[str, dict[str, dict[str, object]]] = {}
                for case in reduced_cases:
                    components = build_anchor_components(
                        timetable_route_departures=by_route,
                        route_occurrences=route_occurrences,
                        rail_departures=rail_departures,
                        case=case,
                        direction=direction,
                    )
                    case_components[case.case_id] = components
                    case_costs[case.case_id] = unit_costs_for_case(
                        unit_count=len(unit_ids),
                        direct_hub_walks=direct_hub_walks,
                        anchor_walks=anchor_walks,
                        anchor_components=components,
                        case=case,
                    )

                for muni in sorted(muni_indices, key=lambda m: (muni_code_by_name[m], m)):
                    indices = muni_indices[muni]
                    lower_key = None
                    lower_case = None
                    lower_idx = None
                    upper_key = None
                    upper_case = None
                    upper_idx = None
                    unbounded_witness = None
                    unreachable_states = 0
                    for case in reduced_cases:
                        values = case_costs[case.case_id]
                        if case.bound_side == "LOW":
                            for idx in indices:
                                value = values[idx]
                                if math.isfinite(value):
                                    key = (value, unit_ids[idx], case.case_id)
                                    if lower_key is None or key < lower_key:
                                        lower_key, lower_case, lower_idx = key, case, idx
                        else:
                            for idx in indices:
                                value = values[idx]
                                if not math.isfinite(value):
                                    unreachable_states += 1
                                    candidate = (unit_ids[idx], case.case_id, idx, case)
                                    if unbounded_witness is None or candidate[:2] < unbounded_witness[:2]:
                                        unbounded_witness = candidate
                                    continue
                                key = (value, unit_ids[idx], case.case_id)
                                if upper_key is None or key > upper_key:
                                    upper_key, upper_case, upper_idx = key, case, idx
                    lower_value = None if lower_key is None else float(lower_key[0])
                    upper_unbounded = unbounded_witness is not None
                    upper_value = None if upper_unbounded or upper_key is None else float(upper_key[0])
                    if lower_value is None:
                        rows_with_no_finite_lower += 1
                    if upper_unbounded:
                        unbounded_upper_rows += 1
                    else:
                        finite_upper_rows += 1

                    lower_w = None
                    if lower_case is not None and lower_idx is not None:
                        lower_w = unit_witness(
                            unit_idx=lower_idx,
                            direct_hub_walks=direct_hub_walks,
                            anchor_walks=anchor_walks,
                            anchor_components=case_components[lower_case.case_id],
                            case=lower_case,
                        )
                        if lower_w is None or not math.isclose(lower_w.cost, lower_value, rel_tol=0.0, abs_tol=1e-8):
                            raise AssertionError("Lower witness reconstruction mismatch")
                        if lower_w.mode == "DIRECT_WALK":
                            direct_option_used_as_lower_witness += 1
                        else:
                            bus_option_used_as_lower_witness += 1
                    upper_w = None
                    if upper_case is not None and upper_idx is not None and not upper_unbounded:
                        upper_w = unit_witness(
                            unit_idx=upper_idx,
                            direct_hub_walks=direct_hub_walks,
                            anchor_walks=anchor_walks,
                            anchor_components=case_components[upper_case.case_id],
                            case=upper_case,
                        )
                        if upper_w is None or not math.isclose(upper_w.cost, upper_value, rel_tol=0.0, abs_tol=1e-8):
                            raise AssertionError("Upper witness reconstruction mismatch")

                    row = {
                        "selected_timetable_id": tid,
                        "scenario_id": timetable["scenario_id"],
                        "topology_family": timetable["topology_family"],
                        "uniform_headway_min": timetable["uniform_headway_min"],
                        "span_id": timetable["span_id"],
                        "origin_municipality_code": muni_code_by_name[muni],
                        "origin_municipality": muni,
                        "rail_direction": direction,
                        "admissible_origin_unit_count": len(indices),
                        "full_grid_lower_conditional_cost_min": fmt(lower_value),
                        "full_grid_upper_conditional_cost_min": fmt(upper_value),
                        "upper_bound_unbounded": str(upper_unbounded).lower(),
                        "unreachable_admissible_state_count": unreachable_states,
                        "lower_witness_population_unit_id": "" if lower_idx is None else unit_ids[lower_idx],
                        "upper_witness_population_unit_id": "" if upper_idx is None or upper_unbounded else unit_ids[upper_idx],
                        "unbounded_witness_population_unit_id": "" if unbounded_witness is None else unbounded_witness[0],
                        "unbounded_witness_sensitivity_case_id": "" if unbounded_witness is None else unbounded_witness[1],
                        "cost_semantics": "BEST_EXACT_SCHEDULE_COMPATIBLE_FEEDER_TO_S8_OR_CERTIFIED_DIRECT_RAIL_WALK_CONDITIONAL_ON_DEPARTURE_OPPORTUNITY",
                        "origin_bus_wait_imputed": "false",
                        "expected_daily_gjt_identified": "false",
                        "municipal_od_downscaled": "false",
                        "resident_population_used_as_demand": "false",
                        "rail_direction_inferred_from_destination": "false",
                        "ranking_or_pruning_authorized": "false",
                    }
                    row.update(witness_fields("lower", lower_w))
                    row.update(witness_fields("upper", upper_w))
                    writer.writerow(row)
                    row_count += 1
    finally:
        text.close()
        raw.close()

    expected_rows = timetable_count * len(muni_indices) * len(RAIL_DIRECTIONS)
    if row_count != expected_rows:
        raise AssertionError(f"Output row count mismatch {row_count} != {expected_rows}")

    validation = {
        "status": STATUS,
        "contract": CONTRACT,
        "selected_exact_timetable_count": timetable_count,
        "selected_exact_trip_count": int(stage_d["selected_exact_trip_row_count"]),
        "population_unit_count": len(unit_ids),
        "municipality_count": len(muni_indices),
        "rail_directions": list(RAIL_DIRECTIONS),
        "output_row_count": row_count,
        "full_factorial_sensitivity_case_count": 243,
        "evaluated_reduced_sensitivity_case_count": len(reduced_cases),
        "parameter_reduction_exact": True,
        "parameter_reduction_semantics": "ENUMERATE_ALL_STATION_TRANSFER_WALK_VALUES_AND_USE_MONOTONE_ALL_LOW_ALL_HIGH_CORNERS_FOR_THE_OTHER_FOUR_NONNEGATIVE_GENERALIZED_COST_COEFFICIENTS",
        "station_transfer_walk_values": sorted({c.station_transfer_walk_min for c in reduced_cases}),
        "reduced_case_ids": [c.case_id for c in reduced_cases],
        "fine_origin_set_identification_materialized": True,
        "fine_origin_point_assignment_performed": False,
        "municipal_od_consumed": False,
        "municipal_od_downscaled": False,
        "worker_locations_imputed": False,
        "resident_population_used_as_passenger_demand": False,
        "resident_population_used_as_worker_location_capacity": False,
        "population_values_used_only_for_certified_catchment_integrity": True,
        "rail_direction_conditioned_not_destination_inferred": True,
        "rail_direction_inferred_from_destination": False,
        "exact_stage_d_trip_times_used": True,
        "exact_s8_departure_times_used": True,
        "next_explicit_public_hub_occurrence_only": True,
        "technical_vehicle_closure_used_as_passenger_return": False,
        "direct_station_access_option": "CERTIFIED_EX_039_PEDESTRIAN_CATCHMENT_INHERITED_BY_RAIL_S01514",
        "origin_bus_wait_imputed": False,
        "half_headway_wait_used": False,
        "departure_time_distribution_used": False,
        "best_available_departure_opportunity_used": True,
        "expected_daily_gjt_identified": False,
        "full_point_demand_weighted_gjt_identified": False,
        "full_point_gjt_improvement_vs_current_identified": False,
        "empirical_missed_connection_probability_identified": False,
        "conditional_cost_is_full_gjt": False,
        "finite_upper_bound_row_count": finite_upper_rows,
        "unbounded_upper_bound_row_count": unbounded_upper_rows,
        "row_with_no_finite_lower_bound_count": rows_with_no_finite_lower,
        "timetable_with_no_public_bus_to_rail_route_count": timetable_with_no_public_bus_to_rail,
        "direct_option_lower_witness_count": direct_option_used_as_lower_witness,
        "bus_option_lower_witness_count": bus_option_used_as_lower_witness,
        "ranking_or_pruning_authorized": False,
        "weighted_composite_score": False,
        "decision_budget_selected": False,
        "uncertainty_band_selected": False,
        "primary_selected": False,
        "runner_up_selected": False,
        "remaining_identifiability_blockers": [
            "EMPIRICAL_OR_POLICY_DECLARED_DEPARTURE_TIME_DISTRIBUTION_FOR_EXPECTED_DAILY_GJT",
            "CERTIFIED_DESTINATION_TO_RAIL_DIRECTION_MAPPING_BEFORE_OD_WEIGHTED_AGGREGATION",
            "COMPLETE_COMPARABLE_CURRENT_SERVICE_GJT_FOR_TRUE_IMPROVEMENT_METRIC",
            "EMPIRICAL_DELAY_DISTRIBUTION_IF_PROBABILISTIC_RELIABILITY_IS_REQUIRED",
        ],
        "lineage": {
            "stage_d_validation_sha256": sha256_path(args.stage_d_validation),
            "stage_d_timetables_sha256": sha256_path(args.stage_d_timetables),
            "stage_d_trips_sha256": sha256_path(args.stage_d_trips),
            "route_input_sha256": sha256_path(args.route_input),
            "s8_events_sha256": sha256_path(args.s8_events),
            "feeder_validation_sha256": sha256_path(args.feeder_validation),
            "access_validation_sha256": sha256_path(args.access_validation),
            "population_units_sha256": sha256_path(args.population_units),
            "anchors_sha256": sha256_path(args.anchors),
            "proposed_catchments_sha256": sha256_path(args.proposed_catchments),
            "existing_catchments_sha256": sha256_path(args.existing_catchments),
            "path_matrix_sha256": sha256_path(args.path_matrix),
            "sensitivity_config_sha256": sha256_path(args.sensitivity_config),
            "output_sha256": sha256_path(args.output),
        },
        "decision_boundary": "SET_IDENTIFICATION_EVIDENCE_ONLY_NO_RANKING_PRUNING_PRIMARY_OR_RUNNER_UP",
    }
    args.validation_output.parent.mkdir(parents=True, exist_ok=True)
    args.validation_output.write_text(json.dumps(validation, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(validation, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
