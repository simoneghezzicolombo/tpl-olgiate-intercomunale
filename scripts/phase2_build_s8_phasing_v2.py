#!/usr/bin/env python3
"""Materialise the Phase 2 V2 S8 clock-phase opportunity envelope.

Every integer-minute phase in each declared headway/span timing archetype is
evaluated, but none is selected or discarded. Vehicle-cycle hub returns are
kept distinct from passenger-service returns: an operational closure added to
an open public route can support fleet feasibility but is never silently
relabelled as a BUS_TO_RAIL passenger event.
"""
from __future__ import annotations

import argparse
import csv
from decimal import Decimal
import gzip
import io
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.phase2_screen_structural_catalog import parse_routes, sha256_path
from src.phase2_s8_phasing_v2 import (
    RailEvent,
    Span,
    phase_raw_gap_metrics,
    runtime_archetype_id,
    stable_route_id,
)


D = Decimal
HUB_ANCHOR = "rail:S01514"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def deterministic_gzip_text(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = path.open("wb")
    gz = gzip.GzipFile(filename="", mode="wb", fileobj=raw, compresslevel=9, mtime=0)
    text = io.TextIOWrapper(gz, encoding="utf-8", newline="")
    return raw, text


def load_matrix_runtime(path: Path) -> dict[tuple[str, str], Decimal]:
    result: dict[tuple[str, str], Decimal] = {}
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"origin", "destination", "runtime_min"}
        if not required <= set(reader.fieldnames or []):
            raise ValueError("Reduced path matrix missing runtime fields")
        for line_no, row in enumerate(reader, start=2):
            key = (str(row["origin"]).strip(), str(row["destination"]).strip())
            if key in result:
                raise ValueError(f"Duplicate matrix runtime leg at line {line_no}: {key}")
            runtime = D(str(row["runtime_min"]).strip())
            if runtime <= 0:
                raise ValueError(f"Non-positive runtime at line {line_no}")
            result[key] = runtime
    if not result:
        raise ValueError("Reduced path matrix contains no runtimes")
    return result


def route_runtime_components(
    anchors: tuple[str, ...], runtime: dict[tuple[str, str], Decimal]
) -> tuple[Decimal, Decimal, bool]:
    """Return public runtime, closed vehicle-cycle runtime and closure flag."""
    if len(anchors) < 2:
        raise ValueError("Route requires at least two anchors")
    public_total = D("0")
    for a, b in zip(anchors[:-1], anchors[1:]):
        try:
            public_total += runtime[(a, b)]
        except KeyError as exc:
            raise ValueError(f"Route references missing matrix leg {a}->{b}") from exc
    closure_added = anchors[0] != anchors[-1]
    cycle_total = public_total
    if closure_added:
        try:
            cycle_total += runtime[(anchors[-1], anchors[0])]
        except KeyError as exc:
            raise ValueError(f"Open route lacks certified vehicle return closure {anchors[-1]}->{anchors[0]}") from exc
    if public_total <= 0 or cycle_total <= 0:
        raise ValueError("Route runtimes must be positive")
    return public_total, cycle_total, closure_added


def load_rail_events(path: Path) -> list[RailEvent]:
    rows: list[RailEvent] = []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"trip_id", "direction", "arrival_min", "departure_min", "epistemic_status"}
        if not required <= set(reader.fieldnames or []):
            raise ValueError("S8 event file has invalid schema")
        for row in reader:
            if str(row["epistemic_status"]) != "DERIVED_FROM_LIVE_OFFICIAL_GTFS":
                raise ValueError("S8 event lost official-GTFS epistemic status")
            event = RailEvent(
                trip_id=str(row["trip_id"]),
                direction=str(row["direction"]).upper(),
                arrival_min=D(str(row["arrival_min"])),
                departure_min=D(str(row["departure_min"])),
            )
            event.validate()
            rows.append(event)
    if len(rows) != 74:
        raise ValueError(f"Expected 74 frozen S8 events, got {len(rows)}")
    if sum(e.direction == "MILANO" for e in rows) != 37 or sum(e.direction == "LECCO" for e in rows) != 37:
        raise ValueError("Expected 37 S8 events per direction")
    return rows


