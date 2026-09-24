"""Contract tests for the Phase 2 operational/passenger-utility engine.

All numeric values in this file are TEST_FIXTURE_ONLY and are never written to
project outputs or used as territorial evidence.
"""
import pytest

from src.phase2_service_engine import (
    BehaviouralWeights,
    JourneyRecord,
    OperatingCycle,
    OperatingPlan,
    OpportunityAccessRecord,
    PopulationAccessRecord,
    ServiceWindow,
    build_hard_constraints,
    compare_weighted_journeys,
    generalised_journey_time,
    municipal_non_regression,
    opportunity_access_summary,
    population_access_summary,
    summarise_operating_plan,
    to_sensitivity_result,
)


def test_operating_plan_computes_production_hours_and_fleet_without_hidden_calendar():
    cycles = (
        OperatingCycle("B1", ("R1",), 10.0, 50.0, 10.0, "DERIVED"),
        OperatingCycle("B2", ("R2",), 8.0, 40.0, 5.0, "DERIVED"),
    )
    windows = (
        ServiceWindow("W1", "B1", "WEEKDAY", 360, 540, 30, 250),
        ServiceWindow("W2", "B2", "WEEKDAY", 360, 540, 30, 250),
    )
    summary = summarise_operating_plan(OperatingPlan("S1", "P1", cycles, windows))

    assert summary.total_annual_departures == pytest.approx(3000.0)
    assert summary.annual_bus_km == pytest.approx((6 * 250 * 10) + (6 * 250 * 8))
    assert summary.annual_vehicle_hours == pytest.approx(
        (6 * 250 * 60 / 60) + (6 * 250 * 45 / 60)
    )
    assert summary.max_active_vehicles == 4
    assert summary.min_recovery_min == 5.0


def test_service_window_phase_is_explicit_and_changes_departure_count():
    no_phase = ServiceWindow("A", "B", "WK", 360, 420, 30, 1, 0)
    late_phase = ServiceWindow("B", "B", "WK", 360, 420, 30, 1, 20)
    assert no_phase.departures_per_day == 2
    assert late_phase.departures_per_day == 2

    almost_outside = ServiceWindow("C", "B", "WK", 360, 380, 30, 1, 25)
    assert almost_outside.departures_per_day == 0


def test_operating_plan_rejects_overlapping_regimes_for_same_block_and_day_type():
    cycle = (OperatingCycle("B1", ("R1",), 10.0, 50.0, 5.0, "DERIVED"),)
    windows = (
        ServiceWindow("W1", "B1", "WK", 360, 540, 30, 250),
        ServiceWindow("W2", "B1", "WK", 500, 600, 60, 250),
    )
    with pytest.raises(ValueError, match="Overlapping service windows"):
        OperatingPlan("S", "P", cycle, windows)


def test_invalidated_or_placeholder_evidence_is_rejected():
    with pytest.raises(ValueError):
        OperatingCycle("B", ("R",), 1.0, 5.0, 1.0, "INVALIDATED")
    with pytest.raises(ValueError):
        JourneyRecord("J", "WORK_OD", "X", 1.0, 1, 1, 1, evidence_status="PLACEHOLDER")


def test_gjt_uses_explicit_components_and_behavioural_weights():
    row = JourneyRecord(
        "J1", "WORK_OD", "A", 10.0,
        walk_min=4.0,
        wait_min=5.0,
        in_vehicle_min=20.0,
        transfer_walk_min=1.0,
        transfer_wait_min=3.0,
        transfers=1,
        missed_connection_probability=0.10,
        missed_connection_cost_min=30.0,
    )
    weights = BehaviouralWeights("SENS_A", 2.0, 2.5, 5.0, 1.0)
    expected = 20 + 2 * 5 + 2.5 * 8 + 5 + 0.10 * 30
    assert generalised_journey_time(row, weights) == pytest.approx(expected)


