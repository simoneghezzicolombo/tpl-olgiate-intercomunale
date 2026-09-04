#!/usr/bin/env python3
"""Build the fail-closed input-readiness pack for the Phase 2 final tournament.

The pack joins the repaired Stage-C context evidence to the cross-audited exact
Stage-D/Stage-E lineage.  It deliberately does not manufacture the metrics
required by ``phase2_finalize_tournament.py`` and never ranks candidates.
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
from typing import Iterable, Mapping


STATUS = "PASS_PHASE2_FINAL_TOURNAMENT_READINESS_AUDIT_RT001_V3"
CONTRACT = "PHASE2_FAIL_CLOSED_FINAL_TOURNAMENT_INPUT_READINESS_RT001_V3"
PASSENGER_STATUS = "PASS_PHASE2_PASSENGER_UTILITY_FRONTIER_RT001_V3"
CONTINUITY_STATUS = "PASS_PHASE2_CURRENT_SERVICE_CONTINUITY_RT001_V3"
STAGE_E_STATUS = "PASS_PHASE2_FINAL_OPERATIONAL_ROBUSTNESS_RT001_V3"
JOURNEY_STATUS = "PASS_PASSENGER_JOURNEY_UNIVERSE_V2_BUILD"

CONTEXT_FIELDS = [
    "plan_context_id",
    "plan_id",
    "selected_timetable_id",
    "scenario_id",
    "topology_family",
    "budget_suffix",
    "budget_cap_annual_bus_km",
    "calendar_id",
    "annual_service_days",
    "uniform_headway_min",
    "span_id",
    "span_minutes",
    "exact_annual_bus_km",
    "exact_budget_margin_annual_bus_km",
    "recovered_from_continuous_hard_filter",
    "public_route_count",
    "public_explicit_field_check_pending_count",
    "public_operational_unknown_distance_share_lower_bound",
    "public_population_coverage_share_5min",
    "public_population_coverage_share_8min",
    "public_population_coverage_share_10min",
    "public_worst_municipality_coverage_share_5min",
    "public_worst_municipality_coverage_share_8min",
    "public_worst_municipality_coverage_share_10min",
    "to_rail_reachable_share",
    "from_rail_reachable_share",
    "bidirectional_reachable_share",
    "to_rail_median_mean_generalized_access_min",
    "from_rail_median_mean_generalized_access_min",
    "retained_current_localizable_cluster_share_lower_bound",
    "retained_current_localizable_directed_adjacent_pair_share_lower_bound",
    "continuity_is_complete_current_service_measure",
    "stage_e_transfer_profile_count",
    "stage_e_bus_to_rail_observed_profile_count",
    "stage_e_bus_to_rail_worst_retention_share_engineering",
    "stage_e_rail_to_bus_worst_retention_share_engineering",
    "stage_e_bidirectional_worst_retention_share_engineering",
    "stage_e_bus_to_rail_max_service_gap_increase_min_engineering",
    "stage_e_rail_to_bus_max_service_gap_increase_min_engineering",
    "stage_e_worst_minimum_block_slack_min_engineering",
    "stage_e_maximum_minimum_vehicle_requirement_engineering",
    "stage_e_maximum_additional_vehicle_requirement_engineering",
    "stage_e_maximum_vehicle_conflict_count_on_nominal_blocks_engineering",
    "stage_e_any_block_infeasibility_under_sensitivity",
    "full_demand_weighted_gjt_available",
    "empirical_missed_connection_probability_available",
    "final_hard_eligibility_evaluated",
    "final_candidate_evaluation_ready",
    "decision_budget_selected",
    "uncertainty_band_selected",
    "primary_selected",
    "runner_up_selected",
    "weighted_composite_score",
]


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    if path.suffix.lower() in {".csv", ".json"}:
        # Git checkouts may materialise LF or CRLF.  Lineage hashes for textual
        # evidence use the repository-canonical LF representation.
        digest.update(path.read_bytes().replace(b"\r\n", b"\n"))
        return digest.hexdigest()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv(path: Path) -> list[dict[str, str]]:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def strict_bool(value: object, *, field: str) -> bool:
    text = str(value).strip().lower()
    if text == "true":
        return True
    if text == "false":
        return False
    raise ValueError(f"{field} must be true or false, got {value!r}")


def finite_float(value: object, *, field: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{field} must be finite")
    return number


def bool_text(value: bool) -> str:
    return "true" if value else "false"


def format_number(value: float) -> str:
    return f"{value:.9f}"


def format_optional_number(value: float | None) -> str:
    return "" if value is None else format_number(value)


def deterministic_gzip_csv(path: Path, fields: list[str], rows: Iterable[Mapping[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, compresslevel=9, mtime=0) as zipped:
            with io.TextIOWrapper(zipped, encoding="utf-8", newline="") as text:
                writer = csv.DictWriter(text, fieldnames=fields, lineterminator="\n", extrasaction="raise")
                writer.writeheader()
                writer.writerows(rows)


def write_csv(path: Path, fields: list[str], rows: Iterable[Mapping[str, object]]) -> None:
    materialized = list(rows)
    if not materialized:
        raise ValueError(f"refusing to write empty CSV {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n", extrasaction="raise")
        writer.writeheader()
        writer.writerows(materialized)


def unique_index(rows: list[dict[str, str]], key_fn, *, label: str) -> dict[object, dict[str, str]]:
    result: dict[object, dict[str, str]] = {}
    for row in rows:
        key = key_fn(row)
        if key in result:
            raise ValueError(f"duplicate {label} key: {key}")
        result[key] = row
    return result


def validate_contracts(args: argparse.Namespace) -> tuple[dict, dict, dict, dict]:
    passenger = read_json(args.passenger_validation)
    continuity = read_json(args.continuity_validation)
    stage_e = read_json(args.stage_e_validation)
    journey = read_json(args.journey_validation)

    if passenger.get("status") != PASSENGER_STATUS:
        raise ValueError("repaired Passenger Utility V3 is not certified PASS")
    if passenger.get("full_gjt_calculated") is not False:
        raise ValueError("Passenger Utility V3 full-GJT boundary changed")
    if passenger.get("lineage", {}).get("frontier_output_sha256") != sha256_path(args.passenger_frontier):
        raise ValueError("Passenger Utility V3 frontier hash mismatch")

    if continuity.get("status") != CONTINUITY_STATUS:
        raise ValueError("RT001 V3 current-service continuity is not certified PASS")
    if continuity.get("continuity_is_complete_current_service_measure") is not False:
        raise ValueError("current-service continuity completeness boundary changed")
    if continuity.get("lineage", {}).get("plan_output_sha256") != sha256_path(args.continuity):
        raise ValueError("current-service continuity hash mismatch")

    if stage_e.get("status") != STAGE_E_STATUS:
        raise ValueError("final Stage E RT001 V3 is not certified PASS")
    if stage_e.get("stage_d_cross_implementation_audit_pass") is not True:
        raise ValueError("Stage D cross-implementation audit is not PASS")
    if stage_e.get("stage_d_fixture_is_final_selection_lineage") is not True:
        raise ValueError("Stage E does not use the final-selection Stage D lineage")
    if stage_e.get("final_selection_authorized") is not False:
        raise ValueError("Stage E selection boundary changed")
    if stage_e.get("passenger_weighting_applied") is not False:
        raise ValueError("Stage E unexpectedly claims passenger weighting")
    if stage_e.get("delay_sensitivity_is_empirical_probability") is not False:
        raise ValueError("Stage E unexpectedly claims empirical delay probability")
    stage_e_lineage = stage_e.get("lineage", {})
    for key, path in (
        ("plan_context_map_sha256", args.stage_e_context_map),
        ("final_operational_robustness_summary_rt001_v3_sha256", args.stage_e_summary),
    ):
        if stage_e_lineage.get(key) != sha256_path(path):
            raise ValueError(f"Stage E hash mismatch: {key}")

    if journey.get("status") != JOURNEY_STATUS:
        raise ValueError("passenger journey-universe audit is not certified PASS")
    if journey.get("full_gjt_ready") is not False:
        raise ValueError("journey-universe full-GJT boundary changed")
    if journey.get("spatial_allocation_performed") is not False:
        raise ValueError("journey-universe spatial-allocation boundary changed")

    return passenger, continuity, stage_e, journey


def aggregate_stage_e_summary(rows: list[dict[str, str]]) -> dict[str, dict[str, object]]:
    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        groups[row["selected_timetable_id"]].append(row)
    aggregates: dict[str, dict[str, object]] = {}
    for timetable_id, group in groups.items():
        scenario_ids = {row["scenario_id"] for row in group}
        topology_families = {row["topology_family"] for row in group}
        profiles = {row["profile_id"] for row in group}
        if len(scenario_ids) != 1 or len(topology_families) != 1 or len(profiles) != len(group):
            raise ValueError(f"inconsistent or duplicate Stage E summary group {timetable_id}")
        for row in group:
            for flag in ("primary_selected", "runner_up_selected", "weighted_composite_score"):
                if strict_bool(row[flag], field=flag):
                    raise ValueError(f"Stage E selection boundary violated: {flag}")
        bus_retention = [
            finite_float(row["bus_to_rail_worst_retention_share"], field="bus_to_rail_worst_retention_share")
            for row in group if row["bus_to_rail_worst_retention_share"] != ""
        ]
        bus_gap = [
            finite_float(row["bus_to_rail_max_service_gap_increase_min"], field="bus_to_rail_max_service_gap_increase_min")
            for row in group if row["bus_to_rail_max_service_gap_increase_min"] != ""
        ]
        if len(bus_retention) != len(bus_gap):
            raise ValueError(f"inconsistent BUS_TO_RAIL availability in Stage E summary {timetable_id}")
        aggregates[timetable_id] = {
            "scenario_id": next(iter(scenario_ids)),
            "topology_family": next(iter(topology_families)),
            "profile_count": len(profiles),
            "bus_to_rail_observed_profile_count": len(bus_retention),
            "bus_to_rail_worst_retention_share": min(bus_retention) if bus_retention else None,
            "rail_to_bus_worst_retention_share": min(
                finite_float(row["rail_to_bus_worst_retention_share"], field="rail_to_bus_worst_retention_share")
                for row in group
            ),
            "bidirectional_worst_retention_share": min(
                finite_float(row["bidirectional_worst_retention_share"], field="bidirectional_worst_retention_share")
                for row in group
            ),
            "bus_to_rail_max_service_gap_increase_min": max(bus_gap) if bus_gap else None,
            "rail_to_bus_max_service_gap_increase_min": max(
                finite_float(row["rail_to_bus_max_service_gap_increase_min"], field="rail_to_bus_max_service_gap_increase_min")
                for row in group
            ),
            "worst_minimum_block_slack_min": min(
                finite_float(row["worst_minimum_block_slack_min"], field="worst_minimum_block_slack_min")
                for row in group
            ),
            "maximum_minimum_vehicle_requirement": max(int(row["maximum_minimum_vehicle_requirement"]) for row in group),
            "maximum_additional_vehicle_requirement": max(int(row["maximum_additional_vehicle_requirement"]) for row in group),
            "maximum_vehicle_conflict_count_on_nominal_blocks": max(
                int(row["maximum_vehicle_conflict_count_on_nominal_blocks"]) for row in group
            ),
            "any_block_infeasibility_under_sensitivity": any(
                strict_bool(row["any_block_infeasibility_under_sensitivity"], field="any_block_infeasibility_under_sensitivity")
                for row in group
            ),
        }
    return aggregates


def build_sensitivity_rows(
    *, stage_e: Mapping[str, object], journey: Mapping[str, object], behavioral_rows: list[dict[str, str]], budget_count: int
) -> list[dict[str, object]]:
    walk_values = sorted({finite_float(row["walk_weight"], field="walk_weight") for row in behavioral_rows})
    wait_values = sorted({finite_float(row["wait_weight"], field="wait_weight") for row in behavioral_rows})
    bus_delays = [float(value) for value in stage_e.get("bus_runtime_delay_minutes", [])]
    rail_delays = [float(value) for value in stage_e.get("rail_arrival_delay_minutes", [])]
    recoveries = [int(value) for value in stage_e.get("recovery_minutes", [])]
    full_gjt_ready = journey.get("full_gjt_ready") is True
    rows = [
        ("WALK_WEIGHT", "REQUIRED", json.dumps(walk_values), "PARAMETER_GRID_ONLY", False,
         "Full passenger journeys are not spatially allocated to candidate routes."),
        ("WAIT_WEIGHT", "REQUIRED", json.dumps(wait_values), "PARAMETER_GRID_ONLY", False,
         "Full passenger journeys are not spatially allocated to candidate routes."),
        ("BUS_RUNNING_TIME", "REQUIRED", json.dumps(bus_delays), "PARTIAL_ENGINEERING_STRESS_ONLY", False,
         "Only non-negative runtime stress is certified; the required decrease case is absent and no empirical distribution exists."),
        ("DWELL_VARIATION", "REQUIRED", "[]", "MISSING", False,
         "No certified Stage-E dwell sensitivity is materialised."),
        ("RECOVERY_REQUIREMENT", "REQUIRED", json.dumps(recoveries), "AVAILABLE_ENGINEERING_SENSITIVITY", False,
         "Recovery cases are evaluated but intentionally not selected."),
        ("RAIL_DELAY", "REQUIRED", json.dumps(rail_delays), "NOMINAL_ONLY", False,
         "No certified non-zero rail-delay contract exists in the current lineage."),
        ("ANNUAL_BUS_KM_ENVELOPE", "REQUIRED", str(budget_count), "AVAILABLE_NOT_SELECTED", False,
         "Six exact budget envelopes are materialised; the normative envelope remains a caller decision."),
        ("DEMAND_WEIGHT_CHANGE", "REQUIRED", "[]", "MISSING", False,
         "Municipal OD is not spatially allocated to candidate routes, so plausible route-level demand perturbation is unavailable."),
        ("FULL_DEMAND_WEIGHTED_GJT", "DECISION_CONTRACT", bool_text(full_gjt_ready), "MISSING", False,
         "The certified journey universe explicitly reports full_gjt_ready=false."),
        ("EMPIRICAL_MISSED_CONNECTION_PROBABILITY", "DECISION_CONTRACT", "false", "MISSING", False,
         "Stage E reports deterministic retention under engineering stress, not a probability distribution."),
    ]
    return [
        {
            "dimension": dimension,
            "requirement": requirement,
            "materialized_values": values,
            "readiness_status": status,
            "authorized_for_final_selection": bool_text(authorized),
            "limitation": limitation,
        }
        for dimension, requirement, values, status, authorized, limitation in rows
    ]


def build(args: argparse.Namespace) -> dict[str, object]:
    passenger_validation, continuity_validation, stage_e_validation, journey_validation = validate_contracts(args)
    passenger_rows = read_csv(args.passenger_frontier)
    continuity_rows = read_csv(args.continuity)
    context_rows = read_csv(args.stage_e_context_map)
    summary_rows = read_csv(args.stage_e_summary)
    behavioral_rows = read_csv(args.behavioral_grid)

    passenger = unique_index(passenger_rows, lambda row: (row["budget_suffix"], row["plan_id"]), label="Passenger Utility")
    continuity = unique_index(continuity_rows, lambda row: (row["budget_suffix"], row["plan_id"]), label="continuity")
    contexts = unique_index(context_rows, lambda row: row["plan_context_id"], label="Stage E context")
    stage_e = aggregate_stage_e_summary(summary_rows)

    if len(contexts) != int(stage_e_validation.get("represented_plan_context_count", -1)):
        raise ValueError("Stage E represented context count mismatch")
    if set(passenger) != {(row["budget_suffix"], row["plan_id"]) for row in contexts.values()}:
        raise ValueError("Stage E context map is not a lossless join to repaired Passenger Utility V3")
    if set(continuity) != set(passenger):
        raise ValueError("continuity rows are not a lossless join to repaired Passenger Utility V3")
    if set(stage_e) != {row["selected_timetable_id"] for row in contexts.values()}:
        raise ValueError("Stage E summary timetable membership does not match the context map")

    joined: list[dict[str, object]] = []
    budgets: dict[tuple[str, float], list[tuple[str, float]]] = defaultdict(list)
    recovered_count = 0
    for context in contexts.values():
        key = (context["budget_suffix"], context["plan_id"])
        pu = passenger[key]
        cont = continuity[key]
        robust = stage_e[context["selected_timetable_id"]]
        expected_context_id = f"{context['budget_suffix']}|{context['plan_id']}"
        if context["plan_context_id"] != expected_context_id:
            raise ValueError(f"unexpected plan_context_id {context['plan_context_id']}")
        for field in ("scenario_id", "topology_family", "calendar_id"):
            if pu[field] != context[field]:
                raise ValueError(f"Passenger Utility/Stage E mismatch for {expected_context_id}: {field}")
        if cont["scenario_id"] != context["scenario_id"] or cont["calendar_id"] != context["calendar_id"]:
            raise ValueError(f"continuity/Stage E mismatch for {expected_context_id}")
        if robust["scenario_id"] != context["scenario_id"] or robust["topology_family"] != context["topology_family"]:
            raise ValueError(f"Stage E summary/context mismatch for {expected_context_id}")
        cap = finite_float(context["budget_cap_annual_bus_km"], field="budget_cap_annual_bus_km")
        exact_km = finite_float(context["exact_annual_bus_km"], field="exact_annual_bus_km")
        if exact_km > cap + 1e-6:
            raise ValueError(f"exact budget violation for {expected_context_id}")
        recovered = strict_bool(pu["recovered_from_continuous_hard_filter"], field="recovered_from_continuous_hard_filter")
        recovered_count += int(recovered)
        budgets[(context["budget_suffix"], cap)].append((context["selected_timetable_id"], exact_km))

        joined.append({
            "plan_context_id": expected_context_id,
            "plan_id": context["plan_id"],
            "selected_timetable_id": context["selected_timetable_id"],
            "scenario_id": context["scenario_id"],
            "topology_family": context["topology_family"],
            "budget_suffix": context["budget_suffix"],
            "budget_cap_annual_bus_km": format_number(cap),
            "calendar_id": context["calendar_id"],
            "annual_service_days": context["annual_service_days"],
            "uniform_headway_min": pu["uniform_headway_min"],
            "span_id": pu["span_id"],
            "span_minutes": pu["span_minutes"],
            "exact_annual_bus_km": format_number(exact_km),
            "exact_budget_margin_annual_bus_km": format_number(cap - exact_km),
            "recovered_from_continuous_hard_filter": bool_text(recovered),
            "public_route_count": pu["public_route_count"],
            "public_explicit_field_check_pending_count": pu["public_explicit_field_check_pending_count"],
            "public_operational_unknown_distance_share_lower_bound": pu["public_operational_unknown_distance_share_lower_bound"],
            "public_population_coverage_share_5min": pu["public_population_coverage_share_5min"],
            "public_population_coverage_share_8min": pu["public_population_coverage_share_8min"],
            "public_population_coverage_share_10min": pu["public_population_coverage_share_10min"],
            "public_worst_municipality_coverage_share_5min": pu["public_worst_municipality_coverage_share_5min"],
            "public_worst_municipality_coverage_share_8min": pu["public_worst_municipality_coverage_share_8min"],
            "public_worst_municipality_coverage_share_10min": pu["public_worst_municipality_coverage_share_10min"],
            "to_rail_reachable_share": pu["to_rail_reachable_share"],
            "from_rail_reachable_share": pu["from_rail_reachable_share"],
            "bidirectional_reachable_share": pu["bidirectional_reachable_share"],
            "to_rail_median_mean_generalized_access_min": pu["to_rail_median_mean_generalized_access_min"],
            "from_rail_median_mean_generalized_access_min": pu["from_rail_median_mean_generalized_access_min"],
            "retained_current_localizable_cluster_share_lower_bound": cont["retained_current_localizable_cluster_share"],
            "retained_current_localizable_directed_adjacent_pair_share_lower_bound": cont["retained_current_localizable_directed_adjacent_pair_share"],
            "continuity_is_complete_current_service_measure": cont["continuity_is_complete_current_service_measure"],
            "stage_e_transfer_profile_count": robust["profile_count"],
            "stage_e_bus_to_rail_observed_profile_count": robust["bus_to_rail_observed_profile_count"],
            "stage_e_bus_to_rail_worst_retention_share_engineering": format_optional_number(robust["bus_to_rail_worst_retention_share"]),
            "stage_e_rail_to_bus_worst_retention_share_engineering": format_number(float(robust["rail_to_bus_worst_retention_share"])),
            "stage_e_bidirectional_worst_retention_share_engineering": format_number(float(robust["bidirectional_worst_retention_share"])),
            "stage_e_bus_to_rail_max_service_gap_increase_min_engineering": format_optional_number(robust["bus_to_rail_max_service_gap_increase_min"]),
            "stage_e_rail_to_bus_max_service_gap_increase_min_engineering": format_number(float(robust["rail_to_bus_max_service_gap_increase_min"])),
            "stage_e_worst_minimum_block_slack_min_engineering": format_number(float(robust["worst_minimum_block_slack_min"])),
            "stage_e_maximum_minimum_vehicle_requirement_engineering": robust["maximum_minimum_vehicle_requirement"],
            "stage_e_maximum_additional_vehicle_requirement_engineering": robust["maximum_additional_vehicle_requirement"],
            "stage_e_maximum_vehicle_conflict_count_on_nominal_blocks_engineering": robust["maximum_vehicle_conflict_count_on_nominal_blocks"],
            "stage_e_any_block_infeasibility_under_sensitivity": bool_text(bool(robust["any_block_infeasibility_under_sensitivity"])),
            "full_demand_weighted_gjt_available": "false",
            "empirical_missed_connection_probability_available": "false",
            "final_hard_eligibility_evaluated": "false",
            "final_candidate_evaluation_ready": "false",
            "decision_budget_selected": "false",
            "uncertainty_band_selected": "false",
            "primary_selected": "false",
            "runner_up_selected": "false",
            "weighted_composite_score": "false",
        })

    joined.sort(key=lambda row: str(row["plan_context_id"]))
    budget_rows = []
    for (suffix, cap), members in sorted(budgets.items(), key=lambda item: item[0][1]):
        budget_rows.append({
            "budget_suffix": suffix,
            "annual_bus_km_cap": format_number(cap),
            "represented_plan_context_count": len(members),
            "distinct_selected_timetable_count": len({timetable_id for timetable_id, _ in members}),
            "minimum_exact_annual_bus_km": format_number(min(km for _, km in members)),
            "maximum_exact_annual_bus_km": format_number(max(km for _, km in members)),
            "decision_budget_selected": "false",
        })

    sensitivity_rows = build_sensitivity_rows(
        stage_e=stage_e_validation,
        journey=journey_validation,
        behavioral_rows=behavioral_rows,
        budget_count=len(budget_rows),
    )
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    context_path = output_dir / "final_tournament_context_readiness_rt001_v3.csv.gz"
    budget_path = output_dir / "final_tournament_budget_envelopes_rt001_v3.csv"
    sensitivity_path = output_dir / "final_tournament_sensitivity_readiness_rt001_v3.csv"
    validation_path = output_dir / "final_tournament_readiness_rt001_v3_validation.json"
    deterministic_gzip_csv(context_path, CONTEXT_FIELDS, joined)
    write_csv(budget_path, list(budget_rows[0]), budget_rows)
    write_csv(sensitivity_path, list(sensitivity_rows[0]), sensitivity_rows)

    blockers = [
        {
            "blocker_id": "FT-001",
            "condition": "FULL_DEMAND_WEIGHTED_GJT_UNAVAILABLE",
            "evidence": "Passenger journey universe has municipal-OD resolution and full_gjt_ready=false; no spatial allocation to candidate routes is authorised.",
        },
        {
            "blocker_id": "FT-002",
            "condition": "EMPIRICAL_MISSED_CONNECTION_PROBABILITY_UNAVAILABLE",
            "evidence": "Stage E is deterministic engineering stress and explicitly is not an empirical delay-probability model.",
        },
        {
            "blocker_id": "FT-003",
            "condition": "REQUIRED_STAGE_F_SENSITIVITIES_INCOMPLETE",
            "evidence": "Dwell variation, bus-runtime decrease, non-zero rail delay and route-level demand-weight perturbation are not certified in the current lineage.",
        },
        {
            "blocker_id": "FT-004",
            "condition": "CURRENT_SERVICE_REFERENCE_IS_LOWER_BOUND_ONLY",
            "evidence": (
                f"Only {continuity_validation.get('current_localizable_row_count')} of "
                f"{int(continuity_validation.get('current_localizable_row_count', 0)) + int(continuity_validation.get('current_unresolved_or_unlocalized_row_count', 0))} "
                "current D184/D185 rows are localised; continuity is not a complete current-service non-regression proof."
            ),
        },
        {
            "blocker_id": "FT-005",
            "condition": "DECISION_BUDGET_NOT_SELECTED",
            "evidence": "The Decision Contract requires an explicit caller-selected budget matching one materialised envelope.",
        },
        {
            "blocker_id": "FT-006",
            "condition": "UNCERTAINTY_BAND_NOT_SELECTED",
            "evidence": "The Decision Contract requires an explicit finite, non-negative uncertainty band in minutes.",
        },
    ]
    validation: dict[str, object] = {
        "status": STATUS,
        "contract": CONTRACT,
        "readiness_audit_pass": True,
        "final_tournament_execution_ready": False,
        "finalizer_invoked": False,
        "candidate_evaluation_rows_materialized": False,
        "recommendation_materialized": False,
        "decision_budget_selected": False,
        "uncertainty_band_selected": False,
        "calendar_selected": False,
        "recovery_selected": False,
        "primary_selected": False,
        "runner_up_selected": False,
        "weighted_composite_score": False,
        "full_demand_weighted_gjt_available": False,
        "empirical_missed_connection_probability_available": False,
        "stage_e_engineering_retention_is_probability": False,
        "text_lineage_hash_newline_normalization": "CRLF_TO_LF",
        "current_service_continuity_is_complete": False,
        "represented_plan_context_count": len(joined),
        "distinct_selected_timetable_count": len(stage_e),
        "selected_timetable_without_bus_to_rail_summary_metric_count": sum(
            row["bus_to_rail_observed_profile_count"] == 0 for row in stage_e.values()
        ),
        "transfer_profile_count_per_timetable": sorted(Counter(row["stage_e_transfer_profile_count"] for row in joined).keys()),
        "budget_envelope_count": len(budget_rows),
        "budget_envelopes_annual_bus_km": [float(row["annual_bus_km_cap"]) for row in budget_rows],
        "rt001_recovered_context_count": recovered_count,
        "blocker_count": len(blockers),
        "blockers": blockers,
        "decision_boundary": (
            "This audit makes the certified evidence joinable and identifies missing final-tournament inputs. "
            "It does not rank contexts, calculate a composite score, select a budget/calendar/recovery, "
            "or materialise PRIMARY/RUNNER_UP."
        ),
        "lineage": {
            "passenger_frontier_sha256": sha256_path(args.passenger_frontier),
            "passenger_validation_sha256": sha256_path(args.passenger_validation),
            "continuity_sha256": sha256_path(args.continuity),
            "continuity_validation_sha256": sha256_path(args.continuity_validation),
            "stage_e_context_map_sha256": sha256_path(args.stage_e_context_map),
            "stage_e_summary_sha256": sha256_path(args.stage_e_summary),
            "stage_e_validation_sha256": sha256_path(args.stage_e_validation),
            "journey_validation_sha256": sha256_path(args.journey_validation),
            "behavioral_grid_sha256": sha256_path(args.behavioral_grid),
            "context_readiness_output_sha256": sha256_path(context_path),
            "budget_envelopes_output_sha256": sha256_path(budget_path),
            "sensitivity_readiness_output_sha256": sha256_path(sensitivity_path),
        },
    }
    validation_path.write_text(json.dumps(validation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return validation


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--passenger-frontier", type=Path, default=Path("outputs/phase2/passenger_utility_frontier_rt001_v3/passenger_utility_frontier_rt001_v3.csv.gz"))
    parser.add_argument("--passenger-validation", type=Path, default=Path("outputs/phase2/passenger_utility_frontier_rt001_v3/passenger_utility_frontier_rt001_v3_validation.json"))
    parser.add_argument("--continuity", type=Path, default=Path("outputs/phase2/current_service_continuity_rt001_v3/passenger_plans_current_service_continuity_rt001_v3.csv.gz"))
    parser.add_argument("--continuity-validation", type=Path, default=Path("outputs/phase2/current_service_continuity_rt001_v3/current_service_continuity_rt001_v3_validation.json"))
    parser.add_argument("--stage-e-context-map", type=Path, default=Path("outputs/phase2/final_operational_robustness_rt001_v3/stage_e_plan_context_map_rt001_v3.csv.gz"))
    parser.add_argument("--stage-e-summary", type=Path, default=Path("outputs/phase2/final_operational_robustness_rt001_v3/final_operational_robustness_summary_rt001_v3.csv.gz"))
    parser.add_argument("--stage-e-validation", type=Path, default=Path("outputs/phase2/final_operational_robustness_rt001_v3/final_operational_robustness_rt001_v3_validation.json"))
    parser.add_argument("--journey-validation", type=Path, default=Path("outputs/phase2/passenger_gjt_v2/passenger_journey_universe_v2_validation.json"))
    parser.add_argument("--behavioral-grid", type=Path, default=Path("outputs/phase2/passenger_gjt_v2/behavioural_sensitivity_grid_v2.csv"))
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/phase2/final_tournament_readiness_rt001_v3"))
    return parser


def main() -> None:
    result = build(build_parser().parse_args())
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