def validate_upstream(
    *,
    catalog_path: Path,
    catalog_validation_path: Path,
    matrix_path: Path,
    matrix_validation_path: Path,
    policy_grid_path: Path,
    policy_validation_path: Path,
    s8_events_path: Path,
    s8_contract_path: Path,
    phasing_config_path: Path,
) -> tuple[dict, dict, dict, dict]:
    catalog = load_json(catalog_validation_path)
    matrix = load_json(matrix_validation_path)
    policy = load_json(policy_validation_path)
    s8 = load_json(s8_contract_path)
    config = load_json(phasing_config_path)
    if catalog.get("status") != "PASS_STRUCTURAL_CATALOG_V2_BUILD" or catalog.get("contract") != "PHASE2_BALANCED_STRUCTURAL_SEARCH_V2":
        raise ValueError("Structural Catalog V2 is not certified")
    if catalog.get("lineage", {}).get("scenario_catalog_sha256") != sha256_path(catalog_path):
        raise ValueError("Structural Catalog V2 hash mismatch")
    if matrix.get("status") != "PASS_REDUCED_PATH_MATRIX_V2_BUILD" or matrix.get("contract") != "PHASE2_REDUCED_STOP_PATH_MATRIX_V2":
        raise ValueError("Reduced Path Matrix V2 is not certified")
    if matrix.get("lineage", {}).get("reduced_path_matrix_sha256") != sha256_path(matrix_path):
        raise ValueError("Reduced Path Matrix V2 hash mismatch")
    if policy.get("status") != "PASS_SERVICE_POLICY_SEARCH_V2_BUILD" or policy.get("contract") != "PHASE2_SERVICE_POLICY_FEASIBILITY_SEARCH_V2":
        raise ValueError("Service Policy Search V2 is not certified")
    if policy.get("lineage", {}).get("policy_grid_sha256") != sha256_path(policy_grid_path):
        raise ValueError("Service-policy grid hash mismatch")
    if s8.get("model") != "PHASE2_S8_INTERCHANGE_OPPORTUNITY_V1" or int(s8.get("active_s8_events", -1)) != 74:
        raise ValueError("S8 interchange evidence contract is not certified")
    if config.get("contract") != "PHASE2_S8_PHASE_OPPORTUNITY_SURFACE_V2":
        raise ValueError("Unexpected S8 phasing config contract")
    if config.get("status") != "ASSUMPTION_PHASE_GRID_NOT_TIMETABLE_SELECTION":
        raise ValueError("S8 phasing config is not explicitly an assumption grid")
    if int(config.get("phase_resolution_min", -1)) != 1:
        raise ValueError("This V2 gate requires the declared one-minute phase grid")
    if any(config.get(key) is not False for key in (
        "transfer_walk_applied", "preferred_wait_utility_applied", "delay_cases_applied",
        "passenger_demand_weights_applied", "phase_selected", "topology_ranked", "service_policy_selected",
    )):
        raise ValueError("S8 phasing config contains a forbidden downstream assumption/selection")
    rules = config.get("passenger_event_rules", {})
    if "VEHICLE_ONLY_RETURN_CLOSURES_ARE_NOT_PASSENGER_EVENTS" not in str(rules.get("BUS_TO_RAIL", "")):
        raise ValueError("S8 phasing config does not protect vehicle-only closure semantics")
    return catalog, matrix, policy, s8


def load_timing_archetypes(policy_grid_path: Path) -> list[tuple[int, Span]]:
    pairs: dict[tuple[int, str], Span] = {}
    with policy_grid_path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            if row.get("exact_timetable") != "false" or row.get("s8_phase_selected") != "false":
                raise ValueError("Upstream policy grid already contains exact timetable/S8 selection")
            h = int(row["uniform_headway_min"])
            span = Span(str(row["span_id"]), int(row["span_start_min"]), int(row["span_end_min"]))
            span.validate()
            key = (h, span.span_id)
            if key in pairs and pairs[key] != span:
                raise ValueError(f"Conflicting span definition for {key}")
            pairs[key] = span
    rows = sorted(((h, span) for (h, _), span in pairs.items()), key=lambda x: (x[0], x[1].span_id))
    if len(rows) != 8:
        raise ValueError(f"Expected 8 unique headway/span timing archetypes, got {len(rows)}")
    return rows


