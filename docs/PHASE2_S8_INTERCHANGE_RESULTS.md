# Phase 2 S8 interchange - validated results

## Validated computation

Branch: `phase2-s8-interchange`

Computational commit: `342821e8bf4aac1838b65fd6b8a76bcedd578ffb`

CI run: `33767222689`

CI job: `100688069927`

Tests: **15/15 PASS** plus production-contract integration PASS.

Artifact: `9898027891`, `phase2-s8-interchange-342821e8bf4aac1838b65fd6b8a76bcedd578ffb`.

Artifact ZIP SHA256: `d6942ffb8d42b49533288d0bd6b1b18d51e14df5b80e5d0068bcf9487e1b9fbb`.

The production run verifies that the Phase 2 Trenord ZIP has the exact SHA256 required by Gate C: `b4296f145b42ccb35c26085470ff4b3fd5dffe533251c0aab312312a73820ad6`.

## Active S8 events at Olgiate-Calco-Brivio

Service date: **2026-09-03**.

All 74 Gate C events are recovered from the matching official GTFS and assigned direction from their ordered stop sequence.

| Direction | Events | First arrival | First departure | Last arrival | Last departure | Same-direction headway |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Milano | 37 | 05:25 | 05:26 | 23:25 | 23:26 | 30 min exactly |
| Lecco | 37 | 06:02 | 06:03 | 24:02 | 24:03 | 30 min exactly |

`24:02` and `24:03` are valid GTFS service times after midnight on the same service day.

For each direction the observed active-day series contains 36 consecutive headways and all of them equal 30 minutes. Therefore mean, median, p10, p90, minimum and maximum headway are all 30 minutes on this service date.

## Symmetry and phase asymmetry

The active timetable is strongly symmetric in service quantity and cadence:

- 37 events in each direction;
- 18-hour departure span in each direction;
- exact 30-minute headway in each direction.

It is not symmetric in clock phase or service-day endpoints:

- Milano departs at minute-of-hour `:26` and `:56`;
- Lecco departs at `:03` and `:33`;
- the first Lecco departure is 37 minutes after the first Milano departure;
- the last Lecco departure is likewise 37 minutes after the last Milano departure.

If one looks only at **hub event phase**, not passenger travel frequency, the four departure offsets in an hour are `:03, :26, :33, :56`. Consecutive cross-direction hub events therefore alternate 23 and 7 minutes. This must not be labelled a combined 15-minute rail headway because Milano and Lecco are different destinations.

## Transfer opportunity representation

The model does not freeze one useful/not-useful transfer window.

For each S8 event it preserves the physical arrival/departure anchor and lets a bus timetable be evaluated continuously.

BUS to S8:

`slack = rail departure - bus arrival - transfer walk`

The preferred bus-arrival target, for a chosen sensitivity profile, is centred at:

`rail departure - transfer walk - preferred wait`

S8 to BUS:

`slack = bus departure - rail arrival - transfer walk`

The preferred bus-departure target is centred at:

`rail arrival + transfer walk + preferred wait`

Distance from that target is scored continuously. There is no hard quality cutoff. Negative slack remains separately observable as a physical missed connection.

## Robustness contract

The same scheduled bus event can be evaluated under deterministic weighted pairs of bus and rail delays. The model returns expected quality, worst-case quality, physical-miss probability and expected slack.

No random sampling is used. Delay cases remain `ASSUMPTION` sensitivity inputs unless a future empirical delay distribution is explicitly integrated.

## 2021 work demand

The audited Phase 2 work-demand total is 8,754 resident workers. **1,882** have work destinations already classified `S8_DIRECT` and independently supported by the GTFS-derived S8 station-to-municipality map.

This means infrastructure addressability only. It is **not** a rail mode share, expected ridership or probability of choosing S8.

No verified non-direct rail-transfer map was supplied in this workstream, so the production layer deliberately assigns **0 workers** to `TRANSFER_RAIL_GTFS_VERIFIED`. The remaining 6,872 workers are `NOT_RAIL_ASSIGNED` in this rail-opportunity layer.

That zero means **no additional transfer destination is claimed without verified evidence**. It does not mean that zero real-world journeys with a train transfer are possible.

## SFR context

Olgiate-Calco-Brivio records:

- 1,420 `Saliti24H` in 2019, index 100;
- 2,400 `Saliti24H` in 2025;
- 2025 index `169.0140845` on the 2019=100 scale.

This is station-use context only. SFR is not used as OD demand, as a mode share or as a multiplier for the 1,882 S8-addressable workers.

## Optimizer handoff

The optimizer-facing rail scorer requires only hub events:

- `scenario_id`;
- `event_type` (`BUS_ARRIVAL` or `BUS_DEPARTURE`);
- `event_time`.

It does not require a topology identifier and contains no special case for loop, radial, figure-8 or interlining structures. Any topology that produces a candidate timetable at `S01514` can be evaluated by the same function.