def test_weighted_comparison_matches_same_demand_universe_and_reports_municipal_floor():
    weights = BehaviouralWeights("SENS_A", 1.0, 1.0, 0.0)
    baseline = [
        JourneyRecord("J1", "WORK_OD", "A", 3.0, 2, 5, 20),
        JourneyRecord("J2", "WORK_OD", "B", 1.0, 2, 5, 20),
    ]
    candidate = [
        JourneyRecord("J1", "WORK_OD", "A", 3.0, 2, 3, 18),
        JourneyRecord("J2", "WORK_OD", "B", 1.0, 2, 8, 20),
    ]
    comparison = compare_weighted_journeys(baseline, candidate, weights)

    assert comparison.demand_weighted_gjt_improvement_min == pytest.approx(2.25)
    assert comparison.municipal_gjt_improvement_min["A"] == pytest.approx(4.0)
    assert comparison.municipal_gjt_improvement_min["B"] == pytest.approx(-3.0)
    assert comparison.worst_municipality_gjt_improvement_min == pytest.approx(-3.0)
    assert municipal_non_regression(comparison) is False
    assert municipal_non_regression(comparison, tolerance_min=3.0) is True

    sensitivity = to_sensitivity_result(scenario_id="SCENARIO", comparison=comparison)
    assert sensitivity.scenario_id == "SCENARIO"
    assert sensitivity.sensitivity_id == "SENS_A"


def test_weighted_comparison_refuses_changed_demand_weights():
    weights = BehaviouralWeights("SENS", 1.0, 1.0, 0.0)
    baseline = [JourneyRecord("J1", "WORK_OD", "A", 3.0, 1, 1, 1)]
    candidate = [JourneyRecord("J1", "WORK_OD", "A", 4.0, 1, 1, 1)]
    with pytest.raises(ValueError, match="Demand weight differs"):
        compare_weighted_journeys(baseline, candidate, weights)


def test_population_access_is_separate_from_od_utility():
    rows = [
        PopulationAccessRecord("C1", "A", 60.0, 4.0),
        PopulationAccessRecord("C2", "A", 40.0, 9.0),
        PopulationAccessRecord("C3", "B", 100.0, 7.0),
    ]
    summary = population_access_summary(rows, thresholds_min=(5, 8, 10))
    all_8 = next(row for row in summary if row["municipality"] == "ALL" and row["threshold_min"] == 8.0)
    a_8 = next(row for row in summary if row["municipality"] == "A" and row["threshold_min"] == 8.0)
    assert all_8["population_served"] == pytest.approx(160.0)
    assert all_8["population_served_share"] == pytest.approx(0.8)
    assert a_8["population_served_share"] == pytest.approx(0.6)


def test_opportunity_access_remains_separate_when_trip_weights_are_unknown():
    rows = [
        OpportunityAccessRecord("C1", "A", "HEALTH", 60.0, 20.0),
        OpportunityAccessRecord("C2", "A", "HEALTH", 40.0, 35.0),
        OpportunityAccessRecord("C1", "A", "SCHOOL", 60.0, 15.0),
        OpportunityAccessRecord("C2", "A", "SCHOOL", 40.0, 25.0),
    ]
    summary = opportunity_access_summary(rows, thresholds_min=(20, 30))
    health_20 = next(
        row for row in summary
        if row["opportunity_type"] == "HEALTH" and row["threshold_min"] == 20.0
    )
    school_20 = next(
        row for row in summary
        if row["opportunity_type"] == "SCHOOL" and row["threshold_min"] == 20.0
    )
    assert health_20["population_reached_share"] == pytest.approx(0.6)
    assert school_20["population_reached_share"] == pytest.approx(0.6)


def test_hard_constraints_keep_budget_fleet_recovery_and_equity_explicit():
    plan = OperatingPlan(
        "S", "P",
        (OperatingCycle("B", ("R",), 10.0, 50.0, 10.0, "DERIVED"),),
        (ServiceWindow("W", "B", "WK", 360, 420, 30, 250),),
    )
    summary = summarise_operating_plan(plan)
    hard = build_hard_constraints(
        summary=summary,
        road_integrity=True,
        budget_km=6000,
        fleet_cap=2,
        minimum_recovery_min=5,
        territorial_non_regression=True,
        upstream_evidence_valid=True,
    )
    assert hard.eligible is True

    too_small_budget = build_hard_constraints(
        summary=summary,
        road_integrity=True,
        budget_km=1000,
        fleet_cap=2,
        minimum_recovery_min=5,
        territorial_non_regression=True,
        upstream_evidence_valid=True,
    )
    assert too_small_budget.within_budget is False
    assert too_small_budget.eligible is False
