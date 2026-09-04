#!/usr/bin/env python3
"""Run Passenger Utility Frontier V2 retaining all certified 5/8/10 access thresholds.

The initial Stage-C builder intentionally separates passenger-facing utility from
technical tie-break dimensions, but its first draft omitted the certified
8-minute accessibility threshold. This adapter restores the complete certified
5/8/10 threshold family without changing any other selection semantics.
"""
from __future__ import annotations

import scripts.phase2_build_passenger_utility_frontier_v2 as base

EXTRA_ACCESS_FIELDS = (
    "public_population_coverage_share_8min",
    "public_worst_municipality_coverage_share_8min",
)

base.PASSENGER_MAX_AXES = (
    "public_population_coverage_share_5min",
    "public_population_coverage_share_8min",
    "public_population_coverage_share_10min",
    "public_worst_municipality_coverage_share_5min",
    "public_worst_municipality_coverage_share_8min",
    "public_worst_municipality_coverage_share_10min",
    "territorial_other_core_worker_mass_upper_bound",
    "territorial_other_external_worker_mass_upper_bound",
    "to_rail_reachable_share",
    "to_rail_worst_municipality_reachable_share",
    "from_rail_reachable_share",
    "from_rail_worst_municipality_reachable_share",
    "bidirectional_reachable_share",
    "bidirectional_worst_municipality_reachable_share",
    "s8_complete_supported_route_share",
)

for field in EXTRA_ACCESS_FIELDS:
    if field not in base.COMPACT_SOURCE_FIELDS:
        base.COMPACT_SOURCE_FIELDS = (*base.COMPACT_SOURCE_FIELDS, field)

PASSENGER_MAX_AXES = base.PASSENGER_MAX_AXES
PASSENGER_MIN_AXES = base.PASSENGER_MIN_AXES
AVAILABILITY_MAX_AXES = base.AVAILABILITY_MAX_AXES


def main() -> int:
    return base.main()


if __name__ == "__main__":
    raise SystemExit(main())
