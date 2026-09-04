#!/usr/bin/env python3
"""Construct exact clockface timetables for every BASE_UNRESTRICTED frontier plan.

This gate fixes one explicit minute-phase per public route, constructs every
public departure, verifies exact annual bus-km against the 111,419 km reference
budget and colours the resulting common-hub vehicle intervals into exact
minimum vehicle blocks for recovery sensitivities 5/10/15 minutes.

S8 phase choice is route-unweighted across public routes.  The certified 1,882
work reference is used only inside each route to weight Milano versus Lecco
transfer directions.  It is never allocated to routes.  Connection margins
0/2/5 minutes are an explicit robustness sensitivity and are not claimed to be
measured station walking times.

This stage selects candidate timetable phases for every candidate plan.  It does
NOT rank plans, select a topology/service policy, PRIMARY or RUNNER-UP.
"""
from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from decimal import Decimal
import gzip
import hashlib
import itertools
import json
import math
from pathlib import Path
import sys
from typing import Sequence

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.phase2_build_s8_phasing_v2 import load_rail_events
from scripts.phase2_build_s8_transfer_gap_envelope_v2 import load_work_weights
from src.phase2_exact_timetable_v2 import (
    RouteCycle,
    materialise_route_trips,
    minimum_common_hub_blocks,
    summarise_margin_gaps,
)

