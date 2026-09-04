#!/usr/bin/env python3
"""Exhaustive exact Stage-D timetable/S8 reference over all Stage-C survivors.

The Stage-D input manifest proves that every retained daily timing problem has
one or two public routes, so full integer-minute phase enumeration is tractable.
This builder evaluates every route-specific phase vector and then applies the
annual bus-km hard cap independently to every budget-qualified Stage-C context.

Phase selection follows the current PHASE2_S8_PHASING_SENSITIVITY_V2 robust
objective: maximise the minimum transfer-quality cell, then the unweighted mean
across profiles, supported connection types, rail directions and public routes.
No passenger/route/topology weights are used. Exact common-hub fleet is reported
for recovery 5/10/15 but is not used as a hidden phase score.
"""
from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from decimal import Decimal
import gzip
import hashlib
import io
import itertools
import json
from pathlib import Path
from typing import Sequence

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT))

from src.phase2_stage_d_exact_reference_v2 import (
    D,
    ExactRailEvent,
    ExactRoute,
    RoutePhaseEvidence,
    TransferProfile,
    aggregate_hard_miss,
    materialise_route_trips,
    minimum_common_hub_blocks,
    phase_vector_objective,
    route_phase_evidence,
)

STATUS = "PASS_PHASE2_STAGE_D_EXACT_BRUTEFORCE_REFERENCE_V2"
CONTRACT = "PHASE2_EXHAUSTIVE_ROUTE_SPECIFIC_EXACT_TIMETABLE_REFERENCE_V2"
RECOVERIES = (5, 10, 15)
TOL = D("0.000001")


@dataclass(frozen=True)
class TimingInput:
    input_id: str
    scenario_id: str
    topology_family: str
    headway: int
    span_id: str
    span_start: int
    span_end: int
    route_ids: tuple[str, ...]
    expected_phase_vectors: int


@dataclass(frozen=True)
class PlanContext:
    context_id: str
    plan_id: str
    budget_suffix: str
    budget_cap: Decimal
    scenario_id: str
    topology_family: str
    headway: int
    span_id: str
    calendar_id: str
    annual_service_days: int
    continuous_annual_bus_km: Decimal


@dataclass(frozen=True)
class VectorRecord:
    phases: tuple[int, ...]
    route_rows: tuple[RoutePhaseEvidence, ...]
    exact_daily_bus_km: Decimal
    robust_min_quality: float
    robust_mean_quality: float


