#!/usr/bin/env python3
"""Corrected Stage-D exact timetable integration surface.

This stage reuses the efficient exhaustive daily phase engine, but applies the
current certified continuous-quality target semantics and re-evaluates every
budget-qualified Stage-C context after exact trip materialisation.  It does not
select a budget, calendar, recovery, topology, PRIMARY or RUNNER-UP.
"""
from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
import gzip
import hashlib
import io
import itertools
import json
import math
from pathlib import Path
from typing import Mapping, Sequence

from src.phase2_exact_timetable_optimizer_v2 import (
    RECOVERIES,
    RouteInput,
    clockface_times,
    evaluate_phase_vector,
    exact_vehicle_blocks,
    load_profiles,
    precompute_route_phase_cells,
    rail_event_index,
    strict_bool,
)

STATUS = "PASS_PHASE2_STAGE_D_EXACT_TIMETABLE_INTEGRATION_FIX_V2"
CONTRACT = "PHASE2_BUDGET_QUALIFIED_EXACT_CLOCKFACE_TIMETABLE_V2"
TIMETABLE_ID_PREFIX = "D4FIX2_"
EPS = 1e-8


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
    writer = csv.DictWriter(text, fieldnames=list(fields), lineterminator="\n", extrasaction="ignore")
    writer.writeheader()
    return raw, text, writer


def stable_timetable_id(stage_d_input_id: str, phases: Sequence[int]) -> str:
    payload = json.dumps({"stage_d_input_id": stage_d_input_id, "phases": list(phases)}, sort_keys=True, separators=(",", ":"))
    return TIMETABLE_ID_PREFIX + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def load_budget_caps(validation: dict, passenger_frontier: Path) -> dict[str, float]:
    """Load the declared budget set without selecting a reference envelope.

    Legacy V2 validations expose a ``budget_summary``.  The RT-001 lossless
    validation instead closes its lineage to the budget-envelope artifact, while
    every certified Passenger Utility row carries its own cap.  In that case the
    complete set is derived from the frontier and checked for within-suffix
    consistency.
    """
    result = {
        str(suffix): float(row["cap_annual_bus_km"])
        for suffix, row in validation.get("budget_summary", {}).items()
    }
    for row in read_gzip_csv(passenger_frontier):
        suffix = str(row["budget_suffix"])
        cap = float(row["budget_cap_annual_bus_km"])
        previous = result.setdefault(suffix, cap)
        if not math.isclose(previous, cap, rel_tol=0.0, abs_tol=EPS):
            raise ValueError(f"Inconsistent cap for budget {suffix}: {previous} != {cap}")
    if not result:
        raise ValueError("No budget envelopes represented")
    expected_count = validation.get("budget_count")
    if expected_count is not None and len(result) != int(expected_count):
        raise ValueError(f"Budget count mismatch: {len(result)} != {expected_count}")
    return dict(sorted(result.items()))


def load_s8_events(path: Path):
    rows = list(read_csv(path))
    if len(rows) != 74:
        raise ValueError(f"Expected 74 frozen S8 events, got {len(rows)}")
    if any(str(r.get("epistemic_status")) != "DERIVED_FROM_LIVE_OFFICIAL_GTFS" for r in rows):
        raise ValueError("S8 event lost official-GTFS epistemic status")
    if sum(str(r["direction"]).upper() == "MILANO" for r in rows) != 37:
        raise ValueError("Expected 37 MILANO S8 events")
    if sum(str(r["direction"]).upper() == "LECCO" for r in rows) != 37:
        raise ValueError("Expected 37 LECCO S8 events")
    return rows


def load_matrix_distances(path: Path) -> dict[tuple[str, str], float]:
    result = {}
    for row in read_csv(path):
        key = (str(row["origin"]), str(row["destination"]))
        if key in result:
            raise ValueError(f"Duplicate path-matrix leg {key}")
        value = float(row["distance_km"])
        if not math.isfinite(value) or value <= 0:
            raise ValueError(f"Invalid distance for {key}")
        result[key] = value
    if not result:
        raise ValueError("Empty reduced path matrix")
    return result


@dataclass(frozen=True)
class RouteEvidence:
    route: RouteInput
    cycle_distance_km: float