def extract_routes_and_mapping(
    *,
    catalog_path: Path,
    runtime_lookup: dict[tuple[str, str], Decimal],
    route_output: Path,
    scenario_mapping_output: Path,
) -> dict:
    routes: dict[str, dict] = {}
    scenario_count = 0
    raw, text = deterministic_gzip_text(scenario_mapping_output)
    try:
        with catalog_path.open(encoding="utf-8-sig", newline="") as source:
            reader = csv.DictReader(source)
            writer = csv.DictWriter(
                text,
                fieldnames=["scenario_id", "topology_family", "public_route_ids_json", "extension_route_ids_json"],
                lineterminator="\n",
            )
            writer.writeheader()
            for line_no, row in enumerate(reader, start=2):
                public = parse_routes(row["routes_json"], field="routes_json", line_no=line_no)
                extensions = parse_routes(row["optional_extensions_json"], field="optional_extensions_json", line_no=line_no)
                role_ids: dict[str, list[str]] = {"PUBLIC": [], "EXTENSION": []}
                for role, patterns in (("PUBLIC", public), ("EXTENSION", extensions)):
                    for pattern in patterns:
                        anchors = tuple(pattern)
                        if anchors[0] != HUB_ANCHOR:
                            raise ValueError(f"Phase 2 route does not start at certified hub {HUB_ANCHOR}: {anchors}")
                        route_id = stable_route_id(anchors)
                        public_runtime, cycle_runtime, closure_added = route_runtime_components(anchors, runtime_lookup)
                        existing = routes.get(route_id)
                        if existing is not None and existing["anchors"] != anchors:
                            raise AssertionError("Route ID collision")
                        if existing is None:
                            routes[route_id] = {
                                "anchors": anchors,
                                "public_runtime": public_runtime,
                                "cycle_runtime": cycle_runtime,
                                "closure_added": closure_added,
                                "roles": {role},
                                "occurrence_count": 1,
                            }
                        else:
                            if existing["public_runtime"] != public_runtime or existing["cycle_runtime"] != cycle_runtime:
                                raise AssertionError("Same route ID received conflicting runtime")
                            if existing["closure_added"] != closure_added:
                                raise AssertionError("Same route ID received conflicting closure semantics")
                            existing["roles"].add(role)
                            existing["occurrence_count"] += 1
                        role_ids[role].append(route_id)
                writer.writerow({
                    "scenario_id": row["scenario_id"],
                    "topology_family": row["topology_family"],
                    "public_route_ids_json": json.dumps(role_ids["PUBLIC"], separators=(",", ":")),
                    "extension_route_ids_json": json.dumps(role_ids["EXTENSION"], separators=(",", ":")),
                })
                scenario_count += 1
    finally:
        text.close()
        raw.close()
    if scenario_count != 100_000:
        raise ValueError(f"Expected 100000 scenario mappings, got {scenario_count}")

    route_output.parent.mkdir(parents=True, exist_ok=True)
    runtime_ids: dict[str, Decimal] = {}
    closure_count = 0
    public_return_count = 0
    with route_output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "route_id", "runtime_archetype_id", "public_runtime_min", "cycle_runtime_min", "roles",
                "occurrence_count", "public_service_starts_at_hub", "public_service_returns_to_hub",
                "vehicle_closure_added", "rail_to_bus_passenger_event_supported",
                "bus_to_rail_passenger_event_supported", "anchors_json",
            ],
            lineterminator="\n",
        )
        writer.writeheader()
        for route_id in sorted(routes):
            entry = routes[route_id]
            runtime_id = runtime_archetype_id(entry["cycle_runtime"])
            if runtime_id in runtime_ids and runtime_ids[runtime_id] != entry["cycle_runtime"]:
                raise AssertionError("Runtime archetype ID collision")
            runtime_ids[runtime_id] = entry["cycle_runtime"]
            returns_to_hub = entry["anchors"][-1] == HUB_ANCHOR
            closure_added = bool(entry["closure_added"])
            if closure_added == returns_to_hub:
                raise AssertionError("Vehicle closure flag conflicts with public route geometry")
            if closure_added:
                closure_count += 1
            else:
                public_return_count += 1
            writer.writerow({
                "route_id": route_id,
                "runtime_archetype_id": runtime_id,
                "public_runtime_min": format(entry["public_runtime"], "f"),
                "cycle_runtime_min": format(entry["cycle_runtime"], "f"),
                "roles": "|".join(sorted(entry["roles"])),
                "occurrence_count": entry["occurrence_count"],
                "public_service_starts_at_hub": "true",
                "public_service_returns_to_hub": "true" if returns_to_hub else "false",
                "vehicle_closure_added": "true" if closure_added else "false",
                "rail_to_bus_passenger_event_supported": "true",
                "bus_to_rail_passenger_event_supported": "true" if returns_to_hub else "false",
                "anchors_json": json.dumps(list(entry["anchors"]), ensure_ascii=False, separators=(",", ":")),
            })
    if closure_count <= 0 or public_return_count <= 0:
        raise ValueError("Expected both open public routes with vehicle closure and explicit hub-returning public routes")
    return {
        "scenario_count": scenario_count,
        "unique_route_count": len(routes),
        "unique_runtime_archetype_count": len(runtime_ids),
        "public_service_start_hub_route_count": len(routes),
        "public_service_return_hub_route_count": public_return_count,
        "vehicle_closure_route_count": closure_count,
        "rail_to_bus_passenger_supported_route_count": len(routes),
        "bus_to_rail_passenger_supported_route_count": public_return_count,
        "runtime_archetypes": runtime_ids,
    }


