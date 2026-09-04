#!/usr/bin/env python3
"""Rejoin certified scenario continuity evidence to repaired Stage-C RT-001 V3.

Scenario-level continuity is recomputed from the same certified localisable
current-service lower bound and frozen route universe. Only repaired Stage-C
membership changes. No unresolved current stop is inferred and continuity is
not used to eliminate or rank candidates here.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys

import scripts.phase2_build_current_service_continuity_v2 as base

NEW_PU_STATUS = "PASS_PHASE2_PASSENGER_UTILITY_FRONTIER_RT001_V3"
NEW_PU_CONTRACT = "PHASE2_NO_WEIGHT_PASSENGER_UTILITY_EXACT_EXISTENTIAL_BUDGET_V3"
STATUS = "PASS_PHASE2_CURRENT_SERVICE_CONTINUITY_RT001_V3"
CONTRACT = "PHASE2_CERTIFIED_LOCALIZABLE_CURRENT_SERVICE_CONTINUITY_LOWER_BOUND_RT001_V3"
_seen_repaired_pu = False


def validate_upstream_rt001(args):
    global _seen_repaired_pu
    current = base.read_json(args.current_validation)
    matrix = base.read_json(args.matrix_validation)
    s8 = base.read_json(args.s8_validation)
    passenger = base.read_json(args.passenger_validation)

    if current.get("status") != "PASS_CURRENT_SERVICE_ACCESS_LOWER_BOUND_V2" or current.get("contract") != "PHASE2_CURRENT_SERVICE_CERTIFIED_LOCALIZABLE_ACCESS_LOWER_BOUND_V2":
        raise ValueError("Certified current-service lower-bound validation is required")
    if current.get("baseline_complete") is not False or current.get("may_infer_true_current_total_coverage") is not False or current.get("may_use_unresolved_rows_for_spatial_access") is not False:
        raise ValueError("Current baseline must remain explicitly incomplete and unresolved rows spatially prohibited")
    if current.get("historical_station_identity_kept_separate_from_project_hub_bridge") is not True:
        raise ValueError("Historical station/project bridge distinction changed")
    if current.get("historical_station_stop_id") != "300407" or current.get("project_station_access_cluster") != "EX_039" or current.get("project_station_access_stop_id") != "L00407":
        raise ValueError("Current/project station identity contract changed")
    if current.get("lineage", {}).get("localized_output_sha256") != base.sha256_path(args.current_localized):
        raise ValueError("Current-service localised-row hash mismatch")

    if matrix.get("status") != "PASS_REDUCED_PATH_MATRIX_V2_BUILD" or matrix.get("contract") != "PHASE2_REDUCED_STOP_PATH_MATRIX_V2":
        raise ValueError("Certified reduced path matrix required")
    if matrix.get("lineage", {}).get("routing_anchor_universe_sha256") != base.sha256_path(args.routing_anchors):
        raise ValueError("Routing anchor universe hash mismatch")

    if s8.get("status") != "PASS_S8_PHASE_OPPORTUNITY_V2_BUILD" or s8.get("contract") != "PHASE2_S8_PHASE_OPPORTUNITY_SURFACE_V2":
        raise ValueError("Certified S8 route/mapping lineage required")
    if s8.get("lineage", {}).get("route_universe_sha256") != base.sha256_path(args.route_universe):
        raise ValueError("S8 route universe hash mismatch")
    if s8.get("lineage", {}).get("scenario_route_mapping_sha256") != base.sha256_path(args.scenario_mapping):
        raise ValueError("S8 scenario mapping hash mismatch")

    if passenger.get("status") != NEW_PU_STATUS or passenger.get("contract") != NEW_PU_CONTRACT:
        raise ValueError("Repaired Passenger Utility RT001 V3 required")
    if passenger.get("rt001_repair") is not True or passenger.get("exact_budget_eligibility_repaired_before_stage_c") is not True:
        raise ValueError("Passenger Utility does not prove RT-001 repair")
    if passenger.get("lineage", {}).get("frontier_output_sha256") != base.sha256_path(args.passenger_frontier):
        raise ValueError("Passenger frontier hash mismatch")
    if int(passenger.get("passenger_utility_frontier_row_count_all_budgets", -1)) <= 0:
        raise ValueError("Invalid repaired Passenger Utility row count")
    if passenger.get("primary_selected") is not False or passenger.get("runner_up_selected") is not False:
        raise ValueError("Passenger upstream already contains forbidden final selection")
    _seen_repaired_pu = True
    return current, matrix, s8, passenger


base.validate_upstream = validate_upstream_rt001
base.STATUS = STATUS
base.CONTRACT = CONTRACT


def _validation_path() -> Path:
    try:
        return Path(sys.argv[sys.argv.index("--validation") + 1])
    except (ValueError, IndexError) as exc:
        raise ValueError("Missing --validation") from exc


def main() -> int:
    rc = base.main()
    if not _seen_repaired_pu:
        raise RuntimeError("Repaired Passenger Utility V3 was not consumed")
    path = _validation_path()
    v = json.loads(path.read_text(encoding="utf-8"))
    v["status"] = STATUS
    v["contract"] = CONTRACT
    v["rt001_repair"] = True
    v["passenger_utility_upstream_status"] = NEW_PU_STATUS
    v["passenger_utility_upstream_contract"] = NEW_PU_CONTRACT
    v["baseline_role"] = "CERTIFIED_LOCALIZABLE_LOWER_BOUND_ONLY"
    v["continuity_is_true_current_service_nonregression_proof"] = False
    v["epistemic_note"] += " Repaired Stage-C membership changes only which plans receive this same scenario-level lower-bound evidence."
    path.write_text(json.dumps(v, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
