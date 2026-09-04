#!/usr/bin/env python3
"""Rebuild Stage-C Passenger Utility on the RT-001 budget-lossless surface.

This adapter deliberately reuses the red-teamed Passenger Utility V2 Pareto
algorithm, including the certified 5/8/10 accessibility family. It changes only
its upstream contract and recovery-collapse input cardinality so that the input
is the exact-existential budget-lossless surface rather than the old continuous
clockface budget filter.

The compatibility ``annual_bus_km`` field inherited from the RT-001 surface is
an exact MINIMUM over the complete integer phase domain, not selected-timetable
production. It remains outside passenger dominance and may not be used as a
final resource tie-break until Stage D materialises an exact phase vector.
"""
from __future__ import annotations

import csv
import gzip
import json
import math
from pathlib import Path
import sys

import scripts.phase2_build_passenger_utility_frontier_v2_all_thresholds as thresholds

base = thresholds.base

STATUS = "PASS_PHASE2_PASSENGER_UTILITY_FRONTIER_RT001_V3"
CONTRACT = "PHASE2_NO_WEIGHT_PASSENGER_UTILITY_EXACT_EXISTENTIAL_BUDGET_V3"
RT001_STATUS = "PASS_PHASE2_BUDGET_LOSSLESS_POLICY_SURFACE_V2"
RT001_CONTRACT = "PHASE2_EXACT_EXISTENTIAL_INTEGER_PHASE_BUDGET_SURFACE_V2"

RT001_COPY_FIELDS = (
    "exact_min_departures_per_route_per_day",
    "exact_max_departures_per_route_per_day",
    "continuous_pattern_sets_per_day_audit_only",
    "exact_min_annual_bus_km",
    "exact_max_annual_bus_km",
    "continuous_annual_bus_km_audit_only",
    "annual_bus_km_semantics",
    "exact_budget_phase_feasibility_class",
    "exact_budget_phase_feasible",
    "continuous_hard_filter_would_pass",
    "recovered_from_continuous_hard_filter",
)
for field in RT001_COPY_FIELDS:
    if field not in base.COMPACT_SOURCE_FIELDS:
        base.COMPACT_SOURCE_FIELDS = (*base.COMPACT_SOURCE_FIELDS, field)

base.STATUS = STATUS
base.CONTRACT = CONTRACT

_expected_input_rows: int | None = None
_rt001_validation: dict | None = None


def validate_upstream(args):
    global _expected_input_rows, _rt001_validation
    budget = base.read_json(args.budget_policy_validation)
    feeder = base.read_json(args.feeder_validation)
    if budget.get("status") != RT001_STATUS or budget.get("contract") != RT001_CONTRACT:
        raise ValueError("RT-001 budget-lossless policy surface is not certified")
    if budget.get("lineage", {}).get("output_sha256") != base.sha256_path(args.budget_policy_frontier):
        raise ValueError("RT-001 budget-lossless surface hash mismatch")
    _expected_input_rows = int(budget.get("retained_exact_phase_feasible_context_count", -1))
    if _expected_input_rows <= 0:
        raise ValueError("Invalid RT-001 retained context count")
    if int(budget.get("budget_count", -1)) != 6 or int(budget.get("no_extension_policy_count", -1)) != 72:
        raise ValueError("Unexpected RT-001 policy/budget design space")
    for key in (
        "continuous_clockface_used_as_hard_filter", "old_feasibility_bitmask_used_as_hard_filter",
        "pareto_screening_applied_in_this_stage", "phase_dependent_annual_bus_km_used_for_dominance",
        "positive_extension_share_in_main_surface", "exact_phase_selected", "exact_timetable_constructed",
        "decision_budget_selected", "calendar_selected", "recovery_selected", "service_policy_selected",
        "weighted_composite_score", "primary_selected", "runner_up_selected",
    ):
        if budget.get(key) is not False:
            raise ValueError(f"RT-001 upstream violates lossless contract: {key}")

    if feeder.get("status") != "PASS_FEEDER_GENERALIZED_ACCESS_V2_BUILD" or feeder.get("contract") != "PHASE2_PRE_PHASE_FEEDER_GENERALIZED_ACCESS_V2":
        raise ValueError("Feeder Generalized Access V2 is not certified")
    if feeder.get("lineage", {}).get("timing_output_sha256") != base.sha256_path(args.feeder_timing):
        raise ValueError("Feeder generalized-access timing hash mismatch")
    if int(feeder.get("service_ready_row_count", -1)) != 21237 or int(feeder.get("service_ready_unique_scenario_count", -1)) != 2883:
        raise ValueError("Unexpected feeder generalized-access universe")
    if int(feeder.get("sensitivity_case_count", -1)) != 243:
        raise ValueError("Unexpected feeder generalized-access sensitivity count")
    for key in (
        "technical_return_closure_used_for_to_rail", "municipal_work_od_downscaled",
        "resident_population_is_passenger_demand", "ridership_forecast", "weighted_composite_score",
        "exact_s8_phase_used", "full_gjt_calculated", "exact_timetable_constructed",
        "primary_selected", "runner_up_selected",
    ):
        if feeder.get(key) is not False:
            raise ValueError(f"Feeder upstream violates epistemic contract: {key}")

    _rt001_validation = budget
    compat = dict(budget)
    compat["frontier_row_count"] = _expected_input_rows
    compat["declared_budget_envelope_count"] = 6
    compat["declared_no_extension_policy_context_count"] = 72
    compat["positive_extension_share_in_main_surface"] = False
    compat.setdefault("lineage", {})["frontier_output_sha256"] = budget["lineage"]["output_sha256"]
    return compat, feeder


