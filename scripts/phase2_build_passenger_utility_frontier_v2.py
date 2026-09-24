#!/usr/bin/env python3
"""Build the no-weight Stage-C passenger-utility frontier for Phase 2.

Inputs are already hard-feasible Budget×Policy Frontiers V2 plus the certified
pre-phase Feeder Generalized Access V2 surface. Recovery 5/10/15 variants are
collapsed into one passenger plan while retaining all three fleet lower bounds;
no recovery value is selected.

The skyline is exact in two stages. First, passenger dominance is evaluated
inside identical budget×headway×span×calendar contexts. A plan dominated there
can never become nondominated globally because every availability attribute is
identical to its dominator. Second, the union is compared within each budget
with service span and annual service days added as passenger-availability axes.

Technical resource and implementation dimensions such as bus-km, route count,
field checks and unknown-distance exposure are retained for downstream tie-break
and exact-timetable audit, but deliberately do not prevent Stage-C passenger
utility dominance once the explicit budget hard cap has been satisfied.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import math
from collections import defaultdict
from pathlib import Path

STATUS = "PASS_PHASE2_PASSENGER_UTILITY_FRONTIER_V2"
CONTRACT = "PHASE2_NO_WEIGHT_PASSENGER_UTILITY_FRONTIER_V2"
BUDGET_SUFFIXES = ("m20pct", "m10pct", "reference", "p10pct", "p20pct", "p30pct")
RECOVERIES = (5, 10, 15)
EPS = 1e-9

PASSENGER_MAX_AXES = (
    "public_population_coverage_share_5min",
    "public_population_coverage_share_10min",
    "public_worst_municipality_coverage_share_5min",
    "public_worst_municipality_coverage_share_10min",
    "territorial_other_core_worker_mass_upper_bound",
    "territorial_other_external_worker_mass_upper_bound",
    "to_rail_reachable_share",
    "to_rail_worst_municipality_reachable_share",
    "from_rail_reachable_share",
    "from_rail_worst_municipality_reachable_share",
    "bidirectional_reachable_share",
    "bidirectional_worst_municipality_reachable_share",
    "s8_complete_supported_route_share",
)
AVAILABILITY_MAX_AXES = ("annual_service_days", "span_minutes")
PASSENGER_MIN_AXES = (
    "to_rail_median_mean_generalized_access_min",
    "to_rail_p90_mean_generalized_access_min",
    "to_rail_worst_municipality_p90_mean_generalized_access_min",
    "from_rail_median_mean_generalized_access_min",
    "from_rail_p90_mean_generalized_access_min",
    "from_rail_worst_municipality_p90_mean_generalized_access_min",
)
OPTIONAL_COST_DIRECTION = {
    "to_rail_median_mean_generalized_access_min": "to_rail_reachable_share",
    "to_rail_p90_mean_generalized_access_min": "to_rail_reachable_share",
    "to_rail_worst_municipality_p90_mean_generalized_access_min": "to_rail_reachable_share",
    "from_rail_median_mean_generalized_access_min": "from_rail_reachable_share",
    "from_rail_p90_mean_generalized_access_min": "from_rail_reachable_share",
    "from_rail_worst_municipality_p90_mean_generalized_access_min": "from_rail_reachable_share",
}

COMPACT_SOURCE_FIELDS = (
    "scenario_id", "topology_family", "uniform_headway_min", "span_id", "span_start_min", "span_end_min",
    "calendar_id", "annual_service_days", "extension_share", "annual_bus_km",
    "budget_suffix", "budget_change_fraction", "budget_cap_annual_bus_km",
    "public_population_coverage_share_5min", "public_population_coverage_share_10min",
    "public_worst_municipality_coverage_share_5min", "public_worst_municipality_coverage_share_10min",
    "territorial_other_core_worker_mass_upper_bound", "territorial_other_external_worker_mass_upper_bound",
    "s8_complete_supported_route_count", "s8_incomplete_supported_route_count",
    "public_route_count", "public_explicit_field_check_pending_count",
    "public_operational_unknown_distance_share_lower_bound", "public_explicit_existing_stop_count",
    "public_explicit_proposed_stop_count", "public_distance_km", "public_runtime_min",
    "public_equal_pattern_set_cycle_distance_km_lower_bound",
    "public_equal_pattern_set_cycle_runtime_min_lower_bound",
    "expected_pattern_set_cycle_distance_km", "expected_pattern_set_cycle_runtime_min",
)

GFA_COPY_FIELDS = (
    "direct_hub_walk_population_excluded", "feeder_dependent_located_population",
    "to_rail_reachable_population", "to_rail_reachable_share", "to_rail_worst_municipality",
    "to_rail_worst_municipality_reachable_share", "from_rail_reachable_population",
    "from_rail_reachable_share", "from_rail_worst_municipality",
    "from_rail_worst_municipality_reachable_share", "bidirectional_reachable_population",
    "bidirectional_reachable_share", "bidirectional_worst_municipality",
    "bidirectional_worst_municipality_reachable_share",
    *PASSENGER_MIN_AXES,
)


def sha256_path(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def finite_float(value: object, *, field: str) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"Non-finite {field}: {value!r}")
    return result


def stable_plan_id(scenario_id: str, headway: int, span_id: str, calendar_id: str) -> str:
    payload = json.dumps(
        {
            "scenario_id": scenario_id,
            "uniform_headway_min": headway,
            "span_id": span_id,
            "calendar_id": calendar_id,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return "PU2_" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def deterministic_gzip_writer(path: Path, fields: list[str]):
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = path.open("wb")
    gz = gzip.GzipFile(filename="", mode="wb", fileobj=raw, compresslevel=9, mtime=0)
    text = io.TextIOWrapper(gz, encoding="utf-8", newline="")
    writer = csv.DictWriter(text, fieldnames=fields, lineterminator="\n", extrasaction="ignore")
    writer.writeheader()
    return raw, text, writer


def validate_upstream(args) -> tuple[dict, dict]:
    budget = read_json(args.budget_policy_validation)
    feeder = read_json(args.feeder_validation)
    if budget.get("status") != "PASS_PHASE2_BUDGET_POLICY_FRONTIERS_V2" or budget.get("contract") != "PHASE2_EXPLICIT_POLICY_CONTEXT_BUDGET_PARETO_V2":
        raise ValueError("Budget×Policy Frontiers V2 is not certified")
    if budget.get("lineage", {}).get("frontier_output_sha256") != sha256_path(args.budget_policy_frontier):
        raise ValueError("Budget×Policy frontier hash mismatch")
    if int(budget.get("frontier_row_count", -1)) != 490962:
        raise ValueError("Unexpected Budget×Policy frontier row count")
    if int(budget.get("declared_budget_envelope_count", -1)) != 6 or int(budget.get("declared_no_extension_policy_context_count", -1)) != 72:
        raise ValueError("Unexpected Budget×Policy design-space cardinality")
    for key in ("decision_budget_selected", "calendar_selected", "recovery_selected", "service_policy_selected", "s8_phase_selected", "full_gjt_calculated", "weighted_composite_score"):
        if budget.get(key) is not False:
            raise ValueError(f"Budget×Policy upstream violates selection contract: {key}")
    if budget.get("positive_extension_share_in_main_surface") is not False:
        raise ValueError("Passenger utility V2 main surface requires no-extension Budget×Policy upstream")

    if feeder.get("status") != "PASS_FEEDER_GENERALIZED_ACCESS_V2_BUILD" or feeder.get("contract") != "PHASE2_PRE_PHASE_FEEDER_GENERALIZED_ACCESS_V2":
        raise ValueError("Feeder Generalized Access V2 is not certified")
    if feeder.get("lineage", {}).get("timing_output_sha256") != sha256_path(args.feeder_timing):
        raise ValueError("Feeder generalized-access timing hash mismatch")
    if int(feeder.get("service_ready_row_count", -1)) != 21237 or int(feeder.get("service_ready_unique_scenario_count", -1)) != 2883:
        raise ValueError("Unexpected feeder generalized-access universe")
    if int(feeder.get("sensitivity_case_count", -1)) != 243:
        raise ValueError("Unexpected feeder generalized-access sensitivity count")
    for key in ("technical_return_closure_used_for_to_rail", "municipal_work_od_downscaled", "resident_population_is_passenger_demand", "ridership_forecast", "weighted_composite_score", "exact_s8_phase_used", "full_gjt_calculated", "exact_timetable_constructed", "primary_selected", "runner_up_selected"):
        if feeder.get(key) is not False:
            raise ValueError(f"Feeder upstream violates epistemic contract: {key}")
    return budget, feeder


def load_feeder_timing(path: Path) -> dict[tuple[str, int, str], dict[str, str]]:
    out: dict[tuple[str, int, str], dict[str, str]] = {}
    with gzip.open(path, "rt", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"scenario_id", "uniform_headway_min", "span_id", *GFA_COPY_FIELDS}
        if not required <= set(reader.fieldnames or []):
            raise ValueError(f"Feeder timing schema missing {sorted(required-set(reader.fieldnames or []))}")
        for row in reader:
            key = (str(row["scenario_id"]), int(row["uniform_headway_min"]), str(row["span_id"]))
            if key in out:
                raise ValueError(f"Duplicate feeder timing row {key}")
            out[key] = row
    if len(out) != 21237:
        raise ValueError(f"Unexpected feeder timing row count {len(out)}")
    return out


def compact_source_row(row: dict[str, str]) -> dict[str, object]:
    missing = [field for field in COMPACT_SOURCE_FIELDS if field not in row]
    if missing:
        raise ValueError(f"Budget×Policy row missing compact fields {missing}")
    out: dict[str, object] = {field: row[field] for field in COMPACT_SOURCE_FIELDS}
    out["uniform_headway_min"] = int(row["uniform_headway_min"])
    out["span_start_min"] = int(row["span_start_min"])
    out["span_end_min"] = int(row["span_end_min"])
    out["span_minutes"] = int(row["span_end_min"]) - int(row["span_start_min"])
    out["annual_service_days"] = int(row["annual_service_days"])
    out["public_route_count"] = int(row["public_route_count"])
    out["s8_complete_supported_route_count"] = int(float(row["s8_complete_supported_route_count"]))
    out["s8_incomplete_supported_route_count"] = int(float(row["s8_incomplete_supported_route_count"]))
    denominator = out["s8_complete_supported_route_count"] + out["s8_incomplete_supported_route_count"]
    if denominator <= 0:
        raise ValueError("S8 supported-route denominator is zero")
    out["s8_complete_supported_route_share"] = out["s8_complete_supported_route_count"] / denominator
    out["s8_all_supported_routes_complete"] = 1 if out["s8_incomplete_supported_route_count"] == 0 else 0
    if abs(finite_float(row["extension_share"], field="extension_share")) > 1e-12:
        raise ValueError("Passenger utility main surface received positive extension share")
    for field in (
        "annual_bus_km", "budget_change_fraction", "budget_cap_annual_bus_km",
        "public_population_coverage_share_5min", "public_population_coverage_share_10min",
        "public_worst_municipality_coverage_share_5min", "public_worst_municipality_coverage_share_10min",
        "territorial_other_core_worker_mass_upper_bound", "territorial_other_external_worker_mass_upper_bound",
        "public_operational_unknown_distance_share_lower_bound", "public_distance_km", "public_runtime_min",
        "public_equal_pattern_set_cycle_distance_km_lower_bound", "public_equal_pattern_set_cycle_runtime_min_lower_bound",
        "expected_pattern_set_cycle_distance_km", "expected_pattern_set_cycle_runtime_min",
    ):
        out[field] = finite_float(row[field], field=field)
    for field in ("public_explicit_field_check_pending_count", "public_explicit_existing_stop_count", "public_explicit_proposed_stop_count"):
        out[field] = int(float(row[field]))
    return out


def collapse_recovery_rows(path: Path, feeder_lookup: dict[tuple[str, int, str], dict[str, str]]):
    groups: dict[tuple[str, str, int, str, str], dict[str, object]] = {}
    row_count = 0
    with gzip.open(path, "rt", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = set(COMPACT_SOURCE_FIELDS) | {"recovery_min", "policy_id", "aggregate_interlinable_fleet_lower_bound"}
        if not required <= set(reader.fieldnames or []):
            raise ValueError(f"Budget×Policy schema missing {sorted(required-set(reader.fieldnames or []))}")
        for row in reader:
            row_count += 1
            budget = str(row["budget_suffix"])
            if budget not in BUDGET_SUFFIXES:
                raise ValueError(f"Unknown budget suffix {budget}")
            sid = str(row["scenario_id"])
            headway = int(row["uniform_headway_min"])
            span_id = str(row["span_id"])
            calendar = str(row["calendar_id"])
            key = (budget, sid, headway, span_id, calendar)
            recovery = int(row["recovery_min"])
            if recovery not in RECOVERIES:
                raise ValueError(f"Unexpected recovery {recovery}")
            fleet = int(float(row["aggregate_interlinable_fleet_lower_bound"]))
            if fleet <= 0:
                raise ValueError("Fleet lower bound must be positive")
            group = groups.get(key)
            if group is None:
                base = compact_source_row(row)
                gfa_key = (sid, headway, span_id)
                if gfa_key not in feeder_lookup:
                    raise ValueError(f"Missing feeder generalized-access timing {gfa_key}")
                feeder = feeder_lookup[gfa_key]
                for field in GFA_COPY_FIELDS:
                    base[field] = feeder[field]
                base["plan_id"] = stable_plan_id(sid, headway, span_id, calendar)
                base["recovery_sensitivity_count"] = 0
                base["policy_ids_by_recovery"] = {}
                base["fleet_by_recovery"] = {}
                groups[key] = base
                group = base
            else:
                # All passenger-facing and availability attributes must be identical across recovery variants.
                check = compact_source_row(row)
                for field in COMPACT_SOURCE_FIELDS:
                    if str(check[field]) != str(group[field]) and field not in {
                        "annual_bus_km", "budget_change_fraction", "budget_cap_annual_bus_km",
                        "public_population_coverage_share_5min", "public_population_coverage_share_10min",
                        "public_worst_municipality_coverage_share_5min", "public_worst_municipality_coverage_share_10min",
                        "territorial_other_core_worker_mass_upper_bound", "territorial_other_external_worker_mass_upper_bound",
                        "public_operational_unknown_distance_share_lower_bound", "public_distance_km", "public_runtime_min",
                        "public_equal_pattern_set_cycle_distance_km_lower_bound", "public_equal_pattern_set_cycle_runtime_min_lower_bound",
                        "expected_pattern_set_cycle_distance_km", "expected_pattern_set_cycle_runtime_min",
                    }:
                        raise ValueError(f"Recovery variants disagree on {field} for {key}")
                for field in (
                    "annual_bus_km", "budget_change_fraction", "budget_cap_annual_bus_km",
                    "public_population_coverage_share_5min", "public_population_coverage_share_10min",
                    "public_worst_municipality_coverage_share_5min", "public_worst_municipality_coverage_share_10min",
                    "territorial_other_core_worker_mass_upper_bound", "territorial_other_external_worker_mass_upper_bound",
                    "public_operational_unknown_distance_share_lower_bound", "public_distance_km", "public_runtime_min",
                    "public_equal_pattern_set_cycle_distance_km_lower_bound", "public_equal_pattern_set_cycle_runtime_min_lower_bound",
                    "expected_pattern_set_cycle_distance_km", "expected_pattern_set_cycle_runtime_min",
                ):
                    if not math.isclose(float(check[field]), float(group[field]), rel_tol=0.0, abs_tol=1e-8):
                        raise ValueError(f"Recovery variants disagree numerically on {field} for {key}")
            policy_ids = group["policy_ids_by_recovery"]
            fleets = group["fleet_by_recovery"]
            assert isinstance(policy_ids, dict) and isinstance(fleets, dict)
            if recovery in policy_ids:
                raise ValueError(f"Duplicate recovery {recovery} for {key}")
            policy_ids[recovery] = str(row["policy_id"])
            fleets[recovery] = fleet
            group["recovery_sensitivity_count"] = int(group["recovery_sensitivity_count"]) + 1
    if row_count != 490962:
        raise ValueError(f"Unexpected Budget×Policy frontier rows {row_count}")
    plans_by_budget: dict[str, list[dict[str, object]]] = {suffix: [] for suffix in BUDGET_SUFFIXES}
    for (budget, _, _, _, _), group in groups.items():
        policy_ids = group.pop("policy_ids_by_recovery")
        fleets = group.pop("fleet_by_recovery")
        if set(policy_ids) != set(RECOVERIES) or set(fleets) != set(RECOVERIES):
            raise ValueError(f"Recovery sensitivity incomplete for {group['plan_id']}")
        if int(group["recovery_sensitivity_count"]) != 3:
            raise ValueError("Recovery sensitivity count is not three")
        group["policy_id_recovery5"] = policy_ids[5]
        group["policy_id_recovery10"] = policy_ids[10]
        group["policy_id_recovery15"] = policy_ids[15]
        group["fleet_lower_bound_recovery5"] = fleets[5]
        group["fleet_lower_bound_recovery10"] = fleets[10]
        group["fleet_lower_bound_recovery15"] = fleets[15]
        group["recovery_selected"] = "false"
        group["exact_timetable_constructed"] = "false"
        group["primary_selected"] = "false"
        group["runner_up_selected"] = "false"
        # Parse joined passenger numeric fields now and keep labels as strings.
        for field in (
            "direct_hub_walk_population_excluded", "feeder_dependent_located_population",
            "to_rail_reachable_population", "to_rail_reachable_share", "to_rail_worst_municipality_reachable_share",
            "from_rail_reachable_population", "from_rail_reachable_share", "from_rail_worst_municipality_reachable_share",
            "bidirectional_reachable_population", "bidirectional_reachable_share", "bidirectional_worst_municipality_reachable_share",
        ):
            group[field] = finite_float(group[field], field=field)
        for field in PASSENGER_MIN_AXES:
            text = str(group[field]).strip()
            group[field] = None if not text else finite_float(text, field=field)
        plans_by_budget[budget].append(group)
    for suffix in BUDGET_SUFFIXES:
        plans_by_budget[suffix].sort(key=lambda r: (int(r["uniform_headway_min"]), str(r["span_id"]), str(r["calendar_id"]), str(r["plan_id"])))
    return plans_by_budget, len(groups)


def optional_min_compare(a: dict[str, object], b: dict[str, object], field: str):
    av = a[field]
    bv = b[field]
    if av is None and bv is None:
        return 0
    if av is None:
        return 1  # a is worse: no reachable passengers in this direction
    if bv is None:
        return -1 # a is better than missing cost
    af, bf = float(av), float(bv)
    if af < bf - EPS:
        return -1
    if af > bf + EPS:
        return 1
    return 0


def dominates(a: dict[str, object], b: dict[str, object], *, include_availability: bool) -> bool:
    strict = False
    max_axes = PASSENGER_MAX_AXES + (AVAILABILITY_MAX_AXES if include_availability else ())
    for field in max_axes:
        av, bv = float(a[field]), float(b[field])
        if av < bv - EPS:
            return False
        if av > bv + EPS:
            strict = True
    for field in PASSENGER_MIN_AXES:
        comparison = optional_min_compare(a, b, field)
        if comparison > 0:
            return False
        if comparison < 0:
            strict = True
    return strict


def sort_key(row: dict[str, object], *, include_availability: bool):
    max_axes = PASSENGER_MAX_AXES + (AVAILABILITY_MAX_AXES if include_availability else ())
    max_part = tuple(-float(row[field]) for field in max_axes)
    min_part = tuple(math.inf if row[field] is None else float(row[field]) for field in PASSENGER_MIN_AXES)
    return (*max_part, *min_part, str(row["plan_id"]))


def profile_key(row: dict[str, object], *, include_availability: bool):
    max_axes = PASSENGER_MAX_AXES + (AVAILABILITY_MAX_AXES if include_availability else ())
    values: list[object] = [round(float(row[field]), 9) for field in max_axes]
    for field in PASSENGER_MIN_AXES:
        values.append(None if row[field] is None else round(float(row[field]), 9))
    return tuple(values)


def pareto(rows: list[dict[str, object]], *, include_availability: bool) -> list[dict[str, object]]:
    if not rows:
        return []
    equivalent: dict[tuple, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        equivalent[profile_key(row, include_availability=include_availability)].append(row)
    representatives = [sorted(same, key=lambda r: str(r["plan_id"]))[0] for same in equivalent.values()]
    frontier: list[dict[str, object]] = []
    for row in sorted(representatives, key=lambda r: sort_key(r, include_availability=include_availability)):
        if any(dominates(existing, row, include_availability=include_availability) for existing in frontier):
            continue
        frontier = [existing for existing in frontier if not dominates(row, existing, include_availability=include_availability)]
        frontier.append(row)
    frontier_profiles = {profile_key(row, include_availability=include_availability) for row in frontier}
    expanded = [row for key, same in equivalent.items() if key in frontier_profiles for row in same]
    expanded.sort(key=lambda r: str(r["plan_id"]))
    return expanded


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--budget-policy-frontier", type=Path, required=True)
    p.add_argument("--budget-policy-validation", type=Path, required=True)
    p.add_argument("--feeder-timing", type=Path, required=True)
    p.add_argument("--feeder-validation", type=Path, required=True)
    p.add_argument("--frontier-output", type=Path, required=True)
    p.add_argument("--context-audit-output", type=Path, required=True)
    p.add_argument("--validation-output", type=Path, required=True)
    args = p.parse_args()
    for path in (args.budget_policy_frontier, args.budget_policy_validation, args.feeder_timing, args.feeder_validation):
        if not path.is_file():
            raise FileNotFoundError(path)

    budget_val, feeder_val = validate_upstream(args)
    feeder_lookup = load_feeder_timing(args.feeder_timing)
    plans_by_budget, collapsed_plan_count_all_budgets = collapse_recovery_rows(args.budget_policy_frontier, feeder_lookup)

    final_rows: list[dict[str, object]] = []
    audit_rows: list[dict[str, object]] = []
    budget_summary: dict[str, dict[str, object]] = {}
    for suffix in BUDGET_SUFFIXES:
        plans = plans_by_budget[suffix]
        contexts: dict[tuple[int, str, str], list[dict[str, object]]] = defaultdict(list)
        for row in plans:
            contexts[(int(row["uniform_headway_min"]), str(row["span_id"]), str(row["calendar_id"]))].append(row)
        stage1_union: dict[str, dict[str, object]] = {}
        for context in sorted(contexts):
            rows_here = contexts[context]
            frontier_here = pareto(rows_here, include_availability=False)
            for row in frontier_here:
                stage1_union[str(row["plan_id"])] = row
            audit_rows.append({
                "budget_suffix": suffix,
                "uniform_headway_min": context[0],
                "span_id": context[1],
                "calendar_id": context[2],
                "annual_service_days": int(rows_here[0]["annual_service_days"]),
                "input_plan_count": len(rows_here),
                "passenger_context_frontier_plan_count": len(frontier_here),
            })
        stage1 = list(stage1_union.values())
        final = pareto(stage1, include_availability=True)
        final_ids = {str(row["plan_id"]) for row in final}
        for row in final:
            out = dict(row)
            out["passenger_utility_frontier"] = "true"
            out["passenger_utility_axes_weighted"] = "false"
            out["exact_s8_phase_used"] = "false"
            out["full_gjt_calculated"] = "false"
            out["service_policy_selected"] = "false"
            final_rows.append(out)
        scenario_ids = {str(row["scenario_id"]) for row in final}
        scenario_ids_frequent = {str(row["scenario_id"]) for row in final if int(row["uniform_headway_min"]) <= 30}
        budget_summary[suffix] = {
            "collapsed_recovery_plan_count": len(plans),
            "passenger_context_count": len(contexts),
            "stage1_context_frontier_union_plan_count": len(stage1),
            "passenger_utility_frontier_plan_count": len(final),
            "passenger_utility_frontier_unique_scenario_count": len(scenario_ids),
            "passenger_utility_frontier_unique_scenario_count_headway_30_or_better": len(scenario_ids_frequent),
            "passenger_utility_frontier_plan_ids_sha256": hashlib.sha256("|".join(sorted(final_ids)).encode("utf-8")).hexdigest(),
        }

    final_rows.sort(key=lambda r: (BUDGET_SUFFIXES.index(str(r["budget_suffix"])), int(r["uniform_headway_min"]), str(r["span_id"]), str(r["calendar_id"]), str(r["plan_id"])))
    if not final_rows:
        raise ValueError("Passenger utility frontier is empty")
    fields = list(final_rows[0].keys())
    raw, text, writer = deterministic_gzip_writer(args.frontier_output, fields)
    try:
        for row in final_rows:
            serial = {key: ("" if value is None else value) for key, value in row.items()}
            writer.writerow(serial)
    finally:
        text.close()
        raw.close()

    args.context_audit_output.parent.mkdir(parents=True, exist_ok=True)
    with args.context_audit_output.open("w", encoding="utf-8", newline="") as handle:
        writer2 = csv.DictWriter(handle, fieldnames=list(audit_rows[0].keys()), lineterminator="\n")
        writer2.writeheader()
        writer2.writerows(audit_rows)

    validation = {
        "status": STATUS,
        "contract": CONTRACT,
        "budget_count": 6,
        "recovery_values_collapsed_not_selected": list(RECOVERIES),
        "budget_policy_frontier_row_count_upstream": int(budget_val["frontier_row_count"]),
        "collapsed_recovery_plan_count_all_budgets": collapsed_plan_count_all_budgets,
        "passenger_utility_frontier_row_count_all_budgets": len(final_rows),
        "budget_summary": budget_summary,
        "passenger_maximise_axes_within_service_context": list(PASSENGER_MAX_AXES),
        "passenger_minimise_axes_within_service_context": list(PASSENGER_MIN_AXES),
        "global_additional_availability_maximise_axes": list(AVAILABILITY_MAX_AXES),
        "two_stage_skyline_equivalence": "EXACT_BECAUSE_STAGE1_DOMINANCE_OCCURS_WITHIN_IDENTICAL_HEADWAY_SPAN_CALENDAR_AND_BUDGET_CONTEXT",
        "budget_is_hard_constraint_not_utility_axis": True,
        "annual_bus_km_retained_for_tie_break_not_passenger_dominance": True,
        "route_count_retained_for_tie_break_not_passenger_dominance": True,
        "field_checks_retained_for_tie_break_not_passenger_dominance": True,
        "unknown_distance_exposure_retained_for_tie_break_not_passenger_dominance": True,
        "recovery_selected": False,
        "calendar_selected": False,
        "service_policy_selected": False,
        "decision_budget_selected": False,
        "exact_s8_phase_used": False,
        "exact_timetable_constructed": False,
        "full_gjt_calculated": False,
        "weighted_composite_score": False,
        "municipal_work_od_downscaled": False,
        "resident_population_is_passenger_demand": False,
        "ridership_forecast": False,
        "primary_selected": False,
        "runner_up_selected": False,
        "lineage": {
            "budget_policy_frontier": str(args.budget_policy_frontier),
            "budget_policy_frontier_sha256": sha256_path(args.budget_policy_frontier),
            "budget_policy_validation": str(args.budget_policy_validation),
            "budget_policy_validation_sha256": sha256_path(args.budget_policy_validation),
            "feeder_timing": str(args.feeder_timing),
            "feeder_timing_sha256": sha256_path(args.feeder_timing),
            "feeder_validation": str(args.feeder_validation),
            "feeder_validation_sha256": sha256_path(args.feeder_validation),
            "frontier_output": str(args.frontier_output),
            "frontier_output_sha256": sha256_path(args.frontier_output),
            "context_audit_output": str(args.context_audit_output),
            "context_audit_output_sha256": sha256_path(args.context_audit_output),
        },
        "upstream_statuses": {
            "budget_policy": budget_val["status"],
            "feeder_generalized_access": feeder_val["status"],
        },
        "limitations": [
            "This is Stage-C passenger-utility screening, not final Passenger GJT.",
            "Exact S8 phase, train connection waiting, missed connections, delay robustness and exact vehicle blocks remain downstream.",
            "Municipal work OD enters only through structural territorial addressability axes and is not downscaled to passengers or routes.",
            "Building resident population remains potential feeder accessibility weight, not ridership.",
            "Positive scheduled-extension shares remain outside this main no-extension surface and require separate sensitivity comparison.",
            "Final PRIMARY/RUNNER-UP remains blocked by the declared decision-budget and uncertainty-band contract."
        ],
    }
    args.validation_output.parent.mkdir(parents=True, exist_ok=True)
    args.validation_output.write_text(json.dumps(validation, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(validation, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