D = Decimal
STATUS = "PASS_BASE_EXACT_TIMETABLES_V2_BUILD"
CONTRACT = "PHASE2_BASE_EXACT_TIMETABLES_V2"
REFERENCE_BUDGET = D("111419")
RECOVERIES = (5, 10, 15)
CONNECTION_MARGINS = (0, 2, 5)


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def loadj(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def bool_text(value: str, *, field: str) -> bool:
    text = str(value).strip().lower()
    if text == "true":
        return True
    if text == "false":
        return False
    raise ValueError(f"{field} must be explicit true/false, got {value!r}")


def parse_json_list(value: str, *, field: str) -> list[str]:
    raw = json.loads(value)
    if not isinstance(raw, list) or any(not isinstance(item, str) or not item for item in raw):
        raise ValueError(f"Invalid JSON string list in {field}")
    return raw


@dataclass(frozen=True)
class RouteEvidence:
    cycle: RouteCycle
    anchors: tuple[str, ...]


@dataclass(frozen=True)
class MarginEvidence:
    incomplete: bool
    unmatched_events: int
    weighted_mean_gap_min: float | None


@dataclass(frozen=True)
class PhaseEvidence:
    phase_min: int
    departure_count: int
    daily_bus_km: Decimal
    margins: dict[int, MarginEvidence]


def validate_upstream(args) -> None:
    frontier = loadj(args.frontier_validation)
    s8 = loadj(args.s8_validation)
    matrix = loadj(args.matrix_validation)
    weights = loadj(args.work_weights_validation)
    if frontier.get("status") != "PASS_PLAN_LEVEL_FRONTIERS_V2_BUILD" or frontier.get("lineage", {}).get("output_sha256") != sha(args.frontier):
        raise ValueError("Plan-Level Frontiers V2 is not certified")
    if int(frontier.get("frontier_class_plan_counts", {}).get("BASE_UNRESTRICTED", -1)) != 394:
        raise ValueError("Unexpected BASE_UNRESTRICTED frontier count")
    if s8.get("status") != "PASS_S8_PHASE_OPPORTUNITY_V2_BUILD":
        raise ValueError("S8 Phase Opportunity V2 is not certified")
    lineage = s8.get("lineage", {})
    if lineage.get("route_universe_sha256") != sha(args.route_universe):
        raise ValueError("S8 route-universe hash mismatch")
    if lineage.get("scenario_route_mapping_sha256") != sha(args.scenario_mapping):
        raise ValueError("S8 scenario-route mapping hash mismatch")
    if lineage.get("s8_events_sha256") != sha(args.s8_events):
        raise ValueError("S8 event hash mismatch")
    if s8.get("phase_selected") is not False or s8.get("all_phases_retained_downstream") is not True:
        raise ValueError("Upstream S8 phase domain is not complete/unselected")
    if matrix.get("status") != "PASS_REDUCED_PATH_MATRIX_V2_BUILD" or matrix.get("lineage", {}).get("reduced_path_matrix_sha256") != sha(args.path_matrix):
        raise ValueError("Reduced Path Matrix V2 is not certified")
    if weights.get("status") != "PASS_S8_WORK_DIRECTION_WEIGHTS_V2_BUILD":
        raise ValueError("S8 work-direction weights V2 are not certified")
    if weights.get("lineage", {}).get("summary_sha256") != sha(args.work_direction_summary):
        raise ValueError("S8 work-direction summary hash mismatch")
    if float(weights.get("demand_weight_sum", -1)) != 1882.0:
        raise ValueError("Unexpected S8 worker direction reference")


def load_base_frontier(path: Path):
    rows = []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = list(reader.fieldnames or [])
        required = {
            "plan_id", "scenario_id", "topology_family", "uniform_headway_min", "span_id",
            "span_start_min", "span_end_min", "span_minutes", "calendar_id", "annual_service_days",
            "extension_share", "annual_bus_km", "fleet_lower_bound_recovery5", "fleet_lower_bound_recovery10",
            "fleet_lower_bound_recovery15", "plan_level_frontier_classes", "s8_phase_selected",
            "exact_timetable_constructed", "topology_ranked", "service_policy_selected", "primary_selected", "runner_up_selected",
        }
        if not required <= set(fields):
            raise ValueError(f"Frontier schema missing {sorted(required-set(fields))}")
        for row in reader:
            classes = set(str(row["plan_level_frontier_classes"]).split(";"))
            if "BASE_UNRESTRICTED" not in classes:
                continue
            if abs(float(row["extension_share"])) > 1e-12:
                raise ValueError("BASE_UNRESTRICTED row has positive extension share")
            if any(bool_text(row[field], field=field) for field in (
                "s8_phase_selected", "exact_timetable_constructed", "topology_ranked",
                "service_policy_selected", "primary_selected", "runner_up_selected",
            )):
                raise ValueError("Base frontier already contains forbidden downstream selection")
            rows.append(row)
    if len(rows) != 394:
        raise ValueError(f"Expected 394 base frontier plans, got {len(rows)}")
    if len({row["plan_id"] for row in rows}) != len(rows):
        raise ValueError("Duplicate plan ID in base frontier")
    return rows, fields


def load_scenario_routes(path: Path, wanted: set[str]) -> dict[str, list[str]]:
    out = {}
    with gzip.open(path, "rt", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"scenario_id", "public_route_ids_json", "extension_route_ids_json"}
        if not required <= set(reader.fieldnames or []):
            raise ValueError("Scenario-route mapping schema mismatch")
        for row in reader:
            sid = row["scenario_id"]
            if sid not in wanted:
                continue
            if sid in out:
                raise ValueError(f"Duplicate mapping scenario {sid}")
            public_ids = parse_json_list(row["public_route_ids_json"], field="public_route_ids_json")
            extension_ids = parse_json_list(row["extension_route_ids_json"], field="extension_route_ids_json")
            if not public_ids or len(public_ids) != len(set(public_ids)):
                raise ValueError(f"Invalid public route IDs for {sid}")
            # Base timetable deliberately ignores optional extension routes.
            out[sid] = public_ids
    if set(out) != wanted:
        raise ValueError(f"Missing route mapping for {len(wanted-set(out))} base scenarios")
    return out


def load_matrix(path: Path):
    lookup = {}
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"origin", "destination", "distance_km", "runtime_min"}
        if not required <= set(reader.fieldnames or []):
            raise ValueError("Path matrix schema mismatch")
        for row in reader:
            key = (row["origin"], row["destination"])
            if key in lookup:
                raise ValueError(f"Duplicate path leg {key}")
            lookup[key] = (D(row["distance_km"]), D(row["runtime_min"]))
    return lookup


def compute_route_from_anchors(route_id: str, anchors: tuple[str, ...], matrix) -> RouteCycle:
    if len(anchors) < 2:
        raise ValueError(f"Route {route_id} has fewer than two anchors")
    public_distance = D(0)
    public_runtime = D(0)
    for a, b in zip(anchors[:-1], anchors[1:]):
        if (a, b) not in matrix:
            raise ValueError(f"Route {route_id} missing path leg {a}->{b}")
        distance, runtime = matrix[(a, b)]
        public_distance += distance
        public_runtime += runtime
    cycle_distance, cycle_runtime = public_distance, public_runtime
    returns = anchors[0] == anchors[-1]
    if not returns:
        closure = (anchors[-1], anchors[0])
        if closure not in matrix:
            raise ValueError(f"Route {route_id} missing closure {closure}")
        distance, runtime = matrix[closure]
        cycle_distance += distance
        cycle_runtime += runtime
    cycle = RouteCycle(route_id, public_runtime, cycle_runtime, cycle_distance, returns)
    cycle.validate()
    return cycle