def collapse_recovery_rows(path: Path, feeder_lookup):
    if _expected_input_rows is None:
        raise RuntimeError("validate_upstream must run before recovery collapse")
    groups = {}
    row_count = 0
    with gzip.open(path, "rt", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = set(base.COMPACT_SOURCE_FIELDS) | {"recovery_min", "policy_id", "aggregate_interlinable_fleet_lower_bound"}
        if not required <= set(reader.fieldnames or []):
            raise ValueError(f"RT-001 surface schema missing {sorted(required-set(reader.fieldnames or []))}")
        for row in reader:
            row_count += 1
            budget = str(row["budget_suffix"])
            if budget not in base.BUDGET_SUFFIXES:
                raise ValueError(f"Unknown budget suffix {budget}")
            if row.get("exact_budget_phase_feasible") != "true":
                raise ValueError("RT-001 Stage C received a non-feasible exact-existential context")
            if row.get("annual_bus_km_semantics") != "EXACT_MINIMUM_OVER_COMPLETE_INTEGER_PHASE_DOMAIN_NOT_SELECTED_TIMETABLE":
                raise ValueError("RT-001 annual_bus_km compatibility semantics changed")
            sid = str(row["scenario_id"])
            headway = int(row["uniform_headway_min"])
            span_id = str(row["span_id"])
            calendar = str(row["calendar_id"])
            key = (budget, sid, headway, span_id, calendar)
            recovery = int(row["recovery_min"])
            if recovery not in base.RECOVERIES:
                raise ValueError(f"Unexpected recovery {recovery}")
            fleet = int(float(row["aggregate_interlinable_fleet_lower_bound"]))
            if fleet <= 0:
                raise ValueError("Fleet lower bound must be positive")
            group = groups.get(key)
            if group is None:
                compact = base.compact_source_row(row)
                gfa_key = (sid, headway, span_id)
                if gfa_key not in feeder_lookup:
                    raise ValueError(f"Missing feeder generalized-access timing {gfa_key}")
                feeder = feeder_lookup[gfa_key]
                for field in base.GFA_COPY_FIELDS:
                    compact[field] = feeder[field]
                compact["plan_id"] = base.stable_plan_id(sid, headway, span_id, calendar)
                compact["recovery_sensitivity_count"] = 0
                compact["policy_ids_by_recovery"] = {}
                compact["fleet_by_recovery"] = {}
                groups[key] = compact
                group = compact
            else:
                check = base.compact_source_row(row)
                for field in base.COMPACT_SOURCE_FIELDS:
                    left, right = check[field], group[field]
                    try:
                        lf, rf = float(left), float(right)
                        both_numeric = math.isfinite(lf) and math.isfinite(rf)
                    except (TypeError, ValueError):
                        both_numeric = False
                    if both_numeric:
                        if not math.isclose(lf, rf, rel_tol=0.0, abs_tol=1e-8):
                            raise ValueError(f"Recovery variants disagree numerically on {field} for {key}")
                    elif str(left) != str(right):
                        raise ValueError(f"Recovery variants disagree on {field} for {key}")
            policy_ids = group["policy_ids_by_recovery"]
            fleets = group["fleet_by_recovery"]
            if recovery in policy_ids:
                raise ValueError(f"Duplicate recovery {recovery} for {key}")
            policy_ids[recovery] = str(row["policy_id"])
            fleets[recovery] = fleet
            group["recovery_sensitivity_count"] = int(group["recovery_sensitivity_count"]) + 1

    if row_count != _expected_input_rows:
        raise ValueError(f"Unexpected RT-001 surface rows {row_count}, expected {_expected_input_rows}")

    plans_by_budget = {suffix: [] for suffix in base.BUDGET_SUFFIXES}
    for (budget, _, _, _, _), group in groups.items():
        policy_ids = group.pop("policy_ids_by_recovery")
        fleets = group.pop("fleet_by_recovery")
        if set(policy_ids) != set(base.RECOVERIES) or set(fleets) != set(base.RECOVERIES):
            raise ValueError(f"Recovery sensitivity incomplete for {group['plan_id']}")
        if int(group["recovery_sensitivity_count"]) != 3:
            raise ValueError("Recovery sensitivity count is not three")
        for r in base.RECOVERIES:
            group[f"policy_id_recovery{r}"] = policy_ids[r]
            group[f"fleet_lower_bound_recovery{r}"] = fleets[r]
        group["recovery_selected"] = "false"
        group["exact_timetable_constructed"] = "false"
        group["primary_selected"] = "false"
        group["runner_up_selected"] = "false"
        group["annual_bus_km_selected"] = "false"
        group["rt001_budget_lossless_upstream"] = "true"
        for field in (
            "direct_hub_walk_population_excluded", "feeder_dependent_located_population",
            "to_rail_reachable_population", "to_rail_reachable_share", "to_rail_worst_municipality_reachable_share",
            "from_rail_reachable_population", "from_rail_reachable_share", "from_rail_worst_municipality_reachable_share",
            "bidirectional_reachable_population", "bidirectional_reachable_share", "bidirectional_worst_municipality_reachable_share",
        ):
            group[field] = base.finite_float(group[field], field=field)
        for field in base.PASSENGER_MIN_AXES:
            text = str(group[field]).strip()
            group[field] = None if not text else base.finite_float(text, field=field)
        plans_by_budget[budget].append(group)
    for suffix in base.BUDGET_SUFFIXES:
        plans_by_budget[suffix].sort(key=lambda r: (int(r["uniform_headway_min"]), str(r["span_id"]), str(r["calendar_id"]), str(r["plan_id"])))
    return plans_by_budget, len(groups)


base.validate_upstream = validate_upstream
base.collapse_recovery_rows = collapse_recovery_rows


def _arg_value(flag: str) -> Path:
    try:
        return Path(sys.argv[sys.argv.index(flag) + 1])
    except (ValueError, IndexError) as exc:
        raise ValueError(f"Missing {flag}") from exc


def main() -> int:
    rc = base.main()
    validation_path = _arg_value("--validation-output")
    payload = json.loads(validation_path.read_text(encoding="utf-8"))
    if _rt001_validation is None:
        raise RuntimeError("RT-001 validation was not retained")
    payload.update({
        "rt001_repair": True,
        "rt001_upstream_status": RT001_STATUS,
        "rt001_upstream_contract": RT001_CONTRACT,
        "rt001_input_context_count": int(_rt001_validation["retained_exact_phase_feasible_context_count"]),
        "rt001_recovered_from_continuous_hard_filter_total": int(_rt001_validation["recovered_from_continuous_hard_filter_total"]),
        "rt001_recovered_unique_scenario_count": int(_rt001_validation["recovered_unique_scenario_count"]),
        "annual_bus_km_is_selected_timetable_production": False,
        "annual_bus_km_is_exact_phase_domain_minimum": True,
        "annual_bus_km_used_for_passenger_dominance": False,
        "exact_budget_eligibility_repaired_before_stage_c": True,
    })
    payload["limitations"] = [
        "This remains a Stage-C passenger-utility screening frontier, not final demand-weighted GJT.",
        "The annual_bus_km compatibility field is the exact minimum over the integer phase domain and is not final timetable production.",
        "Exact phase-specific budget production must be re-applied in rebuilt Stage D.",
        "Current-service non-regression remains relative only to the certified localizable lower bound.",
    ]
    validation_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
