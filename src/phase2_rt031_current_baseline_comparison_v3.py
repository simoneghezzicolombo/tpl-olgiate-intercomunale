"""Fail-closed comparison of RT031 potential access with a current structural subset.

Only exact official source identifiers may bridge Current-Service V4 physical
clusters to the RT028 stop universe.  This module deliberately has no geographic,
name-similarity or nearest-neighbour fallback.
"""
from __future__ import annotations

from fractions import Fraction
import json


DIMENSIONS = (
    "potential_core_share_5min",
    "potential_core_share_8min",
    "potential_core_share_10min",
    "potential_worst_municipality_share_5min",
    "potential_worst_municipality_share_8min",
    "potential_worst_municipality_share_10min",
)


def _tokens(value: str, separator: str) -> tuple[str, ...]:
    return tuple(x.strip() for x in str(value).split(separator) if x.strip())


def exact_current_stop_subset(v4_clusters, final_stops) -> dict:
    """Map V4 route stops to RT028 stop places by shared official ID only."""
    member_owner: dict[str, str] = {}
    for row in v4_clusters:
        cluster = str(row.get("physical_stop_cluster_id", "")).strip()
        routes = set(_tokens(row.get("routes", ""), ";"))
        if not cluster or not routes or not routes <= {"D184", "D185"}:
            raise ValueError("V4 cluster requires D184/D185 identity and routes")
        for member in _tokens(row.get("member_stop_ids", ""), ";"):
            if member in member_owner and member_owner[member] != cluster:
                raise ValueError("official V4 stop ID belongs to multiple clusters")
            member_owner[member] = cluster
    if not member_owner:
        raise ValueError("empty V4 official stop universe")

    matched: list[dict] = []
    stop_places: set[str] = set()
    for row in final_stops:
        stop_place = str(row.get("stop_place_id", "")).strip()
        if str(row.get("service_class", "")).strip() != "CONVENTIONAL_TPL":
            continue
        native = set(_tokens(row.get("source_native_ids", ""), "|"))
        overlap = sorted(native & member_owner.keys())
        clusters = sorted({member_owner[x] for x in overlap})
        if len(clusters) > 1:
            raise ValueError("one RT028 stop place bridges multiple V4 physical clusters")
        if overlap:
            if not stop_place or stop_place in stop_places:
                raise ValueError("missing/duplicate mapped RT028 stop place")
            stop_places.add(stop_place)
            matched.append({"stop_place_id": stop_place,
                            "official_source_ids": overlap,
                            "v4_physical_stop_cluster_id": clusters[0]})
    if not matched:
        raise ValueError("no exact official-ID bridge to RT028")
    matched.sort(key=lambda x: x["stop_place_id"])
    return {
        "mapped_stop_place_ids": [x["stop_place_id"] for x in matched],
        "mapping_rows": matched,
        "v4_official_stop_id_count": len(member_owner),
        "mapped_v4_physical_cluster_count": len({x["v4_physical_stop_cluster_id"] for x in matched}),
        "mapping_method": "EXACT_SOURCE_NATIVE_ID_INTERSECTION_ONLY",
    }


def parse_candidate_vector(row: dict) -> tuple[Fraction, ...]:
    try:
        values = json.loads(row["exact_threshold_ratios"])
        vector = tuple(Fraction(x) for x in values)
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError("invalid exact candidate threshold vector") from exc
    if len(vector) != len(DIMENSIONS) or any(x < 0 or x > 1 for x in vector):
        raise ValueError("candidate threshold vector must contain six shares")
    return vector


def compare_with_structural_subset(candidate_rows, baseline_vector) -> dict:
    """Exact componentwise audit; no score, tolerance or selection is created."""
    baseline = tuple(Fraction(x) for x in baseline_vector)
    if len(baseline) != len(DIMENSIONS) or any(x < 0 or x > 1 for x in baseline):
        raise ValueError("baseline vector must contain six shares")
    rows = list(candidate_rows)
    if not rows:
        raise ValueError("candidate universe is empty")
    vectors = [parse_candidate_vector(row) for row in rows]
    maxima = tuple(max(v[i] for v in vectors) for i in range(len(DIMENSIONS)))
    candidate_no_worse_all = [i for i, v in enumerate(vectors)
                              if all(x >= y for x, y in zip(v, baseline))]
    candidate_strictly_broad = [i for i in candidate_no_worse_all
                                if any(x > y for x, y in zip(vectors[i], baseline))]
    baseline_no_worse_all = [i for i, v in enumerate(vectors)
                             if all(y >= x for x, y in zip(v, baseline))]
    return {
        "candidate_count": len(rows),
        "candidate_componentwise_maxima": maxima,
        "candidate_no_worse_than_baseline_all_six_count": len(candidate_no_worse_all),
        "candidate_strictly_broadly_superior_count": len(candidate_strictly_broad),
        "baseline_no_worse_than_candidate_all_six_count": len(baseline_no_worse_all),
        "broad_replacement_case_established": bool(candidate_strictly_broad),
        "status": ("BROAD_REPLACEMENT_CASE_EXISTS_IN_SUPPLIED_POOL"
                   if candidate_strictly_broad else
                   "NO_BROAD_ACCESS_REPLACEMENT_CASE_IN_SUPPLIED_POOL"),
    }
