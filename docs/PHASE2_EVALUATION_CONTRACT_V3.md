# Phase 2 Evaluation Contract V3 (RT-011)

## Purpose

RT-011 defines how future territorial network candidates may be evaluated after corrected passenger-stop materialization and passenger routing are available.

It does **not** select a route, consume the evolving stop inventory, or authorize a territorial recommendation.

## Why this contract exists

A threshold-only catchment can hide large differences in actual walking burden. Two candidates may both place 100% of population within 15 walking minutes while one places most residents 3–5 minutes from service and the other 11–14 minutes away.

V3 therefore treats walking distance/time as a distribution, not a single covered/uncovered flag.

## Walking burden

For population-weighted network walking times, retain separately:

- weighted mean walking minutes;
- weighted median;
- weighted P90;
- weighted P95;
- population share within 5 minutes;
- population share within 8 minutes;
- population share within 10 minutes;
- population share within 12 minutes;
- population share above 10 minutes;
- population share above 12 minutes.

Thresholds are diagnostics. None of them is a complete accessibility objective.

Continuous accessibility or decay-weighted opportunity measures supplied by a later passenger-routing layer remain continuous measures and can be declared as separate Pareto dimensions.

## Territorial guard

Required policy groups are generic IDs. A candidate passes this guard only if upstream passenger-stop evidence confirms a boarding opportunity in every required policy group.

The guard is not inferred from names, nearest walking distance or a catchment threshold.

## Service-area sanity diagnostics

A later territorial audit may supply service-area rows containing:

- whether the area is served;
- nearest passenger stop;
- network walking time to that stop;
- optional marginal extra route-km to serve the area;
- optional marginal extra runtime to serve the area.

These are diagnostic outputs. An unserved service area does not become a mandatory waypoint merely because it appears in this table.

## Pareto semantics

There is no weighted composite score.

For explicitly declared dimensions, candidate A strictly dominates candidate B only when A is no worse than B on every declared dimension and strictly better on at least one. Trade-offs and exact ties remain on the frontier.

This prevents an operationally shorter candidate from automatically defeating a candidate with substantially better passenger access, and vice versa.

## Controlled audit

The RT-011 controlled fixture intentionally includes:

1. two synthetic walking distributions with identical 100% coverage at 15 minutes but sharply different mean/P90 walking burden;
2. a lower-km candidate and a better-access candidate that remain non-dominated;
3. a candidate strictly dominated on all declared dimensions;
4. a missing generic policy group;
5. an unserved generic service area with marginal-service diagnostics.

The fixture contains no territorial data and cannot support a route recommendation.

## Downstream requirement

Before real candidates can be compared under RT-011, the project still requires:

1. corrected multi-operator existing-stop inventory;
2. passenger-stop materialization along candidate corridors;
3. network walking / passenger routing evidence;
4. operational metrics on the same candidate definitions;
5. a human-readable geographic sanity gate before any finalist status.
