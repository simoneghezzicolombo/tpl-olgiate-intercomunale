"""Fail-closed fixed-epoch Overpass acquisition for RT-017.

A single Overpass backend is used for every tiled acquisition in one territorial
run. The first backend that can return all four tiles without internal element
conflicts is locked for the remainder of that run. Once locked, backend failure
is fatal rather than silently mixing historical replicas across envelope levels.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Callable, Sequence

import requests


def canonical_json_bytes(value: object) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        + "\n"
    ).encode("utf-8")


def tiles4(
    bbox: tuple[float, float, float, float]
) -> list[tuple[float, float, float, float]]:
    south, west, north, east = bbox
    mid_lat = (south + north) / 2.0
    mid_lon = (west + east) / 2.0
    return [
        (south, west, mid_lat, mid_lon),
        (south, mid_lon, mid_lat, east),
        (mid_lat, west, north, mid_lon),
        (mid_lat, mid_lon, north, east),
    ]


def build_query(
    tile: tuple[float, float, float, float], snapshot_timestamp: str
) -> str:
    south, west, north, east = tile
    return f'''[out:json][timeout:180][date:"{snapshot_timestamp}"];
(
  way["highway"]({south:.8f},{west:.8f},{north:.8f},{east:.8f});
  relation["type"="restriction"]({south:.8f},{west:.8f},{north:.8f},{east:.8f});
);
(._;>;);
out meta;'''


def merge_consistent_tiles(payloads: Sequence[dict]) -> list[dict]:
    """Merge tiled payloads, rejecting conflicting versions of the same OSM object."""
    merged: dict[tuple[str, int], dict] = {}
    for payload in payloads:
        for element in payload.get("elements", []):
            key = (str(element.get("type")), int(element.get("id")))
            previous = merged.get(key)
            if (
                previous is not None
                and canonical_json_bytes(previous) != canonical_json_bytes(element)
            ):
                raise AssertionError(
                    f"conflicting OSM element versions inside one backend snapshot: {key}"
                )
            merged[key] = element
    type_order = {"node": 0, "way": 1, "relation": 2}
    return sorted(
        merged.values(),
        key=lambda element: (
            type_order.get(str(element.get("type")), 9),
            int(element.get("id")),
        ),
    )


@dataclass
class HistoricalOverpassLevelAcquirer:
    endpoints: Sequence[str]
    snapshot_timestamp: str
    user_agent: str
    attempts_per_tile: int = 2
    request_timeout_s: int = 210
    retry_sleep_s: float = 1.0
    post: Callable = requests.post
    sleep: Callable[[float], None] = time.sleep
    locked_endpoint: str | None = field(default=None, init=False)

    def _query_tile_from_endpoint(
        self,
        endpoint: str,
        tile: tuple[float, float, float, float],
    ) -> dict:
        query = build_query(tile, self.snapshot_timestamp)
        errors: list[str] = []
        for attempt in range(self.attempts_per_tile):
            try:
                response = self.post(
                    endpoint,
                    data={"data": query},
                    headers={"User-Agent": self.user_agent},
                    timeout=self.request_timeout_s,
                )
                response.raise_for_status()
                payload = response.json()
                if not payload.get("elements"):
                    raise ValueError("empty historical Overpass response")
                return payload
            except Exception as exc:
                errors.append(f"attempt={attempt + 1}:{type(exc).__name__}:{exc}")
                if attempt + 1 < self.attempts_per_tile:
                    self.sleep(self.retry_sleep_s)
        raise RuntimeError(
            f"historical Overpass tile acquisition failed at {endpoint}: "
            + " | ".join(errors)
        )

    def _acquire_all_tiles_from_endpoint(
        self,
        endpoint: str,
        bbox: tuple[float, float, float, float],
    ) -> dict:
        payloads = [
            self._query_tile_from_endpoint(endpoint, tile)
            for tile in tiles4(bbox)
        ]
        elements = merge_consistent_tiles(payloads)
        return {
            "version": 0.6,
            "generator": "RT-017 fixed-epoch single-backend tiled Overpass canonical merge",
            "snapshot_timestamp": self.snapshot_timestamp,
            "elements": elements,
        }

    def acquire_level_snapshot(
        self,
        bbox: tuple[float, float, float, float],
    ) -> tuple[dict, list[str]]:
        """Acquire one envelope level without ever mixing Overpass backends.

        Before a backend is locked, complete four-tile acquisition is attempted on
        each backend in deterministic order. Any tile failure or duplicate-object
        conflict rejects that backend as a whole. Once a backend succeeds it is
        locked. Later failure on the locked backend fails the run closed because
        switching replicas mid-convergence would contaminate level comparisons.
        """
        if self.locked_endpoint is not None:
            payload = self._acquire_all_tiles_from_endpoint(self.locked_endpoint, bbox)
            return payload, [self.locked_endpoint] * 4

        failures: list[str] = []
        for endpoint in self.endpoints:
            try:
                payload = self._acquire_all_tiles_from_endpoint(endpoint, bbox)
            except Exception as exc:
                failures.append(f"{endpoint}:{type(exc).__name__}:{exc}")
                continue
            self.locked_endpoint = endpoint
            return payload, [endpoint] * 4

        raise RuntimeError(
            "no internally consistent historical Overpass backend available: "
            + " || ".join(failures)
        )