def load_route_evidence(path: Path, wanted: set[str], matrix) -> dict[str, RouteEvidence]:
    out = {}
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {
            "route_id", "public_runtime_min", "cycle_runtime_min", "public_service_returns_to_hub",
            "bus_to_rail_passenger_event_supported", "rail_to_bus_passenger_event_supported", "anchors_json",
        }
        if not required <= set(reader.fieldnames or []):
            raise ValueError("Route-universe schema mismatch")
        for row in reader:
            route_id = row["route_id"]
            if route_id not in wanted:
                continue
            if route_id in out:
                raise ValueError(f"Duplicate route universe row {route_id}")
            anchors_raw = json.loads(row["anchors_json"])
            if not isinstance(anchors_raw, list) or len(anchors_raw) < 2:
                raise ValueError(f"Invalid anchors_json for {route_id}")
            anchors = tuple(str(value) for value in anchors_raw)
            cycle = compute_route_from_anchors(route_id, anchors, matrix)
            if abs(cycle.public_runtime_min - D(row["public_runtime_min"])) > D("0.000001"):
                raise ValueError(f"Public runtime mismatch for {route_id}")
            if abs(cycle.cycle_runtime_min - D(row["cycle_runtime_min"])) > D("0.000001"):
                raise ValueError(f"Cycle runtime mismatch for {route_id}")
            returns = bool_text(row["public_service_returns_to_hub"], field="public_service_returns_to_hub")
            b2r = bool_text(row["bus_to_rail_passenger_event_supported"], field="bus_to_rail_passenger_event_supported")
            r2b = bool_text(row["rail_to_bus_passenger_event_supported"], field="rail_to_bus_passenger_event_supported")
            if returns != cycle.public_returns_to_hub or b2r != returns or not r2b:
                raise ValueError(f"Passenger support geometry mismatch for {route_id}")
            out[route_id] = RouteEvidence(cycle, anchors)
    if set(out) != wanted:
        raise ValueError(f"Missing {len(wanted-set(out))} route-universe rows")
    return out


def weighted_cell_mean(cells: Sequence[tuple[float, float | None]]) -> float | None:
    used = [(weight, value) for weight, value in cells if value is not None and weight > 0]
    if not used:
        return None
    return sum(weight * float(value) for weight, value in used) / sum(weight for weight, _ in used)


def phase_evidence(
    route: RouteCycle,
    *,
    phase: int,
    headway: int,
    span_start: int,
    span_end: int,
    rail_events,
    weights,
) -> PhaseEvidence:
    trips = materialise_route_trips(
        route, phase_min=phase, headway_min=headway, span_start_min=span_start, span_end_min=span_end
    )
    departures = tuple(trip.departure_min for trip in trips)
    public_returns = tuple(
        trip.public_service_end_min
        for trip in trips
        if route.public_returns_to_hub and D(span_start) <= trip.public_service_end_min < D(span_end)
    )
    margins = {}
    for margin in CONNECTION_MARGINS:
        unmatched = 0
        cells: list[tuple[float, float | None]] = []
        for direction in ("MILANO", "LECCO"):
            events = [event for event in rail_events if event.direction == direction]
            rail_arrivals = tuple(
                sorted(event.arrival_min for event in events if D(span_start) <= event.arrival_min < D(span_end))
            )
            rail_departures = tuple(sorted(event.departure_min for event in events))
            r2b = summarise_margin_gaps(rail_arrivals, departures, margin_min=margin)
            unmatched += r2b.unmatched_count
            cells.append((float(weights.return_rail_to_bus[direction]), r2b.mean_gap_min))
            if route.public_returns_to_hub:
                b2r = summarise_margin_gaps(public_returns, rail_departures, margin_min=margin)
                unmatched += b2r.unmatched_count
                cells.append((float(weights.outbound_bus_to_rail[direction]), b2r.mean_gap_min))
        margins[margin] = MarginEvidence(
            incomplete=unmatched > 0,
            unmatched_events=unmatched,
            weighted_mean_gap_min=weighted_cell_mean(cells),
        )
    return PhaseEvidence(
        phase_min=phase,
        departure_count=len(trips),
        daily_bus_km=route.cycle_distance_km * len(trips),
        margins=margins,
    )