def _range(values: list[float | None]) -> tuple[float | None, float | None]:
    finite = [v for v in values if v is not None]
    return (min(finite), max(finite)) if finite else (None, None)


def build_phase_envelope(
    *,
    runtime_archetypes: dict[str, Decimal],
    rail_events: list[RailEvent],
    timing_archetypes: list[tuple[int, Span]],
    output_path: Path,
) -> dict:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rows = 0
    phase_evaluations = 0
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        fields = [
            "runtime_archetype_id", "cycle_runtime_min", "uniform_headway_min", "span_id", "span_start_min", "span_end_min",
            "evaluated_phase_count", "phase_domain", "all_phases_retained_downstream",
        ]
        for connection in ("vehicle_cycle_to_rail", "rail_to_bus"):
            for direction in ("milano", "lecco"):
                for metric in ("mean_gap_min", "median_gap_min", "p90_gap_min"):
                    fields.extend([f"{connection}_{direction}_{metric}_min_across_phases", f"{connection}_{direction}_{metric}_max_across_phases"])
                fields.extend([f"{connection}_{direction}_unmatched_count_min_across_phases", f"{connection}_{direction}_unmatched_count_max_across_phases"])
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for runtime_id in sorted(runtime_archetypes):
            runtime = runtime_archetypes[runtime_id]
            for headway, span in timing_archetypes:
                phase_metrics = [
                    phase_raw_gap_metrics(
                        rail_events=rail_events,
                        cycle_runtime_min=runtime,
                        headway_min=headway,
                        span=span,
                        phase_min=phase,
                    )
                    for phase in range(headway)
                ]
                out = {
                    "runtime_archetype_id": runtime_id,
                    "cycle_runtime_min": format(runtime, "f"),
                    "uniform_headway_min": headway,
                    "span_id": span.span_id,
                    "span_start_min": span.start_min,
                    "span_end_min": span.end_min,
                    "evaluated_phase_count": headway,
                    "phase_domain": f"0..{headway-1}",
                    "all_phases_retained_downstream": "true",
                }
                for connection in ("vehicle_cycle_to_rail", "rail_to_bus"):
                    for direction in ("milano", "lecco"):
                        prefix = f"{connection}_{direction}"
                        for metric in ("mean_gap_min", "median_gap_min", "p90_gap_min"):
                            lo, hi = _range([m[f"{prefix}_{metric}"] for m in phase_metrics])
                            out[f"{prefix}_{metric}_min_across_phases"] = "" if lo is None else f"{lo:.9f}"
                            out[f"{prefix}_{metric}_max_across_phases"] = "" if hi is None else f"{hi:.9f}"
                        unmatched = [int(m[f"{prefix}_unmatched_count"]) for m in phase_metrics]
                        out[f"{prefix}_unmatched_count_min_across_phases"] = min(unmatched)
                        out[f"{prefix}_unmatched_count_max_across_phases"] = max(unmatched)
                writer.writerow(out)
                rows += 1
                phase_evaluations += headway
    return {"phase_envelope_rows": rows, "integer_phase_evaluations": phase_evaluations}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--catalog", required=True, type=Path)
    p.add_argument("--catalog-validation", required=True, type=Path)
    p.add_argument("--path-matrix", required=True, type=Path)
    p.add_argument("--matrix-validation", required=True, type=Path)
    p.add_argument("--policy-grid", required=True, type=Path)
    p.add_argument("--policy-validation", required=True, type=Path)
    p.add_argument("--s8-events", required=True, type=Path)
    p.add_argument("--s8-contract", required=True, type=Path)
    p.add_argument("--phasing-config", required=True, type=Path)
    p.add_argument("--route-universe-output", required=True, type=Path)
    p.add_argument("--scenario-route-mapping-output", required=True, type=Path)
    p.add_argument("--phase-envelope-output", required=True, type=Path)
    p.add_argument("--validation", required=True, type=Path)
    return p


