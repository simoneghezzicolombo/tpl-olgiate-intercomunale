from __future__ import annotations

import json
from pathlib import Path

from scripts.phase2_redteam_alpha_gjt_bounds_pass_a import (
    evidence_fixture,
    fixed_event_fixture,
    optimizer_oracle_fixture,
    population_integrity_only_fixture,
    reduction_fixture,
    span_fixture,
)

ROOT = Path(__file__).resolve().parents[1]
SENSITIVITY = ROOT / "config/phase2_feeder_generalized_access_sensitivity_v2.json"
ALPHA_VALIDATION = ROOT / "outputs/phase2/gjt_set_bounds_exact_v3/exact_feeder_s8_set_bounds_v3_validation.json"
ALPHA_OUTPUT = ROOT / "outputs/phase2/gjt_set_bounds_exact_v3/exact_feeder_s8_set_bounds_v3.csv.gz"


def parameter_grid():
    return json.loads(SENSITIVITY.read_text(encoding="utf-8"))["parameter_grid"]


def test_previous_out_of_span_failure_fixture_is_now_closed():
    result = span_fixture()
    assert result["pre_fix_failure_fixture_replayed"] is True
    assert result["out_of_span_public_return_leak_detected"] is False
    assert result["out_of_span_opportunity_count"] == 0


def test_fixed_event_failure_is_not_rebound_to_later_train():
    result = fixed_event_fixture()
    assert result["fixed_event_infeasible"] is True
    assert result["later_event_feasible_when_explicitly_evaluated"] is True
    assert result["next_train_rebinding_observed"] is False


def test_incremental_fixed_event_selector_matches_independent_bruteforce_oracle():
    result = optimizer_oracle_fixture(parameter_grid())
    assert result["reduced_case_count_checked"] == 6
    assert result["fixed_event_optimizer_equals_all_opportunity_oracle"] is True


def test_six_case_reduction_matches_full_243_envelope_with_itinerary_switching():
    result = reduction_fixture(parameter_grid())
    assert result["full_factorial_case_count_checked"] == 243
    assert result["reduced_case_count_checked"] == 6
    assert result["full_min_equals_reduced_low_corner_min"] is True
    assert result["full_max_equals_reduced_high_corner_max"] is True
    assert result["itinerary_switching_exercised"] is True


def test_population_values_are_only_catchment_integrity_checks():
    result = population_integrity_only_fixture()
    assert result["population_values_used_for_row_integrity_equality_only"] is True
    assert result["population_weighted_cost_aggregation_detected"] is False


def test_persisted_alpha_evidence_has_consistent_witness_partition_and_hash():
    result = evidence_fixture(ALPHA_VALIDATION, ALPHA_OUTPUT)
    assert result["output_row_count"] == 60000
    assert result["finite_upper_bound_row_count"] == 0
    assert result["unbounded_upper_bound_row_count"] == 60000
    assert result["row_with_no_finite_lower_bound_count"] == 16990
    assert result["lower_witness_partition_consistent"] is True
    assert result["total_origin_event_stationwalk_state_count"] == 5_791_536_000
    assert result["unreachable_origin_event_stationwalk_state_count"] == 4_479_523_293
    assert 0.773 < result["unreachable_share"] < 0.774
    assert result["decision_use_boundary_preserved"] is True
