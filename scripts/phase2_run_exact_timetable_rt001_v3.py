#!/usr/bin/env python3
"""Lossless Stage-D exact timetable for the repaired RT-001 Phase-2 lineage.

Every integer route-specific phase vector in the certified Stage-D manifest is
explicitly evaluated.  For each budget-qualified Stage-C context, the hard
annual bus-km cap is re-applied after exact trip materialisation and the best
S8 phase vector is selected only among budget-feasible vectors.

The stage selects no budget, calendar, recovery, topology, PRIMARY or RUNNER-UP.
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
    rail_event_index,
    strict_bool,
)
from src.phase2_exact_timetable_contract_v2 import precompute_route_phase_cells_contract

STATUS = "PASS_PHASE2_STAGE_D_EXACT_TIMETABLE_RT001_V3"
CONTRACT = "PHASE2_RT001_LOSSLESS_BUDGET_QUALIFIED_EXACT_CLOCKFACE_TIMETABLE_V3"
MANIFEST_STATUS = "PASS_PHASE2_STAGE_D_INPUT_MANIFEST_RT001_V3"
MANIFEST_CONTRACT = "PHASE2_LOSSLESS_DAILY_TIMING_INPUT_MANIFEST_RT001_V3"
PASSENGER_STATUS = "PASS_PHASE2_PASSENGER_UTILITY_FRONTIER_RT001_V3"
PASSENGER_CONTRACT = "PHASE2_NO_WEIGHT_PASSENGER_UTILITY_EXACT_EXISTENTIAL_BUDGET_V3"
BUDGET_STATUS = "PASS_PHASE2_BUDGET_LOSSLESS_POLICY_SURFACE_V2"
BUDGET_CONTRACT = "PHASE2_EXACT_EXISTENTIAL_INTEGER_PHASE_BUDGET_SURFACE_V2"
BUDGET_SUFFIX_BY_FRACTION = {
    -0.2: "m20pct",
    -0.1: "m10pct",
    0.0: "reference",
    0.1: "p10pct",
    0.2: "p20pct",
    0.3: "p30pct",
}
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
    payload = json.dumps(
        {"stage_d_input_id": str(stage_d_input_id), "phases": [int(v) for v in phases]},
        sort_keys=True,
        separators=(",", ":"),
    )
    return "D3RT1_" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


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
    upstream_exact_min_annual_bus_km: float


@dataclass(frozen=True)
class VectorEvidence:
    phases: tuple[int, ...]
    robust_min_transfer_quality: float
    robust_unweighted_mean_transfer_quality: float
    exact_daily_bus_km: float

    @property
    def objective_key(self) -> tuple[float, ...]:
        return (
            self.robust_min_transfer_quality,
            self.robust_unweighted_mean_transfer_quality,
            *(-phase for phase in self.phases),
        )


def load_budget_caps(path: Path, validation: Mapping[str, object]) -> dict[str, float]:
    if validation.get("status") != "PASS" or int(validation.get("envelope_count", -1)) != 6:
        raise ValueError("Budget envelopes are not certified")
    caps: dict[str, float] = {}
    for row in read_csv(path):
        fraction = round(float(row["budget_change_fraction"]), 10)
        suffix = BUDGET_SUFFIX_BY_FRACTION.get(fraction)
        if suffix is None:
            raise ValueError(f"Unexpected budget fraction {fraction}")
        if suffix in caps:
            raise ValueError(f"Duplicate budget suffix {suffix}")
        cap = float(row["annual_bus_km_cap"])
        if not math.isfinite(cap) or cap <= 0:
            raise ValueError(f"Invalid budget cap {suffix}")
        caps[suffix] = cap
    if set(caps) != set(BUDGET_SUFFIX_BY_FRACTION.values()):
        raise ValueError(f"Incomplete budget envelope: {sorted(caps)}")
    declared = sorted(float(x) for x in validation.get("annual_bus_km_caps", []))
    if len(declared) != 6 or any(abs(a - b) > 1e-6 for a, b in zip(declared, sorted(caps.values()))):
        raise ValueError("Budget envelope CSV disagrees with validation")
    return caps


def load_s8_events(path: Path):
    rows = list(read_csv(path))
    if len(rows) != 74:
        raise ValueError(f"Expected 74 frozen S8 events, got {len(rows)}")
    if any(str(r.get("epistemic_status")) != "DERIVED_FROM_LIVE_OFFICIAL_GTFS" for r in rows):
        raise ValueError("S8 event lost official-GTFS epistemic status")
    for direction in ("MILANO", "LECCO"):
        if sum(str(r["direction"]).upper() == direction for r in rows) != 37:
            raise ValueError(f"Expected 37 {direction} S8 events")
    return rows


def load_matrix_distances(path: Path) -> dict[tuple[str, str], float]:
    result: dict[tuple[str, str], float] = {}
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


def load_route_evidence(
    path: Path,
    distances: Mapping[tuple[str, str], float],
    expected_count: int,
) -> dict[str, RouteEvidence]:
    result: dict[str, RouteEvidence] = {}
    for row in read_csv(path):
        route_id = str(row["route_id"])
        anchors = json.loads(row["anchors_json"])
        if not isinstance(anchors, list) or len(anchors) < 2 or str(anchors[0]) != "rail:S01514":
            raise ValueError(f"Invalid route anchors {route_id}")
        public_distance = math.fsum(
            distances[(str(a), str(b))] for a, b in zip(anchors[:-1], anchors[1:])
        )
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
        result[route_id] = RouteEvidence(route=route, cycle_distance_km=cycle_distance)
    if len(result) != expected_count:
        raise ValueError(f"Route count mismatch {len(result)} != {expected_count}")
    return result


def load_plan_contexts(
    path: Path,
    caps: Mapping[str, float],
    expected_count: int,
) -> dict[str, PlanContext]:
    result: dict[str, PlanContext] = {}
    for row in read_gzip_csv(path):
        budget = str(row["budget_suffix"])
        if budget not in caps:
            raise ValueError(f"Unknown budget suffix {budget}")
        context_id = f"{budget}|{row['plan_id']}"
        if context_id in result:
            raise ValueError(f"Duplicate Stage-C context {context_id}")
        upstream_min = float(row["annual_bus_km"])
        if upstream_min > caps[budget] + EPS:
            raise ValueError(f"Repaired Stage-C context above its existential budget cap: {context_id}")
        result[context_id] = PlanContext(
            context_id=context_id,
            plan_id=str(row["plan_id"]),
            budget_suffix=budget,
            budget_cap=float(caps[budget]),
            calendar_id=str(row["calendar_id"]),
            annual_service_days=int(row["annual_service_days"]),
            upstream_exact_min_annual_bus_km=upstream_min,
        )
    if len(result) != expected_count:
        raise ValueError(f"Stage-C context count mismatch {len(result)} != {expected_count}")
    return result


def select_best_budget_feasible(
    vectors: Sequence[VectorEvidence],
    annual_service_days: int,
    budget_cap: float,
) -> tuple[VectorEvidence | None, int]:
    feasible = [v for v in vectors if v.exact_daily_bus_km * annual_service_days <= budget_cap + EPS]
    return (max(feasible, key=lambda v: v.objective_key) if feasible else None, len(feasible))


def validate_upstream(args) -> tuple[dict, dict, dict, dict]:
    manifest = read_json(args.manifest_validation)
    passenger = read_json(args.passenger_validation)
    budget_lossless = read_json(args.budget_lossless_validation)
    matrix = read_json(args.matrix_validation)
    s8 = read_json(args.s8_validation)
    budget_envelopes = read_json(args.budget_envelope_validation)

    if manifest.get("status") != MANIFEST_STATUS or manifest.get("contract") != MANIFEST_CONTRACT:
        raise ValueError("Stage-D repaired manifest is not certified")
    if manifest.get("rt001_repair") is not True or manifest.get("exact_budget_eligibility_repaired_upstream") is not True:
        raise ValueError("Stage-D manifest lost RT-001 repair semantics")
    if manifest.get("lineage", {}).get("timing_output_sha256") != sha256_path(args.timing_inputs):
        raise ValueError("Stage-D timing input hash mismatch")
    if manifest.get("lineage", {}).get("route_output_sha256") != sha256_path(args.route_inputs):
        raise ValueError("Stage-D route input hash mismatch")

    if passenger.get("status") != PASSENGER_STATUS or passenger.get("contract") != PASSENGER_CONTRACT:
        raise ValueError("Passenger Utility RT001 V3 is not certified")
    if passenger.get("rt001_repair") is not True or passenger.get("annual_bus_km_is_selected_timetable_production") is not False:
        raise ValueError("Passenger Utility annual-km semantics changed")
    if passenger.get("lineage", {}).get("frontier_output_sha256") != sha256_path(args.passenger_frontier):
        raise ValueError("Passenger Utility frontier hash mismatch")

    if budget_lossless.get("status") != BUDGET_STATUS or budget_lossless.get("contract") != BUDGET_CONTRACT:
        raise ValueError("Budget-lossless RT-001 surface is not certified")
    if budget_lossless.get("continuous_clockface_used_as_hard_filter") is not False:
        raise ValueError("Continuous clockface unexpectedly restored as hard filter")

    if matrix.get("status") != "PASS_REDUCED_PATH_MATRIX_V2_BUILD":
        raise ValueError("Reduced path matrix is not certified")
    if matrix.get("lineage", {}).get("reduced_path_matrix_sha256") != sha256_path(args.path_matrix):
        raise ValueError("Reduced path matrix hash mismatch")
    if s8.get("status") != "PASS_S8_PHASE_OPPORTUNITY_V2_BUILD":
        raise ValueError("S8 phase opportunity is not certified")
    if budget_envelopes.get("status") != "PASS":
        raise ValueError("Budget envelopes validation is not PASS")
    return manifest, passenger, budget_lossless, budget_envelopes


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    for name in (
        "timing_inputs", "route_inputs", "manifest_validation",
        "passenger_frontier", "passenger_validation", "budget_lossless_validation",
        "budget_envelopes", "budget_envelope_validation",
        "path_matrix", "matrix_validation", "s8_events", "s8_validation",
        "s8_sensitivity_config", "context_output", "timetable_output", "trip_output", "validation",
    ):
        p.add_argument("--" + name.replace("_", "-"), dest=name, type=Path, required=True)
    args = p.parse_args()

    manifest, passenger_validation, budget_lossless_validation, envelope_validation = validate_upstream(args)
    input_count = int(manifest["stage_d_daily_timing_input_count"])
    context_count = int(manifest["passenger_plan_context_count_represented"])
    route_count = int(manifest["used_public_route_count"])
    expected_vectors = int(manifest["naive_joint_phase_vector_count_sum"])
    if context_count != int(passenger_validation["passenger_utility_frontier_row_count_all_budgets"]):
        raise ValueError("Manifest and Passenger Utility context counts disagree")

    caps = load_budget_caps(args.budget_envelopes, envelope_validation)
    contexts = load_plan_contexts(args.passenger_frontier, caps, context_count)
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
        "upstream_exact_min_annual_bus_km", "exact_selected_minus_upstream_exact_min_annual_bus_km",
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
        "vehicle_id_recovery15", "departure_min", "public_service_end_min", "vehicle_return_hub_min",
        "candidate_timetable_not_final_recommendation",
    ]

    context_raw, context_text, context_writer = deterministic_gzip_writer(args.context_output, context_fields)
    timetable_rows: dict[str, dict[str, object]] = {}
    trip_payload: dict[str, tuple[dict[str, str], tuple[RouteEvidence, ...], tuple[int, ...], dict]] = {}
    seen_context_ids: set[str] = set()
    phase_vectors_evaluated = 0
    eligible_by_budget = {b: 0 for b in caps}
    selected_above_exact_min_count = 0
    phase_divergent_context_group_count = 0
    fleet_min = {r: math.inf for r in RECOVERIES}
    fleet_max = {r: -math.inf for r in RECOVERIES}

    try:
        timing_rows = list(read_gzip_csv(args.timing_inputs))
        if len(timing_rows) != input_count:
            raise ValueError(f"Stage-D timing count mismatch {len(timing_rows)} != {input_count}")
        for timing in timing_rows:
            input_id = str(timing["stage_d_input_id"])
            scenario_id = str(timing["scenario_id"])
            topology = str(timing["topology_family"])
            headway = int(timing["uniform_headway_min"])
            span_start = int(timing["span_start_min"])
            span_end = int(timing["span_end_min"])
            route_ids = tuple(str(v) for v in json.loads(timing["public_route_ids_json"]))
            if len(route_ids) != int(timing["public_route_count"]) or not route_ids:
                raise ValueError(f"Route cardinality mismatch for {input_id}")
            route_evidence = tuple(routes[rid] for rid in route_ids)
            route_inputs = tuple(e.route for e in route_evidence)

            precomputed = precompute_route_phase_cells_contract(
                route_inputs,
                headway=headway,
                span_start=span_start,
                span_end=span_end,
                rail_index=rail_index,
                profiles=profiles,
            )
            per_route_daily_km = tuple(
                tuple(
                    evidence.cycle_distance_km * len(clockface_times(phase, headway, span_start, span_end))
                    for phase in range(headway)
                )
                for evidence in route_evidence
            )
            vectors: list[VectorEvidence] = []
            for phases in itertools.product(range(headway), repeat=len(route_ids)):
                score = evaluate_phase_vector(phases, precomputed)
                daily_km = math.fsum(per_route_daily_km[i][phase] for i, phase in enumerate(phases))
                vectors.append(VectorEvidence(
                    phases=tuple(int(v) for v in phases),
                    robust_min_transfer_quality=score.robust_min_transfer_quality,
                    robust_unweighted_mean_transfer_quality=score.robust_unweighted_mean_transfer_quality,
                    exact_daily_bus_km=daily_km,
                ))
            expected_here = int(timing["naive_joint_phase_vector_count"])
            if len(vectors) != expected_here or expected_here != headway ** len(route_ids):
                raise ValueError(f"Exact phase enumeration mismatch for {input_id}")
            phase_vectors_evaluated += len(vectors)

            context_ids = tuple(str(v) for v in json.loads(timing["represented_plan_context_ids_json"]))
            if len(context_ids) != int(timing["represented_plan_count"]):
                raise ValueError(f"Represented context mismatch for {input_id}")
            constraint_cache: dict[tuple[int, str], tuple[VectorEvidence | None, int]] = {}
            block_cache: dict[tuple[int, ...], tuple[dict[int, int], dict[tuple[str, int], int]]] = {}
            selected_phase_set: set[tuple[int, ...]] = set()

            for context_id in context_ids:
                if context_id in seen_context_ids:
                    raise ValueError(f"Duplicate represented context {context_id}")
                seen_context_ids.add(context_id)
                context = contexts[context_id]
                constraint_key = (context.annual_service_days, context.budget_suffix)
                if constraint_key not in constraint_cache:
                    constraint_cache[constraint_key] = select_best_budget_feasible(
                        vectors, context.annual_service_days, context.budget_cap
                    )
                best, feasible_count = constraint_cache[constraint_key]
                if best is None:
                    raise ValueError(
                        f"RT-001 invariant violated: Stage-C context {context_id} has no exact budget-feasible phase"
                    )

                selected_phase_set.add(best.phases)
                timetable_id = stable_timetable_id(input_id, best.phases)
                if best.phases not in block_cache:
                    fleets: dict[int, int] = {}
                    assignment15 = None
                    for recovery in RECOVERIES:
                        fleet, assignment = exact_vehicle_blocks(
                            route_inputs,
                            best.phases,
                            headway=headway,
                            span_start=span_start,
                            span_end=span_end,
                            recovery_min=recovery,
                        )
                        fleets[recovery] = fleet
                        fleet_min[recovery] = min(fleet_min[recovery], fleet)
                        fleet_max[recovery] = max(fleet_max[recovery], fleet)
                        if recovery == 15:
                            assignment15 = assignment
                    assert assignment15 is not None
                    block_cache[best.phases] = (fleets, assignment15)
                fleets, assignment15 = block_cache[best.phases]

                exact_annual = best.exact_daily_bus_km * context.annual_service_days
                if exact_annual > context.budget_cap + EPS:
                    raise AssertionError("Selected exact timetable exceeds hard budget cap")
                delta_min = exact_annual - context.upstream_exact_min_annual_bus_km
                if delta_min < -1e-6:
                    raise ValueError(f"Selected production below certified phase-domain minimum: {context_id}")
                if delta_min > 1e-6:
                    selected_above_exact_min_count += 1
                eligible_by_budget[context.budget_suffix] += 1

                phase_rule = (
                    "MAX_ROBUST_MIN_QUALITY_THEN_MAX_UNWEIGHTED_MEAN_QUALITY_"
                    "THEN_LOWEST_ROUTE_PHASE_TUPLE__AFTER_CONTEXT_EXACT_BUDGET_FILTER"
                )
                context_writer.writerow({
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
                    "exact_budget_hard_eligible": "true",
                    "selected_timetable_id": timetable_id,
                    "selected_phase_vector_json": json.dumps(list(best.phases), separators=(",", ":")),
                    "robust_min_transfer_quality": f"{best.robust_min_transfer_quality:.12f}",
                    "robust_unweighted_mean_transfer_quality": f"{best.robust_unweighted_mean_transfer_quality:.12f}",
                    "exact_daily_bus_km": f"{best.exact_daily_bus_km:.9f}",
                    "exact_annual_bus_km": f"{exact_annual:.6f}",
                    "upstream_exact_min_annual_bus_km": f"{context.upstream_exact_min_annual_bus_km:.6f}",
                    "exact_selected_minus_upstream_exact_min_annual_bus_km": f"{delta_min:.6f}",
                    "exact_fleet_recovery5": fleets[5],
                    "exact_fleet_recovery10": fleets[10],
                    "exact_fleet_recovery15": fleets[15],
                    "retained_current_localizable_cluster_count": timing["retained_current_localizable_cluster_count"],
                    "retained_current_localizable_cluster_share": timing["retained_current_localizable_cluster_share"],
                    "phase_selection_rule": phase_rule,
                    "s8_target_selection_semantics": "MAX_CONTINUOUS_TRANSFER_QUALITY_OVER_FINITE_EXPLICIT_TARGET_EVENTS",
                    "worker_reference_used_for_phase_selection": "false",
                    "decision_budget_selected": "false",
                    "calendar_selected": "false",
                    "recovery_selected": "false",
                    "topology_ranked": "false",
                    "primary_selected": "false",
                    "runner_up_selected": "false",
                    "weighted_composite_score": "false",
                })

                if timetable_id not in timetable_rows:
                    trip_count = sum(
                        len(clockface_times(phase, headway, span_start, span_end))
                        for phase in best.phases
                    )
                    timetable_rows[timetable_id] = {
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
                        "phase_selection_rule": phase_rule,
                        "exact_timetable_constructed": "true",
                    }
                    trip_payload[timetable_id] = (timing, route_evidence, best.phases, assignment15)

            if len(selected_phase_set) > 1:
                phase_divergent_context_group_count += 1
    finally:
        context_text.flush()
        context_text.close()
        context_raw.close()

    if seen_context_ids != set(contexts):
        raise ValueError(
            f"Stage-D context coverage mismatch missing={len(set(contexts)-seen_context_ids)} "
            f"extra={len(seen_context_ids-set(contexts))}"
        )
    if phase_vectors_evaluated != expected_vectors:
        raise ValueError(f"Global exact phase count mismatch {phase_vectors_evaluated} != {expected_vectors}")

    args.timetable_output.parent.mkdir(parents=True, exist_ok=True)
    with args.timetable_output.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=timetable_fields, lineterminator="\n")
        writer.writeheader()
        for timetable_id in sorted(timetable_rows):
            writer.writerow(timetable_rows[timetable_id])

    trip_raw, trip_text, trip_writer = deterministic_gzip_writer(args.trip_output, trip_fields)
    total_trip_rows = 0
    try:
        for timetable_id in sorted(trip_payload):
            timing, route_evidence, phases, assignment15 = trip_payload[timetable_id]
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
                        "vehicle_id_recovery15": f"V{assignment15[(evidence.route.route_id, ordinal)] + 1}",
                        "departure_min": f"{departure:.6f}",
                        "public_service_end_min": f"{departure + evidence.route.public_runtime_min:.6f}",
                        "vehicle_return_hub_min": f"{departure + evidence.route.cycle_runtime_min:.6f}",
                        "candidate_timetable_not_final_recommendation": "true",
                    })
    finally:
        trip_text.flush()
        trip_text.close()
        trip_raw.close()

    if not timetable_rows or total_trip_rows <= 0:
        raise ValueError("Exact timetable materialisation unexpectedly empty")

    validation = {
        "status": STATUS,
        "contract": CONTRACT,
        "rt001_repair": True,
        "stage_d_daily_timing_input_count": input_count,
        "stage_c_plan_context_count": context_count,
        "used_public_route_count": route_count,
        "phase_vectors_evaluated_once": phase_vectors_evaluated,
        "manifest_phase_vector_count": expected_vectors,
        "exhaustive_route_specific_phase_domain": True,
        "exact_phase_domain_pruned": False,
        "approximate_or_heuristic_phase_search": False,
        "s8_target_selection_semantics": "MAX_CONTINUOUS_TRANSFER_QUALITY_OVER_FINITE_EXPLICIT_TARGET_EVENTS",
        "s8_target_localisation_is_exact_not_heuristic": True,
        "bus_to_rail_public_returns_start_inclusive_end_exclusive": True,
        "vehicle_only_technical_return_used_as_passenger_service": False,
        "exact_budget_hard_cap_reapplied_after_materialisation": True,
        "upstream_exact_existential_budget_invariant_enforced": True,
        "exact_budget_hard_eligible_context_count": context_count,
        "exact_budget_hard_ineligible_context_count": 0,
        "budget_calendar_identity_preserved": True,
        "eligible_context_count_by_budget": dict(sorted(eligible_by_budget.items())),
        "selected_timetable_count": len(timetable_rows),
        "explicit_public_trip_count": total_trip_rows,
        "phase_divergent_context_group_count": phase_divergent_context_group_count,
        "selected_timetable_production_above_upstream_phase_domain_minimum_context_count": selected_above_exact_min_count,
        "exact_fleet_min_by_recovery": {str(r): int(fleet_min[r]) for r in RECOVERIES},
        "exact_fleet_max_by_recovery": {str(r): int(fleet_max[r]) for r in RECOVERIES},
        "recovery_values_retained_not_selected": list(RECOVERIES),
        "passenger_weighting_applied": False,
        "topology_weighting_applied": False,
        "worker_reference_used_for_phase_selection": False,
        "worker_reference_assigned_to_routes": False,
        "municipal_od_downscaled": False,
        "ridership_forecast": False,
        "weighted_composite_score": False,
        "decision_budget_selected": False,
        "calendar_selected": False,
        "recovery_selected": False,
        "topology_ranked": False,
        "primary_selected": False,
        "runner_up_selected": False,
        "delay_stress_certified_as_robustness": False,
        "limitations": [
            "Stage D selects exact route phases within each retained budget/calendar context; it does not select a budget or service policy.",
            "Rail-delay robustness remains downstream in Stage E and is source-closed to certified delay contracts.",
            "Current-service continuity remains a certified localizable lower bound, not full observed current-service continuity.",
        ],
        "lineage": {
            "manifest_validation_sha256": sha256_path(args.manifest_validation),
            "timing_inputs_sha256": sha256_path(args.timing_inputs),
            "route_inputs_sha256": sha256_path(args.route_inputs),
            "passenger_frontier_sha256": sha256_path(args.passenger_frontier),
            "passenger_validation_sha256": sha256_path(args.passenger_validation),
            "budget_lossless_validation_sha256": sha256_path(args.budget_lossless_validation),
            "budget_envelopes_sha256": sha256_path(args.budget_envelopes),
            "budget_envelope_validation_sha256": sha256_path(args.budget_envelope_validation),
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
    args.validation.parent.mkdir(parents=True, exist_ok=True)
    args.validation.write_text(
        json.dumps(validation, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