def main() -> int:
    args = build_parser().parse_args()
    for path in (
        args.catalog, args.catalog_validation, args.path_matrix, args.matrix_validation,
        args.policy_grid, args.policy_validation, args.s8_events, args.s8_contract, args.phasing_config,
    ):
        if not path.is_file():
            raise FileNotFoundError(path)
    catalog_val, matrix_val, policy_val, s8_contract = validate_upstream(
        catalog_path=args.catalog,
        catalog_validation_path=args.catalog_validation,
        matrix_path=args.path_matrix,
        matrix_validation_path=args.matrix_validation,
        policy_grid_path=args.policy_grid,
        policy_validation_path=args.policy_validation,
        s8_events_path=args.s8_events,
        s8_contract_path=args.s8_contract,
        phasing_config_path=args.phasing_config,
    )
    runtime_lookup = load_matrix_runtime(args.path_matrix)
    route_info = extract_routes_and_mapping(
        catalog_path=args.catalog,
        runtime_lookup=runtime_lookup,
        route_output=args.route_universe_output,
        scenario_mapping_output=args.scenario_route_mapping_output,
    )
    rail_events = load_rail_events(args.s8_events)
    timing_archetypes = load_timing_archetypes(args.policy_grid)
    runtime_archetypes = route_info.pop("runtime_archetypes")
    surface_info = build_phase_envelope(
        runtime_archetypes=runtime_archetypes,
        rail_events=rail_events,
        timing_archetypes=timing_archetypes,
        output_path=args.phase_envelope_output,
    )
    validation = {
        "status": "PASS_S8_PHASE_OPPORTUNITY_V2_BUILD",
        "contract": "PHASE2_S8_PHASE_OPPORTUNITY_SURFACE_V2",
        "evidence_label": "RAW_PRE_WALK_PHASE_GEOMETRY_NOT_PHASE_SELECTION",
        **route_info,
        **surface_info,
        "timing_archetype_count": len(timing_archetypes),
        "s8_event_count": len(rail_events),
        "s8_direction_counts": {
            "MILANO": sum(e.direction == "MILANO" for e in rail_events),
            "LECCO": sum(e.direction == "LECCO" for e in rail_events),
        },
        "phase_resolution_min": 1,
        "all_integer_phases_evaluated": True,
        "all_phases_retained_downstream": True,
        "phase_selected": False,
        "phase_pruned": False,
        "vehicle_cycle_return_is_passenger_event_for_open_routes": False,
        "passenger_bus_to_rail_event_requires_public_return_to_hub": True,
        "transfer_walk_applied": False,
        "preferred_wait_utility_applied": False,
        "delay_cases_applied": False,
        "passenger_demand_weights_applied": False,
        "passenger_utility_calculated": False,
        "topology_ranked": False,
        "service_policy_selected": False,
        "exact_vehicle_block_plan_constructed": False,
        "lineage": {
            "catalog": str(args.catalog), "catalog_sha256": sha256_path(args.catalog),
            "catalog_validation": str(args.catalog_validation), "catalog_validation_sha256": sha256_path(args.catalog_validation),
            "path_matrix": str(args.path_matrix), "path_matrix_sha256": sha256_path(args.path_matrix),
            "matrix_validation": str(args.matrix_validation), "matrix_validation_sha256": sha256_path(args.matrix_validation),
            "policy_grid": str(args.policy_grid), "policy_grid_sha256": sha256_path(args.policy_grid),
            "policy_validation": str(args.policy_validation), "policy_validation_sha256": sha256_path(args.policy_validation),
            "s8_events": str(args.s8_events), "s8_events_sha256": sha256_path(args.s8_events),
            "s8_contract": str(args.s8_contract), "s8_contract_sha256": sha256_path(args.s8_contract),
            "phasing_config": str(args.phasing_config), "phasing_config_sha256": sha256_path(args.phasing_config),
            "route_universe": str(args.route_universe_output), "route_universe_sha256": sha256_path(args.route_universe_output),
            "scenario_route_mapping": str(args.scenario_route_mapping_output), "scenario_route_mapping_sha256": sha256_path(args.scenario_route_mapping_output),
            "phase_envelope": str(args.phase_envelope_output), "phase_envelope_sha256": sha256_path(args.phase_envelope_output),
            "validated_s8_transfer_model_source_sha": "e149a6aeead645e7987109a251d0c69867bf00a1",
            "upstream_catalog_contract": catalog_val["contract"],
            "upstream_matrix_contract": matrix_val["contract"],
            "upstream_policy_contract": policy_val["contract"],
            "upstream_s8_model": s8_contract["model"],
        },
        "epistemic_note": (
            "This gate derives raw clock-phase timing geometry only. Every integer-minute phase in the declared "
            "headway domain remains reconstructible downstream. RAIL_TO_BUS departures are public-service events because "
            "the structural routes start at the hub. A closed vehicle-cycle return is a BUS_TO_RAIL passenger event only "
            "when the public route itself explicitly returns to the hub; vehicle-only closures remain operational evidence."
        ),
    }
    args.validation.parent.mkdir(parents=True, exist_ok=True)
    args.validation.write_text(json.dumps(validation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(validation, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