@dataclass(frozen=True)
class PlanContext:
    context_id: str
    plan_id: str
    budget_suffix: str
    budget_cap: float
    calendar_id: str
    annual_service_days: int
    continuous_annual_bus_km: float
    exact_budget_phase_feasibility_class: str
    recovered_from_continuous_hard_filter: bool


@dataclass(frozen=True)
class VectorEvidence:
    phases: tuple[int, ...]
    robust_min_transfer_quality: float
    robust_unweighted_mean_transfer_quality: float
    exact_daily_bus_km: float

    @property
    def objective_key(self):
        return (
            self.robust_min_transfer_quality,
            self.robust_unweighted_mean_transfer_quality,
            *(-p for p in self.phases),
        )


def load_route_evidence(
    route_path: Path,
    distances: Mapping[tuple[str, str], float],
    expected_route_count: int,
) -> dict[str, RouteEvidence]:
    result = {}
    for row in read_csv(route_path):
        route_id = str(row["route_id"])
        anchors = json.loads(row["anchors_json"])
        if not isinstance(anchors, list) or len(anchors) < 2 or str(anchors[0]) != "rail:S01514":
            raise ValueError(f"Invalid route anchors {route_id}")
        public_distance = 0.0
        for a, b in zip(anchors[:-1], anchors[1:]):
            public_distance += distances[(str(a), str(b))]
        public_returns = str(anchors[-1]) == str(anchors[0])
        cycle_distance = public_distance
        if not public_returns:
            cycle_distance += distances[(str(anchors[-1]), str(anchors[0]))]
        route = RouteInput(
            route_id=route_id,
            public_runtime_min=float(row["public_runtime_min"]),
            cycle_runtime_min=float(row["cycle_runtime_min"]),
            public_service_starts_at_hub=strict_bool(row["public_service_starts_at_hub"]),
            public_service_returns_to_hub=strict_bool(row["public_service_returns_to_hub"]),
            vehicle_closure_added=strict_bool(row["vehicle_closure_added"]),
            rail_to_bus_passenger_event_supported=strict_bool(row["rail_to_bus_passenger_event_supported"]),
            bus_to_rail_passenger_event_supported=strict_bool(row["bus_to_rail_passenger_event_supported"]),
        )
        route.validate()
        if route.public_service_returns_to_hub != public_returns:
            raise ValueError(f"Route return geometry mismatch {route_id}")
        if route_id in result:
            raise ValueError(f"Duplicate route {route_id}")
        result[route_id] = RouteEvidence(route, cycle_distance)
    if len(result) != expected_route_count:
        raise ValueError(f"Stage-D route count mismatch: {len(result)} != {expected_route_count}")
    return result


def load_passenger_contexts(
    path: Path,
    caps: Mapping[str, float],
    expected_context_count: int,
) -> dict[str, PlanContext]:
    result = {}
    for row in read_gzip_csv(path):
        budget = str(row["budget_suffix"])
        if budget not in caps:
            raise ValueError(f"Unknown budget {budget}")
        context_id = f"{budget}|{row['plan_id']}"
        if context_id in result:
            raise ValueError(f"Duplicate context {context_id}")
        result[context_id] = PlanContext(
            context_id=context_id,
            plan_id=str(row["plan_id"]),
            budget_suffix=budget,
            budget_cap=float(caps[budget]),
            calendar_id=str(row["calendar_id"]),
            annual_service_days=int(row["annual_service_days"]),
            continuous_annual_bus_km=float(
                row.get("continuous_annual_bus_km_audit_only") or row["annual_bus_km"]
            ),
            exact_budget_phase_feasibility_class=str(
                row.get("exact_budget_phase_feasibility_class") or "LEGACY_V2_NOT_RECORDED"
            ),
            recovered_from_continuous_hard_filter=(
                strict_bool(row["recovered_from_continuous_hard_filter"])
                if row.get("recovered_from_continuous_hard_filter") not in (None, "")
                else False
            ),
        )
    if len(result) != expected_context_count:
        raise ValueError(f"Stage-C context count mismatch: {len(result)} != {expected_context_count}")
    return result


