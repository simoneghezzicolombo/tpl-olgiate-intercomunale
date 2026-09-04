#!/usr/bin/env python3
"""Build a lossless Stage-D daily-timing input manifest from certified Stage-C plans.

The only deduplication performed is across plan contexts sharing the same
(scenario_id, headway, span). Budget and annual calendar do not alter the daily
route geometry or clockface phase domain, so those plan contexts are preserved
as members of one exact-timing input. No cross-scenario or route-set equivalence
is assumed, no phase is selected and no candidate is removed.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

STATUS = "PASS_PHASE2_STAGE_D_INPUT_MANIFEST_V2"
CONTRACT = "PHASE2_LOSSLESS_DAILY_TIMING_INPUT_MANIFEST_V2"
RECOVERIES = (5, 10, 15)


def sha256_path(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def read_gzip_csv(path: Path):
    with gzip.open(path, "rt", encoding="utf-8-sig", newline="") as handle:
        yield from csv.DictReader(handle)


def deterministic_gzip_writer(path: Path, fields: list[str]):
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = path.open("wb")
    gz = gzip.GzipFile(filename="", mode="wb", fileobj=raw, compresslevel=9, mtime=0)
    text = io.TextIOWrapper(gz, encoding="utf-8", newline="")
    writer = csv.DictWriter(text, fieldnames=fields, lineterminator="\n", extrasaction="ignore")
    writer.writeheader()
    return raw, text, writer


def stable_input_id(scenario_id: str, headway: int, span_id: str) -> str:
    payload = json.dumps(
        {"scenario_id": scenario_id, "uniform_headway_min": headway, "span_id": span_id},
        sort_keys=True,
        separators=(",", ":"),
    )
    return "D4I2_" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def validate_upstream(args):
    passenger = read_json(args.passenger_validation)
    s8opp = read_json(args.s8_opportunity_validation)
    continuity = read_json(args.continuity_validation)
    s8 = read_json(args.s8_validation)

    if passenger.get("status") != "PASS_PHASE2_PASSENGER_UTILITY_FRONTIER_V2" or passenger.get("contract") != "PHASE2_NO_WEIGHT_PASSENGER_UTILITY_FRONTIER_V2":
        raise ValueError("Certified Passenger Utility Frontier V2 is required")
    if passenger.get("lineage", {}).get("frontier_output_sha256") != sha256_path(args.passenger_frontier):
        raise ValueError("Passenger frontier hash mismatch")
    if int(passenger.get("passenger_utility_frontier_row_count_all_budgets", -1)) != 16883:
        raise ValueError("Unexpected Passenger Utility plan count")

    if s8opp.get("status") != "PASS_PHASE2_S8_ROBUST_OPPORTUNITY_SURFACE_V2" or s8opp.get("contract") != "PHASE2_LINEAGE_PINNED_PRE_TIMETABLE_S8_OPPORTUNITY_V2":
        raise ValueError("Certified S8 Robust Opportunity V2 is required")
    if s8opp.get("lineage_compatibility", {}).get("output_sha256") != sha256_path(args.s8_opportunity):
        raise ValueError("S8 opportunity output hash mismatch")
    if int(s8opp.get("passenger_utility_plan_count", -1)) != 16883:
        raise ValueError("Unexpected S8 opportunity plan count")
    if s8opp.get("cross_route_phase_selected") is not False or s8opp.get("exact_timetable_constructed") is not False:
        raise ValueError("S8 opportunity upstream already contains Stage-D selection")

    if continuity.get("status") != "PASS_PHASE2_CURRENT_SERVICE_CONTINUITY_LOWER_BOUND_V2" or continuity.get("contract") != "PHASE2_CERTIFIED_LOCALIZABLE_CURRENT_SERVICE_CONTINUITY_LOWER_BOUND_V2":
        raise ValueError("Certified current-service continuity V2 is required")
    if continuity.get("lineage", {}).get("scenario_output_sha256") != sha256_path(args.continuity_scenarios):
        raise ValueError("Continuity scenario output hash mismatch")
    if continuity.get("continuity_used_to_eliminate_candidate") is not False:
        raise ValueError("Continuity upstream must not eliminate candidates")

    if s8.get("status") != "PASS_S8_PHASE_OPPORTUNITY_V2_BUILD" or s8.get("contract") != "PHASE2_S8_PHASE_OPPORTUNITY_SURFACE_V2":
        raise ValueError("Certified S8 route/mapping lineage is required")
    if s8.get("lineage", {}).get("route_universe_sha256") != sha256_path(args.route_universe):
        raise ValueError("Route-universe hash mismatch")
    if s8.get("lineage", {}).get("scenario_route_mapping_sha256") != sha256_path(args.scenario_mapping):
        raise ValueError("Scenario-mapping hash mismatch")
    if s8.get("phase_selected") is not False or s8.get("all_phases_retained_downstream") is not True:
        raise ValueError("Upstream phase domain must remain complete and unselected")
    return passenger, s8opp, continuity, s8


def load_passenger_groups(path: Path):
    groups: dict[tuple[str, int, str], list[dict[str, str]]] = defaultdict(list)
    plan_ids: set[str] = set()
    for row in read_gzip_csv(path):
        plan_id = str(row["plan_id"])
        if plan_id in plan_ids:
            raise ValueError(f"Duplicate Passenger Utility plan_id {plan_id}")
        plan_ids.add(plan_id)
        key = (str(row["scenario_id"]), int(row["uniform_headway_min"]), str(row["span_id"]))
        groups[key].append(row)
    if len(plan_ids) != 16883:
        raise ValueError(f"Unexpected Passenger Utility plan count {len(plan_ids)}")
    return groups, plan_ids


def load_s8_opportunity(path: Path) -> dict[tuple[str, int, str], dict[str, str]]:
    out: dict[tuple[str, int, str], dict[str, str]] = {}
    for row in read_gzip_csv(path):
        key = (str(row["scenario_id"]), int(row["uniform_headway_min"]), str(row["span_id"]))
        if key in out:
            # This file is plan-level, so duplicate scenario/timing keys are expected.
            prior = out[key]
            invariant = [
                "s8_opportunity_class", "s8_public_complete_match_route_count",
                "s8_public_complete_match_route_share", "s8_public_all_routes_have_some_complete_match_phase",
                "s8_public_any_route_has_some_complete_match_phase",
                "s8_roundtrip_best_complete_gap_min_min", "s8_roundtrip_best_complete_gap_min_max",
                "s8_roundtrip_worst_complete_gap_min_min", "s8_roundtrip_worst_complete_gap_min_max",
                "s8_rail_to_bus_only_best_complete_gap_min_min", "s8_rail_to_bus_only_best_complete_gap_min_max",
                "s8_rail_to_bus_only_worst_complete_gap_min_min", "s8_rail_to_bus_only_worst_complete_gap_min_max",
            ]
            if any(str(prior.get(f, "")) != str(row.get(f, "")) for f in invariant):
                raise ValueError(f"S8 opportunity differs within same scenario/timing key {key}")
            continue
        out[key] = row
    return out


def load_continuity(path: Path) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    for row in read_gzip_csv(path):
        sid = str(row["scenario_id"])
        if sid in out:
            raise ValueError(f"Duplicate continuity scenario {sid}")
        out[sid] = row
    if len(out) != 100000:
        raise ValueError("Continuity scenario universe must contain 100000 rows")
    return out


def load_scenario_mapping(path: Path, wanted_scenarios: set[str]):
    out: dict[str, tuple[str, list[str]]] = {}
    for row in read_gzip_csv(path):
        sid = str(row["scenario_id"])
        if sid not in wanted_scenarios:
            continue
        route_ids = json.loads(row["public_route_ids_json"])
        if not isinstance(route_ids, list) or not route_ids:
            raise ValueError(f"Scenario {sid} has invalid public route mapping")
        out[sid] = (str(row["topology_family"]), [str(x) for x in route_ids])
    missing = wanted_scenarios - set(out)
    if missing:
        raise ValueError(f"Scenario mapping missing {len(missing)} Stage-D scenarios")
    return out


def load_routes(path: Path) -> dict[str, dict[str, str]]:
    rows = read_csv(path)
    out: dict[str, dict[str, str]] = {}
    for row in rows:
        rid = str(row["route_id"])
        if rid in out:
            raise ValueError(f"Duplicate route_id {rid}")
        anchors = json.loads(row["anchors_json"])
        if not isinstance(anchors, list) or len(anchors) < 2 or str(anchors[0]) != "rail:S01514":
            raise ValueError(f"Invalid route anchors for {rid}")
        out[rid] = row
    return out


def _json_sorted(values) -> str:
    return json.dumps(sorted(set(values)), ensure_ascii=False, separators=(",", ":"))


def _optional_invariant(group: list[dict[str, str]], field: str):
    values = {str(r.get(field, "")) for r in group}
    if len(values) != 1:
        raise ValueError(f"Daily timing invariant {field} differs within grouped plan context")
    return next(iter(values))


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--passenger-frontier", type=Path, required=True)
    p.add_argument("--passenger-validation", type=Path, required=True)
    p.add_argument("--s8-opportunity", type=Path, required=True)
    p.add_argument("--s8-opportunity-validation", type=Path, required=True)
    p.add_argument("--continuity-scenarios", type=Path, required=True)
    p.add_argument("--continuity-validation", type=Path, required=True)
    p.add_argument("--scenario-mapping", type=Path, required=True)
    p.add_argument("--route-universe", type=Path, required=True)
    p.add_argument("--s8-validation", type=Path, required=True)
    p.add_argument("--timing-output", type=Path, required=True)
    p.add_argument("--route-output", type=Path, required=True)
    p.add_argument("--validation", type=Path, required=True)
    args = p.parse_args()

    passenger_v, s8opp_v, continuity_v, s8_v = validate_upstream(args)
    groups, all_plan_ids = load_passenger_groups(args.passenger_frontier)
    if len(groups) != int(s8opp_v.get("unique_stage_c_scenario_timing_key_count", -1)):
        raise ValueError(f"Stage-D grouping count differs from certified S8 opportunity keys: {len(groups)}")
    s8opp = load_s8_opportunity(args.s8_opportunity)
    if set(groups) != set(s8opp):
        raise ValueError("Passenger and S8-opportunity scenario/timing key universes differ")
    continuity = load_continuity(args.continuity_scenarios)
    wanted_scenarios = {key[0] for key in groups}
    mapping = load_scenario_mapping(args.scenario_mapping, wanted_scenarios)
    routes = load_routes(args.route_universe)

    timing_fields = [
        "stage_d_input_id", "scenario_id", "topology_family", "uniform_headway_min", "span_id",
        "span_start_min", "span_end_min", "public_route_count", "public_route_ids_json",
        "naive_joint_phase_vector_count", "naive_joint_phase_vector_log10",
        "represented_plan_count", "represented_plan_ids_json", "represented_budget_suffixes_json",
        "represented_calendar_ids_json", "represented_annual_service_days_json", "recovery_values_json",
        "s8_opportunity_class", "s8_public_complete_match_route_count", "s8_public_complete_match_route_share",
        "s8_public_all_routes_have_some_complete_match_phase", "s8_public_any_route_has_some_complete_match_phase",
        "retained_current_localizable_cluster_count", "retained_current_localizable_cluster_share",
        "retained_current_localizable_directed_adjacent_pair_count", "retained_current_localizable_directed_adjacent_pair_share",
        "retained_current_localizable_undirected_adjacent_pair_count", "retained_current_localizable_undirected_adjacent_pair_share",
        "historical_station_cluster_EX_011_retained", "daily_timing_context_deduplicated_losslessly",
        "cross_scenario_equivalence_assumed", "phase_selected", "exact_timetable_constructed",
        "candidate_eliminated", "primary_selected", "runner_up_selected",
    ]

    route_use_count: Counter[str] = Counter()
    route_count_dist: Counter[int] = Counter()
    headway_dist: Counter[int] = Counter()
    complexity_values: list[int] = []
    represented_seen: set[str] = set()

    raw, text, writer = deterministic_gzip_writer(args.timing_output, timing_fields)
    try:
        for key in sorted(groups, key=lambda x: (x[1], x[2], x[0])):
            sid, headway, span_id = key
            group = groups[key]
            topology, route_ids = mapping[sid]
            for rid in route_ids:
                if rid not in routes:
                    raise ValueError(f"Stage-D scenario {sid} references unknown route {rid}")
                route_use_count[rid] += 1
            if int(_optional_invariant(group, "uniform_headway_min")) != headway:
                raise ValueError("Headway changed inside Stage-D group")
            if _optional_invariant(group, "span_id") != span_id:
                raise ValueError("Span changed inside Stage-D group")
            span_start = int(_optional_invariant(group, "span_start_min"))
            span_end = int(_optional_invariant(group, "span_end_min"))
            if span_end <= span_start:
                raise ValueError("Invalid Stage-D span")
            if any(str(r["topology_family"]) != topology for r in group):
                raise ValueError(f"Topology family mismatch for {sid}")
            if any(int(r["public_route_count"]) != len(route_ids) for r in group):
                raise ValueError(f"Public route count mismatch for {sid}")

            plan_ids = [str(r["plan_id"]) for r in group]
            overlap = represented_seen.intersection(plan_ids)
            if overlap:
                raise ValueError(f"Passenger plans represented in multiple Stage-D inputs: {sorted(overlap)[:3]}")
            represented_seen.update(plan_ids)

            phase_vectors = headway ** len(route_ids)
            route_count_dist[len(route_ids)] += 1
            headway_dist[headway] += 1
            complexity_values.append(phase_vectors)
            opp = s8opp[key]
            cont = continuity[sid]
            writer.writerow({
                "stage_d_input_id": stable_input_id(sid, headway, span_id),
                "scenario_id": sid,
                "topology_family": topology,
                "uniform_headway_min": headway,
                "span_id": span_id,
                "span_start_min": span_start,
                "span_end_min": span_end,
                "public_route_count": len(route_ids),
                "public_route_ids_json": json.dumps(route_ids, separators=(",", ":")),
                "naive_joint_phase_vector_count": str(phase_vectors),
                "naive_joint_phase_vector_log10": f"{math.log10(phase_vectors):.9f}",
                "represented_plan_count": len(plan_ids),
                "represented_plan_ids_json": _json_sorted(plan_ids),
                "represented_budget_suffixes_json": _json_sorted(str(r["budget_suffix"]) for r in group),
                "represented_calendar_ids_json": _json_sorted(str(r["calendar_id"]) for r in group),
                "represented_annual_service_days_json": _json_sorted(int(r["annual_service_days"]) for r in group),
                "recovery_values_json": json.dumps(list(RECOVERIES), separators=(",", ":")),
                "s8_opportunity_class": str(opp["s8_opportunity_class"]),
                "s8_public_complete_match_route_count": str(opp["s8_public_complete_match_route_count"]),
                "s8_public_complete_match_route_share": str(opp["s8_public_complete_match_route_share"]),
                "s8_public_all_routes_have_some_complete_match_phase": str(opp["s8_public_all_routes_have_some_complete_match_phase"]),
                "s8_public_any_route_has_some_complete_match_phase": str(opp["s8_public_any_route_has_some_complete_match_phase"]),
                "retained_current_localizable_cluster_count": str(cont["retained_current_localizable_cluster_count"]),
                "retained_current_localizable_cluster_share": str(cont["retained_current_localizable_cluster_share"]),
                "retained_current_localizable_directed_adjacent_pair_count": str(cont["retained_current_localizable_directed_adjacent_pair_count"]),
                "retained_current_localizable_directed_adjacent_pair_share": str(cont["retained_current_localizable_directed_adjacent_pair_share"]),
                "retained_current_localizable_undirected_adjacent_pair_count": str(cont["retained_current_localizable_undirected_adjacent_pair_count"]),
                "retained_current_localizable_undirected_adjacent_pair_share": str(cont["retained_current_localizable_undirected_adjacent_pair_share"]),
                "historical_station_cluster_EX_011_retained": str(cont["historical_station_cluster_EX_011_retained"]),
                "daily_timing_context_deduplicated_losslessly": "true",
                "cross_scenario_equivalence_assumed": "false",
                "phase_selected": "false",
                "exact_timetable_constructed": "false",
                "candidate_eliminated": "false",
                "primary_selected": "false",
                "runner_up_selected": "false",
            })
    finally:
        text.close()
        raw.close()

    if represented_seen != all_plan_ids:
        raise ValueError("Stage-D manifest does not losslessly represent all Passenger Utility plans")

    used_routes = sorted(route_use_count)
    route_fields = [
        "route_id", "runtime_archetype_id", "public_runtime_min", "cycle_runtime_min", "roles",
        "public_service_starts_at_hub", "public_service_returns_to_hub", "vehicle_closure_added",
        "rail_to_bus_passenger_event_supported", "bus_to_rail_passenger_event_supported", "anchors_json",
        "stage_d_timing_input_occurrence_count",
    ]
    args.route_output.parent.mkdir(parents=True, exist_ok=True)
    with args.route_output.open("w", encoding="utf-8", newline="") as handle:
        w = csv.DictWriter(handle, fieldnames=route_fields, lineterminator="\n")
        w.writeheader()
        for rid in used_routes:
            row = routes[rid]
            w.writerow({**{field: row[field] for field in route_fields if field != "stage_d_timing_input_occurrence_count"},
                        "stage_d_timing_input_occurrence_count": route_use_count[rid]})

    threshold_counts = {
        ">=1e4": sum(v >= 10_000 for v in complexity_values),
        ">=1e5": sum(v >= 100_000 for v in complexity_values),
        ">=1e6": sum(v >= 1_000_000 for v in complexity_values),
        ">=1e7": sum(v >= 10_000_000 for v in complexity_values),
    }
    report = {
        "status": STATUS,
        "contract": CONTRACT,
        "passenger_plan_count_represented": len(all_plan_ids),
        "stage_d_daily_timing_input_count": len(groups),
        "unique_stage_d_scenario_count": len(wanted_scenarios),
        "used_public_route_count": len(used_routes),
        "recovery_values_retained_not_selected": list(RECOVERIES),
        "route_count_distribution": {str(k): route_count_dist[k] for k in sorted(route_count_dist)},
        "headway_distribution": {str(k): headway_dist[k] for k in sorted(headway_dist)},
        "naive_joint_phase_vector_count_min": min(complexity_values),
        "naive_joint_phase_vector_count_max": max(complexity_values),
        "naive_joint_phase_vector_count_sum": sum(complexity_values),
        "naive_complexity_threshold_counts": threshold_counts,
        "daily_timing_deduplication_semantics": "SAME_SCENARIO_ID__HEADWAY__SPAN_ONLY__BUDGET_AND_CALENDAR_RETAINED_AS_PLAN_CONTEXTS",
        "daily_timing_context_deduplicated_losslessly": True,
        "cross_scenario_or_route_set_equivalence_assumed": False,
        "route_set_signature_used_to_remove_inputs": False,
        "naive_complexity_used_to_remove_inputs": False,
        "phase_selected": False,
        "exact_timetable_constructed": False,
        "joint_vehicle_block_feasibility_evaluated": False,
        "candidate_eliminated": False,
        "decision_budget_selected": False,
        "calendar_selected": False,
        "recovery_selected": False,
        "primary_selected": False,
        "runner_up_selected": False,
        "worker_reference_assigned_to_routes": False,
        "municipal_od_downscaled": False,
        "ridership_forecast": False,
        "weighted_composite_score": False,
        "epistemic_note": (
            "This manifest is a lossless computational packaging layer for Stage D. Multiple Stage-C plan rows are grouped "
            "only when they share the exact same structural scenario, headway and daily span. Budget and annual calendar "
            "memberships remain explicitly listed. The reported headway^route_count quantity is only the naive Cartesian "
            "phase-vector cardinality diagnostic; it is not an objective, threshold or pruning rule. No equivalence across "
            "different scenario IDs or public route sets is assumed."
        ),
        "lineage": {
            "passenger_frontier_sha256": sha256_path(args.passenger_frontier),
            "passenger_validation_sha256": sha256_path(args.passenger_validation),
            "s8_opportunity_sha256": sha256_path(args.s8_opportunity),
            "s8_opportunity_validation_sha256": sha256_path(args.s8_opportunity_validation),
            "continuity_scenarios_sha256": sha256_path(args.continuity_scenarios),
            "continuity_validation_sha256": sha256_path(args.continuity_validation),
            "scenario_mapping_sha256": sha256_path(args.scenario_mapping),
            "route_universe_sha256": sha256_path(args.route_universe),
            "s8_validation_sha256": sha256_path(args.s8_validation),
            "timing_output": str(args.timing_output),
            "timing_output_sha256": sha256_path(args.timing_output),
            "route_output": str(args.route_output),
            "route_output_sha256": sha256_path(args.route_output),
        },
    }
    args.validation.parent.mkdir(parents=True, exist_ok=True)
    args.validation.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in (
        "status", "passenger_plan_count_represented", "stage_d_daily_timing_input_count",
        "unique_stage_d_scenario_count", "used_public_route_count", "route_count_distribution",
        "naive_joint_phase_vector_count_max", "naive_complexity_threshold_counts",
    )}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
