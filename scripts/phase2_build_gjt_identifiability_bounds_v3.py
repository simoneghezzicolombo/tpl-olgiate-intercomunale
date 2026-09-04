#!/usr/bin/env python3
"""Audit whether final demand-weighted GJT is identified by certified Phase 2 evidence.

This builder deliberately does not calculate a passenger-utility point estimate.
It records what is observed, what is only a parameter grid, what could support
set-identification after additional exact-cost materialisation, and what remains
non-identifiable without new evidence or an explicit assumption.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

STATUS = "PASS_PHASE2_GJT_IDENTIFIABILITY_BOUNDS_V3"
CONTRACT = "PHASE2_GJT_IDENTIFIABILITY_AND_SET_BOUNDS_V3"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_path(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        raise ValueError("Refusing to write empty evidence matrix")
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--journey-validation", type=Path, required=True)
    p.add_argument("--demand-profile-validation", type=Path, required=True)
    p.add_argument("--feeder-validation", type=Path, required=True)
    p.add_argument("--current-baseline-v3-validation", type=Path, required=True)
    p.add_argument("--evidence-matrix", type=Path, required=True)
    p.add_argument("--validation", type=Path, required=True)
    args = p.parse_args()

    for path in (
        args.journey_validation,
        args.demand_profile_validation,
        args.feeder_validation,
        args.current_baseline_v3_validation,
    ):
        if not path.is_file():
            raise FileNotFoundError(path)

    journey = read_json(args.journey_validation)
    demand = read_json(args.demand_profile_validation)
    feeder = read_json(args.feeder_validation)
    baseline = read_json(args.current_baseline_v3_validation)

    if journey.get("contract") != "PHASE2_PASSENGER_JOURNEY_UNIVERSE_V2":
        raise ValueError("Unexpected passenger journey contract")
    if journey.get("full_gjt_ready") is not False:
        raise ValueError("Passenger journey universe unexpectedly claims full GJT readiness")
    if journey.get("source_resolution") != "MUNICIPAL_OD":
        raise ValueError("Expected municipal OD resolution")
    if journey.get("spatial_allocation_performed") is not False:
        raise ValueError("Unexpected spatial allocation in journey universe")
    if journey.get("fine_walking_access_combined_with_empirical_OD") is not False:
        raise ValueError("Unexpected fine-access/OD combination")

    if demand.get("source_scope") != "ISTAT_2021_WORK_COMMUTING_ONLY":
        raise ValueError("Unexpected demand source scope")
    if int(demand.get("s8_direct_workers", -1)) != int(journey.get("demand_weight_sum", -2)):
        raise ValueError("S8 worker mass mismatch between certified demand artifacts")

    if feeder.get("contract") != "PHASE2_PRE_PHASE_FEEDER_GENERALIZED_ACCESS_V2":
        raise ValueError("Unexpected feeder GFA contract")
    if feeder.get("full_gjt_calculated") is not False:
        raise ValueError("Feeder screening unexpectedly claims full GJT")
    if feeder.get("municipal_work_od_downscaled") is not False:
        raise ValueError("Feeder screening unexpectedly downscaled municipal OD")
    if feeder.get("resident_population_is_passenger_demand") is not False:
        raise ValueError("Resident population semantics changed")
    if feeder.get("exact_timetable_constructed") is not False:
        raise ValueError("Pre-phase feeder artifact unexpectedly claims exact timetable")
    if feeder.get("exact_train_connection_wait_used") is not False:
        raise ValueError("Pre-phase feeder artifact unexpectedly claims exact S8 waits")

    if baseline.get("contract") != "PHASE2_CURRENT_SERVICE_CERTIFIED_LOCALIZABLE_ACCESS_LOWER_BOUND_V3":
        raise ValueError("Expected certified current-service lower bound V3")
    if baseline.get("baseline_complete") is not False:
        raise ValueError("Current-service baseline unexpectedly claims completeness")
    if baseline.get("may_infer_true_current_total_coverage") is not False:
        raise ValueError("Current baseline semantics permit unsupported total inference")

    # The certified OD/demand validation has no temporal-demand object. This is not
    # inferred from an absent optional field alone: the declared source scope is the
    # ISTAT work-commuting matrix and its materialised outputs are municipal OD and
    # corridor summaries, with no departure-window distribution listed.
    demand_outputs = set(demand.get("outputs", {}))
    has_departure_distribution = any(
        token in path.lower()
        for path in demand_outputs
        for token in ("departure", "time_window", "time_distribution", "hourly")
    )
    if has_departure_distribution:
        raise ValueError("Unexpected temporal-demand output detected; audit contract must be revisited")

    rows = [
        {
            "evidence_object": "ISTAT_2021_S8_WORK_OD",
            "resolution": "MUNICIPAL_OD",
            "observed_weight_semantics": "WORKER_COUNT_BY_ORIGIN_DESTINATION_MUNICIPALITY",
            "fine_spatial_allocation": False,
            "departure_time_distribution": False,
            "exact_timetable_link": False,
            "persisted_unit_level_cost": False,
            "point_gjt_ready": False,
            "candidate_set_bounds_ready_now": False,
            "limitation": "Worker origins are not allocated inside municipalities and no departure-time distribution is observed.",
        },
        {
            "evidence_object": "FEEDER_GENERALIZED_ACCESS_V2",
            "resolution": "POPULATION_UNIT_INTERNAL_THEN_AGGREGATED",
            "observed_weight_semantics": "RESIDENT_POPULATION_AS_POTENTIAL_ACCESS_WEIGHT_NOT_DEMAND",
            "fine_spatial_allocation": True,
            "departure_time_distribution": False,
            "exact_timetable_link": False,
            "persisted_unit_level_cost": False,
            "point_gjt_ready": False,
            "candidate_set_bounds_ready_now": False,
            "limitation": "Fine unit costs are used internally but certified outputs aggregate them before exact timetable and empirical OD combination.",
        },
        {
            "evidence_object": "EXACT_STAGE_D_STAGE_E_TIMETABLE_ROBUSTNESS",
            "resolution": "SELECTED_TIMETABLE_CONNECTION_EVENT",
            "observed_weight_semantics": "UNWEIGHTED_ENGINEERING_CONNECTION_EVIDENCE",
            "fine_spatial_allocation": False,
            "departure_time_distribution": False,
            "exact_timetable_link": True,
            "persisted_unit_level_cost": False,
            "point_gjt_ready": False,
            "candidate_set_bounds_ready_now": False,
            "limitation": "Exact schedules and deterministic robustness exist, but are not joined to fine origins or empirical passenger departure weights.",
        },
        {
            "evidence_object": "CURRENT_SERVICE_ACCESS_BASELINE_V3",
            "resolution": "LOCALIZABLE_STOP_CATCHMENT_LOWER_BOUND",
            "observed_weight_semantics": "RESIDENT_POPULATION_ACCESS_LOWER_BOUND",
            "fine_spatial_allocation": True,
            "departure_time_distribution": False,
            "exact_timetable_link": False,
            "persisted_unit_level_cost": False,
            "point_gjt_ready": False,
            "candidate_set_bounds_ready_now": False,
            "limitation": "Baseline is stronger than V2 but remains incomplete and cannot identify full current-service GJT.",
        },
    ]
    write_csv(args.evidence_matrix, rows)

    candidate_bounds_constructible_after_materialisation = True
    candidate_bounds_recipe = {
        "status": "TECHNICALLY_CONSTRUCTIBLE_NOT_YET_CERTIFIED",
        "required_new_artifact": "EXACT_POPULATION_UNIT_X_SELECTED_TIMETABLE_GENERALIZED_COST_SURFACE",
        "allocation_semantics": "SET_IDENTIFICATION_ONLY_NO_POINT_WORKER_ASSIGNMENT",
        "municipal_bound_rule": "FOR_EACH_ORIGIN_MUNICIPALITY_USE_EXTREMA_OR_OTHER_FORMALLY_DECLARED_FEASIBLE_SET_OVER_UNIT_LEVEL_COSTS_WITHOUT_ASSIGNING_OBSERVED_WORKERS_TO_UNITS",
        "population_capacity_constraint_allowed": False,
        "reason_capacity_constraint_forbidden": "Using resident population as worker-location capacity would add an unsupported worker-residence allocation assumption.",
        "would_identify_point_estimate": False,
        "departure_time_problem_still_open": True,
    }

    blockers = [
        {
            "id": "GJT-ID-001",
            "object": "WITHIN_MUNICIPALITY_WORKER_ORIGIN",
            "status": "MISSING_FOR_POINT_ESTIMATE",
            "detail": "ISTAT OD worker mass is municipal. No authorised allocation to buildings/stops/routes exists.",
        },
        {
            "id": "GJT-ID-002",
            "object": "EMPIRICAL_DEPARTURE_TIME_OR_WINDOW_DISTRIBUTION",
            "status": "MISSING",
            "detail": "Certified demand outputs contain no worker departure-time distribution, so an expected timetable wait/GJT over the day is not identified.",
        },
        {
            "id": "GJT-ID-003",
            "object": "EXACT_FINE_ORIGIN_X_SELECTED_TIMETABLE_COST_SURFACE",
            "status": "NOT_MATERIALIZED",
            "detail": "Feeder GFA computes fine-origin costs internally only in pre-phase form and aggregates them before output; Stage D/E exact schedules are not joined back to those origins.",
        },
        {
            "id": "GJT-ID-004",
            "object": "COMPLETE_CURRENT_SERVICE_GJT_BASELINE",
            "status": "MISSING",
            "detail": "Current-service V3 remains a certified localizable access lower bound, so final GJT improvement versus the complete current service is not identified.",
        },
        {
            "id": "GJT-ID-005",
            "object": "EMPIRICAL_DELAY_DISTRIBUTION",
            "status": "MISSING",
            "detail": "Stage E deterministic engineering stress cannot be converted into missed-connection probability without an observed/authorised delay distribution.",
        },
    ]

    payload = {
        "status": STATUS,
        "contract": CONTRACT,
        "full_point_demand_weighted_gjt_identified": False,
        "full_point_gjt_improvement_vs_current_identified": False,
        "empirical_missed_connection_probability_identified": False,
        "route_level_demand_weight_perturbation_ready": False,
        "empirical_departure_time_weighting_ready": False,
        "current_certified_artifact_candidate_set_bounds_ready": False,
        "candidate_set_bounds_constructible_after_exact_unit_cost_materialization": candidate_bounds_constructible_after_materialisation,
        "candidate_set_bounds_would_authorize_final_selection": False,
        "candidate_bounds_recipe": candidate_bounds_recipe,
        "demand_weight_sum_s8_workers": float(journey["demand_weight_sum"]),
        "resident_population_used_as_passenger_demand": False,
        "municipal_od_downscaled": False,
        "worker_locations_imputed": False,
        "departure_distribution_imputed": False,
        "engineering_stress_converted_to_probability": False,
        "weighted_composite_score": False,
        "primary_selected": False,
        "runner_up_selected": False,
        "blockers": blockers,
        "minimum_new_evidence_or_explicit_policy_needed": [
            "Within-municipality worker-origin evidence or an explicitly authorised allocation model for a point estimate; alternatively retain set identification only.",
            "Observed or explicitly policy-declared departure-time/window distribution if expected timetable GJT is required.",
            "Exact fine-origin × selected-timetable generalized-cost surface to make candidate-only set bounds operational.",
            "Complete comparable current-service timetable/access GJT evidence for a true improvement metric.",
            "Empirical or explicitly modelled delay distribution if missed-connection probability remains a finalizer requirement.",
        ],
        "stage_f_parameter_authorization_gaps": {
            "bus_runtime_decrease": "REQUIRED_BY_SPEC_NUMERIC_RANGE_NOT_CERTIFIED",
            "dwell_variation": "REQUIRED_BY_SPEC_NUMERIC_RANGE_NOT_CERTIFIED",
            "nonzero_rail_delay": "REQUIRED_BY_SPEC_NO_CERTIFIED_CONTRACT",
            "route_level_demand_weight_change": "NOT_IDENTIFIED_WITHOUT_ROUTE_LEVEL_DEMAND_ATTRIBUTION",
        },
        "lineage": {
            "journey_validation_sha256": sha256_path(args.journey_validation),
            "demand_profile_validation_sha256": sha256_path(args.demand_profile_validation),
            "feeder_validation_sha256": sha256_path(args.feeder_validation),
            "current_baseline_v3_validation_sha256": sha256_path(args.current_baseline_v3_validation),
            "evidence_matrix_sha256": sha256_path(args.evidence_matrix),
        },
        "decision_boundary": "THIS_AUDIT_MAY_NARROW_OR_FORMALIZE_MISSING_EVIDENCE_BUT_MUST_NOT_CREATE_CANDIDATE_RANKING_PRIMARY_OR_RUNNER_UP",
    }
    args.validation.parent.mkdir(parents=True, exist_ok=True)
    args.validation.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