def validate_upstream(args) -> tuple[dict, dict, dict]:
    manifest = read_json(args.manifest_validation)
    passenger = read_json(args.passenger_validation)
    budget = read_json(args.budget_validation)
    matrix = read_json(args.matrix_validation)
    s8 = read_json(args.s8_validation)
    manifest_status_contracts = {
        "PASS_PHASE2_STAGE_D_INPUT_MANIFEST_V2": "PHASE2_LOSSLESS_DAILY_TIMING_INPUT_MANIFEST_V2",
        "PASS_PHASE2_STAGE_D_INPUT_MANIFEST_RT001_V3": "PHASE2_LOSSLESS_DAILY_TIMING_INPUT_MANIFEST_RT001_V3",
    }
    if manifest.get("status") not in manifest_status_contracts:
        raise ValueError("Stage-D input manifest is not certified")
    if manifest.get("contract") != manifest_status_contracts[manifest["status"]]:
        raise ValueError("Unexpected Stage-D manifest contract")
    if manifest["status"] == "PASS_PHASE2_STAGE_D_INPUT_MANIFEST_RT001_V3":
        if manifest.get("rt001_repair") is not True:
            raise ValueError("RT-001 manifest lost repair identity")
        if manifest.get("exact_budget_eligibility_repaired_upstream") is not True:
            raise ValueError("RT-001 manifest lacks repaired exact-budget eligibility")
    for key in (
        "stage_d_daily_timing_input_count",
        "passenger_plan_context_count_represented",
        "naive_joint_phase_vector_count_sum",
        "used_public_route_count",
    ):
        if int(manifest.get(key, 0)) <= 0:
            raise ValueError(f"Stage-D manifest lacks positive dynamic cardinality {key}")
    if manifest.get("lineage", {}).get("timing_output_sha256") != sha256_path(args.timing_inputs):
        raise ValueError("Stage-D timing-input hash mismatch")
    if manifest.get("lineage", {}).get("route_output_sha256") != sha256_path(args.route_inputs):
        raise ValueError("Stage-D route-input hash mismatch")
    passenger_statuses = {
        "PASS_PHASE2_PASSENGER_UTILITY_FRONTIER_V2",
        "PASS_PHASE2_PASSENGER_UTILITY_FRONTIER_RT001_V3",
    }
    if passenger.get("status") not in passenger_statuses:
        raise ValueError("Passenger utility frontier is not certified")
    passenger_hash = (
        passenger.get("lineage", {}).get("frontier_output_sha256")
        or passenger.get("lineage", {}).get("output_sha256")
    )
    if passenger_hash != sha256_path(args.passenger_frontier):
        raise ValueError("Passenger utility frontier hash mismatch")
    manifest_passenger_hash = manifest.get("lineage", {}).get("passenger_frontier_sha256")
    if manifest_passenger_hash and manifest_passenger_hash != sha256_path(args.passenger_frontier):
        raise ValueError("Stage-D manifest does not reference the supplied Passenger Utility frontier")
    if passenger.get("status") == "PASS_PHASE2_PASSENGER_UTILITY_FRONTIER_RT001_V3":
        if passenger.get("exact_budget_eligibility_repaired_before_stage_c") is not True:
            raise ValueError("Passenger Utility V3 lost RT-001 budget repair")
        if passenger.get("annual_bus_km_is_selected_timetable_production") is not False:
            raise ValueError("Pre-Stage-D annual bus-km was mislabelled as selected production")
    if budget.get("status") == "PASS_PHASE2_BUDGET_LOSSLESS_POLICY_SURFACE_V2":
        if budget.get("contract") != "PHASE2_EXACT_EXISTENTIAL_INTEGER_PHASE_BUDGET_SURFACE_V2":
            raise ValueError("Unexpected RT-001 budget-lossless contract")
        if budget.get("continuous_clockface_used_as_hard_filter") is not False:
            raise ValueError("RT-001 budget surface reintroduced continuous hard filtering")
        declared_budget_hash = passenger.get("lineage", {}).get("budget_policy_validation_sha256")
        if declared_budget_hash and declared_budget_hash != sha256_path(args.budget_validation):
            raise ValueError("Passenger Utility lineage does not reference the supplied RT-001 validation")
    elif not budget.get("budget_summary"):
        raise ValueError("Budget validation lacks a certified budget set")
    if matrix.get("status") != "PASS_REDUCED_PATH_MATRIX_V2_BUILD":
        raise ValueError("Reduced path matrix is not certified")
    if matrix.get("lineage", {}).get("reduced_path_matrix_sha256") != sha256_path(args.path_matrix):
        raise ValueError("Reduced path-matrix hash mismatch")
    if s8.get("status") != "PASS_S8_PHASE_OPPORTUNITY_V2_BUILD":
        raise ValueError("S8 phase-opportunity surface is not certified")
    return manifest, passenger, budget


