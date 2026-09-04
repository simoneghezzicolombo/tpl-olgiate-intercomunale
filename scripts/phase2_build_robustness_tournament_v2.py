#!/usr/bin/env python3
"""Materialise the exact Phase 2 robustness tournament V2.

Every already-certified exact candidate plan keeps its chosen public-facing
clockface phases. The tournament stresses aggregate route runtime, uncalibrated
stop dwell, S8 clock shift, transfer-walk friction and recovery. It recalculates
S8 scheduled-event match shares/gaps and exact common-hub vehicle blocks for
every stress cell.

The gate deliberately does not infer passenger route weights, modal share,
missed-connection probability or full GJT. It produces robust passenger-facing
Pareto frontiers but does not select PRIMARY or RUNNER-UP.
"""
from __future__ import annotations

import argparse
import csv
from decimal import Decimal
import gzip
import hashlib
import io
import itertools
import json
import math
from collections import Counter
from pathlib import Path
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import scripts.phase2_build_base_exact_timetables_v2 as exact_base
from src.phase2_exact_timetable_v2 import RouteCycle, materialise_route_trips, minimum_common_hub_blocks
from src.phase2_robustness_tournament_v2 import margin_gap_summary, nondominated_indices, weighted_cell_mean

D = Decimal
STATUS = "PASS_ROBUSTNESS_TOURNAMENT_V2_BUILD"
CONTRACT = "PHASE2_ROBUSTNESS_TOURNAMENT_V2"
HUB_ID = "rail:S01514"
MUNICIPALITY_CODES = ("097010", "097012", "097058", "097074", "097092")
REFERENCE_BUDGET = 111419.0


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
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
    raise ValueError(f"{field} must be true/false, got {value!r}")


