import pytest

from src.phase2_passenger_gjt_v2 import (
    EmpiricalJourneyDemand,
    GJTSensitivity,
    PassengerJourneyComponents,
    compare_weighted_journeys,
    generalised_journey_time,
)


def sensitivity():
    return GJTSensitivity("MID", 1.2, 1.75, 2.0, 6.0)


def journey(key="a", municipality="Olgiate Molgora", weight=10, bus=10, wait=5, missed=0.0):
    return PassengerJourneyComponents(
        journey_key=key,
        layer="ISTAT_2021_WORK_S8_DIRECT",
        origin_municipality=municipality,
        demand_weight=weight,
        walk_min=4,
        wait_min=wait,
        bus_ivt_min=bus,
        rail_ivt_min=30,
        transfer_walk_min=2,
        transfer_wait_min=3,
        transfers=1,
        missed_connection_probability=missed,
        missed_connection_cost_min=30,
        spatial_allocation_status="EXPLICIT_TEST_FIXTURE_ONLY",
        evidence_status="DERIVED",
    )


def test_gjt_keeps_bus_ivt_separate_from_rail_ivt():
    row = journey()
    assert generalised_journey_time(row, sensitivity()) == pytest.approx(74.5)


def test_comparison_preserves_demand_universe_and_reports_worst_municipality():
    base = [journey("o", "Olgiate Molgora", 10, bus=15), journey("b", "Brivio", 20, bus=20)]
    cand = [journey("o", "Olgiate Molgora", 10, bus=10), journey("b", "Brivio", 20, bus=22)]
    out = compare_weighted_journeys(base, cand, sensitivity())
    assert out.municipal_gjt_improvement_min["Olgiate Molgora"] == pytest.approx(6.0)
    assert out.municipal_gjt_improvement_min["Brivio"] == pytest.approx(-2.4)
    assert out.worst_municipality_gjt_improvement_min == pytest.approx(-2.4)
    assert out.demand_weighted_gjt_improvement_min == pytest.approx(0.4)


def test_comparison_refuses_changed_empirical_weights():
    with pytest.raises(ValueError, match="Demand weight differs"):
        compare_weighted_journeys([journey(weight=10)], [journey(weight=11)], sensitivity())


def test_full_gjt_refuses_municipal_od_without_spatial_allocation():
    with pytest.raises(ValueError, match="municipal OD alone"):
        PassengerJourneyComponents(
            journey_key="x",
            layer="ISTAT_2021_WORK_S8_DIRECT",
            origin_municipality="Brivio",
            demand_weight=1,
            walk_min=0,
            wait_min=0,
            bus_ivt_min=0,
            rail_ivt_min=0,
            spatial_allocation_status="MUNICIPAL_OD_ONLY_NO_SPATIAL_ALLOCATION",
        )


def test_empirical_demand_accepts_municipal_resolution_without_pretending_full_gjt():
    row = EmpiricalJourneyDemand("097010>015146", "097010", "Brivio", "015146", "Milano", 80)
    assert row.source_resolution == "MUNICIPAL_OD"
