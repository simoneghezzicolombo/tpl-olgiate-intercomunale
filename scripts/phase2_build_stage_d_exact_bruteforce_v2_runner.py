#!/usr/bin/env python3
"""Contract adapter for the Stage-D exhaustive exact reference builder.

The implementation intentionally validates every upstream contract. This runner
binds the budget-policy check to the current certified contract name without
weakening any other lineage or epistemic check.
"""
from __future__ import annotations

import scripts.phase2_build_stage_d_exact_bruteforce_v2 as base


def validate_upstream_current(args):
    manifest = base.load_json(args.manifest_validation)
    passenger = base.load_json(args.passenger_validation)
    budget = base.load_json(args.budget_validation)
    s8 = base.load_json(args.s8_validation)
    matrix = base.load_json(args.matrix_validation)
    s8_contract = base.load_json(args.s8_contract)

    if manifest.get("status") != "PASS_PHASE2_STAGE_D_INPUT_MANIFEST_V2" or manifest.get("contract") != "PHASE2_LOSSLESS_DAILY_TIMING_INPUT_MANIFEST_V2":
        raise ValueError("Certified Stage-D input manifest is required")
    if manifest.get("lineage", {}).get("timing_output_sha256") != base.sha256_path(args.timing_inputs):
        raise ValueError("Stage-D timing manifest hash mismatch")
    if manifest.get("lineage", {}).get("route_output_sha256") != base.sha256_path(args.route_inputs):
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
    if passenger.get("lineage", {}).get("frontier_output_sha256") != base.sha256_path(args.passenger_frontier):
        raise ValueError("Passenger frontier hash mismatch")
    if int(passenger.get("passenger_utility_frontier_row_count_all_budgets", -1)) != 16883:
        raise ValueError("Unexpected Passenger Utility context count")

    if budget.get("status") != "PASS_PHASE2_BUDGET_POLICY_FRONTIERS_V2" or budget.get("contract") != "PHASE2_EXPLICIT_POLICY_CONTEXT_BUDGET_PARETO_V2":
        raise ValueError("Certified budget-policy frontier validation is required")
    if budget.get("budget_semantics") != "EXPLICIT_HARD_CAP_EVALUATED_INDEPENDENTLY_NOT_A_SCORE_WEIGHT":
        raise ValueError("Budget semantics are not an explicit hard cap")

    if s8.get("status") != "PASS_S8_PHASE_OPPORTUNITY_V2_BUILD" or s8.get("contract") != "PHASE2_S8_PHASE_OPPORTUNITY_SURFACE_V2":
        raise ValueError("Certified S8 Phase Opportunity V2 is required")
    if s8.get("lineage", {}).get("s8_events_sha256") != base.sha256_path(args.s8_events):
        raise ValueError("Frozen S8 event hash mismatch")
    if s8.get("phase_selected") is not False or s8.get("all_phases_retained_downstream") is not True:
        raise ValueError("Upstream S8 phase domain is not complete/unselected")

    if matrix.get("status") != "PASS_REDUCED_PATH_MATRIX_V2_BUILD" or matrix.get("contract") != "PHASE2_REDUCED_STOP_PATH_MATRIX_V2":
        raise ValueError("Certified reduced path matrix V2 is required")
    if matrix.get("lineage", {}).get("reduced_path_matrix_sha256") != base.sha256_path(args.path_matrix):
        raise ValueError("Reduced path matrix hash mismatch")

    if s8_contract.get("model") != "PHASE2_S8_INTERCHANGE_OPPORTUNITY_V1":
        raise ValueError("Unexpected S8 interchange contract")
    if int(s8_contract.get("active_s8_events", -1)) != 74:
        raise ValueError("Unexpected frozen S8 event count")
    if s8_contract.get("transfer_quality", {}).get("hard_quality_threshold") is not None:
        raise ValueError("Exact reference must not introduce a hard S8 quality threshold")
    return manifest, passenger, budget, s8, matrix, s8_contract


def main() -> int:
    base.validate_upstream = validate_upstream_current
    return base.main()


if __name__ == "__main__":
    raise SystemExit(main())
