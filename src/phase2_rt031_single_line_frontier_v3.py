"""Combine positive single-walk witnesses without erasing ordered-path identity."""
from __future__ import annotations

from decimal import Decimal
import hashlib


def combine_single_walk_candidates(named_pools, *, hub_stop_id):
    if not hub_stop_id or not named_pools:
        raise ValueError("hub and at least one named pool required")
    paths = {}
    lane_counts = {}
    for lane, pool in named_pools:
        if not lane or lane in lane_counts:
            raise ValueError("unique nonempty discovery lane required")
        if (pool.get("contract") != "RT031_BUDGETED_PHYSICAL_CLOSED_WALK_SEARCH_V3"
                or pool.get("required_root_stop_id") != hub_stop_id
                or pool.get("status") not in (
                    "RESOURCE_LIMIT_INCOMPLETE",
                    "EXHAUSTIVE_WITHIN_DECLARED_PHYSICAL_DOMAIN")):
            raise ValueError("physical single-walk pool contract drift")
        lane_counts[lane] = len(pool.get("candidates", ()))
        for row in pool.get("candidates", ()):
            path = tuple(str(value) for value in row.get("realization_ids", ()))
            stops = tuple(sorted(set(str(value)
                                     for value in row.get("available_stop_ids", ()))))
            distance = Decimal(str(row.get("minimum_found_distance_m", "")))
            if (not path or hub_stop_id not in stops or not distance.is_finite()
                    or distance <= 0):
                raise ValueError("invalid positive hub-rooted single-walk witness")
            previous = paths.get(path)
            signature = (stops, distance)
            if previous is not None and previous["signature"] != signature:
                raise ValueError("same ordered physical path changed semantics")
            if previous is None:
                paths[path] = {"signature": signature, "lanes": {lane}}
            else:
                previous["lanes"].add(lane)
    rows = []
    for path, value in paths.items():
        stops, distance = value["signature"]
        rows.append({
            "candidate_line_id": "SL_" + hashlib.sha256(
                ";".join(path).encode()).hexdigest()[:20],
            "realization_ids": list(path),
            "available_stop_ids": list(stops),
            "minimum_found_distance_m": str(distance),
            "discovery_lanes": sorted(value["lanes"]),
            "physical_closed_walk_count": 1,
            "intended_public_route_identity_count": 1,
        })
    rows.sort(key=lambda row: row["candidate_line_id"])
    return {
        "source_candidate_counts_by_lane": lane_counts,
        "unique_ordered_single_walk_candidate_count": len(rows),
        "candidates": rows,
        "same_stop_union_different_order_collapsed": False,
        "stop_union_is_route_identity": False,
        "single_public_line_required": True,
        "ordered_service_events_bound": False,
        "passenger_service_continuity_certified": False,
        "recognizable_public_line_certified": False,
        "upstream_candidate_domain_complete": all(
            pool.get("exhaustive") is True for _, pool in named_pools),
    }
