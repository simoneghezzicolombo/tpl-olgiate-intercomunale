#!/usr/bin/env python3
"""Build pre-phase, population-weighted S8 feeder generalized-access screening.

This is Stage-C passenger-facing screening, not full Passenger GJT. It uses the
certified dasymetric building-resident population only as potential feeder access
weight. It never downscales municipal work OD, predicts ridership or assigns
workers to routes.

For every Service-Ready V2 scenario, certified walk times are combined with
public-route in-vehicle times in both directions relative to the explicit rail
hub. A vehicle-only return closure is never usable for BUS_TO_RAIL. Residents in
the verified direct station walking catchment are excluded from the feeder-
dependent denominator because they can already reach the hub without a bus.

The timing surface applies a declared factorial sensitivity grid to a pre-phase
screening formula. Exact S8 phase, train connection wait, missed-connection risk,
delay robustness and exact vehicle blocks remain downstream.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import itertools
import json
import math
from pathlib import Path

HUB_ANCHOR = "rail:S01514"
STATUS = "PASS_FEEDER_GENERALIZED_ACCESS_V2_BUILD"
CONTRACT = "PHASE2_PRE_PHASE_FEEDER_GENERALIZED_ACCESS_V2"
DIRECTIONS = ("to_rail", "from_rail")


def sha256_path(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def deterministic_gzip_writer(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = path.open("wb")
    gz = gzip.GzipFile(filename="", mode="wb", fileobj=raw, compresslevel=9, mtime=0)
    text = io.TextIOWrapper(gz, encoding="utf-8", newline="")
    return raw, text


def finite_float(value: object, *, field: str) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"Non-finite {field}: {value!r}")
    return result


def strict_bool(value: object, *, field: str) -> bool:
    text = str(value).strip().lower()
    if text == "true":
        return True
    if text == "false":
        return False
    raise ValueError(f"Invalid boolean {field}: {value!r}")


def pair_id(bus_weight: float, walk_weight: float) -> str:
    return f"B{round(bus_weight * 100):03d}_W{round(walk_weight * 100):03d}"


def load_sensitivity(path: Path) -> tuple[dict, list[dict[str, float]], tuple[tuple[float, float, str], ...]]:
    payload = load_json(path)
    if payload.get("contract") != "PHASE2_FEEDER_GENERALIZED_ACCESS_SENSITIVITY_V2":
        raise ValueError("Unexpected feeder generalized-access sensitivity contract")
    if payload.get("status") != "ASSUMPTION_SENSITIVITY_NOT_EMPIRICAL_INTERVAL":
        raise ValueError("Sensitivity grid is not explicitly an assumption")
    grid = payload.get("parameter_grid") or {}
    keys = (
        "bus_ivt_weight",
        "walk_weight",
        "wait_weight",
        "transfer_penalty_min",
        "station_transfer_walk_min",
    )
    values: list[tuple[float, ...]] = []
    for key in keys:
        raw = grid.get(key)
        if not isinstance(raw, list) or not raw:
            raise ValueError(f"Missing sensitivity grid {key}")
        vals = tuple(finite_float(v, field=key) for v in raw)
        if any(v <= 0 for v in vals):
            raise ValueError(f"Sensitivity values must be positive for {key}")
        values.append(vals)
    cases = [dict(zip(keys, combo)) for combo in itertools.product(*values)]
    expected = int(payload.get("expected_full_factorial_case_count", -1))
    if len(cases) != expected or expected != 243:
        raise ValueError(f"Unexpected sensitivity cardinality {len(cases)} / {expected}")
    pairs = tuple(sorted({
        (case["bus_ivt_weight"], case["walk_weight"], pair_id(case["bus_ivt_weight"], case["walk_weight"]))
        for case in cases
    }))
    if len(pairs) != 9:
        raise ValueError(f"Expected nine bus×walk base-weight pairs, got {len(pairs)}")
    return payload, cases, pairs


def validate_upstream(args) -> tuple[dict, dict, dict, dict]:
    service = load_json(args.service_ready_validation)
    access = load_json(args.access_validation)
    s8 = load_json(args.s8_validation)
    matrix = load_json(args.matrix_validation)
    if service.get("status") != "PASS_PHASE2_SERVICE_READY_FRONTIER_V2" or service.get("contract") != "PHASE2_BUDGET_NEUTRAL_SERVICE_READY_PARETO_V2":
        raise ValueError("Service-Ready Frontier V2 is not certified")
    if service.get("lineage", {}).get("frontier_output_sha256") != sha256_path(args.service_ready_frontier):
        raise ValueError("Service-Ready frontier hash mismatch")
    if int(service.get("frontier_row_count_all_timings", -1)) != 21237:
        raise ValueError("Unexpected Service-Ready frontier cardinality")
    if service.get("budget_filter_applied") is not False or service.get("service_policy_selected") is not False:
        raise ValueError("Service-Ready upstream contains forbidden selection")

    if access.get("status") != "PASS_ACCESS_EQUITY_V2_BUILD" or access.get("contract") != "PHASE2_BUILDING_CATCHMENT_ACCESS_EQUITY_V2":
        raise ValueError("Access Equity V2 is not certified")
    bridge = access.get("hub_access_bridge") or {}
    if bridge.get("status") != "VERIFIED_APPLIED" or bridge.get("rail_anchor_id") != HUB_ANCHOR:
        raise ValueError("Verified pedestrian hub-access bridge is unavailable")
    expected_access_hashes = {
        "population_units_sha256": sha256_path(args.population_units),
        "proposed_catchments_sha256": sha256_path(args.proposed_catchments),
        "existing_catchments_sha256": sha256_path(args.existing_catchments),
        "routing_anchor_universe_sha256": sha256_path(args.anchors),
        "matrix_validation_sha256": sha256_path(args.matrix_validation),
    }
    for key, actual in expected_access_hashes.items():
        if access.get("lineage", {}).get(key) != actual:
            raise ValueError(f"Access Equity lineage hash mismatch for {key}")
    if access.get("passenger_demand_inferred") is not False:
        raise ValueError("Access Equity upstream inferred passenger demand")

    if s8.get("status") != "PASS_S8_PHASE_OPPORTUNITY_V2_BUILD" or s8.get("contract") != "PHASE2_S8_PHASE_OPPORTUNITY_SURFACE_V2":
        raise ValueError("S8 Phase Opportunity V2 is not certified")
    s8_lineage = s8.get("lineage", {})
    if s8_lineage.get("route_universe_sha256") != sha256_path(args.route_universe):
        raise ValueError("S8 route-universe hash mismatch")
    if s8_lineage.get("scenario_route_mapping_sha256") != sha256_path(args.scenario_mapping):
        raise ValueError("S8 scenario-route mapping hash mismatch")
    if s8_lineage.get("path_matrix_sha256") != sha256_path(args.path_matrix):
        raise ValueError("S8 path-matrix hash mismatch")
    if s8.get("phase_selected") is not False or s8.get("passenger_utility_calculated") is not False:
        raise ValueError("S8 upstream contains forbidden passenger utility/phase selection")
    if s8.get("passenger_bus_to_rail_event_requires_public_return_to_hub") is not True:
        raise ValueError("S8 upstream lost explicit public-return passenger semantics")
    if s8.get("vehicle_cycle_return_is_passenger_event_for_open_routes") is not False:
        raise ValueError("S8 upstream treats technical closures as passenger returns")

    if matrix.get("status") != "PASS_REDUCED_PATH_MATRIX_V2_BUILD" or matrix.get("contract") != "PHASE2_REDUCED_STOP_PATH_MATRIX_V2":
        raise ValueError("Reduced Path Matrix V2 is not certified")
    if matrix.get("lineage", {}).get("reduced_path_matrix_sha256") != sha256_path(args.path_matrix):
        raise ValueError("Reduced Path Matrix lineage mismatch")
    return service, access, s8, matrix


def load_service_ready(path: Path) -> tuple[list[dict[str, str]], dict[str, str]]:
    rows: list[dict[str, str]] = []
    families: dict[str, str] = {}
    seen: set[tuple[str, int, str]] = set()
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"scenario_id", "topology_family", "uniform_headway_min", "span_id", "span_start_min", "span_end_min"}
        if not required <= set(reader.fieldnames or []):
            raise ValueError("Service-Ready frontier schema mismatch")
        for row in reader:
            sid = str(row["scenario_id"])
            family = str(row["topology_family"])
            headway = int(row["uniform_headway_min"])
            span_id = str(row["span_id"])
            key = (sid, headway, span_id)
            if key in seen:
                raise ValueError(f"Duplicate Service-Ready scenario×timing {key}")
            seen.add(key)
            if sid in families and families[sid] != family:
                raise ValueError(f"Topology family mismatch for {sid}")
            families[sid] = family
            rows.append({
                "scenario_id": sid,
                "topology_family": family,
                "uniform_headway_min": str(headway),
                "span_id": span_id,
                "span_start_min": str(int(row["span_start_min"])),
                "span_end_min": str(int(row["span_end_min"])),
            })
    if len(rows) != 21237:
        raise ValueError(f"Unexpected Service-Ready row count {len(rows)}")
    return rows, families


def load_population(path: Path):
    unit_ids: list[str] = []
    weights: list[float] = []
    municipalities: list[str] = []
    municipality_codes: dict[str, str] = {}
    by_id: dict[str, int] = {}
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"population_unit_id", "COMUNE", "PRO_COM_T", "building_piece_population_model"}
        if not required <= set(reader.fieldnames or []):
            raise ValueError("Population-unit schema mismatch")
        for line_no, row in enumerate(reader, start=2):
            uid = str(row["population_unit_id"]).strip()
            muni = str(row["COMUNE"]).strip()
            code = str(row["PRO_COM_T"]).strip()
            weight = finite_float(row["building_piece_population_model"], field="building_piece_population_model")
            if not uid or not muni or not code or weight < 0:
                raise ValueError(f"Invalid population unit at line {line_no}")
            if uid in by_id:
                raise ValueError(f"Duplicate population unit {uid}")
            if muni in municipality_codes and municipality_codes[muni] != code:
                raise ValueError(f"Conflicting municipality code for {muni}")
            by_id[uid] = len(unit_ids)
            unit_ids.append(uid)
            weights.append(weight)
            municipalities.append(muni)
            municipality_codes[muni] = code
    if not unit_ids:
        raise ValueError("Population universe is empty")
    return unit_ids, weights, municipalities, municipality_codes, by_id


def load_scenario_routes(path: Path, wanted_scenarios: set[str], expected_families: dict[str, str]):
    out: dict[str, list[str]] = {}
    with gzip.open(path, "rt", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"scenario_id", "topology_family", "public_route_ids_json", "extension_route_ids_json"}
        if not required <= set(reader.fieldnames or []):
            raise ValueError("Scenario-route mapping schema mismatch")
        for row in reader:
            sid = str(row["scenario_id"])
            if sid not in wanted_scenarios:
                continue
            if sid in out:
                raise ValueError(f"Duplicate scenario-route mapping for {sid}")
            if str(row["topology_family"]) != expected_families[sid]:
                raise ValueError(f"Scenario-route topology family mismatch for {sid}")
            public = json.loads(row["public_route_ids_json"])
            if not isinstance(public, list) or not public or any(not isinstance(v, str) or not v for v in public):
                raise ValueError(f"Invalid public route IDs for {sid}")
            if len(public) != len(set(public)):
                raise ValueError(f"Duplicate public route IDs for {sid}")
            out[sid] = public
    if set(out) != wanted_scenarios:
        raise ValueError(f"Missing scenario-route mappings for {len(wanted_scenarios-set(out))} scenarios")
    return out


def load_route_anchors(path: Path, wanted_routes: set[str]) -> dict[str, tuple[str, ...]]:
    out: dict[str, tuple[str, ...]] = {}
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {
            "route_id", "anchors_json", "public_service_starts_at_hub", "public_service_returns_to_hub",
            "vehicle_closure_added", "rail_to_bus_passenger_event_supported", "bus_to_rail_passenger_event_supported",
        }
        if not required <= set(reader.fieldnames or []):
            raise ValueError("Route-universe schema mismatch")
        for row in reader:
            rid = str(row["route_id"])
            if rid not in wanted_routes:
                continue
            if rid in out:
                raise ValueError(f"Duplicate route {rid}")
            anchors_raw = json.loads(row["anchors_json"])
            if not isinstance(anchors_raw, list) or len(anchors_raw) < 2:
                raise ValueError(f"Invalid anchors for {rid}")
            anchors = tuple(str(v) for v in anchors_raw)
            if anchors[0] != HUB_ANCHOR or not strict_bool(row["public_service_starts_at_hub"], field="public_service_starts_at_hub"):
                raise ValueError(f"Route {rid} does not start at certified hub")
            returns = anchors[-1] == HUB_ANCHOR
            if strict_bool(row["public_service_returns_to_hub"], field="public_service_returns_to_hub") != returns:
                raise ValueError(f"Route return flag mismatch for {rid}")
            if strict_bool(row["bus_to_rail_passenger_event_supported"], field="bus_to_rail_passenger_event_supported") != returns:
                raise ValueError(f"BUS_TO_RAIL support mismatch for {rid}")
            if not strict_bool(row["rail_to_bus_passenger_event_supported"], field="rail_to_bus_passenger_event_supported"):
                raise ValueError(f"RAIL_TO_BUS support unexpectedly false for {rid}")
            if strict_bool(row["vehicle_closure_added"], field="vehicle_closure_added") == returns:
                raise ValueError(f"Vehicle closure semantics conflict for {rid}")
            out[rid] = anchors
    if set(out) != wanted_routes:
        raise ValueError(f"Missing route-universe rows for {len(wanted_routes-set(out))} routes")
    return out


def load_runtime_subset(path: Path, required_legs: set[tuple[str, str]]) -> dict[tuple[str, str], float]:
    out: dict[tuple[str, str], float] = {}
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"origin", "destination", "runtime_min"}
        if not required <= set(reader.fieldnames or []):
            raise ValueError("Path-matrix runtime schema mismatch")
        for row in reader:
            key = (str(row["origin"]), str(row["destination"]))
            if key not in required_legs:
                continue
            if key in out:
                raise ValueError(f"Duplicate path-matrix leg {key}")
            runtime = finite_float(row["runtime_min"], field="runtime_min")
            if runtime <= 0:
                raise ValueError(f"Non-positive runtime for {key}")
            out[key] = runtime
    if set(out) != required_legs:
        raise ValueError(f"Missing {len(required_legs-set(out))} required public route legs")
    return out


def route_anchor_ivt(anchors: tuple[str, ...], runtime: dict[tuple[str, str], float]):
    cumulative = [0.0]
    for a, b in zip(anchors[:-1], anchors[1:]):
        cumulative.append(cumulative[-1] + runtime[(a, b)])
    next_hub: list[int | None] = [None] * len(anchors)
    upcoming: int | None = None
    for i in range(len(anchors) - 1, -1, -1):
        if anchors[i] == HUB_ANCHOR:
            upcoming = i
        next_hub[i] = upcoming
    to_rail: dict[str, float] = {}
    from_rail: dict[str, float] = {}
    previous_hub: int | None = None
    for i, anchor in enumerate(anchors):
        if anchor == HUB_ANCHOR:
            previous_hub = i
            continue
        if previous_hub is not None:
            ivt = cumulative[i] - cumulative[previous_hub]
            if ivt <= 0:
                raise ValueError("Non-positive RAIL_TO_BUS in-vehicle time")
            from_rail[anchor] = min(from_rail.get(anchor, math.inf), ivt)
        nh = next_hub[i]
        if nh is not None and nh > i:
            ivt = cumulative[nh] - cumulative[i]
            if ivt <= 0:
                raise ValueError("Non-positive BUS_TO_RAIL in-vehicle time")
            to_rail[anchor] = min(to_rail.get(anchor, math.inf), ivt)
    return to_rail, from_rail


def combine_scenario_anchor_ivt(route_ids: list[str], route_ivt: dict[str, tuple[dict[str, float], dict[str, float]]]):
    to_rail: dict[str, float] = {}
    from_rail: dict[str, float] = {}
    for rid in route_ids:
        r_to, r_from = route_ivt[rid]
        for anchor, ivt in r_to.items():
            to_rail[anchor] = min(to_rail.get(anchor, math.inf), ivt)
        for anchor, ivt in r_from.items():
            from_rail[anchor] = min(from_rail.get(anchor, math.inf), ivt)
    return to_rail, from_rail


def load_anchor_members(path: Path, wanted_anchors: set[str]):
    out: dict[str, tuple[tuple[str, str], ...]] = {}
    proposed_ids: set[str] = set()
    existing_ids: set[str] = set()
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"anchor_id", "source_kind", "source_members"}
        if not required <= set(reader.fieldnames or []):
            raise ValueError("Routing-anchor schema mismatch")
        for row in reader:
            anchor = str(row["anchor_id"]).strip()
            if anchor not in wanted_anchors:
                continue
            kind = str(row["source_kind"]).strip()
            members: list[tuple[str, str]] = []
            if kind == "PROPOSED_STOP":
                members.append((kind, anchor))
                proposed_ids.add(anchor)
            elif kind == "EXISTING_PHYSICAL_STOP_CLUSTER":
                for token in str(row["source_members"]).split(";"):
                    token = token.strip()
                    if token.startswith("existing:"):
                        token = token[len("existing:"):]
                    if token:
                        members.append((kind, token))
                        existing_ids.add(token)
                if not members:
                    raise ValueError(f"Existing anchor {anchor} has no source members")
            elif kind == "HUB_RAIL":
                members = []
            else:
                raise ValueError(f"Unsupported anchor source kind {kind!r}")
            out[anchor] = tuple(members)
    missing = wanted_anchors - set(out)
    if missing:
        raise ValueError(f"Missing routing anchors {sorted(missing)[:5]}")
    return out, proposed_ids, existing_ids


def load_walk_maps(
    proposed_path: Path,
    existing_path: Path,
    *,
    wanted_proposed: set[str],
    wanted_existing: set[str],
    hub_cluster_id: str,
    unit_index: dict[str, int],
    weights: list[float],
):
    proposed: dict[str, dict[int, float]] = {}
    with proposed_path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"candidate_id", "population_unit_id", "walk_min_to_candidate", "building_piece_population_model"}
        if not required <= set(reader.fieldnames or []):
            raise ValueError("Proposed catchment schema mismatch")
        for row in reader:
            stop = str(row["candidate_id"])
            if stop not in wanted_proposed:
                continue
            uid = str(row["population_unit_id"])
            if uid not in unit_index:
                raise ValueError(f"Unknown population unit {uid}")
            idx = unit_index[uid]
            row_weight = finite_float(row["building_piece_population_model"], field="proposed_population")
            if not math.isclose(row_weight, weights[idx], rel_tol=0.0, abs_tol=1e-9):
                raise ValueError(f"Population mismatch for proposed catchment unit {uid}")
            walk = finite_float(row["walk_min_to_candidate"], field="walk_min_to_candidate")
            if walk < 0 or walk > 10 + 1e-9:
                raise ValueError("Proposed walk time outside certified 10-minute envelope")
            prev = proposed.setdefault(stop, {}).get(idx)
            if prev is None or walk < prev:
                proposed[stop][idx] = walk

    existing_targets = set(wanted_existing) | {hub_cluster_id}
    existing: dict[str, dict[int, float]] = {}
    with existing_path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"physical_cluster_id", "population_unit_id", "walk_min_to_stop", "building_piece_population_model"}
        if not required <= set(reader.fieldnames or []):
            raise ValueError("Existing catchment schema mismatch")
        for row in reader:
            stop = str(row["physical_cluster_id"])
            if stop not in existing_targets:
                continue
            uid = str(row["population_unit_id"])
            if uid not in unit_index:
                raise ValueError(f"Unknown population unit {uid}")
            idx = unit_index[uid]
            row_weight = finite_float(row["building_piece_population_model"], field="existing_population")
            if not math.isclose(row_weight, weights[idx], rel_tol=0.0, abs_tol=1e-9):
                raise ValueError(f"Population mismatch for existing catchment unit {uid}")
            walk = finite_float(row["walk_min_to_stop"], field="walk_min_to_stop")
            if walk < 0 or walk > 12 + 1e-9:
                raise ValueError("Existing walk time outside certified 12-minute envelope")
            prev = existing.setdefault(stop, {}).get(idx)
            if prev is None or walk < prev:
                existing[stop][idx] = walk
    if hub_cluster_id not in existing or not existing[hub_cluster_id]:
        raise ValueError("Verified hub stop cluster has no certified walking catchment")
    return proposed, existing


def build_anchor_walks(anchor_members, proposed, existing):
    out: dict[str, dict[int, float]] = {}
    for anchor, members in anchor_members.items():
        merged: dict[int, float] = {}
        for kind, stop in members:
            source = proposed.get(stop, {}) if kind == "PROPOSED_STOP" else existing.get(stop, {})
            for idx, walk in source.items():
                prev = merged.get(idx)
                if prev is None or walk < prev:
                    merged[idx] = walk
        out[anchor] = merged
    return out


def reach_summary(reachable: list[bool], weights, municipalities, feeder_denoms):
    total = 0.0
    by_muni = {muni: 0.0 for muni in feeder_denoms}
    for i, flag in enumerate(reachable):
        if not flag:
            continue
        total += weights[i]
        by_muni[municipalities[i]] += weights[i]
    feeder_total = sum(feeder_denoms.values())
    share = total / feeder_total if feeder_total > 0 else 0.0
    muni_shares = {
        muni: (by_muni[muni] / denom if denom > 0 else 1.0)
        for muni, denom in feeder_denoms.items()
    }
    worst_muni = min(muni_shares, key=lambda m: (muni_shares[m], m))
    return total, share, worst_muni, muni_shares[worst_muni], by_muni


def directional_base_metrics(
    anchor_ivt: dict[str, float],
    anchor_walks: dict[str, dict[int, float]],
    *,
    weights: list[float],
    municipalities: list[str],
    feeder_mask: list[bool],
    feeder_denoms: dict[str, float],
    pairs: tuple[tuple[float, float, str], ...],
):
    n = len(weights)
    best = [[math.inf] * n for _ in pairs]
    reachable = [False] * n
    for anchor, ivt in anchor_ivt.items():
        walks = anchor_walks.get(anchor, {})
        for idx, walk in walks.items():
            if not feeder_mask[idx] or weights[idx] <= 0:
                continue
            reachable[idx] = True
            for k, (bus_weight, walk_weight, _) in enumerate(pairs):
                cost = bus_weight * ivt + walk_weight * walk
                if cost < best[k][idx]:
                    best[k][idx] = cost
    reachable_population, reachable_share, worst_muni, worst_share, by_muni = reach_summary(
        reachable, weights, municipalities, feeder_denoms
    )
    means: dict[str, float | None] = {}
    worst_muni_means: dict[str, float | None] = {}
    if reachable_population <= 0:
        for _, _, pid in pairs:
            means[pid] = None
            worst_muni_means[pid] = None
        return {
            "reachable": reachable,
            "reachable_population": 0.0,
            "reachable_share": 0.0,
            "worst_municipality": worst_muni,
            "worst_municipality_share": worst_share,
            "means": means,
            "worst_municipality_means": worst_muni_means,
        }
    for k, (_, _, pid) in enumerate(pairs):
        total_cost = 0.0
        muni_cost = {muni: 0.0 for muni in feeder_denoms}
        for i, flag in enumerate(reachable):
            if not flag or weights[i] <= 0:
                continue
            value = best[k][i]
            if not math.isfinite(value):
                raise AssertionError("Reachable unit lacks finite base generalized access")
            total_cost += weights[i] * value
            muni_cost[municipalities[i]] += weights[i] * value
        means[pid] = total_cost / reachable_population
        finite_muni_means = [
            muni_cost[muni] / by_muni[muni]
            for muni in feeder_denoms
            if by_muni[muni] > 0
        ]
        worst_muni_means[pid] = max(finite_muni_means) if finite_muni_means else None
    return {
        "reachable": reachable,
        "reachable_population": reachable_population,
        "reachable_share": reachable_share,
        "worst_municipality": worst_muni,
        "worst_municipality_share": worst_share,
        "means": means,
        "worst_municipality_means": worst_muni_means,
    }


def nearest_rank(sorted_values: list[float], q: float) -> float:
    if not sorted_values:
        raise ValueError("Cannot calculate quantile of empty values")
    if not 0 < q <= 1:
        raise ValueError("Quantile must be in (0,1]")
    index = max(0, math.ceil(q * len(sorted_values)) - 1)
    return sorted_values[index]


def robust_timing_summary(base_means, worst_muni_means, headway: int, cases: list[dict[str, float]]):
    if all(value is None for value in base_means.values()):
        return None
    values: list[float] = []
    worst_values: list[float] = []
    for case in cases:
        pid = pair_id(case["bus_ivt_weight"], case["walk_weight"])
        base = base_means[pid]
        worst = worst_muni_means[pid]
        if base is None or worst is None:
            raise AssertionError("Partially missing sensitivity base metrics")
        constant = (
            case["walk_weight"] * case["station_transfer_walk_min"]
            + case["wait_weight"] * (headway / 2.0)
            + case["transfer_penalty_min"]
        )
        values.append(base + constant)
        worst_values.append(worst + constant)
    values.sort()
    worst_values.sort()
    return {
        "minimum": values[0],
        "median": values[len(values) // 2],
        "p90": nearest_rank(values, 0.90),
        "maximum": values[-1],
        "worst_municipality_minimum": worst_values[0],
        "worst_municipality_median": worst_values[len(worst_values) // 2],
        "worst_municipality_p90": nearest_rank(worst_values, 0.90),
        "worst_municipality_maximum": worst_values[-1],
    }


def fmt(value: float | None, digits: int = 9) -> str:
    return "" if value is None else f"{value:.{digits}f}"


def write_gzip_rows(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    raw, text = deterministic_gzip_writer(path)
    try:
        writer = csv.DictWriter(text, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    finally:
        text.close()
        raw.close()


def main() -> int:
    p = argparse.ArgumentParser()
    for name in (
        "service_ready_frontier", "service_ready_validation", "access_validation", "population_units",
        "anchors", "proposed_catchments", "existing_catchments", "route_universe", "scenario_mapping",
        "s8_validation", "path_matrix", "matrix_validation", "sensitivity_config", "base_output",
        "timing_output", "validation_output",
    ):
        p.add_argument("--" + name.replace("_", "-"), dest=name, type=Path, required=True)
    args = p.parse_args()
    for name, path in vars(args).items():
        if name in {"base_output", "timing_output", "validation_output"}:
            continue
        if not path.is_file():
            raise FileNotFoundError(path)

    service_val, access_val, s8_val, matrix_val = validate_upstream(args)
    sensitivity, cases, pairs = load_sensitivity(args.sensitivity_config)
    timing_rows, families = load_service_ready(args.service_ready_frontier)
    wanted_scenarios = set(families)
    scenario_routes = load_scenario_routes(args.scenario_mapping, wanted_scenarios, families)
    wanted_routes = {rid for ids in scenario_routes.values() for rid in ids}
    route_anchors = load_route_anchors(args.route_universe, wanted_routes)
    required_legs = {
        (a, b) for anchors in route_anchors.values() for a, b in zip(anchors[:-1], anchors[1:])
    }
    runtime = load_runtime_subset(args.path_matrix, required_legs)
    route_ivt = {rid: route_anchor_ivt(anchors, runtime) for rid, anchors in route_anchors.items()}
    scenario_ivt = {sid: combine_scenario_anchor_ivt(ids, route_ivt) for sid, ids in scenario_routes.items()}
    wanted_anchors = {
        anchor
        for to_rail, from_rail in scenario_ivt.values()
        for anchor in set(to_rail) | set(from_rail)
    }

    unit_ids, weights, municipalities, municipality_codes, unit_index = load_population(args.population_units)
    anchor_members, wanted_proposed, wanted_existing = load_anchor_members(args.anchors, wanted_anchors)
    hub_cluster = str(access_val["hub_access_bridge"]["physical_cluster_id"])
    proposed_walks, existing_walks = load_walk_maps(
        args.proposed_catchments,
        args.existing_catchments,
        wanted_proposed=wanted_proposed,
        wanted_existing=wanted_existing,
        hub_cluster_id=hub_cluster,
        unit_index=unit_index,
        weights=weights,
    )
    anchor_walks = build_anchor_walks(anchor_members, proposed_walks, existing_walks)
    direct_indices = set(existing_walks[hub_cluster])
    feeder_mask = [i not in direct_indices for i in range(len(unit_ids))]
    located_population = sum(weights)
    direct_hub_walk_population = sum(weights[i] for i in direct_indices)
    feeder_population = sum(weights[i] for i in range(len(weights)) if feeder_mask[i])
    if not 0 < direct_hub_walk_population < located_population or feeder_population <= 0:
        raise ValueError("Invalid direct-hub / feeder-dependent population partition")
    if not math.isclose(located_population, float(access_val["located_population"]), rel_tol=0.0, abs_tol=1e-6):
        raise ValueError("Located population differs from Access Equity V2")
    if len(unit_ids) != int(access_val["population_unit_count"]):
        raise ValueError("Population-unit count differs from Access Equity V2")
    feeder_denoms = {muni: 0.0 for muni in municipality_codes}
    for i, include in enumerate(feeder_mask):
        if include:
            feeder_denoms[municipalities[i]] += weights[i]
    if any(value <= 0 for value in feeder_denoms.values()):
        raise ValueError("A core municipality has no feeder-dependent located population")

    base_rows: list[dict[str, object]] = []
    base_lookup: dict[str, dict[str, object]] = {}
    zero_to_rail = 0
    zero_from_rail = 0
    for sid in sorted(wanted_scenarios):
        to_ivt, from_ivt = scenario_ivt[sid]
        direction_metrics = {
            "to_rail": directional_base_metrics(
                to_ivt, anchor_walks, weights=weights, municipalities=municipalities,
                feeder_mask=feeder_mask, feeder_denoms=feeder_denoms, pairs=pairs,
            ),
            "from_rail": directional_base_metrics(
                from_ivt, anchor_walks, weights=weights, municipalities=municipalities,
                feeder_mask=feeder_mask, feeder_denoms=feeder_denoms, pairs=pairs,
            ),
        }
        if direction_metrics["to_rail"]["reachable_population"] <= 0:
            zero_to_rail += 1
        if direction_metrics["from_rail"]["reachable_population"] <= 0:
            zero_from_rail += 1
        both = [
            bool(direction_metrics["to_rail"]["reachable"][i] and direction_metrics["from_rail"]["reachable"][i])
            for i in range(len(unit_ids))
        ]
        both_pop, both_share, both_worst_muni, both_worst_share, _ = reach_summary(
            both, weights, municipalities, feeder_denoms
        )
        row: dict[str, object] = {
            "scenario_id": sid,
            "topology_family": families[sid],
            "public_route_count": len(scenario_routes[sid]),
            "direct_hub_walk_population_excluded": fmt(direct_hub_walk_population),
            "feeder_dependent_located_population": fmt(feeder_population),
            "to_rail_reachable_population": fmt(direction_metrics["to_rail"]["reachable_population"]),
            "to_rail_reachable_share": fmt(direction_metrics["to_rail"]["reachable_share"], 12),
            "to_rail_worst_municipality": direction_metrics["to_rail"]["worst_municipality"],
            "to_rail_worst_municipality_reachable_share": fmt(direction_metrics["to_rail"]["worst_municipality_share"], 12),
            "from_rail_reachable_population": fmt(direction_metrics["from_rail"]["reachable_population"]),
            "from_rail_reachable_share": fmt(direction_metrics["from_rail"]["reachable_share"], 12),
            "from_rail_worst_municipality": direction_metrics["from_rail"]["worst_municipality"],
            "from_rail_worst_municipality_reachable_share": fmt(direction_metrics["from_rail"]["worst_municipality_share"], 12),
            "bidirectional_reachable_population": fmt(both_pop),
            "bidirectional_reachable_share": fmt(both_share, 12),
            "bidirectional_worst_municipality": both_worst_muni,
            "bidirectional_worst_municipality_reachable_share": fmt(both_worst_share, 12),
            "resident_population_is_passenger_demand": "false",
            "municipal_work_od_downscaled": "false",
            "technical_return_closure_used_for_to_rail": "false",
            "direct_hub_walkers_excluded_from_feeder_denominator": "true",
            "full_gjt_calculated": "false",
            "s8_phase_selected": "false",
            "primary_selected": "false",
            "runner_up_selected": "false",
        }
        for direction in DIRECTIONS:
            metrics = direction_metrics[direction]
            for _, _, pid in pairs:
                row[f"{direction}_mean_base_gfa_{pid}"] = fmt(metrics["means"][pid])
                row[f"{direction}_worst_municipality_mean_base_gfa_{pid}"] = fmt(metrics["worst_municipality_means"][pid])
        base_rows.append(row)
        base_lookup[sid] = {
            "row": row,
            "direction_metrics": direction_metrics,
        }

    base_fields = list(base_rows[0])
    write_gzip_rows(args.base_output, base_rows, base_fields)

    timing_output_rows: list[dict[str, object]] = []
    for timing in sorted(timing_rows, key=lambda r: (int(r["uniform_headway_min"]), r["span_id"], r["scenario_id"])):
        sid = timing["scenario_id"]
        headway = int(timing["uniform_headway_min"])
        base = base_lookup[sid]
        base_row = base["row"]
        out: dict[str, object] = {
            **timing,
            "sensitivity_case_count": len(cases),
            "average_random_arrival_wait_min": fmt(headway / 2.0),
            "direct_hub_walk_population_excluded": base_row["direct_hub_walk_population_excluded"],
            "feeder_dependent_located_population": base_row["feeder_dependent_located_population"],
            "to_rail_reachable_population": base_row["to_rail_reachable_population"],
            "to_rail_reachable_share": base_row["to_rail_reachable_share"],
            "to_rail_worst_municipality": base_row["to_rail_worst_municipality"],
            "to_rail_worst_municipality_reachable_share": base_row["to_rail_worst_municipality_reachable_share"],
            "from_rail_reachable_population": base_row["from_rail_reachable_population"],
            "from_rail_reachable_share": base_row["from_rail_reachable_share"],
            "from_rail_worst_municipality": base_row["from_rail_worst_municipality"],
            "from_rail_worst_municipality_reachable_share": base_row["from_rail_worst_municipality_reachable_share"],
            "bidirectional_reachable_population": base_row["bidirectional_reachable_population"],
            "bidirectional_reachable_share": base_row["bidirectional_reachable_share"],
            "bidirectional_worst_municipality": base_row["bidirectional_worst_municipality"],
            "bidirectional_worst_municipality_reachable_share": base_row["bidirectional_worst_municipality_reachable_share"],
        }
        for direction in DIRECTIONS:
            metrics = base["direction_metrics"][direction]
            robust = robust_timing_summary(metrics["means"], metrics["worst_municipality_means"], headway, cases)
            for metric_name in (
                "minimum", "median", "p90", "maximum",
                "worst_municipality_minimum", "worst_municipality_median",
                "worst_municipality_p90", "worst_municipality_maximum",
            ):
                out[f"{direction}_{metric_name}_mean_generalized_access_min"] = fmt(
                    None if robust is None else robust[metric_name]
                )
        out.update({
            "waiting_semantics": "UNIFORM_CLOCKFACE_RANDOM_ARRIVAL_MEAN_WAIT_HALF_HEADWAY_SCREENING_ASSUMPTION",
            "resident_population_is_passenger_demand": "false",
            "municipal_work_od_downscaled": "false",
            "exact_s8_phase_used": "false",
            "exact_train_connection_wait_used": "false",
            "missed_connection_probability_used": "false",
            "full_gjt_calculated": "false",
            "passenger_facing_screening_metric_calculated": "true",
            "primary_selected": "false",
            "runner_up_selected": "false",
        })
        timing_output_rows.append(out)
    timing_fields = list(timing_output_rows[0])
    write_gzip_rows(args.timing_output, timing_output_rows, timing_fields)

    validation = {
        "status": STATUS,
        "contract": CONTRACT,
        "service_ready_row_count": len(timing_rows),
        "service_ready_unique_scenario_count": len(wanted_scenarios),
        "population_unit_count": len(unit_ids),
        "located_population": located_population,
        "direct_hub_walk_population_excluded": direct_hub_walk_population,
        "direct_hub_walk_population_share": direct_hub_walk_population / located_population,
        "feeder_dependent_located_population": feeder_population,
        "municipality_feeder_denominators": dict(sorted(feeder_denoms.items())),
        "sensitivity_case_count": len(cases),
        "base_bus_walk_weight_pair_count": len(pairs),
        "zero_to_rail_reach_scenario_count": zero_to_rail,
        "zero_from_rail_reach_scenario_count": zero_from_rail,
        "population_weight_semantics": "DASYMETRIC_BUILDING_RESIDENT_POPULATION_AS_POTENTIAL_FEEDER_ACCESS_WEIGHT_NOT_PASSENGER_DEMAND",
        "direction_semantics": {
            "to_rail": "STOP_TO_NEXT_EXPLICIT_PUBLIC_HUB_OCCURRENCE_ONLY",
            "from_rail": "MOST_RECENT_EXPLICIT_PUBLIC_HUB_OCCURRENCE_TO_STOP",
        },
        "direct_station_access_semantics": "VERIFIED_EX_039_WALK_CATCHMENT_EXCLUDED_CONSTANT_FROM_FEEDER_DEPENDENT_DENOMINATOR",
        "technical_return_closure_used_for_to_rail": False,
        "municipal_work_od_downscaled": False,
        "resident_population_is_passenger_demand": False,
        "ridership_forecast": False,
        "weighted_composite_score": False,
        "exact_s8_phase_used": False,
        "exact_train_connection_wait_used": False,
        "missed_connection_probability_used": False,
        "delay_robustness_used": False,
        "full_gjt_calculated": False,
        "exact_timetable_constructed": False,
        "primary_selected": False,
        "runner_up_selected": False,
        "quantile_semantics": "NEAREST_RANK_P90_OVER_DECLARED_243_CASE_SENSITIVITY_GRID",
        "upstream_statuses": {
            "service_ready": service_val["status"],
            "access_equity": access_val["status"],
            "s8_phasing": s8_val["status"],
            "reduced_path_matrix": matrix_val["status"],
        },
        "lineage": {
            "service_ready_frontier": str(args.service_ready_frontier),
            "service_ready_frontier_sha256": sha256_path(args.service_ready_frontier),
            "service_ready_validation": str(args.service_ready_validation),
            "service_ready_validation_sha256": sha256_path(args.service_ready_validation),
            "access_validation": str(args.access_validation),
            "access_validation_sha256": sha256_path(args.access_validation),
            "population_units": str(args.population_units),
            "population_units_sha256": sha256_path(args.population_units),
            "anchors": str(args.anchors),
            "anchors_sha256": sha256_path(args.anchors),
            "proposed_catchments": str(args.proposed_catchments),
            "proposed_catchments_sha256": sha256_path(args.proposed_catchments),
            "existing_catchments": str(args.existing_catchments),
            "existing_catchments_sha256": sha256_path(args.existing_catchments),
            "route_universe": str(args.route_universe),
            "route_universe_sha256": sha256_path(args.route_universe),
            "scenario_mapping": str(args.scenario_mapping),
            "scenario_mapping_sha256": sha256_path(args.scenario_mapping),
            "s8_validation": str(args.s8_validation),
            "s8_validation_sha256": sha256_path(args.s8_validation),
            "path_matrix": str(args.path_matrix),
            "path_matrix_sha256": sha256_path(args.path_matrix),
            "matrix_validation": str(args.matrix_validation),
            "matrix_validation_sha256": sha256_path(args.matrix_validation),
            "sensitivity_config": str(args.sensitivity_config),
            "sensitivity_config_sha256": sha256_path(args.sensitivity_config),
            "base_output": str(args.base_output),
            "base_output_sha256": sha256_path(args.base_output),
            "timing_output": str(args.timing_output),
            "timing_output_sha256": sha256_path(args.timing_output),
        },
        "limitations": [
            "This is pre-phase generalized feeder-access screening, not full Passenger GJT.",
            "Building resident population is a potential access weight, not observed transit demand or ridership.",
            "Municipal work OD is not downscaled to buildings, stops or routes.",
            "The verified direct station walking catchment is excluded from the feeder-dependent denominator because those residents do not require a bus feeder to reach the hub.",
            "Average bus wait is half the uniform clockface headway as a screening assumption; exact S8-linked waiting is deferred.",
            "Exact S8 phase, rail IVT, missed-connection probability, delay robustness and exact vehicle blocks remain downstream.",
        ],
    }
    args.validation_output.parent.mkdir(parents=True, exist_ok=True)
    args.validation_output.write_text(json.dumps(validation, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(validation, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
