"""Historical scheduled-speed plausibility audit for RT031 components."""
from __future__ import annotations

from collections import defaultdict
from decimal import Decimal


def gtfs_time_seconds(value: str) -> int:
    parts = value.strip().split(":")
    if len(parts) != 3:
        raise ValueError("GTFS time must be HH:MM:SS")
    hours, minutes, seconds = map(int, parts)
    if hours < 0 or not 0 <= minutes < 60 or not 0 <= seconds < 60:
        raise ValueError("invalid GTFS time")
    return hours * 3600 + minutes * 60 + seconds


def decimal_median(values):
    ordered = sorted(values)
    if not ordered:
        raise ValueError("median requires values")
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / Decimal(2)


def historical_scheduled_metrics(trips, stop_times, *, route_ids=("D184", "D185"),
                                 comparable_min_distance_km=Decimal("8")):
    selected = {row["trip_id"]: row for row in trips
                if row["route_id"] in route_ids}
    grouped = defaultdict(list)
    for row in stop_times:
        if row["trip_id"] in selected:
            grouped[row["trip_id"]].append(row)
    if set(grouped) != set(selected):
        raise ValueError("selected GTFS trips lost stop-time evidence")
    dwell_seconds = []
    trip_rows = []
    for trip_id, rows in grouped.items():
        rows.sort(key=lambda row: int(row["stop_sequence"]))
        for row in rows:
            dwell = gtfs_time_seconds(row["departure_time"]) - gtfs_time_seconds(row["arrival_time"])
            if dwell < 0:
                raise ValueError("negative scheduled dwell")
            dwell_seconds.append(dwell)
        elapsed = gtfs_time_seconds(rows[-1]["arrival_time"]) - gtfs_time_seconds(rows[0]["departure_time"])
        distance = Decimal(rows[-1]["shape_dist_traveled"]) - Decimal(rows[0]["shape_dist_traveled"])
        if elapsed <= 0 or distance <= 0:
            raise ValueError("non-positive scheduled trip metric")
        speed = distance * Decimal(3600) / Decimal(elapsed)
        trip_rows.append({
            "trip_id": trip_id,
            "route_id": selected[trip_id]["route_id"],
            "distance_km": str(distance),
            "scheduled_runtime_seconds": elapsed,
            "scheduled_speed_kmh": str(speed),
        })
    comparable = [Decimal(row["scheduled_speed_kmh"]) for row in trip_rows
                  if Decimal(row["distance_km"]) >= comparable_min_distance_km]
    return {
        "route_ids": list(route_ids),
        "trip_count": len(trip_rows),
        "stop_time_occurrence_count": len(dwell_seconds),
        "positive_scheduled_dwell_occurrence_count": sum(v > 0 for v in dwell_seconds),
        "all_arrival_departure_pairs_equal": all(v == 0 for v in dwell_seconds),
        "dwell_calibration_available": any(v > 0 for v in dwell_seconds),
        "comparable_min_distance_km": str(comparable_min_distance_km),
        "comparable_trip_count": len(comparable),
        "comparable_scheduled_speed_kmh": {
            "minimum": str(min(comparable)),
            "median": str(decimal_median(comparable)),
            "maximum": str(max(comparable)),
        },
        "trips": sorted(trip_rows, key=lambda row: row["trip_id"]),
    }


def candidate_component_speed_audit(profiles, historical):
    low = Decimal(historical["comparable_scheduled_speed_kmh"]["minimum"])
    high = Decimal(historical["comparable_scheduled_speed_kmh"]["maximum"])
    rows = []
    for profile in profiles:
        runtime_by_id = {
            row["component_id"]: Decimal(row["running_minutes_source_model_excludes_dwell"])
            for row in profile["operational_source_model_screen"]["components"]}
        components = profile["typed_network"]["payload"]["components"]
        if set(runtime_by_id) != set(components):
            raise ValueError("typed component runtime/distance identity mismatch")
        for component_id, component in components.items():
            distance_km = Decimal(component["traversal_length_m"]) / Decimal(1000)
            runtime = runtime_by_id[component_id]
            speed = distance_km * Decimal(60) / runtime
            rows.append({
                "profile_id": profile["profile_id"],
                "component_id": component_id,
                "distance_km": str(distance_km),
                "source_model_running_minutes_excludes_dwell": str(runtime),
                "source_model_speed_kmh": str(speed),
                "within_historical_comparable_scheduled_speed_envelope": low <= speed <= high,
            })
    return sorted(rows, key=lambda row: (row["profile_id"], row["component_id"]))