def phase_vector_s8_objective(route_phase_rows: Sequence[PhaseEvidence]) -> tuple:
    objective = []
    for margin in reversed(CONNECTION_MARGINS):  # conservative 5, then 2, then raw 0
        evidence = [row.margins[margin] for row in route_phase_rows]
        incomplete_routes = sum(item.incomplete for item in evidence)
        unmatched = sum(item.unmatched_events for item in evidence)
        finite = [item.weighted_mean_gap_min for item in evidence if item.weighted_mean_gap_min is not None]
        worst = max(finite) if finite else math.inf
        mean = sum(finite) / len(finite) if finite else math.inf
        objective.extend((incomplete_routes, unmatched, worst, mean))
    return tuple(objective)


def exact_blocks(routes: Sequence[RouteCycle], phases: Sequence[int], *, headway: int, span_start: int, span_end: int, recovery: int):
    trips = []
    for route, phase in zip(routes, phases):
        trips.extend(materialise_route_trips(
            route, phase_min=phase, headway_min=headway, span_start_min=span_start, span_end_min=span_end
        ))
    return minimum_common_hub_blocks(trips, recovery_min=recovery)


def clock_text(value: Decimal) -> str:
    total_seconds = int((value * D(60)).to_integral_value())
    day, rem = divmod(total_seconds, 86400)
    hour, rem = divmod(rem, 3600)
    minute, second = divmod(rem, 60)
    prefix = f"+{day}d " if day else ""
    return f"{prefix}{hour:02d}:{minute:02d}:{second:02d}"


