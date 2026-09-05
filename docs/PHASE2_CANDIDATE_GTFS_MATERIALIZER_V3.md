# Phase 2 Candidate-GTFS Materialization Contract V3 (RT-014)

## Purpose

RT-014 defines a deterministic fail-closed bridge from an upstream candidate service specification to a minimal standard GTFS feed suitable for later passenger-routing evaluation.

It does not choose stops, a topology, headways, a service calendar or a route winner.

## Upstream objects

The materializer accepts only explicit generic objects:

- one agency definition;
- unique boarding points with stable IDs and finite WGS84 coordinates;
- unique route definitions;
- unique service calendars;
- unique directed service patterns;
- ordered stop calls referencing supplied boarding points;
- explicit trip departure times.

No stop may be inferred from a name, nearest coordinate, corridor geometry or legacy anchor.

## Pattern contract

Each service pattern must:

- reference an existing route and service calendar;
- use `direction_id` 0 or 1;
- contain at least two stop calls;
- use contiguous `stop_sequence` values beginning at 1;
- start at cumulative time zero;
- use non-negative integer cumulative time offsets that never decrease;
- contain at least one explicit non-negative integer departure time.

No headway or frequency expansion is performed.

## Deterministic GTFS output

The minimal feed contains exactly:

- `agency.txt`;
- `stops.txt`;
- `routes.txt`;
- `trips.txt`;
- `stop_times.txt`;
- `calendar.txt`.

Rows are sorted by stable identities. CSV uses UTF-8, LF line endings and deterministic quoting. The ZIP uses a fixed file order, stored compression and fixed metadata timestamp, so equivalent logical input produces byte-identical output.

GTFS times are generated from integer seconds without wrapping at midnight. A departure at 25:00 remains `25:00:00`.

## Fail-closed semantics

The build rejects duplicate identities, unresolved foreign keys, invalid coordinates, invalid route/direction values, broken stop sequences, decreasing cumulative times, duplicate departure times, empty departure sets and invalid service calendars.

The materializer never silently drops a supplied stop call and never creates a substitute stop.

## Downstream bridge

Once the authoritative boarding-point inventory is frozen upstream, territorial candidate patterns may reference those exact stable stop IDs. RT-014 can then build one candidate GTFS that is passed unchanged to both the internal passenger-routing engine and the independent R5 engine under RT-013.

## Non-claim

The controlled RT-014 fixture is abstract test data. Passing this gate does not validate any territorial candidate, stop pattern, timetable policy, headway, fleet requirement or recommendation.
