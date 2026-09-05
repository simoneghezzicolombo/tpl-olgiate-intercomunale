#!/usr/bin/env python3
"""Build an empirical stop-density benchmark from frozen D184/D185 GTFS patterns.

This is descriptive evidence only. It intentionally does NOT turn the current
network into a mandatory design standard and does not create an arbitrary stop
spacing threshold. Consecutive-stop distance here is geodesic distance between
official GTFS stop coordinates, not routed road distance; it is therefore a
transparent spatial-density benchmark and a lower bound on path distance.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from math import asin, cos, radians, sin, sqrt
from pathlib import Path
from statistics import median


def sha256_path(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371008.8
    p1, p2 = radians(lat1), radians(lat2)
    dphi, dlambda = radians(lat2 - lat1), radians(lon2 - lon1)
    a = sin(dphi / 2) ** 2 + cos(p1) * cos(p2) * sin(dlambda / 2) ** 2
    return 2 * r * asin(sqrt(a))


def percentile(values: list[float], q: float) -> float:
    if not values:
        raise ValueError("Cannot compute percentile of empty values")
    xs = sorted(values)
    if len(xs) == 1:
        return xs[0]
    pos = (len(xs) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(xs) - 1)
    frac = pos - lo
    return xs[lo] * (1 - frac) + xs[hi] * frac


def fmt(x: float) -> str:
    return f"{x:.3f}"


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--patterns", type=Path, required=True)
    p.add_argument("--route-stops", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    args = p.parse_args()

    patterns = read_csv(args.patterns)
    stop_rows = read_csv(args.route_stops)
    stops: dict[tuple[str, str], dict[str, object]] = {}
    for row in stop_rows:
        key = (row["route_short_name"].strip(), row["stop_id"].strip())
        stops[key] = {
            "name": row["stop_name"].strip(),
            "lat": float(row["stop_lat"]),
            "lon": float(row["stop_lon"]),
        }

    pattern_rows: list[dict[str, object]] = []
    segment_rows: list[dict[str, object]] = []
    weighted_segment_distances: list[float] = []
    unweighted_segment_distances: list[float] = []
    weighted_stop_counts: list[int] = []
    route_pattern_counts: dict[str, int] = {}
    route_trip_counts: dict[str, int] = {}

    for index, row in enumerate(patterns, start=1):
        route = row["route_short_name"].strip()
        trip_count = int(row["trip_count"])
        stop_ids = [x.strip() for x in row["stop_ids"].split("|") if x.strip()]
        stop_names = [x.strip() for x in row["stop_names"].split("|")]
        if len(stop_ids) != int(row["stop_count"]):
            raise AssertionError(f"Pattern row {index} stop_count mismatch")
        if len(stop_ids) != len(stop_names):
            raise AssertionError(f"Pattern row {index} stop name/id mismatch")
        if route not in {"D184", "D185"}:
            raise AssertionError(f"Unexpected route {route}")
        missing = [sid for sid in stop_ids if (route, sid) not in stops]
        if missing:
            raise AssertionError(f"Pattern row {index} missing stop coordinates: {missing}")

        distances: list[float] = []
        for seq, (left_id, right_id) in enumerate(zip(stop_ids[:-1], stop_ids[1:]), start=1):
            left, right = stops[(route, left_id)], stops[(route, right_id)]
            distance = haversine_m(left["lat"], left["lon"], right["lat"], right["lon"])
            distances.append(distance)
            unweighted_segment_distances.append(distance)
            weighted_segment_distances.extend([distance] * trip_count)
            segment_rows.append({
                "pattern_index": index,
                "route_short_name": route,
                "pattern_trip_count": trip_count,
                "segment_sequence": seq,
                "from_stop_id": left_id,
                "from_stop_name": left["name"],
                "to_stop_id": right_id,
                "to_stop_name": right["name"],
                "geodesic_distance_m": fmt(distance),
                "distance_semantics": "OFFICIAL_STOP_COORDINATE_GEODESIC_NOT_ROAD_DISTANCE",
            })

        weighted_stop_counts.extend([len(stop_ids)] * trip_count)
        route_pattern_counts[route] = route_pattern_counts.get(route, 0) + 1
        route_trip_counts[route] = route_trip_counts.get(route, 0) + trip_count
        pattern_rows.append({
            "pattern_index": index,
            "route_short_name": route,
            "trip_count": trip_count,
            "stop_count": len(stop_ids),
            "segment_count": max(0, len(stop_ids) - 1),
            "first_stop_name": stop_names[0],
            "last_stop_name": stop_names[-1],
            "contains_olgiate_station": str(any("Olgiate Molgora" in name and "stazione" in name.lower() for name in stop_names)).lower(),
            "median_geodesic_stop_spacing_m": fmt(median(distances)) if distances else "",
            "p90_geodesic_stop_spacing_m": fmt(percentile(distances, .90)) if distances else "",
            "max_geodesic_stop_spacing_m": fmt(max(distances)) if distances else "",
            "stop_ids": "|".join(stop_ids),
            "stop_names": "|".join(stop_names),
        })

    if len(pattern_rows) != 18:
        raise AssertionError(f"Expected 18 frozen D184/D185 patterns, got {len(pattern_rows)}")

    route_summary = []
    for route in ("D184", "D185"):
        pats = [r for r in pattern_rows if r["route_short_name"] == route]
        segs = [float(r["geodesic_distance_m"]) for r in segment_rows if r["route_short_name"] == route]
        weighted = []
        for ptn in pats:
            pidx = ptn["pattern_index"]
            d = [float(r["geodesic_distance_m"]) for r in segment_rows if r["pattern_index"] == pidx]
            weighted.extend(d * int(ptn["trip_count"]))
        route_summary.append({
            "route_short_name": route,
            "distinct_pattern_count": len(pats),
            "represented_trip_count": sum(int(r["trip_count"]) for r in pats),
            "min_pattern_stop_count": min(int(r["stop_count"]) for r in pats),
            "median_pattern_stop_count_unweighted": fmt(median([int(r["stop_count"]) for r in pats])),
            "max_pattern_stop_count": max(int(r["stop_count"]) for r in pats),
            "median_segment_geodesic_m_unweighted": fmt(median(segs)),
            "p75_segment_geodesic_m_unweighted": fmt(percentile(segs, .75)),
            "p90_segment_geodesic_m_unweighted": fmt(percentile(segs, .90)),
            "max_segment_geodesic_m_unweighted": fmt(max(segs)),
            "median_segment_geodesic_m_trip_weighted": fmt(median(weighted)),
            "p90_segment_geodesic_m_trip_weighted": fmt(percentile(weighted, .90)),
        })

    out = args.output_dir
    out.mkdir(parents=True, exist_ok=True)
    for path, rows in [
        (out / "current_stop_spacing_patterns_v3.csv", pattern_rows),
        (out / "current_stop_spacing_segments_v3.csv", segment_rows),
        (out / "current_stop_spacing_route_summary_v3.csv", route_summary),
    ]:
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()), lineterminator="\n")
            writer.writeheader(); writer.writerows(rows)

    validation = {
        "status": "PASS_CURRENT_STOP_SPACING_BENCHMARK_V3",
        "contract": "DESCRIPTIVE_EMPIRICAL_BENCHMARK_NOT_DESIGN_THRESHOLD",
        "source_pattern_count": len(pattern_rows),
        "source_routes": sorted(route_pattern_counts),
        "represented_trip_count": sum(route_trip_counts.values()),
        "route_pattern_counts": route_pattern_counts,
        "route_trip_counts": route_trip_counts,
        "pattern_stop_count": {
            "min": min(int(r["stop_count"]) for r in pattern_rows),
            "median_unweighted": median([int(r["stop_count"]) for r in pattern_rows]),
            "max": max(int(r["stop_count"]) for r in pattern_rows),
            "median_trip_weighted": median(weighted_stop_counts),
        },
        "segment_geodesic_distance_m": {
            "segment_observation_count_unweighted": len(unweighted_segment_distances),
            "median_unweighted": median(unweighted_segment_distances),
            "p75_unweighted": percentile(unweighted_segment_distances, .75),
            "p90_unweighted": percentile(unweighted_segment_distances, .90),
            "max_unweighted": max(unweighted_segment_distances),
            "median_trip_weighted": median(weighted_segment_distances),
            "p75_trip_weighted": percentile(weighted_segment_distances, .75),
            "p90_trip_weighted": percentile(weighted_segment_distances, .90),
            "max_trip_weighted": max(weighted_segment_distances),
        },
        "distance_semantics": "GEODESIC_DISTANCE_BETWEEN_CONSECUTIVE_OFFICIAL_GTFS_STOPS_NOT_ROUTED_ROAD_DISTANCE",
        "design_threshold_selected": False,
        "current_network_declared_optimal": False,
        "purpose": "BENCHMARK_FUTURE_V3_STOP_PATTERN_DENSITY_AND_FLAG_SPARSE_LOCAL_SERVICE",
        "lineage": {
            "patterns": {"path": str(args.patterns), "sha256": sha256_path(args.patterns)},
            "route_stops": {"path": str(args.route_stops), "sha256": sha256_path(args.route_stops)},
        },
    }
    (out / "current_stop_spacing_benchmark_v3_validation.json").write_text(
        json.dumps(validation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(validation, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
