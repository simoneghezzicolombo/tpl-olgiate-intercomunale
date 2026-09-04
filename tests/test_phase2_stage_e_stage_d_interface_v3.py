import pytest

from src.phase2_stage_e_stage_d_interface_v3 import validate_exact_interface


def validation(**overrides):
    payload = {
        "status": "PASS_PHASE2_STAGE_D_EXACT_TIMETABLE_TEST",
        "contract": "PHASE2_EXHAUSTIVE_EXACT_TIMETABLE_TEST",
        "exact_timetable_constructed": True,
        "joint_vehicle_blocks_evaluated": True,
        "recovery_values_evaluated_not_selected": [5, 10, 15],
        "decision_budget_selected": False,
        "calendar_selected": False,
        "recovery_selected": False,
        "primary_selected": False,
        "runner_up_selected": False,
        "weighted_composite_score": False,
        "ridership_forecast": False,
        "municipal_od_downscaled": False,
    }
    payload.update(overrides)
    return payload


def legacy_summary():
    return [{
        "stage_d_input_id": "D1",
        "scenario_id": "S1",
        "selected_phase_vector_json": "[0]",
        "represented_plan_context_ids_json": "[\"reference|P1\"]",
    }]


def legacy_trips():
    return [{"stage_d_input_id": "D1", "route_id": "R1", "trip_ordinal": "0"}]


def test_legacy_v2_identity_remains_consumable():
    out = validate_exact_interface(
        validation(represented_stage_c_plan_context_count=1),
        legacy_summary(),
        legacy_trips(),
        summary_fields=legacy_summary()[0].keys(),
        trip_fields=legacy_trips()[0].keys(),
    )
    assert out["identity_field"] == "stage_d_input_id"
    assert out["stage_e_can_consume_without_context_collapse"] is True


def test_context_dependent_split_uses_explicit_exact_timetable_id():
    summary = [
        {
            "exact_timetable_id": "E1", "stage_d_input_id": "D1", "scenario_id": "S1",
            "selected_phase_vector_json": "[0]", "represented_plan_context_ids_json": "[\"m20|P1\"]",
        },
        {
            "exact_timetable_id": "E2", "stage_d_input_id": "D1", "scenario_id": "S1",
            "selected_phase_vector_json": "[1]", "represented_plan_context_ids_json": "[\"reference|P1\"]",
        },
    ]
    trips = [
        {"exact_timetable_id": "E1", "stage_d_input_id": "D1", "route_id": "R1", "trip_ordinal": "0"},
        {"exact_timetable_id": "E2", "stage_d_input_id": "D1", "route_id": "R1", "trip_ordinal": "0"},
    ]
    out = validate_exact_interface(
        validation(represented_stage_c_plan_context_count=2), summary, trips,
        summary_fields=summary[0].keys(), trip_fields=trips[0].keys(),
    )
    assert out["identity_field"] == "exact_timetable_id"
    assert out["stage_d_inputs_with_context_dependent_exact_split"] == 1
    assert out["represented_plan_context_count_observed"] == 2


def test_overlapping_context_mapping_fails_closed():
    summary = [
        {"exact_timetable_id": "E1", "stage_d_input_id": "D1", "scenario_id": "S1", "represented_plan_context_ids_json": "[\"x|P1\"]"},
        {"exact_timetable_id": "E2", "stage_d_input_id": "D1", "scenario_id": "S1", "represented_plan_context_ids_json": "[\"x|P1\"]"},
    ]
    trips = [
        {"exact_timetable_id": "E1", "route_id": "R1", "trip_ordinal": "0"},
        {"exact_timetable_id": "E2", "route_id": "R1", "trip_ordinal": "0"},
    ]
    with pytest.raises(ValueError, match="represented by multiple"):
        validate_exact_interface(validation(), summary, trips, summary_fields=summary[0].keys(), trip_fields=trips[0].keys())


def test_orphan_trip_fails_closed():
    summary = [{"exact_timetable_id": "E1", "stage_d_input_id": "D1", "scenario_id": "S1"}]
    trips = [{"exact_timetable_id": "E2", "route_id": "R1", "trip_ordinal": "0"}]
    with pytest.raises(ValueError, match="unknown exact timetable"):
        validate_exact_interface(validation(), summary, trips, summary_fields=summary[0].keys(), trip_fields=trips[0].keys())


def test_missing_trip_set_fails_closed():
    summary = [{"exact_timetable_id": "E1", "stage_d_input_id": "D1", "scenario_id": "S1"}]
    with pytest.raises(ValueError, match="without trips"):
        validate_exact_interface(validation(), summary, [], summary_fields=summary[0].keys(), trip_fields=["exact_timetable_id", "route_id", "trip_ordinal"])


def test_declared_context_count_must_match_observed_mapping():
    summary = [{
        "stage_d_input_id": "D1", "scenario_id": "S1",
        "represented_plan_context_ids_json": "[\"reference|P1\"]",
    }]
    trips = legacy_trips()
    with pytest.raises(ValueError, match="coverage mismatch"):
        validate_exact_interface(
            validation(represented_stage_c_plan_context_count=2), summary, trips,
            summary_fields=summary[0].keys(), trip_fields=trips[0].keys(),
        )


def test_non_decisional_boundary_is_enforced():
    with pytest.raises(ValueError, match="primary_selected"):
        validate_exact_interface(
            validation(primary_selected=True), legacy_summary(), legacy_trips(),
            summary_fields=legacy_summary()[0].keys(), trip_fields=legacy_trips()[0].keys(),
        )


def test_recovery_sensitivity_must_remain_explicit():
    with pytest.raises(ValueError, match="recovery sensitivities"):
        validate_exact_interface(
            validation(recovery_values_evaluated_not_selected=[]), legacy_summary(), legacy_trips(),
            summary_fields=legacy_summary()[0].keys(), trip_fields=legacy_trips()[0].keys(),
        )
