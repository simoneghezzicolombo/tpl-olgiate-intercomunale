# Phase 2 r5py Cross-check V3 (RT-012)

## Purpose

RT-012 establishes `r5py`/R5 as an independent passenger-routing engine that can later challenge the project's internal accessibility calculations.

It is not a replacement for Gate D road routing and it does not yet use territorial candidate data.

## Pinned smoke environment

- Python 3.12
- JDK 21
- `r5py==1.1.7`
- `r5py.sampledata.helsinki==1.1.1`

The upstream Helsinki sample package is used only as a controlled integration fixture. It is not project evidence.

## Smoke contract

The audit must:

1. materialize the pinned upstream OSM PBF and GTFS fixture;
2. read the GTFS and choose a real service date deterministically;
3. build an R5 `TransportNetwork`;
4. compute a WALK travel-time matrix;
5. repeat the WALK matrix request and verify exact tabular equality;
6. compute a TRANSIT travel-time matrix;
7. require finite non-negative travel times;
8. record Python, Java and r5py versions;
9. emit no territorial recommendation or score.

## Intended later role

Once the corrected territorial stop inventory and candidate GTFS outputs exist, a later bridge can feed the same frozen origins/destinations to:

- the internal accessibility pipeline;
- r5py/R5.

Disagreement must be surfaced as an audit result. The two engines must not be averaged together to hide differences.

## Why this is independent

R5 is a separate routing engine and implementation stack. Its purpose in this project is therefore cross-engine validation of walking/transit accessibility and door-to-door travel times, not route generation.
