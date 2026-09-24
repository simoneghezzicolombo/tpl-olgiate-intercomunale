"""Derive direct S8 destination direction from official GTFS stop sequences.

No geography heuristic is used. A destination stop is assigned to MILANO or
LECCO only when it appears downstream of Olgiate-Calco-Brivio on at least one
active S8 trip whose direction has already been derived from the matching
validated GTFS snapshot.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Mapping, Sequence

from src.phase2_s8_interchange import STATION_ID, S8ModelError


DIRECTIONS = {"MILANO", "LECCO"}


def opposite_direction(direction: str) -> str:
    direction = str(direction).strip().upper()
    if direction == "MILANO":
        return "LECCO"
    if direction == "LECCO":
        return "MILANO"
    raise S8ModelError(f"Unsupported S8 direction {direction!r}")


def direct_stop_direction_map(
    active_events: Sequence[Mapping[str, object]],
    stop_times: Sequence[Mapping[str, str]],
) -> dict[str, str]:
    """Map every downstream direct stop to its S8 direction at the hub."""
    trip_direction: dict[str, str] = {}
    for event in active_events:
        trip_id = str(event.get("trip_id", "")).strip()
        direction = str(event.get("direction", "")).strip().upper()
        if not trip_id or direction not in DIRECTIONS:
            raise S8ModelError("Active S8 events require trip_id and validated direction")
        if trip_id in trip_direction and trip_direction[trip_id] != direction:
            raise S8ModelError(f"Conflicting directions for active S8 trip {trip_id}")
        trip_direction[trip_id] = direction
    if not trip_direction:
        raise S8ModelError("No active S8 trips supplied")

    grouped: dict[str, list[Mapping[str, str]]] = defaultdict(list)
    for row in stop_times:
        trip_id = str(row.get("trip_id", "")).strip()
        if trip_id in trip_direction:
            grouped[trip_id].append(row)

    stop_directions: dict[str, set[str]] = defaultdict(set)
    for trip_id, direction in trip_direction.items():
        rows = grouped.get(trip_id, [])
        if not rows:
            raise S8ModelError(f"No stop_times for active S8 trip {trip_id}")
        try:
            ordered = sorted(rows, key=lambda row: int(row["stop_sequence"]))
        except (KeyError, TypeError, ValueError) as exc:
            raise S8ModelError(f"Invalid stop_sequence for active S8 trip {trip_id}") from exc
        positions = [i for i, row in enumerate(ordered) if row.get("stop_id") == STATION_ID]
        if len(positions) != 1:
            raise S8ModelError(f"{trip_id}: expected exactly one {STATION_ID} stop")
        for row in ordered[positions[0] + 1 :]:
            stop_id = str(row.get("stop_id", "")).strip()
            if stop_id:
                stop_directions[stop_id].add(direction)

    result: dict[str, str] = {}
    for stop_id, directions in stop_directions.items():
        if len(directions) != 1:
            raise S8ModelError(
                f"Direct stop {stop_id} appears downstream in conflicting directions: {sorted(directions)}"
            )
        result[stop_id] = next(iter(directions))
    if not result:
        raise S8ModelError("No direct downstream S8 stops derived")
    return dict(sorted(result.items()))


def municipality_direction_map(
    station_rows: Sequence[Mapping[str, str]],
    stop_directions: Mapping[str, str],
) -> dict[str, str]:
    """Map municipality code to one unique direct S8 direction."""
    by_code: dict[str, set[str]] = defaultdict(set)
    for row in station_rows:
        stop_id = str(row.get("stop_id", "")).strip()
        code = str(row.get("procom", "")).strip()
        if stop_id == STATION_ID:
            continue
        direction = stop_directions.get(stop_id)
        if direction is None:
            continue
        if direction not in DIRECTIONS:
            raise S8ModelError(f"Invalid direction {direction!r} for {stop_id}")
        if not code:
            raise S8ModelError(f"S8 station {stop_id} lacks municipality code")
        by_code[code].add(direction)

    result: dict[str, str] = {}
    for code, directions in by_code.items():
        if len(directions) != 1:
            raise S8ModelError(
                f"Municipality {code} maps to conflicting direct S8 directions: {sorted(directions)}"
            )
        result[code] = next(iter(directions))
    if not result:
        raise S8ModelError("No direct S8 municipality directions derived")
    return dict(sorted(result.items()))
