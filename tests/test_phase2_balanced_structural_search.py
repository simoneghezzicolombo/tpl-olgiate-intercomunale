from __future__ import annotations

from src.phase2_balanced_structural_search import (
    FAMILIES,
    allocate_family_targets,
    generate_balanced_structural_scenarios,
)
from src.phase2_optimizer_core import PathLeg, ReducedPathMatrix, TopologyFamily


def complete_matrix(n: int = 14) -> tuple[list[str], ReducedPathMatrix]:
    anchors = [f"A{i:02d}" for i in range(n)]
    all_nodes = ["H", *anchors]
    legs = []
    for i, origin in enumerate(all_nodes):
        for j, destination in enumerate(all_nodes):
            if origin == destination:
                continue
            # Deliberately asymmetric directed metrics.
            legs.append(
                PathLeg(
                    origin=origin,
                    destination=destination,
                    distance_km=1.0 + i * 0.01 + j * 0.001,
                    runtime_min=3.0 + i * 0.03 + j * 0.002,
                    uncertainty="RESOLVED",
                )
            )
    return anchors, ReducedPathMatrix(legs)


def test_allocation_conserves_budget_and_caps_finite_radials() -> None:
    targets = allocate_family_targets(max_scenarios=100_000, valid_radial_count=220)
    assert sum(targets.values()) == 100_000
    assert targets[TopologyFamily.MULTIPLE_SHORT_RADIALS] == 220
    others = [value for family, value in targets.items() if family != TopologyFamily.MULTIPLE_SHORT_RADIALS]
    assert max(others) - min(others) <= 1


def test_balanced_search_includes_every_family_before_global_cap() -> None:
    anchors, matrix = complete_matrix()
    result = generate_balanced_structural_scenarios(
        hub="H",
        anchors=anchors,
        matrix=matrix,
        max_scenarios=660,
        max_loop_intermediate_anchors=4,
    )
    assert set(result.family_counts) == {family.value for family in FAMILIES}
    assert all(result.family_counts[family.value] > 0 for family in FAMILIES)
    assert result.family_counts[TopologyFamily.MULTIPLE_SHORT_RADIALS.value] == len(anchors)
    assert len({row.scenario_id for row in result.scenarios}) == len(result.scenarios)
    for row in result.scenarios:
        row.validate_paths(matrix)


def test_anchor_input_order_does_not_change_catalog() -> None:
    anchors, matrix = complete_matrix()
    first = generate_balanced_structural_scenarios(
        hub="H", anchors=anchors, matrix=matrix, max_scenarios=440
    )
    second = generate_balanced_structural_scenarios(
        hub="H", anchors=list(reversed(anchors)), matrix=matrix, max_scenarios=440
    )
    assert [row.scenario_id for row in first.scenarios] == [row.scenario_id for row in second.scenarios]
    assert first.family_counts == second.family_counts
    assert first.family_targets == second.family_targets


def test_late_family_cannot_be_starved_by_early_loop_enumeration() -> None:
    anchors, matrix = complete_matrix(18)
    result = generate_balanced_structural_scenarios(
        hub="H",
        anchors=anchors,
        matrix=matrix,
        max_scenarios=550,
        max_loop_intermediate_anchors=4,
    )
    # These were structurally late in the original sequential enumerator.
    assert result.family_counts[TopologyFamily.TRUNK_BRANCHES.value] > 0
    assert result.family_counts[TopologyFamily.SHORT_TURN_OVERLAY.value] > 0
    assert result.family_counts[TopologyFamily.SCHEDULED_EXTENSIONS.value] > 0
    assert result.family_counts[TopologyFamily.INTERLINED_FIGURE8.value] > 0


def test_search_uses_no_topology_preference_score() -> None:
    anchors, matrix = complete_matrix()
    result = generate_balanced_structural_scenarios(
        hub="H", anchors=anchors, matrix=matrix, max_scenarios=330
    )
    assert result.allocation_rule == "EQUAL_FAMILY_AFTER_FINITE_SINGLE_RADIAL_CAPACITY"
    assert sum(result.family_targets.values()) == 330