def deterministic_gzip_writer(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = path.open("wb")
    gz = gzip.GzipFile(filename="", mode="wb", fileobj=raw, compresslevel=9, mtime=0)
    text = io.TextIOWrapper(gz, encoding="utf-8", newline="")
    return raw, text


def validate_upstream(args) -> tuple[dict, dict, dict, dict, dict, dict]:
    exact = loadj(args.exact_validation)
    access = loadj(args.access_validation)
    current = loadj(args.current_baseline)
    robust = loadj(args.robustness_config)
    transfer = loadj(args.transfer_config)
    service = loadj(args.service_config)

    if exact.get("status") != "PASS_BASE_EXACT_TIMETABLES_V2_BUILD":
        raise ValueError("Base Exact Timetables V2 is not certified")
    if exact.get("lineage", {}).get("plan_output_sha256") != sha(args.exact_plans):
        raise ValueError("Exact plan hash mismatch")
    if exact.get("exact_timetable_constructed") is not True or exact.get("joint_vehicle_block_timetable_feasibility_evaluated") is not True:
        raise ValueError("Exact candidate plans are not timetable/block certified")
    if exact.get("primary_selected") is not False or exact.get("runner_up_selected") is not False:
        raise ValueError("Exact upstream already selected a final recommendation")

    if access.get("status") != "PASS_ACCESS_EQUITY_V2_BUILD" or access.get("hub_boarding_access_included") is not True:
        raise ValueError("Hub-corrected Access Equity V2 is required")
    if access.get("lineage", {}).get("scenario_output_sha256") != sha(args.access):
        raise ValueError("Access output hash mismatch")
    if access.get("hub_access_proxy_cluster_id") != "EX_039":
        raise ValueError("Unexpected certified hub-access proxy")

    if current.get("status") != "PASS_CURRENT_ACCESS_LOWER_BOUND_V2_BUILD":
        raise ValueError("Current-service access lower bound is not certified")
    if current.get("full_current_service_spatial_baseline_complete") is not False:
        raise ValueError("Current-service lower bound was unexpectedly promoted to complete baseline")

    if robust.get("contract") != CONTRACT or robust.get("status") != "ASSUMPTION_SENSITIVITY_GRID_NOT_EMPIRICAL_INTERVAL":
        raise ValueError("Unexpected robustness sensitivity contract")
    if robust.get("full_gjt_calculated") is not False or robust.get("selection_in_this_gate") is not False:
        raise ValueError("Robustness config violates epistemic/selection boundary")
    if transfer.get("contract") != "PHASE2_S8_PHASING_SENSITIVITY_V2" or transfer.get("status") != "ASSUMPTION_SENSITIVITY_NOT_EMPIRICAL_INTERVAL":
        raise ValueError("Declared S8 transfer sensitivity profiles are required")
    if service.get("contract") != "PHASE2_SERVICE_POLICY_DESIGN_SPACE_V2":
        raise ValueError("Service-policy sensitivity source is not certified")
    if [int(v) for v in service.get("recovery_min", [])] != [5, 10, 15]:
        raise ValueError("Unexpected recovery sensitivity values")

    # Recheck exact routing/S8 lineage against the same files used for stress recomputation.
    lineage = exact.get("lineage", {})
    for label, expected, path in (
        ("scenario mapping", lineage.get("scenario_mapping_sha256"), args.scenario_mapping),
        ("route universe", lineage.get("route_universe_sha256"), args.route_universe),
        ("path matrix", lineage.get("path_matrix_sha256"), args.path_matrix),
        ("S8 events", lineage.get("s8_events_sha256"), args.s8_events),
        ("work direction summary", lineage.get("work_direction_summary_sha256"), args.work_direction_summary),
    ):
        if expected != sha(path):
            raise ValueError(f"Exact upstream hash mismatch for {label}")
    return exact, access, current, robust, transfer, service


def load_exact_plans(path: Path, expected_count: int):
    rows = []
    with path.open(encoding="utf-8-sig", newline="") as f:
        r = csv.DictReader(f)
        fields = list(r.fieldnames or [])
        required = {
            "plan_id", "scenario_id", "topology_family", "uniform_headway_min", "span_start_min", "span_end_min",
            "span_minutes", "calendar_id", "annual_service_days", "exact_annual_bus_km", "exact_fleet_recovery15",
            "candidate_route_phases_json", "s8_public_route_count", "public_population_coverage_share_10min",
            "public_worst_municipality_coverage_share_10min", "public_structurally_addressable_worker_od_mass_upper_bound",
            "public_explicit_existing_stop_count", "public_explicit_proposed_stop_count", "public_explicit_field_check_pending_count",
            "exact_timetable_constructed", "joint_vehicle_block_timetable_feasibility_evaluated",
            "final_service_policy_selected", "final_topology_selected", "primary_selected", "runner_up_selected",
        }
        if not required <= set(fields):
            raise ValueError(f"Exact plan schema missing {sorted(required-set(fields))}")
        for row in r:
            if row["plan_id"] in {x["plan_id"] for x in rows}:
                raise ValueError(f"Duplicate exact plan {row['plan_id']}")
            if float(row["exact_annual_bus_km"]) > REFERENCE_BUDGET + 1e-6:
                raise ValueError(f"Exact plan exceeds reference budget: {row['plan_id']}")
            if not bool_text(row["exact_timetable_constructed"], field="exact_timetable_constructed"):
                raise ValueError("Exact plan lost timetable status")
            if not bool_text(row["joint_vehicle_block_timetable_feasibility_evaluated"], field="joint_vehicle_block_timetable_feasibility_evaluated"):
                raise ValueError("Exact plan lost block status")
            if any(bool_text(row[k], field=k) for k in ("final_service_policy_selected", "final_topology_selected", "primary_selected", "runner_up_selected")):
                raise ValueError("Exact plan contains forbidden final selection")
            rows.append(row)
    if len(rows) != expected_count:
        raise ValueError(f"Expected {expected_count} exact plans, got {len(rows)}")
    return rows, fields


def load_access_subset(path: Path, wanted: set[str]):
    out = {}
    required = {
        "scenario_id", "topology_family",
        "public_population_coverage_share_5min", "public_population_coverage_share_8min", "public_population_coverage_share_10min",
        "public_worst_municipality_coverage_share_5min", "public_worst_municipality_coverage_share_8min", "public_worst_municipality_coverage_share_10min",
        *{f"public_municipality_{code}_coverage_share_10min" for code in MUNICIPALITY_CODES},
    }
    with gzip.open(path, "rt", encoding="utf-8-sig", newline="") as f:
        r = csv.DictReader(f)
        if not required <= set(r.fieldnames or []):
            raise ValueError(f"Access schema missing {sorted(required-set(r.fieldnames or []))}")
        for row in r:
            sid = row["scenario_id"]
            if sid not in wanted:
                continue
            if sid in out:
                raise ValueError(f"Duplicate access scenario {sid}")
            out[sid] = {k: row[k] for k in required}
    if set(out) != wanted:
        raise ValueError(f"Missing access rows for {len(wanted-set(out))} exact scenarios")
    return out


def stress_grid(robust: dict, transfer: dict):
    runtimes = [D(str(v)) for v in robust["runtime_multiplier"]]
    dwells = [D(str(v)) for v in robust["dwell_per_nonhub_public_stop_occurrence_min"]]
    shifts = [D(str(v)) for v in robust["rail_event_clock_shift_min"]]
    profiles = []
    for row in transfer["transfer_profiles"]:
        profiles.append((str(row["profile_id"]), D(str(row["transfer_walk_min"]))))
    grid = list(itertools.product(runtimes, dwells, shifts, profiles))
    if len(grid) != int(robust["expected_stress_case_count_per_plan"]):
        raise ValueError("Robustness factorial size mismatch")
    return grid


def stressed_cycle(evidence, runtime_multiplier: Decimal, dwell_per_stop: Decimal) -> tuple[RouteCycle, int]:
    anchors = evidence.anchors
    nonhub_public_stop_occurrences = sum(anchor != HUB_ID for anchor in anchors[1:])
    dwell_total = dwell_per_stop * nonhub_public_stop_occurrences
    base = evidence.cycle
    public_runtime = base.public_runtime_min * runtime_multiplier + dwell_total
    cycle_runtime = base.cycle_runtime_min * runtime_multiplier + dwell_total
    cycle = RouteCycle(
        route_id=base.route_id,
        public_runtime_min=public_runtime,
        cycle_runtime_min=cycle_runtime,
        cycle_distance_km=base.cycle_distance_km,
        public_returns_to_hub=base.public_returns_to_hub,
    )
    cycle.validate()
    return cycle, nonhub_public_stop_occurrences


def evaluate_case(*, plan, route_evidence, phases, rail_events, weights, runtime_multiplier, dwell_per_stop, rail_shift, transfer_walk, recoveries):
    headway = int(plan["uniform_headway_min"])
    span_start = int(plan["span_start_min"])
    span_end = int(plan["span_end_min"])
    route_rows = []
    all_trips = []
    vehicle_cycle_minutes = D(0)

    shifted_by_direction = {}
    for direction in ("MILANO", "LECCO"):
        events = [event for event in rail_events if event.direction == direction]
        arrivals = tuple(sorted(event.arrival_min + rail_shift for event in events if D(span_start) <= event.arrival_min + rail_shift < D(span_end)))
        departures = tuple(sorted(event.departure_min + rail_shift for event in events))
        shifted_by_direction[direction] = (arrivals, departures)

    for evidence in route_evidence:
        stressed, stop_occurrences = stressed_cycle(evidence, runtime_multiplier, dwell_per_stop)
        phase = phases[stressed.route_id]
        trips = materialise_route_trips(
            stressed,
            phase_min=phase,
            headway_min=headway,
            span_start_min=span_start,
            span_end_min=span_end,
        )
        all_trips.extend(trips)
        vehicle_cycle_minutes += stressed.cycle_runtime_min * len(trips)
        departures_bus = tuple(trip.departure_min for trip in trips)
        public_returns = tuple(
            trip.public_service_end_min
            for trip in trips
            if stressed.public_returns_to_hub and D(span_start) <= trip.public_service_end_min < D(span_end)
        )
        cells = []
        source_events = matched_events = unmatched_events = 0
        for direction in ("MILANO", "LECCO"):
            rail_arrivals, rail_departures = shifted_by_direction[direction]
            r2b = margin_gap_summary(rail_arrivals, departures_bus, margin_min=transfer_walk)
            source_events += r2b.source_count
            matched_events += r2b.matched_count
            unmatched_events += r2b.unmatched_count
            cells.append((float(weights.return_rail_to_bus[direction]), r2b.mean_gap_min))
            if stressed.public_returns_to_hub:
                b2r = margin_gap_summary(public_returns, rail_departures, margin_min=transfer_walk)
                source_events += b2r.source_count
                matched_events += b2r.matched_count
                unmatched_events += b2r.unmatched_count
                cells.append((float(weights.outbound_bus_to_rail[direction]), b2r.mean_gap_min))
        route_rows.append({
            "route_id": stressed.route_id,
            "source_events": source_events,
            "matched_events": matched_events,
            "unmatched_events": unmatched_events,
            "weighted_mean_gap_min": weighted_cell_mean(cells),
            "incomplete": unmatched_events > 0,
            "nonhub_public_stop_occurrences": stop_occurrences,
        })

    fleets = {}
    for recovery in recoveries:
        fleet, _ = minimum_common_hub_blocks(all_trips, recovery_min=recovery)
        fleets[recovery] = fleet
    source_events = sum(row["source_events"] for row in route_rows)
    matched_events = sum(row["matched_events"] for row in route_rows)
    unmatched_events = sum(row["unmatched_events"] for row in route_rows)
    finite = [float(row["weighted_mean_gap_min"]) for row in route_rows if row["weighted_mean_gap_min"] is not None]
    return {
        "incomplete_route_count": sum(bool(row["incomplete"]) for row in route_rows),
        "required_connection_source_event_count": source_events,
        "matched_connection_event_count": matched_events,
        "unmatched_connection_event_count": unmatched_events,
        "connection_match_share": (matched_events / source_events) if source_events else 0.0,
        "route_unweighted_mean_gap_min": (sum(finite) / len(finite)) if finite else None,
        "worst_route_weighted_mean_gap_min": max(finite) if finite else None,
        "fleet_recovery5": fleets[5],
        "fleet_recovery10": fleets[10],
        "fleet_recovery15": fleets[15],
        "vehicle_cycle_hours_per_service_day": float(vehicle_cycle_minutes / D(60)),
    }


def quantile_nearest(values: list[float], p: float) -> float:
    if not values:
        return math.nan
    rows = sorted(values)
    idx = max(0, math.ceil(p * len(rows)) - 1)
    return rows[idx]


def main() -> int:
    p = argparse.ArgumentParser()
    for name in (
        "exact_plans", "exact_validation", "access", "access_validation", "current_baseline",
        "robustness_config", "transfer_config", "service_config", "scenario_mapping", "route_universe",
        "path_matrix", "s8_events", "work_direction_summary", "summary_output", "stress_output",
        "frontier_output", "validation",
    ):
        p.add_argument("--" + name.replace("_", "-"), dest=name, type=Path, required=True)
    args = p.parse_args()

    exact_validation, access_validation, current, robust, transfer, service = validate_upstream(args)
    plans, source_fields = load_exact_plans(args.exact_plans, int(exact_validation["exact_timetable_plan_count"]))
    scenario_ids = {row["scenario_id"] for row in plans}
    access = load_access_subset(args.access, scenario_ids)
    scenario_routes = exact_base.load_scenario_routes(args.scenario_mapping, scenario_ids)
    route_ids = {route_id for ids in scenario_routes.values() for route_id in ids}
    matrix = exact_base.load_matrix(args.path_matrix)
    route_evidence = exact_base.load_route_evidence(args.route_universe, route_ids, matrix)
    rail_events = exact_base.load_rail_events(args.s8_events)
    weights = exact_base.load_work_weights(args.work_direction_summary)
    recoveries = tuple(int(v) for v in service["recovery_min"])
    grid = stress_grid(robust, transfer)

    current10 = current["access_lower_bound_by_threshold"]["10"]
    current_worst_lb = float(current10["worst_municipality_coverage_share_lower_bound"])
    current_municipal_lb = {
        code: float(current10["municipality_coverage_share_lower_bound"][code]["share"])
        for code in MUNICIPALITY_CODES
    }

    stress_fields = [
        "plan_id", "scenario_id", "topology_family", "runtime_multiplier",
        "dwell_per_nonhub_public_stop_occurrence_min", "rail_event_clock_shift_min",
        "transfer_profile_id", "transfer_walk_min", "incomplete_route_count",
        "required_connection_source_event_count", "matched_connection_event_count",
        "unmatched_connection_event_count", "connection_match_share",
        "route_unweighted_mean_gap_min", "worst_route_weighted_mean_gap_min",
        "fleet_recovery5", "fleet_recovery10", "fleet_recovery15",
        "vehicle_cycle_hours_per_service_day", "stress_case_is_empirical_probability_draw",
    ]
    raw, text = deterministic_gzip_writer(args.stress_output)
    stress_writer = csv.DictWriter(text, fieldnames=stress_fields, lineterminator="\n")
    stress_writer.writeheader()

    summaries = []
    total_stress_rows = 0
    try:
        for plan in sorted(plans, key=lambda r: r["plan_id"]):
            sid = plan["scenario_id"]
            a = access[sid]
            if a["topology_family"] != plan["topology_family"]:
                raise ValueError(f"Access family mismatch for {sid}")
            route_ids_plan = scenario_routes[sid]
            phases = json.loads(plan["candidate_route_phases_json"])
            if set(phases) != set(route_ids_plan):
                raise ValueError(f"Candidate phase vector does not match public routes for {plan['plan_id']}")
            if len(route_ids_plan) != int(plan["s8_public_route_count"]):
                raise ValueError(f"Route count mismatch for {plan['plan_id']}")
            evidences = [route_evidence[route_id] for route_id in route_ids_plan]

            case_rows = []
            for runtime_multiplier, dwell, rail_shift, profile in grid:
                profile_id, transfer_walk = profile
                result = evaluate_case(
                    plan=plan,
                    route_evidence=evidences,
                    phases={str(k): int(v) for k, v in phases.items()},
                    rail_events=rail_events,
                    weights=weights,
                    runtime_multiplier=runtime_multiplier,
                    dwell_per_stop=dwell,
                    rail_shift=rail_shift,
                    transfer_walk=transfer_walk,
                    recoveries=recoveries,
                )
                stress_row = {
                    "plan_id": plan["plan_id"],
                    "scenario_id": sid,
                    "topology_family": plan["topology_family"],
                    "runtime_multiplier": format(runtime_multiplier, "f"),
                    "dwell_per_nonhub_public_stop_occurrence_min": format(dwell, "f"),
                    "rail_event_clock_shift_min": format(rail_shift, "f"),
                    "transfer_profile_id": profile_id,
                    "transfer_walk_min": format(transfer_walk, "f"),
                    **{k: ("" if v is None else (f"{v:.9f}" if isinstance(v, float) else v)) for k, v in result.items()},
                    "stress_case_is_empirical_probability_draw": "false",
                }
                stress_writer.writerow(stress_row)
                total_stress_rows += 1
                case_rows.append(result)

            if len(case_rows) != int(robust["expected_stress_case_count_per_plan"]):
                raise AssertionError("Per-plan stress case count mismatch")
            match_shares = [float(row["connection_match_share"]) for row in case_rows]
            unmatched = [int(row["unmatched_connection_event_count"]) for row in case_rows]
            incomplete_routes = [int(row["incomplete_route_count"]) for row in case_rows]
            mean_gaps = [float(row["route_unweighted_mean_gap_min"]) for row in case_rows if row["route_unweighted_mean_gap_min"] is not None]
            worst_gaps = [float(row["worst_route_weighted_mean_gap_min"]) for row in case_rows if row["worst_route_weighted_mean_gap_min"] is not None]
            fleet15 = [int(row["fleet_recovery15"]) for row in case_rows]
            hours = [float(row["vehicle_cycle_hours_per_service_day"]) for row in case_rows]
            baseline_fleet15 = int(plan["exact_fleet_recovery15"])

            known_regressions = [
                code for code in MUNICIPALITY_CODES
                if float(a[f"public_municipality_{code}_coverage_share_10min"]) < current_municipal_lb[code] - 1e-9
            ]
            hard_nonregression = float(a["public_worst_municipality_coverage_share_10min"]) >= current_worst_lb - 1e-9
            summaries.append({
                "plan_id": plan["plan_id"],
                "scenario_id": sid,
                "topology_family": plan["topology_family"],
                "uniform_headway_min": int(plan["uniform_headway_min"]),
                "span_id": plan["span_id"],
                "span_minutes": int(plan["span_minutes"]),
                "calendar_id": plan["calendar_id"],
                "annual_service_days": int(plan["annual_service_days"]),
                "exact_annual_bus_km": float(plan["exact_annual_bus_km"]),
                "public_route_count": int(plan["s8_public_route_count"]),
                "public_population_coverage_share_5min": float(a["public_population_coverage_share_5min"]),
                "public_population_coverage_share_8min": float(a["public_population_coverage_share_8min"]),
                "public_population_coverage_share_10min": float(a["public_population_coverage_share_10min"]),
                "public_worst_municipality_coverage_share_5min": float(a["public_worst_municipality_coverage_share_5min"]),
                "public_worst_municipality_coverage_share_8min": float(a["public_worst_municipality_coverage_share_8min"]),
                "public_worst_municipality_coverage_share_10min": float(a["public_worst_municipality_coverage_share_10min"]),
                "public_structurally_addressable_worker_od_mass_upper_bound": float(plan["public_structurally_addressable_worker_od_mass_upper_bound"]),
                "stress_case_count": len(case_rows),
                "stress_min_connection_match_share": min(match_shares),
                "stress_median_connection_match_share": statistics.median(match_shares),
                "stress_p10_connection_match_share": sorted(match_shares)[max(0, math.ceil(0.10*len(match_shares))-1)],
                "stress_max_unmatched_connection_event_count": max(unmatched),
                "stress_median_unmatched_connection_event_count": statistics.median(unmatched),
                "stress_max_incomplete_route_count": max(incomplete_routes),
                "stress_complete_all_routes_case_count": sum(value == 0 for value in incomplete_routes),
                "stress_complete_all_routes_case_share": sum(value == 0 for value in incomplete_routes) / len(incomplete_routes),
                "stress_median_route_unweighted_mean_gap_min": statistics.median(mean_gaps) if mean_gaps else math.inf,
                "stress_p90_route_unweighted_mean_gap_min": quantile_nearest(mean_gaps, 0.90),
                "stress_worst_route_weighted_mean_gap_min": max(worst_gaps) if worst_gaps else math.inf,
                "stress_max_fleet_recovery15": max(fleet15),
                "stress_fleet_recovery15_escalation_case_count": sum(v > baseline_fleet15 for v in fleet15),
                "stress_max_vehicle_cycle_hours_per_service_day": max(hours),
                "baseline_exact_fleet_recovery15": baseline_fleet15,
                "public_explicit_existing_stop_count": int(plan["public_explicit_existing_stop_count"]),
                "public_explicit_proposed_stop_count": int(plan["public_explicit_proposed_stop_count"]),
                "public_explicit_field_check_pending_count": int(plan["public_explicit_field_check_pending_count"]),
                "current_worst_municipality_access_lower_bound_10min": current_worst_lb,
                "hard_current_worst_municipality_lower_bound_nonregression_pass": hard_nonregression,
                "known_current_municipal_lower_bound_regression_count_10min": len(known_regressions),
                "known_current_municipal_lower_bound_regression_codes_10min_json": json.dumps(known_regressions, separators=(",", ":")),
                "full_current_service_baseline_complete": False,
                "weighted_composite_score_used": False,
                "full_gjt_calculated": False,
                "missed_connection_probability_inferred": False,
                "passenger_route_weights_inferred": False,
                "primary_selected": False,
                "runner_up_selected": False,
            })
    finally:
        text.close()
        raw.close()

    if total_stress_rows != len(plans) * int(robust["expected_stress_case_count_per_plan"]):
        raise AssertionError("Total robustness stress row count mismatch")

    eligible = [row for row in summaries if row["hard_current_worst_municipality_lower_bound_nonregression_pass"]]
    maximize = (
        "public_population_coverage_share_5min",
        "public_population_coverage_share_8min",
        "public_population_coverage_share_10min",
        "public_worst_municipality_coverage_share_5min",
        "public_worst_municipality_coverage_share_8min",
        "public_worst_municipality_coverage_share_10min",
        "public_structurally_addressable_worker_od_mass_upper_bound",
        "stress_min_connection_match_share",
        "span_minutes",
        "annual_service_days",
    )
    minimize = (
        "uniform_headway_min",
        "stress_max_unmatched_connection_event_count",
        "stress_worst_route_weighted_mean_gap_min",
    )
    unrestricted_idx = set(nondominated_indices(eligible, maximize=maximize, minimize=minimize))
    frequent_source = [row for row in eligible if row["uniform_headway_min"] <= 30]
    frequent_idx = set(nondominated_indices(frequent_source, maximize=maximize, minimize=minimize))
    frequent_ids = {frequent_source[i]["plan_id"] for i in frequent_idx}
    unrestricted_ids = {eligible[i]["plan_id"] for i in unrestricted_idx}

    for row in summaries:
        classes = []
        if row["plan_id"] in unrestricted_ids:
            classes.append("ROBUST_PASSENGER_UNRESTRICTED")
        if row["plan_id"] in frequent_ids:
            classes.append("ROBUST_PASSENGER_FREQUENT_30")
        row["robust_frontier_classes"] = ";".join(classes)
        row["robust_frontier_member"] = bool(classes)

    summary_fields = list(summaries[0])
    args.summary_output.parent.mkdir(parents=True, exist_ok=True)
    with args.summary_output.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=summary_fields, lineterminator="\n")
        w.writeheader()
        for row in sorted(summaries, key=lambda r: r["plan_id"]):
            w.writerow({k: (str(v).lower() if isinstance(v, bool) else ("" if isinstance(v, float) and not math.isfinite(v) else v)) for k, v in row.items()})

    frontier_rows = [row for row in summaries if row["robust_frontier_member"]]
    with args.frontier_output.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=summary_fields, lineterminator="\n")
        w.writeheader()
        for row in sorted(frontier_rows, key=lambda r: r["plan_id"]):
            w.writerow({k: (str(v).lower() if isinstance(v, bool) else ("" if isinstance(v, float) and not math.isfinite(v) else v)) for k, v in row.items()})

    family_counts = Counter(row["topology_family"] for row in frontier_rows)
    headway_counts = Counter(int(row["uniform_headway_min"]) for row in frontier_rows)
    validation = {
        "status": STATUS,
        "contract": CONTRACT,
        "exact_input_plan_count": len(plans),
        "eligible_hard_nonregression_plan_count": len(eligible),
        "stress_case_count_per_plan": int(robust["expected_stress_case_count_per_plan"]),
        "stress_row_count": total_stress_rows,
        "robust_passenger_unrestricted_frontier_count": len(unrestricted_ids),
        "robust_passenger_frequent30_frontier_count": len(frequent_ids),
        "robust_frontier_union_count": len(frontier_rows),
        "robust_frontier_unique_scenario_count": len({row["scenario_id"] for row in frontier_rows}),
        "robust_frontier_family_counts": dict(sorted(family_counts.items())),
        "robust_frontier_headway_counts": dict(sorted(headway_counts.items())),
        "dominance_axes": {"maximize": list(maximize), "minimize": list(minimize)},
        "runtime_multiplier_sensitivities": [float(v) for v in robust["runtime_multiplier"]],
        "dwell_per_stop_sensitivities_min": [float(v) for v in robust["dwell_per_nonhub_public_stop_occurrence_min"]],
        "rail_clock_shift_sensitivities_min": [float(v) for v in robust["rail_event_clock_shift_min"]],
        "transfer_profiles": [row["profile_id"] for row in transfer["transfer_profiles"]],
        "recovery_sensitivities_min": list(recoveries),
        "full_current_service_baseline_complete": False,
        "current_nonregression_semantics": current["non_regression_use"],
        "weighted_composite_score_used": False,
        "full_gjt_calculated": False,
        "missed_connection_probability_inferred": False,
        "passenger_route_weights_inferred": False,
        "topology_ranked": False,
        "service_policy_selected": False,
        "primary_selected": False,
        "runner_up_selected": False,
        "lineage": {
            "exact_plans_sha256": sha(args.exact_plans),
            "exact_validation_sha256": sha(args.exact_validation),
            "access_sha256": sha(args.access),
            "access_validation_sha256": sha(args.access_validation),
            "current_baseline_sha256": sha(args.current_baseline),
            "robustness_config_sha256": sha(args.robustness_config),
            "transfer_config_sha256": sha(args.transfer_config),
            "service_config_sha256": sha(args.service_config),
            "scenario_mapping_sha256": sha(args.scenario_mapping),
            "route_universe_sha256": sha(args.route_universe),
            "path_matrix_sha256": sha(args.path_matrix),
            "s8_events_sha256": sha(args.s8_events),
            "work_direction_summary_sha256": sha(args.work_direction_summary),
            "summary_output_sha256": sha(args.summary_output),
            "stress_output_sha256": sha(args.stress_output),
            "frontier_output_sha256": sha(args.frontier_output),
        },
        "epistemic_note": (
            "The robustness tournament uses a deterministic assumption grid, not an empirical probability distribution. "
            "It stress-tests the exact timetable phases against aggregate runtime scaling, per-stop dwell, S8 clock shifts, "
            "declared transfer-walk profiles and recovery. Scheduled-event match shares are not probabilities. Current-service "
            "access remains only a one-sided lower bound. No worker is allocated to a bus route and no full GJT is calculated."
        ),
    }
    args.validation.write_text(json.dumps(validation, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(validation, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
