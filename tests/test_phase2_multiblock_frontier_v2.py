from scripts.phase2_build_multiblock_frontier_v2 import (
    MAX_AXES,
    MIN_AXES,
    TERRITORIAL_CORE_AXIS,
    TERRITORIAL_EXTERNAL_AXIS,
    dominates,
    pareto,
)


def base_row(scenario_id: str) -> dict[str, object]:
    row: dict[str, object] = {"scenario_id": scenario_id}
    for field in MAX_AXES:
        row[field] = 0.0
    for field in MIN_AXES:
        row[field] = 0.0
    return row


def test_territorial_axes_are_separate_and_not_collapsed():
    assert TERRITORIAL_CORE_AXIS in MAX_AXES
    assert TERRITORIAL_EXTERNAL_AXIS in MAX_AXES
    assert TERRITORIAL_CORE_AXIS != TERRITORIAL_EXTERNAL_AXIS


def test_old_dominance_can_disappear_when_territorial_axis_is_added():
    old_better = base_row("A")
    territorial_better = base_row("B")
    old_better["public_population_coverage_share_10min"] = 0.8
    territorial_better["public_population_coverage_share_10min"] = 0.7
    territorial_better[TERRITORIAL_CORE_AXIS] = 500

    # A would dominate B if the territorial dimension did not exist, but under
    # the multiblock contract neither dominates the other.
    assert not dominates(old_better, territorial_better)
    assert not dominates(territorial_better, old_better)
    assert {r["scenario_id"] for r in pareto([old_better, territorial_better])} == {"A", "B"}


def test_componentwise_better_row_dominates():
    strong = base_row("strong")
    weak = base_row("weak")
    for field in MAX_AXES:
        strong[field] = 1.0
    for field in MIN_AXES:
        strong[field] = 0.0
        weak[field] = 1.0
    assert dominates(strong, weak)
    assert [r["scenario_id"] for r in pareto([weak, strong])] == ["strong"]


def test_core_external_tradeoff_remains_nondominated_without_weights():
    core = base_row("core")
    external = base_row("external")
    core[TERRITORIAL_CORE_AXIS] = 1000
    core[TERRITORIAL_EXTERNAL_AXIS] = 300
    external[TERRITORIAL_CORE_AXIS] = 900
    external[TERRITORIAL_EXTERNAL_AXIS] = 500
    assert not dominates(core, external)
    assert not dominates(external, core)
