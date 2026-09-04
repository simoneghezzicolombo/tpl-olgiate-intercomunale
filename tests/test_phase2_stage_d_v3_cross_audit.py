import copy

from src.phase2_stage_d_v3_cross_audit import Dataset, compare_datasets


def _validation():
    return {
        "status": "PASS_PHASE2_STAGE_D_EXACT_TIMETABLE_RT001_V3",
        "exact_budget_hard_cap_reapplied_after_materialisation": True,
        "s8_target_selection_semantics": "MAX_CONTINUOUS_TRANSFER_QUALITY_OVER_FINITE_EXPLICIT_TARGET_EVENTS",
        "technical_vehicle_closure_used_as_passenger_return": False,
        "decision_budget_selected": False,
        "calendar_selected": False,
        "recovery_selected": False,
        "primary_selected": False,
        "runner_up_selected": False,
        "weighted_composite_score": False,
    }


def _context(tid="A1", phase="[0]"):
    return {
        "plan_context_id": "m20pct|P1",
        "plan_id": "P1",
        "budget_suffix": "m20pct",
        "budget_cap_annual_bus_km": "100.000000",
        "stage_d_input_id": "D1",
        "scenario_id": "S1",
        "topology_family": "CORE",
        "uniform_headway_min": "20",
        "span_id": "SPAN",
        "calendar_id": "CAL260",
        "annual_service_days": "260",
        "phase_vectors_evaluated_once_for_daily_input": "20",
        "exact_budget_feasible_phase_vector_count": "10",
        "exact_budget_hard_eligible": "true",
        "selected_timetable_id": tid,
        "selected_phase_vector_json": phase,
        "robust_min_transfer_quality": "0.500000000000",
        "robust_unweighted_mean_transfer_quality": "0.600000000000",
        "exact_daily_bus_km": "0.300000000",
        "exact_annual_bus_km": "78.000000",
        "exact_fleet_recovery5": "1",
        "exact_fleet_recovery10": "1",
        "exact_fleet_recovery15": "1",
        "retained_current_localizable_cluster_count": "2",
        "retained_current_localizable_cluster_share": "0.500000000",
        "s8_target_selection_semantics": "MAX_CONTINUOUS_TRANSFER_QUALITY_OVER_FINITE_EXPLICIT_TARGET_EVENTS",
    }


def _table(tid="A1", phase="[0]"):
    return {
        "selected_timetable_id": tid,
        "stage_d_input_id": "D1",
        "scenario_id": "S1",
        "topology_family": "CORE",
        "uniform_headway_min": "20",
        "span_id": "SPAN",
        "span_start_min": "330",
        "span_end_min": "1440",
        "public_route_count": "1",
        "public_route_ids_json": '["R1"]',
        "selected_phase_vector_json": phase,
        "robust_min_transfer_quality": "0.500000000000",
        "robust_unweighted_mean_transfer_quality": "0.600000000000",
        "exact_daily_bus_km": "0.300000000",
        "explicit_public_trip_count": "1",
        "exact_fleet_recovery5": "1",
        "exact_fleet_recovery10": "1",
        "exact_fleet_recovery15": "1",
        "s8_target_selection_semantics": "MAX_CONTINUOUS_TRANSFER_QUALITY_OVER_FINITE_EXPLICIT_TARGET_EVENTS",
    }


def _trip(tid="A1", phase="0", vehicle="V1"):
    return {
        "selected_timetable_id": tid,
        "stage_d_input_id": "D1",
        "route_id": "R1",
        "route_phase_min": phase,
        "trip_ordinal": "0",
        "departure_min": "330.000000",
        "public_service_end_min": "350.000000",
        "vehicle_return_hub_min": "355.000000",
        "vehicle_id_recovery5": vehicle,
        "vehicle_id_recovery10": vehicle,
        "vehicle_id_recovery15": vehicle,
    }


def _dataset(label, tid="A1", phase="[0]"):
    return Dataset(label, _validation(), [_context(tid, phase)], [_table(tid, phase)], [_trip(tid, phase.strip("[]"))])


def test_implementation_specific_timetable_ids_are_ignored():
    out = compare_datasets(_dataset("A", "A1"), _dataset("B", "B9"))
    assert out["equivalent"] is True
    assert out["differing_context_count"] == 0
    assert out["differing_selected_phase_context_count"] == 0


def test_phase_difference_is_detected():
    out = compare_datasets(_dataset("A", "A1", "[0]"), _dataset("B", "B9", "[1]"))
    assert out["equivalent"] is False
    assert out["differing_selected_phase_context_count"] == 1


def test_vehicle_labels_are_compared_as_partitions_not_names():
    a = _dataset("A", "A1")
    b = _dataset("B", "B9")
    btrips = [copy.deepcopy(b.trips[0])]
    btrips[0]["vehicle_id_recovery15"] = "VEHICLE_99"
    b = Dataset(b.label, b.validation, b.contexts, b.timetables, btrips)
    out = compare_datasets(a, b)
    assert out["equivalent"] is True
    assert out["block_partition_mismatch_count_by_recovery"][15] == 0


def test_exact_km_difference_is_detected():
    b = _dataset("B", "B9")
    contexts = [copy.deepcopy(b.contexts[0])]
    contexts[0]["exact_annual_bus_km"] = "79.000000"
    b = Dataset(b.label, b.validation, contexts, b.timetables, b.trips)
    out = compare_datasets(_dataset("A", "A1"), b)
    assert out["equivalent"] is False
    assert out["differing_context_count"] == 1
