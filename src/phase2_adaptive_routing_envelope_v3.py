"""RT-017 adaptive border-neutral road-routing envelope contract V3.

This module is deliberately geographic but municipality-neutral.  It knows only
metric coordinates, nested envelopes and directed-pair routing results.  Municipal
boundaries remain service-accounting inputs elsewhere and are never routing rules.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable, Sequence

import pandas as pd

CONTRACT = "ADAPTIVE_BORDER_NEUTRAL_ROAD_ROUTING_ENVELOPE_V3"
MAX_SNAP_M = 250.0  # inherited validated Gate-D snap ceiling
INITIAL_MARGIN_M = 2.0 * MAX_SNAP_M
GROWTH_FACTOR = 2.0
REQUIRED_CONFIRMING_EXPANSIONS = 2
RUNTIME_TOL_MIN = 1e-9
DISTANCE_TOL_M = 1e-6
BOUNDARY_GUARD_M = MAX_SNAP_M
MATERIAL_RUNTIME_IMPROVEMENT_MIN = 0.05
MATERIAL_DISTANCE_IMPROVEMENT_M = 10.0


@dataclass(frozen=True)
class EnvelopeLevel:
    level: int
    margin_m: float
    min_x: float
    min_y: float
    max_x: float
    max_y: float

    @property
    def bounds(self) -> tuple[float, float, float, float]:
        return (self.min_x, self.min_y, self.max_x, self.max_y)


@dataclass(frozen=True)
class ConvergenceDecision:
    converged: bool
    frozen_level: int | None
    reason: str


def derive_levels(
    points_xy: Sequence[tuple[float, float]],
    *,
    max_levels: int = 7,
    initial_margin_m: float = INITIAL_MARGIN_M,
    growth_factor: float = GROWTH_FACTOR,
) -> list[EnvelopeLevel]:
    """Return deterministic nested rectangular envelopes around routing probes.

    The initial margin is twice the already validated 250 m routing-snap ceiling.
    Each subsequent level doubles the margin.  The sequence therefore has no
    municipality semantics and no hand-selected final buffer.  `max_levels` is a
    fail-closed computational ceiling, not a convergence claim.
    """
    if not points_xy:
        raise ValueError("at least one routing probe is required")
    if max_levels < REQUIRED_CONFIRMING_EXPANSIONS + 1:
        raise ValueError("max_levels must allow two confirming expansions")
    if initial_margin_m <= 0:
        raise ValueError("initial_margin_m must be positive")
    if growth_factor <= 1:
        raise ValueError("growth_factor must be > 1")
    xs = [float(x) for x, _ in points_xy]
    ys = [float(y) for _, y in points_xy]
    if not all(math.isfinite(v) for v in [*xs, *ys]):
        raise ValueError("routing probe coordinates must be finite")
    base = (min(xs), min(ys), max(xs), max(ys))
    levels: list[EnvelopeLevel] = []
    for level in range(max_levels):
        margin = float(initial_margin_m * (growth_factor ** level))
        levels.append(
            EnvelopeLevel(
                level=level,
                margin_m=margin,
                min_x=base[0] - margin,
                min_y=base[1] - margin,
                max_x=base[2] + margin,
                max_y=base[3] + margin,
            )
        )
    return levels


def point_in_bounds(x: float, y: float, bounds: tuple[float, float, float, float]) -> bool:
    min_x, min_y, max_x, max_y = bounds
    return min_x <= float(x) <= max_x and min_y <= float(y) <= max_y


def segment_in_bounds(
    a: tuple[float, float],
    b: tuple[float, float],
    bounds: tuple[float, float, float, float],
) -> bool:
    """Strict acquisition clipping: keep a segment only when both endpoints fit."""
    return point_in_bounds(*a, bounds) and point_in_bounds(*b, bounds)


def boundary_clearance_m(
    points_xy: Iterable[tuple[float, float]],
    bounds: tuple[float, float, float, float],
) -> float:
    min_x, min_y, max_x, max_y = bounds
    clearances = []
    for x, y in points_xy:
        x, y = float(x), float(y)
        if not point_in_bounds(x, y, bounds):
            return -1.0
        clearances.append(min(x - min_x, max_x - x, y - min_y, max_y - y))
    if not clearances:
        return math.inf
    return float(min(clearances))


def compare_pair_results(previous: pd.DataFrame, current: pd.DataFrame) -> dict:
    required = {
        "pair_id",
        "route_found",
        "path_edge_ids",
        "path_geometry_sha256",
        "running_minutes_model",
        "distance_m",
    }
    for frame, label in [(previous, "previous"), (current, "current")]:
        missing = required - set(frame.columns)
        if missing:
            raise ValueError(f"{label} pair results missing {sorted(missing)}")
        if frame["pair_id"].duplicated().any():
            raise ValueError(f"duplicate pair_id in {label} results")

    a = previous.copy().fillna("").set_index("pair_id")
    b = current.copy().fillna("").set_index("pair_id")
    if set(a.index) != set(b.index):
        return {
            "stable": False,
            "pair_universe_equal": False,
            "changed_pair_count": len(set(a.index) ^ set(b.index)),
            "newly_routable_count": 0,
            "lost_route_count": 0,
            "material_improvement_count": 0,
        }

    changed = newly = lost = material = 0
    exact_edge = exact_geometry = 0
    max_runtime_delta = 0.0
    max_distance_delta = 0.0
    for pair_id in sorted(a.index):
        old, new = a.loc[pair_id], b.loc[pair_id]
        old_found = str(old["route_found"]).lower() in {"true", "1", "yes"}
        new_found = str(new["route_found"]).lower() in {"true", "1", "yes"}
        if old_found != new_found:
            changed += 1
            newly += int(new_found)
            lost += int(old_found)
            continue
        if not old_found:
            continue
        old_rt, new_rt = float(old["running_minutes_model"]), float(new["running_minutes_model"])
        old_dist, new_dist = float(old["distance_m"]), float(new["distance_m"])
        rt_delta = abs(new_rt - old_rt)
        dist_delta = abs(new_dist - old_dist)
        max_runtime_delta = max(max_runtime_delta, rt_delta)
        max_distance_delta = max(max_distance_delta, dist_delta)
        edge_same = str(old["path_edge_ids"]) == str(new["path_edge_ids"])
        geometry_same = str(old["path_geometry_sha256"]) == str(new["path_geometry_sha256"])
        exact_edge += int(edge_same)
        exact_geometry += int(geometry_same)
        if (
            not edge_same
            or not geometry_same
            or rt_delta > RUNTIME_TOL_MIN
            or dist_delta > DISTANCE_TOL_M
        ):
            changed += 1
        if (
            old_rt - new_rt >= MATERIAL_RUNTIME_IMPROVEMENT_MIN
            or old_dist - new_dist >= MATERIAL_DISTANCE_IMPROVEMENT_M
        ):
            material += 1

    stable = changed == 0
    return {
        "stable": stable,
        "pair_universe_equal": True,
        "changed_pair_count": int(changed),
        "newly_routable_count": int(newly),
        "lost_route_count": int(lost),
        "material_improvement_count": int(material),
        "exact_edge_sequence_count": int(exact_edge),
        "exact_geometry_digest_count": int(exact_geometry),
        "max_runtime_delta_min": max_runtime_delta,
        "max_distance_delta_m": max_distance_delta,
        "runtime_tolerance_min": RUNTIME_TOL_MIN,
        "distance_tolerance_m": DISTANCE_TOL_M,
    }


def choose_smallest_converged_level(
    level_audits: Sequence[dict],
    transition_audits: Sequence[dict],
    *,
    confirmations: int = REQUIRED_CONFIRMING_EXPANSIONS,
) -> ConvergenceDecision:
    """Freeze the earliest level demonstrated stable by later expansions.

    With the default two confirmations, level k is accepted only after k->k+1 and
    k+1->k+2 are both exactly stable, all directed probe pairs are routable at k,
    and no accepted path at k lies within the inherited 250 m boundary guard.
    """
    if confirmations < 1:
        raise ValueError("confirmations must be >= 1")
    levels = {int(row["level"]): row for row in level_audits}
    transitions = {
        (int(row["from_level"]), int(row["to_level"])): row
        for row in transition_audits
    }
    for k in sorted(levels):
        row = levels[k]
        if not bool(row.get("all_pairs_routable", False)):
            continue
        if int(row.get("boundary_sensitive_pair_count", 1)) != 0:
            continue
        ok = True
        for offset in range(confirmations):
            transition = transitions.get((k + offset, k + offset + 1))
            if transition is None or not bool(transition.get("stable", False)):
                ok = False
                break
        if ok:
            return ConvergenceDecision(True, k, f"STABLE_WITH_{confirmations}_SUCCESSIVE_CONFIRMATIONS")
    return ConvergenceDecision(False, None, "NO_LEVEL_HAS_REQUIRED_STABLE_SUCCESSORS_AND_BOUNDARY_CLEARANCE")
