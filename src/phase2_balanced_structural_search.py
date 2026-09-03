"""Family-balanced deterministic structural search for Phase 2.

The original structural enumerator is useful for small anchor sets, but a global
`max_scenarios` can truncate before later topology families are reached when the
anchor universe is large. This module fixes that search-design bias without
adding a decision score or random sampling.

Search coverage rule:
- every feasible topology family receives an explicit equal-family allocation;
- the finite single-radial family may exhaust below that allocation and its
  unused capacity is redistributed equally to the other families;
- within a family, anchors are traversed in a stable SHA-256 ring and tuple
  lengths are round-robin interleaved, so the first quota is not simply the
  lexicographically earliest geography;
- all emitted routes still require real directed legs in the supplied matrix.

This is a search-space coverage mechanism, not a preference weight and not a
claim that topology families are equally valuable.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from itertools import combinations
from math import ceil, sqrt
from typing import Iterable, Iterator, Mapping, Sequence

from src.phase2_optimizer_core import (
    ReducedPathMatrix,
    RoutePattern,
    ScenarioSkeleton,
    TopologyFamily,
)


FAMILIES: tuple[TopologyFamily, ...] = tuple(TopologyFamily)


def _stable_anchor_order(anchors: Sequence[str]) -> list[str]:
    return sorted(
        {anchor for anchor in anchors if anchor},
        key=lambda value: (sha256(value.encode("utf-8")).hexdigest(), value),
    )


def _valid_route(matrix: ReducedPathMatrix, anchors: Sequence[str]) -> bool:
    return len(anchors) >= 2 and all(
        matrix.has_leg(origin, destination)
        for origin, destination in zip(anchors[:-1], anchors[1:])
    )


def _ring_tuples(anchors: Sequence[str], width: int) -> Iterator[tuple[str, ...]]:
    """Yield stable, spatially agnostic tuples while spreading starts and offsets.

    For width=2, every directed ordered pair appears exactly once. For wider
    tuples, steps whose cycle is too short are simply skipped. This avoids
    factorial materialisation while ensuring every anchor appears repeatedly in
    every tuple position as capacity grows.
    """
    ordered = _stable_anchor_order(anchors)
    n = len(ordered)
    if width <= 0 or width > n:
        return
    seen: set[tuple[str, ...]] = set()
    for step in range(1, n):
        for start in range(n):
            item = tuple(ordered[(start + position * step) % n] for position in range(width))
            if len(set(item)) != width or item in seen:
                continue
            seen.add(item)
            yield item


def _round_robin(iterators: Sequence[Iterator[tuple[str, ...]]]) -> Iterator[tuple[str, ...]]:
    active = list(iterators)
    while active:
        next_active: list[Iterator[tuple[str, ...]]] = []
        for iterator in active:
            try:
                yield next(iterator)
                next_active.append(iterator)
            except StopIteration:
                continue
        active = next_active


def _loop_anchor_sequences(
    hub: str,
    anchors: Sequence[str],
    matrix: ReducedPathMatrix,
    max_intermediate_anchors: int,
) -> Iterator[tuple[str, ...]]:
    max_width = min(max_intermediate_anchors, len(anchors))
    if max_width < 2:
        return
    iterators = [_ring_tuples(anchors, width) for width in range(2, max_width + 1)]
    for middle in _round_robin(iterators):
        route = (hub, *middle, hub)
        if _valid_route(matrix, route):
            yield route


def _valid_radials(hub: str, anchors: Sequence[str], matrix: ReducedPathMatrix) -> list[RoutePattern]:
    rows: list[RoutePattern] = []
    for anchor in _stable_anchor_order(anchors):
        route = (hub, anchor, hub)
        if _valid_route(matrix, route):
            rows.append(RoutePattern(route))
    return rows


def _emit_unique(
    iterator: Iterable[ScenarioSkeleton],
    *,
    family: TopologyFamily,
    target: int,
) -> tuple[list[ScenarioSkeleton], bool]:
    if target <= 0:
        return [], False
    rows: list[ScenarioSkeleton] = []
    seen: set[str] = set()
    exhausted = True
    for scenario in iterator:
        if scenario.family != family:
            raise ValueError(f"Family generator emitted {scenario.family} for {family}")
        sid = scenario.scenario_id
        if sid in seen:
            continue
        seen.add(sid)
        rows.append(scenario)
        if len(rows) >= target:
            exhausted = False
            break
    return rows, exhausted


def _single_radial_scenarios(radials: Sequence[RoutePattern]) -> Iterator[ScenarioSkeleton]:
    for radial in radials:
        yield ScenarioSkeleton(TopologyFamily.MULTIPLE_SHORT_RADIALS, (radial,))


def _paired_radial_scenarios(
    *,
    family: TopologyFamily,
    hub: str,
    anchors: Sequence[str],
    matrix: ReducedPathMatrix,
) -> Iterator[ScenarioSkeleton]:
    for left, right in _ring_tuples(anchors, 2):
        lroute = (hub, left, hub)
        rroute = (hub, right, hub)
        if not _valid_route(matrix, lroute) or not _valid_route(matrix, rroute):
            continue
        yield ScenarioSkeleton(
            family,
            (RoutePattern(lroute), RoutePattern(rroute)),
        )


def _single_loop_scenarios(
    *,
    family: TopologyFamily,
    hub: str,
    anchors: Sequence[str],
    matrix: ReducedPathMatrix,
    max_intermediate_anchors: int,
) -> Iterator[ScenarioSkeleton]:
    for route in _loop_anchor_sequences(hub, anchors, matrix, max_intermediate_anchors):
        yield ScenarioSkeleton(family, (RoutePattern(route),))


def _bidirectional_loop_scenarios(
    *,
    hub: str,
    anchors: Sequence[str],
    matrix: ReducedPathMatrix,
    max_intermediate_anchors: int,
) -> Iterator[ScenarioSkeleton]:
    for route in _loop_anchor_sequences(hub, anchors, matrix, max_intermediate_anchors):
        middle = route[1:-1]
        reverse = (hub, *reversed(middle), hub)
        if route >= reverse or not _valid_route(matrix, reverse):
            continue
        yield ScenarioSkeleton(
            TopologyFamily.BIDIRECTIONAL_LOOP_PAIR,
            (RoutePattern(route), RoutePattern(reverse)),
        )


def _paired_loop_scenarios(
    *,
    family: TopologyFamily,
    hub: str,
    anchors: Sequence[str],
    matrix: ReducedPathMatrix,
    max_intermediate_anchors: int,
    target_hint: int,
) -> Iterator[ScenarioSkeleton]:
    # A pool proportional to sqrt(target) supplies O(target) loop pairs without
    # factorially materialising the full loop universe. The multiplier only
    # provides search diversity and is not a geographic/service parameter.
    pool_goal = max(4, 4 * ceil(sqrt(max(1, target_hint))))
    pool: list[RoutePattern] = []
    for route in _loop_anchor_sequences(hub, anchors, matrix, max_intermediate_anchors):
        pool.append(RoutePattern(route))
        if len(pool) >= pool_goal:
            break
    pool = sorted(
        pool,
        key=lambda pattern: (
            sha256("\0".join(pattern.anchors).encode("utf-8")).hexdigest(),
            pattern.anchors,
        ),
    )
    for left, right in combinations(pool, 2):
        if set(left.anchors[1:-1]) & set(right.anchors[1:-1]):
            continue
        yield ScenarioSkeleton(family, (left, right))


def _trunk_branch_scenarios(
    *,
    family: TopologyFamily,
    hub: str,
    anchors: Sequence[str],
    matrix: ReducedPathMatrix,
) -> Iterator[ScenarioSkeleton]:
    for trunk, branch_a, branch_b in _ring_tuples(anchors, 3):
        left = (hub, trunk, branch_a)
        right = (hub, trunk, branch_b)
        if not _valid_route(matrix, left) or not _valid_route(matrix, right):
            continue
        yield ScenarioSkeleton(family, (RoutePattern(left), RoutePattern(right)))


def _scheduled_extension_scenarios(
    *,
    hub: str,
    anchors: Sequence[str],
    matrix: ReducedPathMatrix,
) -> Iterator[ScenarioSkeleton]:
    for outer, extension in _ring_tuples(anchors, 2):
        base = (hub, outer, hub)
        extended = (hub, outer, extension, outer, hub)
        if not _valid_route(matrix, base) or not _valid_route(matrix, extended):
            continue
        yield ScenarioSkeleton(
            TopologyFamily.SCHEDULED_EXTENSIONS,
            (RoutePattern(base),),
            optional_extensions=(RoutePattern(extended),),
        )


def _family_generator(
    family: TopologyFamily,
    *,
    hub: str,
    anchors: Sequence[str],
    matrix: ReducedPathMatrix,
    max_intermediate_anchors: int,
    target_hint: int,
    radials: Sequence[RoutePattern],
) -> Iterable[ScenarioSkeleton]:
    if family == TopologyFamily.MULTIPLE_SHORT_RADIALS:
        return _single_radial_scenarios(radials)
    if family in {TopologyFamily.TWO_RADIAL_FEEDERS, TopologyFamily.HYBRID_INTERLINED}:
        return _paired_radial_scenarios(
            family=family, hub=hub, anchors=anchors, matrix=matrix
        )
    if family in {TopologyFamily.SINGLE_COMPACT_LOOP, TopologyFamily.BLANK_SLATE}:
        return _single_loop_scenarios(
            family=family,
            hub=hub,
            anchors=anchors,
            matrix=matrix,
            max_intermediate_anchors=max_intermediate_anchors,
        )
    if family == TopologyFamily.BIDIRECTIONAL_LOOP_PAIR:
        return _bidirectional_loop_scenarios(
            hub=hub,
            anchors=anchors,
            matrix=matrix,
            max_intermediate_anchors=max_intermediate_anchors,
        )
    if family in {TopologyFamily.TWO_INDEPENDENT_LOOPS, TopologyFamily.INTERLINED_FIGURE8}:
        return _paired_loop_scenarios(
            family=family,
            hub=hub,
            anchors=anchors,
            matrix=matrix,
            max_intermediate_anchors=max_intermediate_anchors,
            target_hint=target_hint,
        )
    if family in {TopologyFamily.TRUNK_BRANCHES, TopologyFamily.SHORT_TURN_OVERLAY}:
        return _trunk_branch_scenarios(
            family=family, hub=hub, anchors=anchors, matrix=matrix
        )
    if family == TopologyFamily.SCHEDULED_EXTENSIONS:
        return _scheduled_extension_scenarios(hub=hub, anchors=anchors, matrix=matrix)
    raise ValueError(f"Unsupported topology family: {family}")


@dataclass(frozen=True)
class BalancedSearchResult:
    scenarios: tuple[ScenarioSkeleton, ...]
    family_targets: Mapping[str, int]
    family_counts: Mapping[str, int]
    exhausted_families: tuple[str, ...]
    valid_radial_count: int
    allocation_rule: str = "EQUAL_FAMILY_AFTER_FINITE_SINGLE_RADIAL_CAPACITY"


def allocate_family_targets(*, max_scenarios: int, valid_radial_count: int) -> dict[TopologyFamily, int]:
    if max_scenarios < len(FAMILIES):
        raise ValueError("max_scenarios must permit at least one slot per topology family")
    if valid_radial_count <= 0:
        raise ValueError("At least one valid hub out-and-back radial is required")

    equal_share = max_scenarios // len(FAMILIES)
    radial_target = min(valid_radial_count, equal_share)
    other_families = [f for f in FAMILIES if f != TopologyFamily.MULTIPLE_SHORT_RADIALS]
    remaining = max_scenarios - radial_target
    base = remaining // len(other_families)
    remainder = remaining % len(other_families)
    targets = {TopologyFamily.MULTIPLE_SHORT_RADIALS: radial_target}
    for index, family in enumerate(sorted(other_families, key=lambda f: f.value)):
        targets[family] = base + (1 if index < remainder else 0)
    if sum(targets.values()) != max_scenarios:
        raise AssertionError("Balanced family allocation did not conserve max_scenarios")
    return targets


def generate_balanced_structural_scenarios(
    *,
    hub: str,
    anchors: Sequence[str],
    matrix: ReducedPathMatrix,
    max_scenarios: int,
    max_loop_intermediate_anchors: int = 4,
) -> BalancedSearchResult:
    """Generate a deterministic, family-balanced structural catalog.

    `max_scenarios` is a search-computation budget, not a service budget. No
    scenario is ranked here. The only allocation principle is equal structural
    coverage across topology families after the inherently finite one-radial
    family has used its available capacity.
    """
    if not hub:
        raise ValueError("hub is required")
    unique_anchors = [anchor for anchor in _stable_anchor_order(anchors) if anchor != hub]
    if len(unique_anchors) < 3:
        raise ValueError("Balanced search requires at least three non-hub anchors")
    if max_loop_intermediate_anchors < 2:
        raise ValueError("max_loop_intermediate_anchors must be at least 2")

    radials = _valid_radials(hub, unique_anchors, matrix)
    targets = allocate_family_targets(
        max_scenarios=max_scenarios,
        valid_radial_count=len(radials),
    )

    all_rows: list[ScenarioSkeleton] = []
    family_counts: dict[str, int] = {}
    exhausted: list[str] = []
    global_ids: set[str] = set()
    for family in sorted(FAMILIES, key=lambda f: f.value):
        target = targets[family]
        generated, was_exhausted = _emit_unique(
            _family_generator(
                family,
                hub=hub,
                anchors=unique_anchors,
                matrix=matrix,
                max_intermediate_anchors=max_loop_intermediate_anchors,
                target_hint=target,
                radials=radials,
            ),
            family=family,
            target=target,
        )
        for scenario in generated:
            if scenario.scenario_id in global_ids:
                raise AssertionError("Scenario ID collided across topology families")
            scenario.validate_paths(matrix)
            global_ids.add(scenario.scenario_id)
        all_rows.extend(generated)
        family_counts[family.value] = len(generated)
        if was_exhausted and len(generated) < target:
            exhausted.append(family.value)

    all_rows = sorted(all_rows, key=lambda row: (row.family.value, row.scenario_id))
    return BalancedSearchResult(
        scenarios=tuple(all_rows),
        family_targets={family.value: targets[family] for family in sorted(FAMILIES, key=lambda f: f.value)},
        family_counts=dict(sorted(family_counts.items())),
        exhausted_families=tuple(sorted(exhausted)),
        valid_radial_count=len(radials),
    )
