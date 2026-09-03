# Phase 2 — S8 interchange opportunity model

## Status and scope

This component builds the railway-side opportunity model for Olgiate-Calco-Brivio FS (`S01514`). It does **not** choose a bus topology. Its public scoring functions consume hub arrival/departure events only, so the same model can evaluate loops, radials, figure-8 services, interlining, trunk/branches, short turns and future generated topologies.

Baseline branch: `phase2-service-design` at `1b9b3d359be48bf58e592e0698702f58e7559e19`.

## Frozen evidence

Rail service is pinned to Gate C PASS commit `dcc3e75ae3b4f4ea5170f48e85345b83620c5536` and its active-day evidence `outputs/gate_c/live_trenord_2026-09-03.json`.

Gate C establishes for 2026-09-03:

- official Regione Lombardia / Trenord GTFS;
- station `S01514 Olgiate-Calco-Brivio`;
- 74 active S8 trips and 74 station events;
- official GTFS download SHA256 `b4296f145b42ccb35c26085470ff4b3fd5dffe533251c0aab312312a73820ad6`;
- epistemic status `DERIVED_FROM_LIVE_OFFICIAL_GTFS`.

The Phase 2 builder refuses a GTFS ZIP whose SHA256 differs from the Gate C evidence. It then joins every active Gate C trip to `trips.txt`, `stop_times.txt` and `stops.txt` from that exact feed.

## Direction is derived, not guessed

Direction is inferred from the ordered stop sequence downstream of Olgiate-Calco-Brivio:

- a trip continuing to `S01645 Milano Porta Garibaldi` is `MILANO`;
- a trip continuing to `S01520 Lecco` is `LECCO`.

The model does not use odd/even train-number heuristics. Ambiguous stop sequences fail closed.

Every rail event output preserves:

- service date;
- trip ID and short name;
- direction;
- Olgiate arrival and departure time;
- service-minute representation;
- origin and terminal stop;
- station position in the stop sequence;
- total number of stops;
- epistemic status.

## Timetable characterisation

`characterize_timetable()` computes separately for Milano and Lecco:

- number of events;
- first/last arrival;
- first/last departure;
- service span;
- mean and median headway;
- minimum headway;
- p10 and p90 headway;
- maximum headway;
- minute-of-hour departure offsets.

It also reports descriptive asymmetry between the two directions. These are timetable properties, not passenger-demand weights.

## Transfer anchors and continuous quality

The physical anchors are intentionally asymmetric:

- **BUS → S8:** bus arrival at the hub versus S8 **departure**;
- **S8 → BUS:** S8 **arrival** versus bus departure from the hub.

For BUS → S8:

`slack = rail_departure - bus_arrival - station_transfer_walk`

For S8 → BUS:

`slack = bus_departure - rail_arrival - station_transfer_walk`

Negative slack means the connection is physically missed after allowing for the transfer walk. This zero boundary is physical feasibility, not a chosen service-quality threshold.

Phase 2 does **not** classify transfers with one arbitrary min/max wait. The primary score is continuous:

`quality = logistic(slack / transition_scale) × exp(-|max(slack,0)-preferred_wait| / wait_decay)`

The four parameters are explicit `ASSUMPTION` sensitivity inputs:

- station transfer-walk time;
- preferred wait;
- smooth miss-transition scale;
- wait-decay scale.

No parameter value is promoted to FACT. The optimiser should evaluate multiple profiles or parameter ranges rather than hide one preferred threshold.

The legacy Gate F S8 bridge used a binary window (`minimum_transfer_min`, `maximum_wait_min`). It remains valid historical Gate F machinery but is **not** the Phase 2 opportunity scorer.

## Arrival/departure opportunity windows

Each rail event is represented as an anchor rather than a permanently frozen binary interval. A bus timetable therefore induces an event-specific continuous opportunity surface around every rail arrival/departure.

This is the Phase 2 transfer-window contract:

- the rail event supplies the fixed arrival/departure anchor;
- the station walk and behavioural profile supply an explicit sensitivity profile;
- the bus event supplies the candidate time;
- quality is evaluated continuously from slack;
- exact physical misses remain observable through negative slack.

This representation lets a later optimiser shift a bus trip by one minute and receive a correspondingly small score change instead of jumping across an arbitrary useful/not-useful boundary.

## Delay robustness

`robust_connection_quality()` accepts deterministic weighted pairs of bus and rail delay values. It uses no RNG and returns:

- expected continuous quality;
- worst-case quality;
- probability of a physical miss, defined as negative realised slack;
- expected realised slack.

For BUS → rail, bus delay reduces slack while rail delay increases it. For rail → BUS, the relationship reverses. The delay cases and their weights are `ASSUMPTION` sensitivity inputs unless an empirical delay distribution is later supplied and explicitly documented.

## Work-demand addressability

The 2021 demand layer remains exactly what the audited profile says it is: **ISTAT work commuting**, not total mobility.

`S8_DIRECT` means only that the work municipality contains a verified S8 station in `outputs/phase2/s8_station_municipalities.csv`. The Phase 2 model writes the semantics explicitly as:

`INFRASTRUCTURE_ADDRESSABILITY_NOT_MODAL_SHARE`

It never converts those workers into rail passengers or a rail mode-share estimate.

A non-direct destination can enter the rail feeder objective only through an explicit verified-transfer record containing at least:

- transfer station;
- connecting route ID;
- service date;
- evidence source.

Without that evidence the destination remains `NOT_RAIL_ASSIGNED`. This is conservative by design: absence from the verified-transfer layer means **not yet verified**, not that a real-world trip is impossible.

## SFR context

The historical SFR series is loaded separately. For Olgiate-Calco-Brivio it provides observed/derived station-use context, including the 2025 station-boardings value, but it is never used as:

- an origin-destination matrix;
- a rail mode share;
- a multiplier that converts `S8_DIRECT` workers into passengers.

Its contract is `DERIVED_SFR_CONTEXT_NOT_MODAL_SHARE`.

## Optimiser API

The topology-neutral public interface is `score_bus_hub_timetable()`.

Each bus event requires only:

- `scenario_id`;
- `event_type` = `BUS_ARRIVAL` or `BUS_DEPARTURE`;
- `event_time`.

There is no topology field and no route-family branch in the scorer.

For each event it returns scores against both Milano and Lecco S8 opportunities. A future timetable optimiser can aggregate those event-level results using the Phase 2 demand/GJT contract without modifying the rail model.

## Production outputs

`scripts/phase2_build_s8_interchange.py` writes:

- `outputs/phase2/s8_events.csv`;
- `outputs/phase2/s8_direction_summary.csv`;
- `outputs/phase2/s8_timetable_characterization.json`;
- `outputs/phase2/s8_work_demand_addressability.csv`;
- `outputs/phase2/s8_station_context.json`;
- `outputs/phase2/s8_interchange_contract.json`.

The CI build uses the exact Gate C commit, the frozen Phase 2 Trenord GTFS ZIP, audited 2021 work-demand outputs, the GTFS-derived station-to-municipality map and SFR series. It asserts that all 74 active Gate C events survive the join and that the audited direct-S8 work-demand total remains 1,882 workers.