def sha256_path(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv(path: Path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        yield from csv.DictReader(f)


def read_gzip_csv(path: Path):
    with gzip.open(path, "rt", encoding="utf-8-sig", newline="") as f:
        yield from csv.DictReader(f)


def bool_text(value: object, *, field: str) -> bool:
    text = str(value).strip().lower()
    if text == "true":
        return True
    if text == "false":
        return False
    raise ValueError(f"{field} must be explicit true/false")


def deterministic_gzip_writer(path: Path, fields: list[str]):
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = path.open("wb")
    gz = gzip.GzipFile(filename="", mode="wb", fileobj=raw, compresslevel=9, mtime=0)
    text = io.TextIOWrapper(gz, encoding="utf-8", newline="")
    writer = csv.DictWriter(text, fieldnames=fields, lineterminator="\n", extrasaction="ignore")
    writer.writeheader()
    return raw, text, writer


def stable_timetable_id(input_id: str, phases: Sequence[int]) -> str:
    payload = json.dumps({"input_id": input_id, "phases": list(phases)}, sort_keys=True, separators=(",", ":"))
    return "D4TT2_" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def load_profiles(path: Path) -> tuple[list[TransferProfile], dict]:
    cfg = load_json(path)
    if cfg.get("contract") != "PHASE2_S8_PHASING_SENSITIVITY_V2":
        raise ValueError("Unexpected S8 phasing sensitivity contract")
    if cfg.get("status") != "ASSUMPTION_SENSITIVITY_NOT_EMPIRICAL_INTERVAL":
        raise ValueError("S8 phasing profiles lost assumption-sensitivity status")
    objective = cfg.get("phase_objective", {})
    if objective.get("primary") != "MAXIMISE_MINIMUM_MEAN_TRANSFER_QUALITY_ACROSS_ALL_PROFILES_CONNECTION_TYPES_AND_RAIL_DIRECTIONS":
        raise ValueError("Unexpected primary S8 phase objective")
    if objective.get("secondary") != "MAXIMISE_UNWEIGHTED_MEAN_TRANSFER_QUALITY_ACROSS_ALL_PROFILES_CONNECTION_TYPES_AND_RAIL_DIRECTIONS":
        raise ValueError("Unexpected secondary S8 phase objective")
    if objective.get("passenger_weighting") is not False or objective.get("topology_weighting") is not False:
        raise ValueError("Exact reference requires unweighted current S8 phase objective")
    shared = cfg.get("shared_clockface_phase", {})
    if "reconsidered for finalists" not in str(shared.get("note", "")):
        raise ValueError("Current config does not explicitly permit finalist route-specific phase reconsideration")
    if cfg.get("delay_robustness_in_this_stage") is not False:
        raise ValueError("Delay robustness unexpectedly enabled in S8 phasing stage")
    rows = []
    ids = set()
    for raw in cfg.get("transfer_profiles", []):
        pid = str(raw["profile_id"])
        if pid in ids:
            raise ValueError("Duplicate transfer profile")
        ids.add(pid)
        if raw.get("status") != "ASSUMPTION_SENSITIVITY_NOT_EMPIRICAL_INTERVAL":
            raise ValueError("Transfer profile lost assumption status")
        rows.append(TransferProfile(
            profile_id=pid,
            transfer_walk_min=float(raw["transfer_walk_min"]),
            preferred_wait_min=float(raw["preferred_wait_min"]),
            miss_transition_scale_min=float(raw["miss_transition_scale_min"]),
            wait_decay_min=float(raw["wait_decay_min"]),
        ))
    if len(rows) != 3:
        raise ValueError("Expected three certified S8 transfer profiles")
    for row in rows:
        row.as_model_profile()
    return rows, cfg


def validate_upstream(args):
    manifest = load_json(args.manifest_validation)
    passenger = load_json(args.passenger_validation)
    budget = load_json(args.budget_validation)
    s8 = load_json(args.s8_validation)
    matrix = load_json(args.matrix_validation)
    s8_contract = load_json(args.s8_contract)

    if manifest.get("status") != "PASS_PHASE2_STAGE_D_INPUT_MANIFEST_V2" or manifest.get("contract") != "PHASE2_LOSSLESS_DAILY_TIMING_INPUT_MANIFEST_V2":
        raise ValueError("Certified Stage-D input manifest is required")
    if manifest.get("lineage", {}).get("timing_output_sha256") != sha256_path(args.timing_inputs):
        raise ValueError("Stage-D timing manifest hash mismatch")
    if manifest.get("lineage", {}).get("route_output_sha256") != sha256_path(args.route_inputs):
        raise ValueError("Stage-D route manifest hash mismatch")
    if int(manifest.get("stage_d_daily_timing_input_count", -1)) != 5345:
        raise ValueError("Unexpected Stage-D timing input count")
    route_dist = {int(k): int(v) for k, v in manifest.get("route_count_distribution", {}).items()}
    if set(route_dist) - {1, 2} or sum(route_dist.values()) != 5345:
        raise ValueError("Exact brute-force reference requires certified 1-2 route Stage-D universe")
    if int(manifest.get("naive_joint_phase_vector_count_max", -1)) > 3600:
        raise ValueError("Certified exhaustive phase bound unexpectedly increased")

    if passenger.get("status") != "PASS_PHASE2_PASSENGER_UTILITY_FRONTIER_V2" or passenger.get("contract") != "PHASE2_NO_WEIGHT_PASSENGER_UTILITY_FRONTIER_V2":
        raise ValueError("Certified Passenger Utility Frontier is required")
    if passenger.get("lineage", {}).get("frontier_output_sha256") != sha256_path(args.passenger_frontier):
        raise ValueError("Passenger frontier hash mismatch")
    if int(passenger.get("passenger_utility_frontier_row_count_all_budgets", -1)) != 16883:
        raise ValueError("Unexpected Passenger Utility context count")

    if budget.get("status") != "PASS_PHASE2_BUDGET_POLICY_FRONTIERS_V2" or budget.get("contract") != "PHASE2_NO_WEIGHT_BUDGET_POLICY_FRONTIERS_V2":
        raise ValueError("Certified budget-policy frontier validation is required")
    if budget.get("budget_semantics") != "EXPLICIT_HARD_CAP_EVALUATED_INDEPENDENTLY_NOT_A_SCORE_WEIGHT":
        raise ValueError("Budget semantics are not an explicit hard cap")

    if s8.get("status") != "PASS_S8_PHASE_OPPORTUNITY_V2_BUILD" or s8.get("contract") != "PHASE2_S8_PHASE_OPPORTUNITY_SURFACE_V2":
        raise ValueError("Certified S8 Phase Opportunity V2 is required")
    if s8.get("lineage", {}).get("s8_events_sha256") != sha256_path(args.s8_events):
        raise ValueError("Frozen S8 event hash mismatch")
    if s8.get("phase_selected") is not False or s8.get("all_phases_retained_downstream") is not True:
        raise ValueError("Upstream S8 phase domain is not complete/unselected")

    if matrix.get("status") != "PASS_REDUCED_PATH_MATRIX_V2_BUILD" or matrix.get("contract") != "PHASE2_REDUCED_STOP_PATH_MATRIX_V2":
        raise ValueError("Certified reduced path matrix V2 is required")
    if matrix.get("lineage", {}).get("reduced_path_matrix_sha256") != sha256_path(args.path_matrix):
        raise ValueError("Reduced path matrix hash mismatch")

    if s8_contract.get("model") != "PHASE2_S8_INTERCHANGE_OPPORTUNITY_V1":
        raise ValueError("Unexpected S8 interchange contract")
    if int(s8_contract.get("active_s8_events", -1)) != 74:
        raise ValueError("Unexpected frozen S8 event count")
    if s8_contract.get("transfer_quality", {}).get("hard_quality_threshold") is not None:
        raise ValueError("Exact reference must not introduce a hard S8 quality threshold")
    return manifest, passenger, budget, s8, matrix, s8_contract


def load_timing_inputs(path: Path, expected: int) -> dict[tuple[str, int, str], TimingInput]:
    out = {}
    for row in read_gzip_csv(path):
        key = (str(row["scenario_id"]), int(row["uniform_headway_min"]), str(row["span_id"]))
        if key in out:
            raise ValueError(f"Duplicate Stage-D timing key {key}")
        route_ids = json.loads(row["public_route_ids_json"])
        if not isinstance(route_ids, list) or len(route_ids) not in (1, 2):
            raise ValueError("Stage-D exact input route count is outside certified 1-2 range")
        expected_vectors = int(row["naive_joint_phase_vector_count"])
        if expected_vectors != int(row["uniform_headway_min"]) ** len(route_ids):
            raise ValueError("Stage-D manifest phase-vector cardinality mismatch")
        if bool_text(row["phase_selected"], field="phase_selected") or bool_text(row["candidate_eliminated"], field="candidate_eliminated"):
            raise ValueError("Stage-D manifest already selected/pruned candidate")
        out[key] = TimingInput(
            input_id=str(row["stage_d_input_id"]),
            scenario_id=key[0],
            topology_family=str(row["topology_family"]),
            headway=key[1],
            span_id=key[2],
            span_start=int(row["span_start_min"]),
            span_end=int(row["span_end_min"]),
            route_ids=tuple(str(x) for x in route_ids),
            expected_phase_vectors=expected_vectors,
        )
    if len(out) != expected:
        raise ValueError(f"Stage-D timing input count mismatch {len(out)} != {expected}")
    return out


def load_budget_caps(validation: dict) -> dict[str, Decimal]:
    out = {}
    for suffix, row in validation.get("budget_summary", {}).items():
        out[str(suffix)] = D(str(row["cap_annual_bus_km"]))
    expected = {"m20pct", "m10pct", "reference", "p10pct", "p20pct", "p30pct"}
    if set(out) != expected:
        raise ValueError(f"Unexpected budget suffixes {sorted(out)}")
    return out


def load_plan_contexts(path: Path, caps: dict[str, Decimal], timing_keys: set[tuple[str, int, str]]):
    out: dict[tuple[str, int, str], list[PlanContext]] = {key: [] for key in timing_keys}
    context_ids = set()
    for row in read_gzip_csv(path):
        budget = str(row["budget_suffix"])
        if budget not in caps:
            raise ValueError(f"Unknown Passenger Utility budget {budget}")
        key = (str(row["scenario_id"]), int(row["uniform_headway_min"]), str(row["span_id"]))
        if key not in out:
            raise ValueError(f"Passenger context missing Stage-D timing key {key}")
        context_id = f"{budget}|{row['plan_id']}"
        if context_id in context_ids:
            raise ValueError(f"Duplicate budget-qualified plan context {context_id}")
        context_ids.add(context_id)
        out[key].append(PlanContext(
            context_id=context_id,
            plan_id=str(row["plan_id"]),
            budget_suffix=budget,
            budget_cap=caps[budget],
            scenario_id=key[0],
            topology_family=str(row["topology_family"]),
            headway=key[1],
            span_id=key[2],
            calendar_id=str(row["calendar_id"]),
            annual_service_days=int(row["annual_service_days"]),
            continuous_annual_bus_km=D(str(row["annual_bus_km"])),
        ))
    if len(context_ids) != 16883:
        raise ValueError(f"Unexpected Passenger Utility context count {len(context_ids)}")
    if any(not rows for rows in out.values()):
        raise ValueError("Stage-D timing input without Passenger Utility contexts")
    return out, context_ids


def load_rail_events(path: Path) -> tuple[ExactRailEvent, ...]:
    rows = []
    for row in read_csv(path):
        if str(row["epistemic_status"]) != "DERIVED_FROM_LIVE_OFFICIAL_GTFS":
            raise ValueError("S8 event lost official-GTFS status")
        event = ExactRailEvent(
            trip_id=str(row["trip_id"]),
            direction=str(row["direction"]).upper(),
            arrival_min=D(str(row["arrival_min"])),
            departure_min=D(str(row["departure_min"])),
        )
        event.validate()
        rows.append(event)
    if len(rows) != 74 or sum(r.direction == "LECCO" for r in rows) != 37 or sum(r.direction == "MILANO" for r in rows) != 37:
        raise ValueError("Expected 74 S8 events, 37 per direction")
    return tuple(rows)


def load_matrix(path: Path):
    out = {}
    for row in read_csv(path):
        key = (str(row["origin"]), str(row["destination"]))
        if key in out:
            raise ValueError(f"Duplicate path-matrix leg {key}")
        distance = D(str(row["distance_km"]))
        runtime = D(str(row["runtime_min"]))
        if distance <= 0 or runtime <= 0:
            raise ValueError("Path-matrix distance/runtime must be positive")
        out[key] = (distance, runtime)
    if not out:
        raise ValueError("Empty reduced path matrix")
    return out


def compute_route(route_row: dict[str, str], matrix) -> ExactRoute:
    route_id = str(route_row["route_id"])
    anchors = json.loads(route_row["anchors_json"])
    if not isinstance(anchors, list) or len(anchors) < 2 or str(anchors[0]) != "rail:S01514":
        raise ValueError(f"Invalid exact route anchors for {route_id}")
    public_distance = D(0)
    public_runtime = D(0)
    for a, b in zip(anchors[:-1], anchors[1:]):
        try:
            distance, runtime = matrix[(str(a), str(b))]
        except KeyError as exc:
            raise ValueError(f"Missing exact route leg {a}->{b}") from exc
        public_distance += distance
        public_runtime += runtime
    returns = str(anchors[-1]) == str(anchors[0])
    cycle_distance = public_distance
    cycle_runtime = public_runtime
    if not returns:
        try:
            distance, runtime = matrix[(str(anchors[-1]), str(anchors[0]))]
        except KeyError as exc:
            raise ValueError(f"Missing exact technical return leg for {route_id}") from exc
        cycle_distance += distance
        cycle_runtime += runtime
    route = ExactRoute(route_id, public_runtime, cycle_runtime, cycle_distance, returns)
    route.validate()
    if abs(public_runtime - D(str(route_row["public_runtime_min"]))) > TOL:
        raise ValueError(f"Public runtime mismatch for {route_id}")
    if abs(cycle_runtime - D(str(route_row["cycle_runtime_min"]))) > TOL:
        raise ValueError(f"Cycle runtime mismatch for {route_id}")
    declared_returns = bool_text(route_row["public_service_returns_to_hub"], field="public_service_returns_to_hub")
    b2r = bool_text(route_row["bus_to_rail_passenger_event_supported"], field="bus_to_rail_passenger_event_supported")
    r2b = bool_text(route_row["rail_to_bus_passenger_event_supported"], field="rail_to_bus_passenger_event_supported")
    if declared_returns != returns or b2r != returns or not r2b:
        raise ValueError(f"Passenger event geometry mismatch for {route_id}")
    return route


def load_routes(path: Path, matrix) -> dict[str, ExactRoute]:
    out = {}
    for row in read_csv(path):
        route = compute_route(row, matrix)
        if route.route_id in out:
            raise ValueError(f"Duplicate Stage-D route {route.route_id}")
        out[route.route_id] = route
    if not out:
        raise ValueError("Stage-D route input is empty")
    return out


def vector_key(record: VectorRecord) -> tuple:
    # maximise current normative robust objective, then deterministic lowest
    # route-specific phase tuple. Fleet is reported, not hidden in selection.
    return (record.robust_min_quality, record.robust_mean_quality, tuple(-p for p in record.phases))


def block_selected_timetable(routes: Sequence[ExactRoute], phases: Sequence[int], timing: TimingInput):
    trips = []
    for route, phase in zip(routes, phases):
        trips.extend(materialise_route_trips(
            route,
            phase_min=phase,
            headway_min=timing.headway,
            span_start_min=timing.span_start,
            span_end_min=timing.span_end,
        ))
    result = {}
    for recovery in RECOVERIES:
        fleet, blocked = minimum_common_hub_blocks(trips, recovery_min=recovery)
        result[recovery] = (fleet, blocked)
    return tuple(trips), result


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    for name in (
        "timing_inputs", "route_inputs", "manifest_validation",
        "passenger_frontier", "passenger_validation", "budget_validation",
        "path_matrix", "matrix_validation", "s8_events", "s8_validation", "s8_contract",
        "s8_sensitivity_config", "context_output", "timetable_output", "trip_output", "validation",
    ):
        p.add_argument("--" + name.replace("_", "-"), dest=name, type=Path, required=True)
    args = p.parse_args()

    manifest_v, passenger_v, budget_v, s8_v, matrix_v, s8_contract_v = validate_upstream(args)
    profiles, sensitivity_cfg = load_profiles(args.s8_sensitivity_config)
    timings = load_timing_inputs(args.timing_inputs, int(manifest_v["stage_d_daily_timing_input_count"]))
    caps = load_budget_caps(budget_v)
    contexts, all_context_ids = load_plan_contexts(args.passenger_frontier, caps, set(timings))
    matrix = load_matrix(args.path_matrix)
    routes = load_routes(args.route_inputs, matrix)
    rail_events = load_rail_events(args.s8_events)

    phase_cache: dict[tuple[str, int, int, int], tuple[RoutePhaseEvidence, ...]] = {}
    evaluated_vectors_total = 0
    context_rows = []
    selected_timetables: dict[str, dict[str, object]] = {}
    selected_trip_payload: dict[str, tuple[TimingInput, tuple[ExactRoute, ...], tuple[int, ...], tuple, dict]] = {}
    exact_infeasible_contexts = []
    selected_contexts_by_budget = {suffix: 0 for suffix in caps}
    infeasible_contexts_by_budget = {suffix: 0 for suffix in caps}

    for timing_key in sorted(timings, key=lambda x: (x[1], x[2], x[0])):
        timing = timings[timing_key]
        route_list = tuple(routes[rid] for rid in timing.route_ids)
        per_route = []
        for route in route_list:
            cache_key = (route.route_id, timing.headway, timing.span_start, timing.span_end)
            evidence = phase_cache.get(cache_key)
            if evidence is None:
                evidence = tuple(
                    route_phase_evidence(
                        route,
                        phase_min=phase,
                        headway_min=timing.headway,
                        span_start_min=timing.span_start,
                        span_end_min=timing.span_end,
                        rail_events=rail_events,
                        profiles=profiles,
                    )
                    for phase in range(timing.headway)
                )
                phase_cache[cache_key] = evidence
            per_route.append(evidence)

        vectors: list[VectorRecord] = []
        for rows in itertools.product(*per_route):
            phases = tuple(row.phase_min for row in rows)
            qmin, qmean = phase_vector_objective(rows)
            vectors.append(VectorRecord(
                phases=phases,
                route_rows=tuple(rows),
                exact_daily_bus_km=sum((row.exact_daily_bus_km for row in rows), D(0)),
                robust_min_quality=qmin,
                robust_mean_quality=qmean,
            ))
        if len(vectors) != timing.expected_phase_vectors:
            raise ValueError(f"Exact enumeration count mismatch for {timing.input_id}")
        evaluated_vectors_total += len(vectors)

        for context in contexts[timing_key]:
            feasible = [
                rec for rec in vectors
                if rec.exact_daily_bus_km * context.annual_service_days <= context.budget_cap + TOL
            ]
            if not feasible:
                infeasible_contexts_by_budget[context.budget_suffix] += 1
                exact_infeasible_contexts.append(context.context_id)
                context_rows.append({
                    "plan_context_id": context.context_id,
                    "plan_id": context.plan_id,
                    "budget_suffix": context.budget_suffix,
                    "budget_cap_annual_bus_km": f"{context.budget_cap:f}",
                    "scenario_id": context.scenario_id,
                    "topology_family": context.topology_family,
                    "uniform_headway_min": context.headway,
                    "span_id": context.span_id,
                    "calendar_id": context.calendar_id,
                    "annual_service_days": context.annual_service_days,
                    "stage_d_input_id": timing.input_id,
                    "phase_vectors_evaluated_once_for_daily_input": len(vectors),
                    "exact_budget_feasible_phase_vector_count": 0,
                    "exact_budget_hard_eligible": "false",
                    "selected_timetable_id": "",
                    "selected_route_phases_json": "",
                    "robust_min_transfer_quality": "",
                    "robust_unweighted_mean_transfer_quality": "",
                    "worst_cell_nominal_hard_miss_share": "",
                    "mean_cell_nominal_hard_miss_share": "",
                    "exact_daily_bus_km": "",
                    "exact_annual_bus_km": "",
                    "continuous_annual_bus_km": f"{context.continuous_annual_bus_km:f}",
                    "exact_minus_continuous_annual_bus_km": "",
                    "exact_fleet_recovery5": "",
                    "exact_fleet_recovery10": "",
                    "exact_fleet_recovery15": "",
                    "phase_selection_rule": "NO_EXACT_BUDGET_FEASIBLE_PHASE_VECTOR",
                    "worker_reference_used_for_phase_selection": "false",
                    "delay_robustness_evaluated": "false",
                    "primary_selected": "false",
                    "runner_up_selected": "false",
                })
                continue

            best = max(feasible, key=vector_key)
            timetable_id = stable_timetable_id(timing.input_id, best.phases)
            exact_annual_km = best.exact_daily_bus_km * context.annual_service_days
            miss_worst, miss_mean = aggregate_hard_miss(best.route_rows)
            if timetable_id not in selected_timetables:
                trips, blocks = block_selected_timetable(route_list, best.phases, timing)
                route_cells = {
                    row.route_id: {
                        label: {"mean_quality": quality, "nominal_hard_miss_share": miss}
                        for label, quality, miss in zip(row.cell_labels, row.cell_mean_quality, row.cell_hard_miss_share)
                    }
                    for row in best.route_rows
                }
                selected_timetables[timetable_id] = {
                    "selected_timetable_id": timetable_id,
                    "stage_d_input_id": timing.input_id,
                    "scenario_id": timing.scenario_id,
                    "topology_family": timing.topology_family,
                    "uniform_headway_min": timing.headway,
                    "span_id": timing.span_id,
                    "span_start_min": timing.span_start,
                    "span_end_min": timing.span_end,
                    "public_route_count": len(route_list),
                    "public_route_ids_json": json.dumps(list(timing.route_ids), separators=(",", ":")),
                    "selected_route_phases_json": json.dumps(dict(zip(timing.route_ids, best.phases)), sort_keys=True, separators=(",", ":")),
                    "robust_min_transfer_quality": f"{best.robust_min_quality:.12f}",
                    "robust_unweighted_mean_transfer_quality": f"{best.robust_mean_quality:.12f}",
                    "worst_cell_nominal_hard_miss_share": f"{miss_worst:.12f}",
                    "mean_cell_nominal_hard_miss_share": f"{miss_mean:.12f}",
                    "exact_daily_bus_km": f"{best.exact_daily_bus_km:.9f}",
                    "explicit_trip_count_per_service_day": len(trips),
                    "exact_fleet_recovery5": blocks[5][0],
                    "exact_fleet_recovery10": blocks[10][0],
                    "exact_fleet_recovery15": blocks[15][0],
                    "route_profile_cell_evidence_json": json.dumps(route_cells, sort_keys=True, separators=(",", ":")),
                    "phase_selection_rule": "MAX_ROBUST_MIN_QUALITY_THEN_MAX_UNWEIGHTED_MEAN_QUALITY_THEN_LOWEST_ROUTE_PHASE_TUPLE__AFTER_CONTEXT_BUDGET_FILTER",
                    "route_specific_phase_selection": "true",
                    "worker_reference_used_for_phase_selection": "false",
                    "passenger_weighting_applied": "false",
                    "topology_weighting_applied": "false",
                    "hard_s8_quality_threshold_applied": "false",
                    "joint_vehicle_block_timetable_feasibility_evaluated": "true",
                    "exact_timetable_constructed": "true",
                    "delay_robustness_evaluated": "false",
                    "primary_selected": "false",
                    "runner_up_selected": "false",
                }
                selected_trip_payload[timetable_id] = (timing, route_list, best.phases, trips, blocks)
            else:
                existing = selected_timetables[timetable_id]
                if existing["exact_daily_bus_km"] != f"{best.exact_daily_bus_km:.9f}":
                    raise ValueError("Stable timetable ID collision on daily production")

            table = selected_timetables[timetable_id]
            selected_contexts_by_budget[context.budget_suffix] += 1
            context_rows.append({
                "plan_context_id": context.context_id,
                "plan_id": context.plan_id,
                "budget_suffix": context.budget_suffix,
                "budget_cap_annual_bus_km": f"{context.budget_cap:f}",
                "scenario_id": context.scenario_id,
                "topology_family": context.topology_family,
                "uniform_headway_min": context.headway,
                "span_id": context.span_id,
                "calendar_id": context.calendar_id,
                "annual_service_days": context.annual_service_days,
                "stage_d_input_id": timing.input_id,
                "phase_vectors_evaluated_once_for_daily_input": len(vectors),
                "exact_budget_feasible_phase_vector_count": len(feasible),
                "exact_budget_hard_eligible": "true",
                "selected_timetable_id": timetable_id,
                "selected_route_phases_json": table["selected_route_phases_json"],
                "robust_min_transfer_quality": table["robust_min_transfer_quality"],
                "robust_unweighted_mean_transfer_quality": table["robust_unweighted_mean_transfer_quality"],
                "worst_cell_nominal_hard_miss_share": table["worst_cell_nominal_hard_miss_share"],
                "mean_cell_nominal_hard_miss_share": table["mean_cell_nominal_hard_miss_share"],
                "exact_daily_bus_km": table["exact_daily_bus_km"],
                "exact_annual_bus_km": f"{exact_annual_km:.6f}",
                "continuous_annual_bus_km": f"{context.continuous_annual_bus_km:f}",
                "exact_minus_continuous_annual_bus_km": f"{exact_annual_km-context.continuous_annual_bus_km:.6f}",
                "exact_fleet_recovery5": table["exact_fleet_recovery5"],
                "exact_fleet_recovery10": table["exact_fleet_recovery10"],
                "exact_fleet_recovery15": table["exact_fleet_recovery15"],
                "phase_selection_rule": table["phase_selection_rule"],
                "worker_reference_used_for_phase_selection": "false",
                "delay_robustness_evaluated": "false",
                "primary_selected": "false",
                "runner_up_selected": "false",
            })

    if len(context_rows) != len(all_context_ids):
        raise ValueError("Exact Stage-D context output does not preserve all Stage-C contexts")
    if {row["plan_context_id"] for row in context_rows} != all_context_ids:
        raise ValueError("Exact Stage-D context identity mismatch")
    if evaluated_vectors_total != int(manifest_v["naive_joint_phase_vector_count_sum"]):
        raise ValueError(f"Exact vector total {evaluated_vectors_total} != certified manifest cardinality")

    context_fields = list(context_rows[0])
    raw_c, text_c, writer_c = deterministic_gzip_writer(args.context_output, context_fields)
    try:
        for row in sorted(context_rows, key=lambda r: (r["budget_suffix"], r["plan_context_id"])):
            writer_c.writerow(row)
    finally:
        text_c.close(); raw_c.close()

    timetable_fields = list(next(iter(selected_timetables.values()))) if selected_timetables else []
    args.timetable_output.parent.mkdir(parents=True, exist_ok=True)
    with args.timetable_output.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=timetable_fields, lineterminator="\n")
        writer.writeheader()
        for tid in sorted(selected_timetables):
            writer.writerow(selected_timetables[tid])

    trip_fields = [
        "selected_timetable_id", "stage_d_input_id", "scenario_id", "route_id", "route_phase_min",
        "uniform_headway_min", "span_id", "departure_min", "public_service_end_min", "vehicle_return_hub_min",
        "public_service_returns_to_hub", "vehicle_id_recovery5", "ready_min_recovery5",
        "vehicle_id_recovery10", "ready_min_recovery10", "vehicle_id_recovery15", "ready_min_recovery15",
    ]
    raw_t, text_t, writer_t = deterministic_gzip_writer(args.trip_output, trip_fields)
    trip_count = 0
    try:
        for tid in sorted(selected_trip_payload):
            timing, route_list, phases, trips, blocks = selected_trip_payload[tid]
            block_maps = {
                recovery: {
                    (b.trip.route_id, b.trip.departure_min): b
                    for b in blocked
                }
                for recovery, (_, blocked) in blocks.items()
            }
            returns = {route.route_id: route.public_returns_to_hub for route in route_list}
            phase_by_route = dict(zip(timing.route_ids, phases))
            for trip in sorted(trips, key=lambda x: (x.departure_min, x.route_id)):
                row = {
                    "selected_timetable_id": tid,
                    "stage_d_input_id": timing.input_id,
                    "scenario_id": timing.scenario_id,
                    "route_id": trip.route_id,
                    "route_phase_min": phase_by_route[trip.route_id],
                    "uniform_headway_min": timing.headway,
                    "span_id": timing.span_id,
                    "departure_min": f"{trip.departure_min:f}",
                    "public_service_end_min": f"{trip.public_service_end_min:f}",
                    "vehicle_return_hub_min": f"{trip.vehicle_return_hub_min:f}",
                    "public_service_returns_to_hub": "true" if returns[trip.route_id] else "false",
                }
                for recovery in RECOVERIES:
                    b = block_maps[recovery][(trip.route_id, trip.departure_min)]
                    row[f"vehicle_id_recovery{recovery}"] = f"V{b.vehicle_index+1}"
                    row[f"ready_min_recovery{recovery}"] = f"{b.ready_min:f}"
                writer_t.writerow(row)
                trip_count += 1
    finally:
        text_t.close(); raw_t.close()

    feasible_contexts = len(context_rows) - len(exact_infeasible_contexts)
    report = {
        "status": STATUS,
        "contract": CONTRACT,
        "exhaustive_phase_enumeration": True,
        "approximate_or_heuristic_phase_search": False,
        "stage_d_daily_timing_input_count": len(timings),
        "stage_c_plan_context_count": len(context_rows),
        "exact_budget_hard_eligible_context_count": feasible_contexts,
        "exact_budget_hard_ineligible_context_count": len(exact_infeasible_contexts),
        "exact_budget_hard_ineligible_context_ids_sample": sorted(exact_infeasible_contexts)[:50],
        "eligible_context_count_by_budget": selected_contexts_by_budget,
        "ineligible_context_count_by_budget": infeasible_contexts_by_budget,
        "phase_vectors_evaluated": evaluated_vectors_total,
        "certified_phase_vectors_expected": int(manifest_v["naive_joint_phase_vector_count_sum"]),
        "route_phase_evidence_cache_count": len(phase_cache),
        "unique_selected_exact_timetable_count": len(selected_timetables),
        "explicit_trip_row_count": trip_count,
        "max_public_route_count": max(len(t.route_ids) for t in timings.values()),
        "max_phase_vectors_per_timing_input": max(t.expected_phase_vectors for t in timings.values()),
        "recovery_sensitivities_min": list(RECOVERIES),
        "transfer_profile_ids": [p.profile_id for p in profiles],
        "phase_objective_primary": sensitivity_cfg["phase_objective"]["primary"],
        "phase_objective_secondary": sensitivity_cfg["phase_objective"]["secondary"],
        "route_specific_phase_reconsideration_permitted_by_config": True,
        "phase_selection_semantics": "EXACT_ROUTE_SPECIFIC_VECTOR_AFTER_CONTEXT_ANNUAL_BUS_KM_HARD_CAP__ROBUST_MIN_THEN_UNWEIGHTED_MEAN_THEN_LOWEST_PHASE_TUPLE",
        "passenger_weighting_applied": False,
        "topology_weighting_applied": False,
        "worker_reference_used_for_phase_selection": False,
        "worker_reference_assigned_to_routes": False,
        "hard_s8_quality_threshold_applied": False,
        "nominal_hard_miss_is_reported_not_phase_threshold": True,
        "joint_vehicle_block_timetable_feasibility_evaluated": True,
        "exact_timetable_constructed": True,
        "delay_robustness_evaluated": False,
        "delay_robustness_deferred_to": sensitivity_cfg.get("delay_robustness_deferred_to"),
        "municipal_od_downscaled": False,
        "ridership_forecast": False,
        "decision_budget_selected": False,
        "calendar_selected": False,
        "recovery_selected": False,
        "service_policy_selected": False,
        "topology_ranked": False,
        "primary_selected": False,
        "runner_up_selected": False,
        "weighted_composite_score": False,
        "epistemic_note": (
            "This is the exhaustive Stage-D reference oracle, not the final robustness tournament. Every certified "
            "route-specific integer-minute phase vector is evaluated once per daily timing input. Exact annual production "
            "is then checked separately for every budget-qualified Stage-C context because phase offsets can change the "
            "number of trips inside an end-exclusive service span. The S8 phase objective is the current declared "
            "unweighted robust transfer-quality sensitivity objective. Delay/runtime perturbation and final "
            "PRIMARY/RUNNER-UP selection remain downstream."
        ),
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
            "s8_contract_sha256": sha256_path(args.s8_contract),
            "s8_sensitivity_config_sha256": sha256_path(args.s8_sensitivity_config),
            "context_output": str(args.context_output),
            "context_output_sha256": sha256_path(args.context_output),
            "timetable_output": str(args.timetable_output),
            "timetable_output_sha256": sha256_path(args.timetable_output),
            "trip_output": str(args.trip_output),
            "trip_output_sha256": sha256_path(args.trip_output),
        },
    }
    args.validation.parent.mkdir(parents=True, exist_ok=True)
    args.validation.write_text(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in (
        "status", "stage_d_daily_timing_input_count", "stage_c_plan_context_count",
        "exact_budget_hard_eligible_context_count", "exact_budget_hard_ineligible_context_count",
        "phase_vectors_evaluated", "unique_selected_exact_timetable_count", "explicit_trip_row_count",
    )}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