def select_best_budget_feasible_vector(
    vectors: Sequence[VectorEvidence],
    annual_service_days: int,
    budget_cap: float,
) -> tuple[VectorEvidence | None, int]:
    """Apply the hard cap to exact phase production, then optimise S8 quality."""
    feasible = [
        vector
        for vector in vectors
        if vector.exact_daily_bus_km * annual_service_days <= budget_cap + EPS
    ]
    return (max(feasible, key=lambda vector: vector.objective_key) if feasible else None, len(feasible))


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    for name in (
        "timing_inputs", "route_inputs", "manifest_validation",
        "passenger_frontier", "passenger_validation", "budget_validation",
        "path_matrix", "matrix_validation", "s8_events", "s8_validation",
        "s8_sensitivity_config", "context_output", "timetable_output", "trip_output", "validation",
    ):
        p.add_argument("--" + name.replace("_", "-"), dest=name, type=Path, required=True)
    args = p.parse_args()

    manifest, _, budget_validation = validate_upstream(args)
    timing_input_count = int(manifest["stage_d_daily_timing_input_count"])
    context_count = int(manifest["passenger_plan_context_count_represented"])
    phase_vector_count = int(manifest["naive_joint_phase_vector_count_sum"])
    route_count = int(manifest["used_public_route_count"])
    caps = load_budget_caps(budget_validation, args.passenger_frontier)
    contexts = load_passenger_contexts(args.passenger_frontier, caps, context_count)
    distances = load_matrix_distances(args.path_matrix)
    routes = load_route_evidence(args.route_inputs, distances, route_count)
    profiles = load_profiles(args.s8_sensitivity_config)
    rail_index = rail_event_index(load_s8_events(args.s8_events))

    context_fields = [
        "plan_context_id", "plan_id", "budget_suffix", "budget_cap_annual_bus_km",
        "stage_d_input_id", "scenario_id", "topology_family", "uniform_headway_min", "span_id",
        "calendar_id", "annual_service_days", "phase_vectors_evaluated_once_for_daily_input",
        "exact_budget_feasible_phase_vector_count", "exact_budget_hard_eligible",
        "selected_timetable_id", "selected_phase_vector_json", "robust_min_transfer_quality",
        "robust_unweighted_mean_transfer_quality", "exact_daily_bus_km", "exact_annual_bus_km",
        "continuous_annual_bus_km", "exact_minus_continuous_annual_bus_km",
        "upstream_exact_budget_phase_feasibility_class", "recovered_from_continuous_hard_filter",
        "exact_fleet_recovery5", "exact_fleet_recovery10", "exact_fleet_recovery15",
        "retained_current_localizable_cluster_count", "retained_current_localizable_cluster_share",
        "phase_selection_rule", "s8_target_selection_semantics", "worker_reference_used_for_phase_selection",
        "decision_budget_selected", "calendar_selected", "recovery_selected", "topology_ranked",
        "primary_selected", "runner_up_selected", "weighted_composite_score",
    ]
    timetable_fields = [
        "selected_timetable_id", "stage_d_input_id", "scenario_id", "topology_family",
        "uniform_headway_min", "span_id", "span_start_min", "span_end_min", "public_route_count",
        "public_route_ids_json", "selected_phase_vector_json", "robust_min_transfer_quality",
        "robust_unweighted_mean_transfer_quality", "exact_daily_bus_km", "explicit_public_trip_count",
        "exact_fleet_recovery5", "exact_fleet_recovery10", "exact_fleet_recovery15",
        "s8_target_selection_semantics", "phase_selection_rule", "exact_timetable_constructed",
    ]
    trip_fields = [
        "selected_timetable_id", "stage_d_input_id", "route_id", "route_phase_min", "trip_ordinal",
        "vehicle_id_recovery5", "vehicle_id_recovery10", "vehicle_id_recovery15",
        "departure_min", "public_service_end_min", "vehicle_return_hub_min",
        "candidate_timetable_not_final_recommendation",
    ]

    context_raw, context_text, context_writer = deterministic_gzip_writer(args.context_output, context_fields)
    table_rows: dict[str, dict[str, object]] = {}
    trip_payload: dict[
        str,
        tuple[
            dict[str, str],
            tuple[RouteEvidence, ...],
            tuple[int, ...],
            dict[int, dict[tuple[str, int], int]],
        ],
    ] = {}
    seen_context_ids = set()
    phase_vectors_evaluated = 0
    eligible_by_budget = {b: 0 for b in caps}
    ineligible_by_budget = {b: 0 for b in caps}
    recovered_context_count = 0
    recovered_context_eligible_count = 0
    some_phase_context_count = 0
    some_phase_context_eligible_count = 0
    phase_divergent_context_group_count = 0
    max_public_route_count = 0

    try:
        timing_rows = list(read_gzip_csv(args.timing_inputs))
        if len(timing_rows) != timing_input_count:
            raise ValueError(f"Stage-D timing count mismatch: {len(timing_rows)} != {timing_input_count}")
        for timing in timing_rows:
            input_id = str(timing["stage_d_input_id"])
            scenario_id = str(timing["scenario_id"])
            topology = str(timing["topology_family"])
            headway = int(timing["uniform_headway_min"])
            span_start = int(timing["span_start_min"])
            span_end = int(timing["span_end_min"])
            route_ids = tuple(json.loads(timing["public_route_ids_json"]))
            declared_route_count = int(timing["public_route_count"])
            if not route_ids or len(route_ids) != declared_route_count:
                raise ValueError(f"Invalid Stage-D route count for {input_id}")
            max_public_route_count = max(max_public_route_count, len(route_ids))
            route_evidence = tuple(routes[rid] for rid in route_ids)
            route_inputs = tuple(r.route for r in route_evidence)
            precomputed = precompute_route_phase_cells(
                route_inputs, headway=headway, span_start=span_start, span_end=span_end,
                rail_index=rail_index, profiles=profiles,
            )
            per_route_daily_km = []
            for evidence in route_evidence:
                per_route_daily_km.append(tuple(
                    evidence.cycle_distance_km * len(clockface_times(phase, headway, span_start, span_end))
                    for phase in range(headway)
                ))

            vectors: list[VectorEvidence] = []
            for phases in itertools.product(range(headway), repeat=len(route_ids)):
                score = evaluate_phase_vector(phases, precomputed)
                daily_km = math.fsum(per_route_daily_km[i][phase] for i, phase in enumerate(phases))
                vectors.append(VectorEvidence(
                    phases=tuple(phases),
                    robust_min_transfer_quality=score.robust_min_transfer_quality,
                    robust_unweighted_mean_transfer_quality=score.robust_unweighted_mean_transfer_quality,
                    exact_daily_bus_km=daily_km,
                ))
            expected = int(timing["naive_joint_phase_vector_count"])
            if len(vectors) != expected:
                raise ValueError(f"Phase enumeration mismatch for {input_id}: {len(vectors)} != {expected}")
            phase_vectors_evaluated += len(vectors)

            context_ids = tuple(json.loads(timing["represented_plan_context_ids_json"]))
            if len(context_ids) != int(timing["represented_plan_count"]):
                raise ValueError(f"Context cardinality mismatch for {input_id}")
            selected_phase_set = set()
            constraint_cache: dict[tuple[int, str], tuple[VectorEvidence | None, int]] = {}
            block_cache: dict[tuple[int, ...], tuple[dict[int, int], dict[tuple[str, int], int]]] = {}

            for context_id in context_ids:
                if context_id in seen_context_ids:
                    raise ValueError(f"Duplicate represented context {context_id}")
                seen_context_ids.add(context_id)
                context = contexts[context_id]
                constraint_key = (context.annual_service_days, context.budget_suffix)
                cached = constraint_cache.get(constraint_key)
                if cached is None:
                    cached = select_best_budget_feasible_vector(
                        vectors, context.annual_service_days, context.budget_cap
                    )
                    constraint_cache[constraint_key] = cached
                best, feasible_count = cached
                if context.recovered_from_continuous_hard_filter:
                    recovered_context_count += 1
                if context.exact_budget_phase_feasibility_class == "SOME_PHASES_BUDGET_FEASIBLE":
                    some_phase_context_count += 1

                base = {
                    "plan_context_id": context.context_id,
                    "plan_id": context.plan_id,
                    "budget_suffix": context.budget_suffix,
                    "budget_cap_annual_bus_km": f"{context.budget_cap:.6f}",
                    "stage_d_input_id": input_id,
                    "scenario_id": scenario_id,
                    "topology_family": topology,
                    "uniform_headway_min": headway,
                    "span_id": str(timing["span_id"]),
                    "calendar_id": context.calendar_id,
                    "annual_service_days": context.annual_service_days,
                    "phase_vectors_evaluated_once_for_daily_input": len(vectors),
                    "exact_budget_feasible_phase_vector_count": feasible_count,
                    "continuous_annual_bus_km": f"{context.continuous_annual_bus_km:.6f}",
                    "upstream_exact_budget_phase_feasibility_class": context.exact_budget_phase_feasibility_class,
                    "recovered_from_continuous_hard_filter": str(context.recovered_from_continuous_hard_filter).lower(),
                    "retained_current_localizable_cluster_count": timing["retained_current_localizable_cluster_count"],
                    "retained_current_localizable_cluster_share": timing["retained_current_localizable_cluster_share"],
                    "phase_selection_rule": "MAX_ROBUST_MIN_QUALITY_THEN_MAX_UNWEIGHTED_MEAN_QUALITY_THEN_LOWEST_ROUTE_PHASE_TUPLE__AFTER_CONTEXT_EXACT_BUDGET_FILTER",
                    "s8_target_selection_semantics": "MAX_CONTINUOUS_TRANSFER_QUALITY_OVER_FINITE_EXPLICIT_TARGET_EVENTS",
                    "worker_reference_used_for_phase_selection": "false",
                    "decision_budget_selected": "false",
                    "calendar_selected": "false",
                    "recovery_selected": "false",
                    "topology_ranked": "false",
                    "primary_selected": "false",
                    "runner_up_selected": "false",
                    "weighted_composite_score": "false",
                }
                if best is None:
                    ineligible_by_budget[context.budget_suffix] += 1
                    base.update({
                        "exact_budget_hard_eligible": "false", "selected_timetable_id": "",
                        "selected_phase_vector_json": "", "robust_min_transfer_quality": "",
                        "robust_unweighted_mean_transfer_quality": "", "exact_daily_bus_km": "",
                        "exact_annual_bus_km": "", "exact_minus_continuous_annual_bus_km": "",
                        "exact_fleet_recovery5": "", "exact_fleet_recovery10": "", "exact_fleet_recovery15": "",
                    })
                    context_writer.writerow(base)
                    continue

                eligible_by_budget[context.budget_suffix] += 1
                if context.recovered_from_continuous_hard_filter:
                    recovered_context_eligible_count += 1
                if context.exact_budget_phase_feasibility_class == "SOME_PHASES_BUDGET_FEASIBLE":
                    some_phase_context_eligible_count += 1
                selected_phase_set.add(best.phases)
                timetable_id = stable_timetable_id(input_id, best.phases)
                if best.phases not in block_cache:
                    fleets = {}
                    assignments = {}
                    for recovery in RECOVERIES:
                        fleet, assignment = exact_vehicle_blocks(
                            route_inputs, best.phases, headway=headway,
                            span_start=span_start, span_end=span_end, recovery_min=recovery,
                        )
                        fleets[recovery] = fleet
                        assignments[recovery] = assignment
                    block_cache[best.phases] = (fleets, assignments)
                fleets, assignments = block_cache[best.phases]
                exact_annual = best.exact_daily_bus_km * context.annual_service_days
                base.update({
                    "exact_budget_hard_eligible": "true",
                    "selected_timetable_id": timetable_id,
                    "selected_phase_vector_json": json.dumps(list(best.phases), separators=(",", ":")),
                    "robust_min_transfer_quality": f"{best.robust_min_transfer_quality:.12f}",
                    "robust_unweighted_mean_transfer_quality": f"{best.robust_unweighted_mean_transfer_quality:.12f}",
                    "exact_daily_bus_km": f"{best.exact_daily_bus_km:.9f}",
                    "exact_annual_bus_km": f"{exact_annual:.6f}",
                    "exact_minus_continuous_annual_bus_km": f"{exact_annual - context.continuous_annual_bus_km:.6f}",
                    "exact_fleet_recovery5": fleets[5],
                    "exact_fleet_recovery10": fleets[10],
                    "exact_fleet_recovery15": fleets[15],
                })
                context_writer.writerow(base)

                if timetable_id not in table_rows:
                    trip_count = sum(len(clockface_times(phase, headway, span_start, span_end)) for phase in best.phases)
                    table_rows[timetable_id] = {
                        "selected_timetable_id": timetable_id,
                        "stage_d_input_id": input_id,
                        "scenario_id": scenario_id,
                        "topology_family": topology,
                        "uniform_headway_min": headway,
                        "span_id": str(timing["span_id"]),
                        "span_start_min": span_start,
                        "span_end_min": span_end,
                        "public_route_count": len(route_ids),
                        "public_route_ids_json": json.dumps(list(route_ids), separators=(",", ":")),
                        "selected_phase_vector_json": json.dumps(list(best.phases), separators=(",", ":")),
                        "robust_min_transfer_quality": f"{best.robust_min_transfer_quality:.12f}",
                        "robust_unweighted_mean_transfer_quality": f"{best.robust_unweighted_mean_transfer_quality:.12f}",
                        "exact_daily_bus_km": f"{best.exact_daily_bus_km:.9f}",
                        "explicit_public_trip_count": trip_count,
                        "exact_fleet_recovery5": fleets[5],
                        "exact_fleet_recovery10": fleets[10],
                        "exact_fleet_recovery15": fleets[15],
                        "s8_target_selection_semantics": "MAX_CONTINUOUS_TRANSFER_QUALITY_OVER_FINITE_EXPLICIT_TARGET_EVENTS",
                        "phase_selection_rule": base["phase_selection_rule"],
                        "exact_timetable_constructed": "true",
                    }
                    trip_payload[timetable_id] = (timing, route_evidence, best.phases, assignments)
            if len(selected_phase_set) > 1:
                phase_divergent_context_group_count += 1
    finally:
        context_text.flush()
        context_text.close()
        context_raw.close()

    if seen_context_ids != set(contexts):
        missing = set(contexts) - seen_context_ids
        extra = seen_context_ids - set(contexts)
        raise ValueError(f"Stage-D context coverage mismatch missing={len(missing)} extra={len(extra)}")
    if phase_vectors_evaluated != phase_vector_count:
        raise ValueError("Global exact phase-vector count mismatch")

    args.timetable_output.parent.mkdir(parents=True, exist_ok=True)
    with args.timetable_output.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=timetable_fields, lineterminator="\n")
        writer.writeheader()
        for timetable_id in sorted(table_rows):
            writer.writerow(table_rows[timetable_id])

    trip_raw, trip_text, trip_writer = deterministic_gzip_writer(args.trip_output, trip_fields)
    total_trip_rows = 0
    try:
        for timetable_id in sorted(trip_payload):
            timing, route_evidence, phases, assignments = trip_payload[timetable_id]
            headway = int(timing["uniform_headway_min"])
            span_start = int(timing["span_start_min"])
            span_end = int(timing["span_end_min"])
            for evidence, phase in zip(route_evidence, phases):
                departures = clockface_times(phase, headway, span_start, span_end)
                for ordinal, departure in enumerate(departures):
                    total_trip_rows += 1
                    trip_writer.writerow({
                        "selected_timetable_id": timetable_id,
                        "stage_d_input_id": timing["stage_d_input_id"],
                        "route_id": evidence.route.route_id,
                        "route_phase_min": phase,
                        "trip_ordinal": ordinal,
                        "vehicle_id_recovery5": f"V{assignments[5][(evidence.route.route_id, ordinal)] + 1}",
                        "vehicle_id_recovery10": f"V{assignments[10][(evidence.route.route_id, ordinal)] + 1}",
                        "vehicle_id_recovery15": f"V{assignments[15][(evidence.route.route_id, ordinal)] + 1}",
                        "departure_min": f"{departure:.6f}",
                        "public_service_end_min": f"{departure + evidence.route.public_runtime_min:.6f}",
                        "vehicle_return_hub_min": f"{departure + evidence.route.cycle_runtime_min:.6f}",
                        "candidate_timetable_not_final_recommendation": "true",
                    })
    finally:
        trip_text.flush()
        trip_text.close()
        trip_raw.close()

    eligible_total = sum(eligible_by_budget.values())
    ineligible_total = sum(ineligible_by_budget.values())
    validation = {
        "status": STATUS,
        "contract": CONTRACT,
        "stage_d_daily_timing_input_count": timing_input_count,
        "stage_c_plan_context_count": context_count,
        "phase_vectors_evaluated_once": phase_vectors_evaluated,
        "max_public_route_count": max_public_route_count,
        "exact_budget_hard_eligible_context_count": eligible_total,
        "exact_budget_hard_ineligible_context_count": ineligible_total,
        "eligible_context_count_by_budget": eligible_by_budget,
        "ineligible_context_count_by_budget": ineligible_by_budget,
        "upstream_some_phases_budget_feasible_context_count": some_phase_context_count,
        "upstream_some_phases_budget_feasible_eligible_context_count": some_phase_context_eligible_count,
        "recovered_from_continuous_hard_filter_context_count": recovered_context_count,
        "recovered_from_continuous_hard_filter_eligible_context_count": recovered_context_eligible_count,
        "timing_inputs_with_budget_or_calendar_specific_selected_phase_count": phase_divergent_context_group_count,
        "unique_selected_exact_timetable_count": len(table_rows),
        "selected_exact_trip_row_count": total_trip_rows,
        "s8_target_selection_semantics": "MAX_CONTINUOUS_TRANSFER_QUALITY_OVER_FINITE_EXPLICIT_TARGET_EVENTS",
        "s8_target_localisation_is_exact_not_heuristic": True,
        "exhaustive_route_specific_phase_domain": True,
        "approximate_or_heuristic_phase_search": False,
        "exact_budget_hard_cap_reapplied_after_materialisation": True,
        "exact_selected_annual_bus_km_derived_from_materialised_phase_vector": True,
        "pre_stage_d_annual_bus_km_treated_as_envelope_not_selected_timetable": True,
        "budget_calendar_identity_preserved": True,
        "passenger_return_events_restricted_to_declared_service_span": True,
        "technical_vehicle_closure_used_as_passenger_return": False,
        "recovery_values_evaluated_not_selected": list(RECOVERIES),
        "vehicle_block_assignments_materialised_for_recovery_values": list(RECOVERIES),
        "passenger_weighting_applied": False,
        "topology_weighting_applied": False,
        "worker_reference_used_for_phase_selection": False,
        "decision_budget_selected": False,
        "calendar_selected": False,
        "recovery_selected": False,
        "topology_ranked": False,
        "primary_selected": False,
        "runner_up_selected": False,
        "weighted_composite_score": False,
        "delay_stress_certified_as_robustness": False,
        "lineage": {
            "timing_inputs_sha256": sha256_path(args.timing_inputs),
            "route_inputs_sha256": sha256_path(args.route_inputs),
            "manifest_validation_sha256": sha256_path(args.manifest_validation),
            "passenger_frontier_sha256": sha256_path(args.passenger_frontier),
            "passenger_validation_sha256": sha256_path(args.passenger_validation),
            "budget_validation_sha256": sha256_path(args.budget_validation),
            "path_matrix_sha256": sha256_path(args.path_matrix),
            "matrix_validation_sha256": sha256_path(args.matrix_validation),
            "s8_events_sha256": sha256_path(args.s8_events),
            "s8_validation_sha256": sha256_path(args.s8_validation),
            "s8_sensitivity_config_sha256": sha256_path(args.s8_sensitivity_config),
            "context_output_sha256": sha256_path(args.context_output),
            "timetable_output_sha256": sha256_path(args.timetable_output),
            "trip_output_sha256": sha256_path(args.trip_output),
        },
    }
    if eligible_total + ineligible_total != context_count:
        raise ValueError("Exact budget context accounting mismatch")
    args.validation.parent.mkdir(parents=True, exist_ok=True)
    args.validation.write_text(json.dumps(validation, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(validation, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
