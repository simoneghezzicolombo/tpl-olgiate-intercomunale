# Phase 2 Frozen Cross-engine Experiment Manifest V3 (RT-015)

## Purpose

RT-015 freezes the shared experiment identity that must exist before two independent passenger-routing engines may be compared.

It converts a candidate/feed/network/OD/time/mode specification into canonical JSON and a SHA256 manifest identity. RT-013 is authorized only when both engine executions bind to that exact same manifest hash.

## Frozen fields

The manifest records:

- schema version and candidate ID;
- exact candidate-GTFS SHA256;
- exact street-network SHA256;
- unique OD key universe;
- service date and IANA timezone;
- departure-window start/end seconds;
- explicit shared mode semantics.

OD keys and modes are canonicalized by value, so input ordering cannot alter experiment identity.

## Fail-closed semantics

Malformed hashes, duplicate OD keys, empty OD/mode universes, invalid dates/timezones, negative or reversed departure windows and missing identifiers are rejected.

A comparison also fails if engine labels are not distinct or either engine declares a different experiment-manifest hash. This is `EXPERIMENT_IDENTITY_MISMATCH`, not a routing discrepancy.

## Downstream role

RT-014 materializes the candidate GTFS. RT-015 freezes the exact GTFS/network/OD/time/mode experiment. Both engines execute that frozen experiment. RT-013 may compare travel-time outputs only after RT-015 identity validation succeeds.

## Non-claim

The controlled fixture is abstract. RT-015 does not validate territorial OD definitions, stop patterns, timetables or route recommendations.
