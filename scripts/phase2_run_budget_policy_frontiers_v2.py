#!/usr/bin/env python3
"""Run Budget-Policy Frontiers V2 using the certified monotonic-frontier theorem.

The upstream Service-Ready Frontier V2 is Pareto-optimal on the evidence axes,
closed-cycle distance, closed-cycle runtime and public route count. For a fixed
no-extension service-policy context:

* annual bus-km is a strictly positive scalar multiple of closed-cycle distance;
* fleet lower bound is monotone non-decreasing in closed-cycle runtime and
  public route count;
* closed-cycle runtime and public route count remain explicit minimisation axes.

Therefore two members of the certified Service-Ready Pareto set cannot acquire a
new dominance relation merely by replacing cycle distance with annual bus-km and
adding the derived fleet lower bound. Any budget-feasible subset is already
Pareto under the downstream policy-context axes. Recomputing an O(n^2) Pareto
for every one of the 432 policy×budget contexts is mathematically redundant.

This runner validates that the expected axis contract still holds, substitutes a
deterministic identity-frontier operation and delegates all lineage, feasibility
mask, budget, output and epistemic validation to the canonical builder.
"""
from __future__ import annotations

import sys

from scripts import phase2_build_budget_policy_frontiers_v2 as impl
from scripts.phase2_build_service_ready_frontier_v2 import (
    CYCLE_DISTANCE_AXIS,
    CYCLE_RUNTIME_AXIS,
    MAX_AXES as SERVICE_READY_MAX_AXES,
    MIN_AXES as SERVICE_READY_MIN_AXES,
)


def validate_monotonic_frontier_contract() -> None:
    if tuple(impl.MAX_AXES) != tuple(SERVICE_READY_MAX_AXES):
        raise ValueError("Budget-policy and service-ready maximise axes differ")
    if CYCLE_DISTANCE_AXIS not in SERVICE_READY_MIN_AXES:
        raise ValueError("Service-ready frontier lost primitive cycle-distance axis")
    if CYCLE_RUNTIME_AXIS not in SERVICE_READY_MIN_AXES or CYCLE_RUNTIME_AXIS not in impl.MIN_AXES:
        raise ValueError("Cycle runtime must remain an explicit minimisation axis")
    if "public_route_count" not in SERVICE_READY_MIN_AXES or "public_route_count" not in impl.MIN_AXES:
        raise ValueError("Public route count must remain an explicit minimisation axis")
    if impl.ANNUAL_KM_AXIS not in impl.MIN_AXES or impl.FLEET_AXIS not in impl.MIN_AXES:
        raise ValueError("Derived policy resource axes are missing")
    service_ready_without_distance = tuple(
        field for field in SERVICE_READY_MIN_AXES if field != CYCLE_DISTANCE_AXIS
    )
    downstream_primitive_axes = tuple(
        field for field in impl.MIN_AXES
        if field not in (impl.ANNUAL_KM_AXIS, impl.FLEET_AXIS)
    )
    if downstream_primitive_axes != service_ready_without_distance:
        raise ValueError(
            "Budget-policy primitive axes changed; monotonic subset theorem no longer applies"
        )


def certified_budget_subset_frontier(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    """Return the already-Pareto budget-feasible subset deterministically."""
    return sorted(rows, key=lambda row: str(row["scenario_id"]))


def main() -> int:
    validate_monotonic_frontier_contract()
    impl.pareto = certified_budget_subset_frontier
    return impl.main()


if __name__ == "__main__":
    raise SystemExit(main())
