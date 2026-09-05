# Phase 2 Cross-engine Discrepancy Contract V3 (RT-013)

## Purpose

RT-013 defines how two independent passenger-routing engines may be compared on an identical origin-destination universe.

It does not choose which engine is correct and does not create a combined travel time.

## Alignment contract

Each engine must provide unique rows identified by `from_id` + `to_id` with finite non-negative travel time.

The OD key sets must match exactly. Missing, extra or duplicate OD rows fail closed. Absence from one engine is never silently interpreted as unreachable.

## Per-OD diagnostics

For every aligned OD pair preserve:

- engine A travel time;
- engine B travel time;
- signed difference `B - A`;
- absolute difference;
- relative difference against A when A is strictly positive.

If engine A is zero, relative difference is undefined rather than infinite.

## Aggregate diagnostics

Retain separate descriptive summaries of absolute discrepancy, including mean, median, P90, P95 and maximum. Optional reporting bands such as 1, 3 or 5 minutes may describe shares of OD pairs below those differences.

Reporting bands are diagnostics only. They do not create an automatic agreement threshold.

## No averaging

The contract never averages engine A and B and never hides disagreement inside a composite score. A large disagreement remains visible even if most OD pairs agree closely.

## Territorial bridge requirement

A future territorial comparison is interpretable only if both engines receive the same frozen:

- origins and destinations;
- OD identities;
- mode semantics;
- service date and departure window;
- candidate GTFS definition;
- relevant network input vintage.

Differences must then be investigated rather than averaged away.
