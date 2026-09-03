from src.phase2_territorial_work_access_v2 import (
    aggregate_origin_demand,
    modeled_worker_capacity_upper_bound,
    population_proportional_sensitivity,
    scenario_home_access_metrics,
)


def _rows():
    return [
        {"procom_res": "A", "origin_name": "Alpha", "category": "SELF", "workers": "20"},
        {"procom_res": "A", "origin_name": "Alpha", "category": "OTHER_CORE", "workers": "10"},
        {"procom_res": "A", "origin_name": "Alpha", "category": "S8_DIRECT", "workers": "30"},
        {"procom_res": "A", "origin_name": "Alpha", "category": "OTHER_EXTERNAL", "workers": "40"},
        {"procom_res": "B", "origin_name": "Beta", "category": "SELF", "workers": "10"},
        {"procom_res": "B", "origin_name": "Beta", "category": "OTHER_CORE", "workers": "20"},
        {"procom_res": "B", "origin_name": "Beta", "category": "S8_DIRECT", "workers": "10"},
        {"procom_res": "B", "origin_name": "Beta", "category": "OTHER_EXTERNAL", "workers": "60"},
    ]


def test_aggregate_origin_demand_preserves_categories():
    demand = aggregate_origin_demand(_rows())
    assert demand["A"].worker_total == 100
    assert demand["A"].core_local_total == 30
    assert demand["B"].by_category["OTHER_EXTERNAL"] == 60


def test_capacity_upper_bound_is_capacity_not_proportional_estimate():
    assert modeled_worker_capacity_upper_bound(worker_count=100, modeled_covered_residents=35) == 35
    assert modeled_worker_capacity_upper_bound(worker_count=20, modeled_covered_residents=35) == 20
    assert population_proportional_sensitivity(worker_count=100, resident_coverage_share=0.35) == 35
    assert population_proportional_sensitivity(worker_count=20, resident_coverage_share=0.35) == 7


def test_scenario_sensitivity_categories_add_to_total_without_route_allocation():
    demand = aggregate_origin_demand(_rows())
    result = scenario_home_access_metrics(
        origin_demand=demand,
        located_population={"A": 200.0, "B": 100.0},
        coverage_share={"A": 0.25, "B": 0.50},
    )
    assert result["capacity_upper_bound"] == 100.0
    assert result["population_proportional_total"] == 75.0
    assert result["population_proportional_self"] == 10.0
    assert result["population_proportional_other_core"] == 12.5
    assert result["population_proportional_core_local"] == 22.5
    assert result["population_proportional_s8_direct"] == 12.5
    assert result["population_proportional_other_external"] == 40.0
    assert (
        result["population_proportional_self"]
        + result["population_proportional_other_core"]
        + result["population_proportional_s8_direct"]
        + result["population_proportional_other_external"]
        == result["population_proportional_total"]
    )
