#!/usr/bin/env python3
"""RT-017 territorial runner with run-wide single-backend OSM consistency.

This is a thin execution adapter around the certified RT-017 territorial runner.
It replaces only the historical Overpass acquisition function. Routing, snapping,
RT-010 complete directed pairs, Gate-D restrictions, convergence logic and frozen
output semantics remain those of the underlying runner.
"""
from __future__ import annotations

from scripts import phase2_rt017_adaptive_border_neutral_routing_envelope_v3 as rt017
from src.phase2_overpass_consistent_acquisition_v3 import (
    HistoricalOverpassLevelAcquirer,
)


def main() -> int:
    acquirer = HistoricalOverpassLevelAcquirer(
        endpoints=rt017.OVERPASS_ENDPOINTS,
        snapshot_timestamp=rt017.OSM_SNAPSHOT_TIMESTAMP,
        user_agent=rt017.USER_AGENT,
    )
    rt017.acquire_level_snapshot = acquirer.acquire_level_snapshot
    return rt017.main()


if __name__ == "__main__":
    raise SystemExit(main())
