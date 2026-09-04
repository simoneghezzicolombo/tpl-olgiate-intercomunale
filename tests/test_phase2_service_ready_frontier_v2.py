from scripts.phase2_build_service_ready_frontier_v2 import (
    CYCLE_DISTANCE_AXIS,
    CYCLE_RUNTIME_AXIS,
    MAX_AXES,
    MIN_AXES,
    dominates,
    pareto,
)


def row(scenario_id: str) -> dict[str, object]:
    result: dict[str, object] = {"scenario_id": scenario_id}
    for field in MAX_AXES:
        result[field] = 0.0
    for field in MIN_AXES:
        result[field] = 0.0
    return result


def test_cycle_primitives_are_explicit_minimisation_axes():
    assert CYCLE_DISTANCE_AXIS in MIN_AXES
    assert CYCLE_RUNTIME_AXIS in MIN_AXES


def test_policy_outputs_do_not_enter_budget_neutral_frontier_axes():
    assert "annual_bus_km" not in MIN_AXES
    assert "aggregate_interlinable_fleet_lower_bound" not in MIN_AXES


def test_shorter_closed_cycle_can_prevent_wrong_prepolicy_dominance():
    public_shorter = row("public_shorter")
    cycle_shorter = row("cycle_shorter")
    public_shorter["public_distance_km"] = 10
    cycle_shorter["public_distance_km"] = 11
    public_shorter[CYCLE_DISTANCE_AXIS] = 16
    cycle_shorter[CYCLE_DISTANCE_AXIS] = 12
    assert not dominates(public_shorter, cycle_shorter)
    assert not dominates(cycle_shorter, public_shorter)
    assert {r["scenario_id"] for r in pareto([public_shorter, cycle_shorter])} == {
        "public_shorter", "cycle_shorter"
    }


def test_componentwise_better_service_ready_candidate_dominates():
    strong = row("strong")
    weak = row("weak")
    for field in MAX_AXES:
        strong[field] = 1
    for field in MIN_AXES:
        weak[field] = 1
    assert dominates(strong, weak)
    assert [r["scenario_id"] for r in pareto([weak, strong])] == ["strong"]


def test_cycle_runtime_tradeoff_is_preserved_without_weighting():
    access = row("access")
    operations = row("operations")
    access["public_population_coverage_share_10min"] = 0.9
    access[CYCLE_RUNTIME_AXIS] = 100
    operations["public_population_coverage_share_10min"] = 0.8
    operations[CYCLE_RUNTIME_AXIS] = 80
    assert not dominates(access, operations)
    assert not dominates(operations, access)
