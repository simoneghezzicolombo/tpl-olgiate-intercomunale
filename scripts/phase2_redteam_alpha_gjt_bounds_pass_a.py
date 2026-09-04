#!/usr/bin/env python3
"""Independent targeted red-team of Alpha's fixed-event GJT set bounds V3.

This is deliberately a small review, not a new Phase 2 workstream. It checks the
specific failure modes agreed in Issue #1 against the corrected Alpha lineage:
passenger span semantics, fixed-event identity, optimizer/oracle equivalence,
the 243->6 monotonic reduction, witness/count consistency, absence of hidden
demand weighting, and the non-decisional use boundary.
"""
from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import math
from pathlib import Path

from scripts.phase2_build_feeder_generalized_access_v2 import load_walk_maps
from src.phase2_gjt_set_bounds_exact_v3 import (
    HUB_ANCHOR,
    BusOpportunity,
    RailDeparture,
    SensitivityCase,
    brute_force_fixed_event_anchor_components,
    build_public_to_hub_occurrences,
    build_timetable_bus_opportunities,
    bus_generalized_cost,
    direct_walk_generalized_cost,
    fixed_event_anchor_components,
    full_sensitivity_cases,
    reduced_sensitivity_cases,
)

ALPHA_EVIDENCE_COMMIT = "c90232d13fa9e4acde6f3e9732b9a0ec62a89aef"
ALPHA_DOC_HEAD = "9c574ddbebf07707372e8b2747eaec32ea63effa"
STATUS = "PASS_PHASE2_GJT_BOUNDS_TARGETED_REVIEW_A_V3"
CONTRACT = "PHASE2_GJT_BOUNDS_TARGETED_REVIEW_A_V3"
EPS = 1e-12


