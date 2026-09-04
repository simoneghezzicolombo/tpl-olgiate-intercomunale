#!/usr/bin/env python3
"""Rebuild the Phase 2 tournament lineage after the certified hub-access correction.

This orchestration is intentionally boring: it calls the already-audited builders
in dependency order, with the lineage-driven exact-timetable adapter at the end.
It performs no ranking or selection itself.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable


def run(*args: str) -> None:
    subprocess.run([PY, *args], cwd=ROOT, check=True)


def j(path: str) -> dict:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()

    if not args.validate_only:
        run(
            "scripts/phase2_build_hub_access_bridge_v2.py",
            "--routing-membership", "outputs/phase2/reduced_path_matrix_v2/routing_anchor_membership.csv",
            "--existing-stops", "outputs/phase2/stop_universe_v2/existing_official_stops.csv",
            "--existing-catchments", "outputs/phase2/stop_universe_v2/existing_stop_catchment_units_12min.csv",
            "--matrix-validation", "outputs/phase2/reduced_path_matrix_v2/reduced_path_matrix_v2_validation.json",
            "--stop-validation", "outputs/phase2/stop_universe_v2/stop_universe_v2_validation.json",
            "--output", "outputs/phase2/access_equity_v2/hub_access_bridge_v2.json",
        )
        run(
            "scripts/phase2_run_access_equity_hub_corrected_v2.py",
            "--catalog", "outputs/phase2/structural_catalog_v2/structural_scenario_catalog_balanced_v2.csv",
            "--catalog-validation", "outputs/phase2/structural_catalog_v2/structural_scenario_catalog_balanced_v2_validation.json",
            "--stop-validation", "outputs/phase2/stop_universe_v2/stop_universe_v2_validation.json",
            "--matrix-validation", "outputs/phase2/reduced_path_matrix_v2/reduced_path_matrix_v2_validation.json",
            "--anchors", "outputs/phase2/reduced_path_matrix_v2/routing_anchor_universe.csv",
            "--proposed-catchments", "outputs/phase2/stop_universe_v2/proposed_stop_candidate_catchment_units_10min.csv",
            "--existing-catchments", "outputs/phase2/stop_universe_v2/existing_stop_catchment_units_12min.csv",
            "--population-units", "outputs/phase2/stop_universe_v2/accessibility_gap_building_pieces.csv",
            "--hub-access-bridge", "outputs/phase2/access_equity_v2/hub_access_bridge_v2.json",
            "--scenario-output", "outputs/phase2/access_equity_v2/scenario_access_equity_v2.csv.gz",
            "--validation-output", "outputs/phase2/access_equity_v2/access_equity_v2_validation.json",
        )
        run(
            "scripts/phase2_build_current_access_baseline_v2.py",
            "--identity", "outputs/phase2/current_service_stop_identity_2026-09-03.csv",
            "--identity-validation", "outputs/phase2/current_service_stop_identity_validation.json",
            "--v2-existing-stops", "outputs/phase2/stop_universe_v2/existing_official_stops.csv",
            "--stop-validation", "outputs/phase2/stop_universe_v2/stop_universe_v2_validation.json",
            "--existing-catchments", "outputs/phase2/stop_universe_v2/existing_stop_catchment_units_12min.csv",
            "--population-units", "outputs/phase2/stop_universe_v2/accessibility_gap_building_pieces.csv",
            "--access-validation", "outputs/phase2/access_equity_v2/access_equity_v2_validation.json",
            "--mapping-output", "outputs/phase2/current_access_baseline_v2/current_d184_d185_v2_stop_mapping.csv",
            "--validation-output", "outputs/phase2/current_access_baseline_v2/current_access_lower_bound_v2_validation.json",
        )
        run(
            "scripts/phase2_build_frequency_capability_frontiers_v2.py",
            "--access", "outputs/phase2/access_equity_v2/scenario_access_equity_v2.csv.gz",
            "--access-validation", "outputs/phase2/access_equity_v2/access_equity_v2_validation.json",
            "--territorial", "outputs/phase2/territorial_demand_v2/scenario_territorial_commuting_addressability_v2.csv.gz",
            "--territorial-validation", "outputs/phase2/territorial_demand_v2/territorial_commuting_addressability_v2_validation.json",
            "--service-feasibility", "outputs/phase2/service_policy_search_v2/service_policy_feasibility_v2.csv.gz",
            "--service-validation", "outputs/phase2/service_policy_search_v2/service_policy_search_v2_validation.json",
            "--policy-grid", "outputs/phase2/service_policy_search_v2/service_policy_design_space_v2.csv",
            "--frontier-output", "outputs/phase2/frequency_frontiers_v2/frequency_capability_structural_frontiers_v2.csv",
            "--validation", "outputs/phase2/frequency_frontiers_v2/frequency_capability_frontiers_v2_validation.json",
        )
        run(
            "scripts/phase2_build_reference_service_plan_shortlist_v2.py",
            "--access", "outputs/phase2/access_equity_v2/scenario_access_equity_v2.csv.gz",
            "--access-validation", "outputs/phase2/access_equity_v2/access_equity_v2_validation.json",
            "--territorial", "outputs/phase2/territorial_demand_v2/scenario_territorial_commuting_addressability_v2.csv.gz",
            "--territorial-validation", "outputs/phase2/territorial_demand_v2/territorial_commuting_addressability_v2_validation.json",
            "--service-feasibility", "outputs/phase2/service_policy_search_v2/service_policy_feasibility_v2.csv.gz",
            "--service-validation", "outputs/phase2/service_policy_search_v2/service_policy_search_v2_validation.json",
            "--policy-grid", "outputs/phase2/service_policy_search_v2/service_policy_design_space_v2.csv",
            "--operational", "outputs/phase2/operational_screening_v2/operational_screening_v2.csv",
            "--operational-validation", "outputs/phase2/operational_screening_v2/operational_screening_v2_validation.json",
            "--s8-feeder", "outputs/phase2/passenger_gjt_v2/s8_scenario_feeder_envelope_v2.csv.gz",
            "--s8-validation", "outputs/phase2/passenger_gjt_v2/s8_scenario_feeder_envelope_v2_validation.json",
            "--output", "outputs/phase2/reference_service_plan_shortlist_v2/reference_service_plan_shortlist_v2.csv",
            "--validation", "outputs/phase2/reference_service_plan_shortlist_v2/reference_service_plan_shortlist_v2_validation.json",
        )
        run(
            "scripts/phase2_build_plan_level_frontiers_v2.py",
            "--shortlist", "outputs/phase2/reference_service_plan_shortlist_v2/reference_service_plan_shortlist_v2.csv",
            "--shortlist-validation", "outputs/phase2/reference_service_plan_shortlist_v2/reference_service_plan_shortlist_v2_validation.json",
            "--output", "outputs/phase2/plan_level_frontiers_v2/plan_level_frontier_union_v2.csv",
            "--validation", "outputs/phase2/plan_level_frontiers_v2/plan_level_frontiers_v2_validation.json",
        )
        run(
            "scripts/phase2_build_base_exact_timetables_dynamic_v2.py",
            "--frontier", "outputs/phase2/plan_level_frontiers_v2/plan_level_frontier_union_v2.csv",
            "--frontier-validation", "outputs/phase2/plan_level_frontiers_v2/plan_level_frontiers_v2_validation.json",
            "--scenario-mapping", "outputs/phase2/s8_phasing_v2/scenario_to_routes_v2.csv.gz",
            "--route-universe", "outputs/phase2/s8_phasing_v2/unique_route_cycles_v2.csv",
            "--s8-validation", "outputs/phase2/s8_phasing_v2/s8_phasing_v2_validation.json",
            "--path-matrix", "outputs/phase2/reduced_path_matrix_v2/reduced_path_matrix.csv",
            "--matrix-validation", "outputs/phase2/reduced_path_matrix_v2/reduced_path_matrix_v2_validation.json",
            "--s8-events", "outputs/phase2/s8_events.csv",
            "--work-direction-summary", "outputs/phase2/passenger_gjt_v2/s8_work_direction_summary_v2.csv",
            "--work-weights-validation", "outputs/phase2/passenger_gjt_v2/s8_work_direction_weights_v2_validation.json",
            "--plan-output", "outputs/phase2/base_exact_timetables_v2/base_exact_timetable_candidates_v2.csv",
            "--trip-output", "outputs/phase2/base_exact_timetables_v2/base_exact_timetable_trips_v2.csv.gz",
            "--validation", "outputs/phase2/base_exact_timetables_v2/base_exact_timetables_v2_validation.json",
        )

    access = j("outputs/phase2/access_equity_v2/access_equity_v2_validation.json")
    current = j("outputs/phase2/current_access_baseline_v2/current_access_lower_bound_v2_validation.json")
    frequency = j("outputs/phase2/frequency_frontiers_v2/frequency_capability_frontiers_v2_validation.json")
    shortlist = j("outputs/phase2/reference_service_plan_shortlist_v2/reference_service_plan_shortlist_v2_validation.json")
    frontier = j("outputs/phase2/plan_level_frontiers_v2/plan_level_frontiers_v2_validation.json")
    exact = j("outputs/phase2/base_exact_timetables_v2/base_exact_timetables_v2_validation.json")

    assert access["status"] == "PASS_ACCESS_EQUITY_V2_BUILD"
    assert access["hub_boarding_access_included"] is True
    assert access["hub_access_proxy_cluster_id"] == "EX_039"
    assert access["scenario_count"] == 100000
    assert access["scenarios_missing_required_hub"] == 0
    assert current["status"] == "PASS_CURRENT_ACCESS_LOWER_BOUND_V2_BUILD"
    assert current["full_current_service_spatial_baseline_complete"] is False
    assert frequency["status"] == "PASS_FREQUENCY_CAPABILITY_FRONTIERS_V2_BUILD"
    assert frequency["scenario_count"] == 100000
    assert shortlist["status"] == "PASS_REFERENCE_SERVICE_PLAN_SHORTLIST_V2_BUILD"
    assert shortlist["scenario_count_upstream"] == 100000
    assert frontier["status"] == "PASS_PLAN_LEVEL_FRONTIERS_V2_BUILD"
    expected_base = int(frontier["frontier_class_plan_counts"]["BASE_UNRESTRICTED"])
    assert expected_base > 0
    assert exact["status"] == "PASS_BASE_EXACT_TIMETABLES_V2_BUILD"
    assert exact["input_base_frontier_plan_count"] == expected_base
    assert exact["exact_timetable_plan_count"] == expected_base
    assert exact["exact_timetable_constructed"] is True
    assert exact["joint_vehicle_block_timetable_feasibility_evaluated"] is True
    assert exact["exact_budget_infeasible_plan_count"] == 0
    for obj in (access, shortlist, frontier, exact):
        assert obj.get("primary_selected") is False
        assert obj.get("runner_up_selected") is False

    summary = {
        "status": "PASS_HUB_CORRECTED_TOURNAMENT_CASCADE_V2",
        "hub_cluster": access["hub_access_proxy_cluster_id"],
        "max_public_10min_coverage_share": access["max_public_population_coverage_share_10min"],
        "max_public_worst_municipality_10min_share": access["max_public_worst_municipality_coverage_share_10min"],
        "reference_h30_eligible_scenarios": frequency["eligible_scenario_counts"]["reference__h30"],
        "reference_h30_frontier_scenarios": frequency["frontier_scenario_counts"]["reference__h30"],
        "reference_h30_frontier_families": frequency["reference_family_counts"]["h30"],
        "shortlist_plan_count": shortlist["shortlist_scenario_plan_count"],
        "shortlist_frequent_plan_count": shortlist["frequent_30min_or_better_shortlist_count"],
        "base_frontier_plan_count": expected_base,
        "base_frequent_frontier_plan_count": frontier["frontier_class_plan_counts"]["BASE_FREQUENT_30"],
        "exact_plan_count": exact["exact_timetable_plan_count"],
        "exact_frequent_plan_count": exact["frequent_30min_or_better_exact_plan_count"],
        "exact_phase_vectors_evaluated": exact["phase_vectors_evaluated"],
        "exact_trip_rows": exact["trip_row_count_recovery15_blocks"],
        "primary_selected": False,
        "runner_up_selected": False,
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