def main() -> int:
    parser = argparse.ArgumentParser()
    for name in (
        "frontier", "frontier_validation", "scenario_mapping", "route_universe", "s8_validation",
        "path_matrix", "matrix_validation", "s8_events", "work_direction_summary", "work_weights_validation",
        "plan_output", "trip_output", "validation",
    ):
        parser.add_argument("--" + name.replace("_", "-"), dest=name, type=Path, required=True)
    args = parser.parse_args()
    validate_upstream(args)

    plans, source_fields = load_base_frontier(args.frontier)
    scenario_ids = {row["scenario_id"] for row in plans}
    scenario_routes = load_scenario_routes(args.scenario_mapping, scenario_ids)
    route_ids = {route_id for ids in scenario_routes.values() for route_id in ids}
    matrix = load_matrix(args.path_matrix)
    route_evidence = load_route_evidence(args.route_universe, route_ids, matrix)
    rail_events = load_rail_events(args.s8_events)
    weights = load_work_weights(args.work_direction_summary)

    route_count_distribution = {}
    for ids in scenario_routes.values():
        route_count_distribution[len(ids)] = route_count_distribution.get(len(ids), 0) + 1
    max_route_count = max(route_count_distribution)
    # Current structural families are intentionally small-pattern networks. Keep
    # exact Cartesian phase search auditable; fail loudly if the search space is
    # later expanded beyond four simultaneous public patterns.
    if max_route_count > 4:
        raise ValueError(f"Exact V2 phase enumerator requires extension for route_count={max_route_count}")

    phase_cache: dict[tuple[str, int, int, int], tuple[PhaseEvidence, ...]] = {}
    output_rows = []
    trip_rows = []
    no_exact_budget_plan_ids = []
    phase_vectors_evaluated = 0
    budget_feasible_phase_vectors = 0
    exact_fleet_exceeds_lower_bound_count = 0

    for plan in plans:
        sid = plan["scenario_id"]
        route_ids_plan = scenario_routes[sid]
        routes = [route_evidence[route_id].cycle for route_id in route_ids_plan]
        headway = int(plan["uniform_headway_min"])
        span_start = int(plan["span_start_min"])
        span_end = int(plan["span_end_min"])
        service_days = int(plan["annual_service_days"])

        # Cross-check the scenario-level operational sums already attached to the plan.
        aggregate_distance = sum((route.cycle_distance_km for route in routes), D(0))
        aggregate_runtime = sum((route.cycle_runtime_min for route in routes), D(0))
        if abs(aggregate_distance - D(plan["expected_pattern_set_cycle_distance_km"])) > D("0.00001"):
            raise ValueError(f"Aggregate cycle distance mismatch for {plan['plan_id']}")
        if abs(aggregate_runtime - D(plan["expected_pattern_set_cycle_runtime_min"])) > D("0.00001"):
            raise ValueError(f"Aggregate cycle runtime mismatch for {plan['plan_id']}")

        per_route = []
        for route in routes:
            key = (route.route_id, headway, span_start, span_end)
            rows = phase_cache.get(key)
            if rows is None:
                rows = tuple(
                    phase_evidence(
                        route, phase=phase, headway=headway, span_start=span_start, span_end=span_end,
                        rail_events=rail_events, weights=weights,
                    )
                    for phase in range(headway)
                )
                phase_cache[key] = rows
            per_route.append(rows)

        best_s8 = None
        best_vectors = []
        evaluated_this_plan = 0
        budget_feasible_this_plan = 0
        for vector_rows in itertools.product(*per_route):
            evaluated_this_plan += 1
            phase_vectors_evaluated += 1
            exact_annual_km = sum((row.daily_bus_km for row in vector_rows), D(0)) * service_days
            if exact_annual_km > REFERENCE_BUDGET + D("0.000001"):
                continue
            budget_feasible_this_plan += 1
            budget_feasible_phase_vectors += 1
            objective = phase_vector_s8_objective(vector_rows)
            if best_s8 is None or objective < best_s8:
                best_s8 = objective
                best_vectors = [(vector_rows, exact_annual_km)]
            elif objective == best_s8:
                best_vectors.append((vector_rows, exact_annual_km))
        if not best_vectors:
            no_exact_budget_plan_ids.append(plan["plan_id"])
            continue

        chosen = None
        chosen_blocks15 = None
        for vector_rows, exact_annual_km in best_vectors:
            phases = tuple(row.phase_min for row in vector_rows)
            fleets = {}
            blocks15 = None
            for recovery in RECOVERIES:
                fleet, blocks = exact_blocks(
                    routes, phases, headway=headway, span_start=span_start, span_end=span_end, recovery=recovery
                )
                fleets[recovery] = fleet
                if recovery == 15:
                    blocks15 = blocks
            tie = (fleets[15], fleets[10], fleets[5], exact_annual_km, phases)
            if chosen is None or tie < chosen[0]:
                chosen = (tie, vector_rows, exact_annual_km, fleets)
                chosen_blocks15 = blocks15
        assert chosen is not None and chosen_blocks15 is not None
        _, vector_rows, exact_annual_km, fleets = chosen
        phases = tuple(row.phase_min for row in vector_rows)
        exact_daily_km = exact_annual_km / service_days
        exact_vehicle_cycle_hours_day = sum(
            route.cycle_runtime_min * row.departure_count for route, row in zip(routes, vector_rows)
        ) / D(60)
        lower_bound15 = int(plan["fleet_lower_bound_recovery15"])
        if fleets[15] > lower_bound15:
            exact_fleet_exceeds_lower_bound_count += 1

        aggregated_margin = {}
        for margin in CONNECTION_MARGINS:
            evidence = [row.margins[margin] for row in vector_rows]
            finite = [item.weighted_mean_gap_min for item in evidence if item.weighted_mean_gap_min is not None]
            aggregated_margin[margin] = {
                "complete_route_count": sum(not item.incomplete for item in evidence),
                "incomplete_route_count": sum(item.incomplete for item in evidence),
                "unmatched_event_count": sum(item.unmatched_events for item in evidence),
                "route_unweighted_mean_gap_min": (sum(finite) / len(finite)) if finite else None,
                "worst_route_weighted_mean_gap_min": max(finite) if finite else None,
            }

        out = dict(plan)
        out.update({
            "candidate_route_phases_json": json.dumps(dict(zip(route_ids_plan, phases)), sort_keys=True, separators=(",", ":")),
            "phase_vector_count_evaluated": evaluated_this_plan,
            "exact_budget_feasible_phase_vector_count": budget_feasible_this_plan,
            "exact_daily_bus_km": f"{exact_daily_km:.9f}",
            "exact_annual_bus_km": f"{exact_annual_km:.6f}",
            "continuous_model_annual_bus_km": plan["annual_bus_km"],
            "exact_minus_continuous_annual_bus_km": f"{exact_annual_km-D(plan['annual_bus_km']):.6f}",
            "exact_vehicle_cycle_hours_per_service_day": f"{exact_vehicle_cycle_hours_day:.9f}",
            "exact_fleet_recovery5": fleets[5],
            "exact_fleet_recovery10": fleets[10],
            "exact_fleet_recovery15": fleets[15],
            "exact_fleet_minus_lower_bound_recovery15": fleets[15] - lower_bound15,
            "explicit_trip_count_per_service_day": sum(row.departure_count for row in vector_rows),
            "connection_margin_sensitivity_min_json": json.dumps(list(CONNECTION_MARGINS), separators=(",", ":")),
            "candidate_timetable_phase_selection_rule": "LEXICOGRAPHIC_ROUTE_UNWEIGHTED_S8_ROBUSTNESS_MARGIN5_THEN2_THEN0__THEN_MIN_EXACT_FLEET__THEN_KM__THEN_PHASE_VECTOR",
            "candidate_s8_phases_materialised": "true",
            "joint_vehicle_block_timetable_feasibility_evaluated": "true",
            "exact_timetable_constructed": "true",
            "s8_phase_selected": "true",
            "final_service_policy_selected": "false",
            "final_topology_selected": "false",
            "primary_selected": "false",
            "runner_up_selected": "false",
        })
        for margin, metrics in aggregated_margin.items():
            for key, value in metrics.items():
                out[f"margin{margin}_{key}"] = "" if value is None else (f"{value:.9f}" if isinstance(value, float) else value)
        output_rows.append(out)

        block_by_trip = {
            (row.trip.route_id, row.trip.departure_min): row
            for row in chosen_blocks15
        }
        for route, phase_row in zip(routes, vector_rows):
            trips = materialise_route_trips(
                route, phase_min=phase_row.phase_min, headway_min=headway, span_start_min=span_start, span_end_min=span_end
            )
            for trip in trips:
                blocked = block_by_trip[(trip.route_id, trip.departure_min)]
                trip_rows.append({
                    "plan_id": plan["plan_id"],
                    "scenario_id": sid,
                    "topology_family": plan["topology_family"],
                    "route_id": route.route_id,
                    "phase_min": phase_row.phase_min,
                    "headway_min": headway,
                    "vehicle_id_recovery15": f"V{blocked.vehicle_index+1}",
                    "departure_min": f"{trip.departure_min:f}",
                    "departure_clock": clock_text(trip.departure_min),
                    "public_service_end_min": f"{trip.public_service_end_min:f}",
                    "public_service_end_clock": clock_text(trip.public_service_end_min),
                    "vehicle_return_hub_min": f"{trip.vehicle_return_hub_min:f}",
                    "vehicle_return_hub_clock": clock_text(trip.vehicle_return_hub_min),
                    "ready_after_recovery15_min": f"{blocked.ready_min:f}",
                    "ready_after_recovery15_clock": clock_text(blocked.ready_min),
                    "public_service_returns_to_hub": "true" if route.public_returns_to_hub else "false",
                    "candidate_timetable_not_final_recommendation": "true",
                })

    appended = [
        "candidate_route_phases_json", "phase_vector_count_evaluated", "exact_budget_feasible_phase_vector_count",
        "exact_daily_bus_km", "exact_annual_bus_km", "continuous_model_annual_bus_km",
        "exact_minus_continuous_annual_bus_km", "exact_vehicle_cycle_hours_per_service_day",
        "exact_fleet_recovery5", "exact_fleet_recovery10", "exact_fleet_recovery15",
        "exact_fleet_minus_lower_bound_recovery15", "explicit_trip_count_per_service_day",
        "connection_margin_sensitivity_min_json", "candidate_timetable_phase_selection_rule",
        "candidate_s8_phases_materialised", "final_service_policy_selected", "final_topology_selected",
    ]
    for margin in CONNECTION_MARGINS:
        appended.extend([
            f"margin{margin}_complete_route_count", f"margin{margin}_incomplete_route_count",
            f"margin{margin}_unmatched_event_count", f"margin{margin}_route_unweighted_mean_gap_min",
            f"margin{margin}_worst_route_weighted_mean_gap_min",
        ])
    plan_fields = list(source_fields)
    for field in appended:
        if field not in plan_fields:
            plan_fields.append(field)
    args.plan_output.parent.mkdir(parents=True, exist_ok=True)
    with args.plan_output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=plan_fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(output_rows)

    trip_fields = [
        "plan_id", "scenario_id", "topology_family", "route_id", "phase_min", "headway_min",
        "vehicle_id_recovery15", "departure_min", "departure_clock", "public_service_end_min",
        "public_service_end_clock", "vehicle_return_hub_min", "vehicle_return_hub_clock",
        "ready_after_recovery15_min", "ready_after_recovery15_clock", "public_service_returns_to_hub",
        "candidate_timetable_not_final_recommendation",
    ]
    with args.trip_output.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, compresslevel=9, mtime=0) as gz:
            import io
            with io.TextIOWrapper(gz, encoding="utf-8", newline="") as text:
                writer = csv.DictWriter(text, fieldnames=trip_fields, lineterminator="\n")
                writer.writeheader()
                writer.writerows(trip_rows)

    exact_plan_count = len(output_rows)
    frequent_count = sum(int(row["uniform_headway_min"]) <= 30 for row in output_rows)
    validation = {
        "status": STATUS,
        "contract": CONTRACT,
        "input_base_frontier_plan_count": len(plans),
        "exact_timetable_plan_count": exact_plan_count,
        "exact_budget_infeasible_plan_count": len(no_exact_budget_plan_ids),
        "exact_budget_infeasible_plan_ids": no_exact_budget_plan_ids[:50],
        "frequent_30min_or_better_exact_plan_count": frequent_count,
        "unique_scenario_count": len({row["scenario_id"] for row in output_rows}),
        "route_count_distribution_by_unique_scenario": dict(sorted(route_count_distribution.items())),
        "max_public_route_count": max_route_count,
        "unique_route_count_loaded": len(route_ids),
        "phase_vectors_evaluated": phase_vectors_evaluated,
        "budget_feasible_phase_vectors": budget_feasible_phase_vectors,
        "phase_metric_cache_count": len(phase_cache),
        "trip_row_count_recovery15_blocks": len(trip_rows),
        "exact_fleet_exceeds_aggregate_lower_bound_recovery15_plan_count": exact_fleet_exceeds_lower_bound_count,
        "reference_budget_annual_bus_km": float(REFERENCE_BUDGET),
        "recovery_sensitivities_min": list(RECOVERIES),
        "connection_margin_sensitivities_min": list(CONNECTION_MARGINS),
        "connection_margin_semantics": "ASSUMPTION_ROBUSTNESS_MINIMUM_TIME_BETWEEN_SOURCE_EVENT_AND_ONWARD_DEPARTURE; NOT_MEASURED_STATION_WALK_TIME",
        "phase_selection_semantics": "CANDIDATE_TIMETABLE_ROUTE_PHASES_SELECTED_WITHIN_EACH_PLAN; PLANS_NOT_RANKED",
        "route_weighting_applied": False,
        "worker_reference_assigned_to_routes": False,
        "direction_weight_reference_workers": 1882.0,
        "joint_vehicle_block_timetable_feasibility_evaluated": True,
        "candidate_s8_phases_materialised": True,
        "exact_timetable_constructed": True,
        "final_service_policy_selected": False,
        "final_topology_selected": False,
        "topology_ranked": False,
        "primary_selected": False,
        "runner_up_selected": False,
        "lineage": {
            "frontier_sha256": sha(args.frontier),
            "frontier_validation_sha256": sha(args.frontier_validation),
            "scenario_mapping_sha256": sha(args.scenario_mapping),
            "route_universe_sha256": sha(args.route_universe),
            "s8_validation_sha256": sha(args.s8_validation),
            "path_matrix_sha256": sha(args.path_matrix),
            "matrix_validation_sha256": sha(args.matrix_validation),
            "s8_events_sha256": sha(args.s8_events),
            "work_direction_summary_sha256": sha(args.work_direction_summary),
            "work_weights_validation_sha256": sha(args.work_weights_validation),
            "plan_output_sha256": sha(args.plan_output),
            "trip_output_sha256": sha(args.trip_output),
        },
    }
    args.validation.write_text(json.dumps(validation, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(validation, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