def sha256_path(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def span_fixture() -> dict[str, object]:
    """Re-run the exact fixture that failed on Alpha's pre-fix implementation."""
    anchors = (HUB_ANCHOR, "anchor:A", HUB_ANCHOR)
    runtime = {
        (HUB_ANCHOR, "anchor:A"): 10.0,
        ("anchor:A", HUB_ANCHOR): 10.0,
    }
    occurrences = build_public_to_hub_occurrences(
        anchors, runtime, bus_to_rail_passenger_event_supported=True
    )
    rejected = build_timetable_bus_opportunities(
        {"R_CLOSED": (50.0,)},
        {"R_CLOSED": occurrences},
        span_start_min=0.0,
        span_end_min=60.0,
    )
    admitted = build_timetable_bus_opportunities(
        {"R_CLOSED": (30.0,)},
        {"R_CLOSED": occurrences},
        span_start_min=0.0,
        span_end_min=60.0,
    )
    bad_rows = tuple(rejected.get("anchor:A", ()))
    good_rows = tuple(admitted.get("anchor:A", ()))
    assert bad_rows == (), "Out-of-span public hub return leaked into passenger BUS_TO_RAIL opportunities"
    assert len(good_rows) == 1 and math.isclose(good_rows[0].bus_hub_arrival_min, 50.0)
    return {
        "pre_fix_failure_fixture_replayed": True,
        "trip_departure_min": 50.0,
        "physical_public_hub_return_min": 70.0,
        "span_end_min": 60.0,
        "out_of_span_opportunity_count": len(bad_rows),
        "in_span_positive_control_hub_return_min": good_rows[0].bus_hub_arrival_min,
        "out_of_span_public_return_leak_detected": False,
    }


def fixed_event_fixture() -> dict[str, object]:
    case = SensitivityCase("LOW_SW3", 3.0, 1.0, 1.5, 1.5, 2.0, "LOW")
    opportunity = BusOpportunity("anchor:A", "R", 80.0, 99.0, 8.0)
    fixed = RailDeparture("M1", "MILANO", 101.0)
    later = RailDeparture("M2", "MILANO", 120.0)
    fixed_value = bus_generalized_cost(
        access_walk_min=2.0, opportunity=opportunity, rail_event=fixed, case=case
    )
    later_value = bus_generalized_cost(
        access_walk_min=2.0, opportunity=opportunity, rail_event=later, case=case
    )
    assert fixed_value is None
    assert later_value is not None
    return {
        "fixed_event_infeasible": True,
        "later_event_feasible_when_explicitly_evaluated": True,
        "next_train_rebinding_observed": False,
    }


def optimizer_oracle_fixture(parameter_grid: dict[str, list[float]]) -> dict[str, object]:
    opportunities = {
        "A": (
            BusOpportunity("A", "R1", 70.0, 96.0, 12.0),
            BusOpportunity("A", "R2", 75.0, 101.0, 7.0),
            BusOpportunity("A", "R3", 81.0, 109.0, 4.0),
        ),
        "B": (
            BusOpportunity("B", "R4", 60.0, 93.0, 9.0),
            BusOpportunity("B", "R5", 86.0, 112.0, 6.0),
        ),
    }
    events = (
        RailDeparture("M1", "MILANO", 100.0),
        RailDeparture("M2", "MILANO", 110.0),
        RailDeparture("M3", "MILANO", 120.0),
    )
    cases = reduced_sensitivity_cases(parameter_grid)
    for case in cases:
        optimized = fixed_event_anchor_components(opportunities, events, case)
        brute = brute_force_fixed_event_anchor_components(opportunities, events, case)
        assert optimized == brute, f"Optimized selector differs from brute-force oracle in {case.case_id}"
    return {
        "reduced_case_count_checked": len(cases),
        "fixed_event_optimizer_equals_all_opportunity_oracle": True,
    }


def _independent_best_cost(case: SensitivityCase) -> tuple[float, str]:
    event = RailDeparture("M", "MILANO", 120.0)
    scored = [(direct_walk_generalized_cost(hub_walk_min=9.0, case=case), "DIRECT")]
    options = (
        (BusOpportunity("A", "R1", 80.0, 108.5, 8.0), 2.0, "R1"),
        (BusOpportunity("B", "R2", 84.0, 111.5, 5.0), 5.0, "R2"),
        (BusOpportunity("C", "R3", 90.0, 117.5, 3.0), 1.0, "R3"),
    )
    for opportunity, access_walk, label in options:
        result = bus_generalized_cost(
            access_walk_min=access_walk,
            opportunity=opportunity,
            rail_event=event,
            case=case,
        )
        if result is not None:
            scored.append((result[0], label))
    return min(scored)


def reduction_fixture(parameter_grid: dict[str, list[float]]) -> dict[str, object]:
    full = full_sensitivity_cases(parameter_grid)
    reduced = reduced_sensitivity_cases(parameter_grid)
    assert len(full) == 243
    assert len(reduced) == 6
    full_scored = [_independent_best_cost(case) for case in full]
    low_scored = [_independent_best_cost(case) for case in reduced if case.bound_side == "LOW"]
    high_scored = [_independent_best_cost(case) for case in reduced if case.bound_side == "HIGH"]
    full_min = min(v for v, _ in full_scored)
    full_max = max(v for v, _ in full_scored)
    reduced_min = min(v for v, _ in low_scored)
    reduced_max = max(v for v, _ in high_scored)
    assert math.isclose(full_min, reduced_min, rel_tol=0.0, abs_tol=EPS)
    assert math.isclose(full_max, reduced_max, rel_tol=0.0, abs_tol=EPS)
    route_labels = {label for _, label in full_scored}
    assert len(route_labels) >= 2, "Fixture did not exercise itinerary switching"
    station_values = sorted({case.station_transfer_walk_min for case in reduced})
    expected_station_values = sorted({float(v) for v in parameter_grid["station_transfer_walk_min"]})
    assert station_values == expected_station_values
    return {
        "full_factorial_case_count_checked": len(full),
        "reduced_case_count_checked": len(reduced),
        "full_min_equals_reduced_low_corner_min": True,
        "full_max_equals_reduced_high_corner_max": True,
        "itinerary_switching_exercised": True,
        "station_transfer_walk_values_exhaustively_enumerated": station_values,
    }


def population_integrity_only_fixture() -> dict[str, object]:
    """Verify the inherited catchment loader does not aggregate on population weights."""
    source = inspect.getsource(load_walk_maps)
    assert source.count("weights[idx]") == 2
    forbidden = (
        "sum(weights",
        "weights[idx] *",
        "* weights[idx]",
        "weighted_average",
        "np.average",
    )
    for token in forbidden:
        assert token not in source, f"Population weighting appeared in catchment loader: {token}"
    assert "math.isclose(row_weight, weights[idx]" in source
    return {
        "population_value_uses_in_catchment_loader": 2,
        "population_values_used_for_row_integrity_equality_only": True,
        "population_weighted_cost_aggregation_detected": False,
    }


def evidence_fixture(alpha_validation: Path, alpha_output: Path) -> dict[str, object]:
    validation = json.loads(alpha_validation.read_text(encoding="utf-8"))
    assert validation["status"] == "PASS_PHASE2_EXACT_FEEDER_S8_SET_BOUNDS_V3"
    assert validation["contract"] == "PHASE2_FIXED_EVENT_FINE_ORIGIN_SET_IDENTIFICATION_BOUNDS_V3"
    assert validation["selected_exact_timetable_count"] == 6000
    assert validation["population_unit_count"] == 4348
    assert validation["output_row_count"] == 60000
    assert validation["finite_upper_bound_row_count"] == 0
    assert validation["unbounded_upper_bound_row_count"] == 60000
    assert validation["row_with_no_finite_lower_bound_count"] == 16990
    assert validation["direct_option_lower_witness_count"] == 24000
    assert validation["bus_option_lower_witness_count"] == 19010
    assert (
        validation["row_with_no_finite_lower_bound_count"]
        + validation["direct_option_lower_witness_count"]
        + validation["bus_option_lower_witness_count"]
        == validation["output_row_count"]
    )
    assert (
        validation["finite_upper_bound_row_count"]
        + validation["unbounded_upper_bound_row_count"]
        == validation["output_row_count"]
    )
    for key in (
        "municipal_od_downscaled",
        "worker_locations_imputed",
        "resident_population_used_as_passenger_demand",
        "resident_population_used_as_worker_location_capacity",
        "half_headway_wait_used",
        "departure_time_distribution_used",
        "rail_event_probability_weighting_used",
        "next_train_rebinding_used",
        "technical_vehicle_closure_used_as_passenger_return",
        "expected_daily_gjt_identified",
        "full_point_demand_weighted_gjt_identified",
        "conditional_cost_is_full_gjt",
        "ranking_or_pruning_authorized",
        "interval_dominance_applied",
        "weighted_composite_score",
        "primary_selected",
        "runner_up_selected",
    ):
        assert validation[key] is False, f"Forbidden/unsupported semantic flag became true: {key}"
    for key in (
        "fixed_event_bus_component_optimizer_exact",
        "fixed_event_bus_component_optimizer_bruteforce_oracle_tested",
        "fixed_rail_event_identity_preserved_within_itinerary",
        "rail_event_conditioned_before_set_envelope",
        "next_explicit_public_hub_occurrence_only",
        "fine_origin_set_identification_materialized",
    ):
        assert validation[key] is True, f"Required semantic flag is not true: {key}"
    actual_output_sha = sha256_path(alpha_output)
    assert actual_output_sha == validation["lineage"]["output_sha256"]
    station_state_count = 3
    total_state_count = (
        validation["population_unit_count"]
        * sum(validation["rail_event_count_by_direction"].values())
        * station_state_count
        * validation["selected_exact_timetable_count"]
    )
    assert total_state_count == 5_791_536_000
    unreachable = validation["total_unreachable_origin_event_stationwalk_state_count"]
    assert unreachable == 4_479_523_293
    unreachable_share = unreachable / total_state_count
    assert 0.773 < unreachable_share < 0.774
    assert validation["decision_boundary"] == "SET_IDENTIFICATION_EVIDENCE_ONLY_NO_RANKING_PRUNING_INTERVAL_DOMINANCE_PRIMARY_OR_RUNNER_UP"
    return {
        "output_sha256_verified": actual_output_sha,
        "output_row_count": validation["output_row_count"],
        "finite_upper_bound_row_count": validation["finite_upper_bound_row_count"],
        "unbounded_upper_bound_row_count": validation["unbounded_upper_bound_row_count"],
        "row_with_no_finite_lower_bound_count": validation["row_with_no_finite_lower_bound_count"],
        "lower_witness_partition_consistent": True,
        "total_origin_event_stationwalk_state_count": total_state_count,
        "unreachable_origin_event_stationwalk_state_count": unreachable,
        "unreachable_share": unreachable_share,
        "decision_use_boundary_preserved": True,
    }


def perform_audit(alpha_validation: Path, alpha_output: Path, sensitivity_config: Path) -> dict[str, object]:
    sensitivity = json.loads(sensitivity_config.read_text(encoding="utf-8"))
    assert sensitivity["contract"] == "PHASE2_FEEDER_GENERALIZED_ACCESS_SENSITIVITY_V2"
    assert sensitivity["status"] == "ASSUMPTION_SENSITIVITY_NOT_EMPIRICAL_INTERVAL"
    parameter_grid = sensitivity["parameter_grid"]
    payload = {
        "status": STATUS,
        "contract": CONTRACT,
        "certification_pass": True,
        "review_scope": "LIGHTWEIGHT_TARGETED_RED_TEAM_ONLY_NO_NEW_PHASE2_WORKSTREAM",
        "alpha_evidence_commit": ALPHA_EVIDENCE_COMMIT,
        "alpha_documentation_head": ALPHA_DOC_HEAD,
        "span_semantics": span_fixture(),
        "fixed_event_semantics": fixed_event_fixture(),
        "optimizer_oracle": optimizer_oracle_fixture(parameter_grid),
        "sensitivity_reduction": reduction_fixture(parameter_grid),
        "population_semantics": population_integrity_only_fixture(),
        "persisted_evidence": evidence_fixture(alpha_validation, alpha_output),
        "findings": {
            "blocking_issue_count": 0,
            "historical_half_headway_wait_reused": False,
            "hidden_demand_or_worker_weighting_detected": False,
            "municipal_od_downscaled": False,
            "next_train_rebinding_detected": False,
            "technical_return_used_as_passenger_service": False,
            "out_of_span_public_return_leak_detected": False,
            "interval_dominance_can_discriminate_with_current_full_envelope": False,
        },
        "decision_boundary": "PASS_AS_SET_IDENTIFICATION_EVIDENCE_ENRICHMENT_ONLY__NOT_FULL_GJT__NOT_A_RANKING__NOT_PRIMARY_OR_RUNNER_UP",
        "non_blocking_note": "Alpha CI run 33892440844 persisted evidence to GitHub, but its artifact-upload step used literal $OUTDIR and uploaded no artifact. Repository evidence remains intact and hash-verified.",
    }
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--alpha-validation",
        type=Path,
        default=Path("outputs/phase2/gjt_set_bounds_exact_v3/exact_feeder_s8_set_bounds_v3_validation.json"),
    )
    parser.add_argument(
        "--alpha-output",
        type=Path,
        default=Path("outputs/phase2/gjt_set_bounds_exact_v3/exact_feeder_s8_set_bounds_v3.csv.gz"),
    )
    parser.add_argument(
        "--sensitivity-config",
        type=Path,
        default=Path("config/phase2_feeder_generalized_access_sensitivity_v2.json"),
    )
    parser.add_argument("--validation", type=Path, required=True)
    args = parser.parse_args()
    for path in (args.alpha_validation, args.alpha_output, args.sensitivity_config):
        if not path.is_file():
            raise FileNotFoundError(path)
    payload = perform_audit(args.alpha_validation, args.alpha_output, args.sensitivity_config)
    args.validation.parent.mkdir(parents=True, exist_ok=True)
    args.validation.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
