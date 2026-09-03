# Phase 2 service and passenger-evaluation engine

## Purpose

This block converts a structurally feasible network into an explicit service plan that can be compared with the current validated baseline and with other candidate networks.

It is intentionally independent from the 2021 work OD matrix and from any preferred topology. The engine consumes upstream evidence rather than embedding territorial assumptions.

## 1. Operational layer

`src/phase2_service_engine.py` represents service as explicit repeating **vehicle blocks** plus explicit **service windows**.

An `OperatingCycle` contains only upstream-calculated facts/model outputs:

- route/block identifiers;
- routed distance;
- pure running time;
- declared recovery time;
- evidence status;
- count of still-unverified physical elements.

A `ServiceWindow` declares:

- day type;
- start and end time;
- headway;
- annual number of days;
- timetable phase offset.

No 303-day, 365-day, 30-minute or 60-minute constant is silently assumed.

For each plan the engine derives:

- annual bus-km;
- annual scheduled vehicle-hours, including declared recovery;
- annual departures;
- maximum simultaneous vehicles required;
- minimum recovery in any block;
- operational evidence validity.

This permits independent loops, interlined blocks, radials, short turns and scheduled extensions to be evaluated on the same production basis.

## 2. Passenger utility layer

Empirically weighted passenger utility uses `JourneyRecord` and an explicit behavioural sensitivity case.

For a journey:

`GJT = IVT + w_walk*(walk + transfer_walk) + w_wait*(wait + transfer_wait) + transfer_penalty*transfers + missed_connection_probability*missed_connection_cost`

The behavioural coefficients are inputs. They are not embedded as territorial facts and must later be populated from the ranges documented in `PHASE2_TRANSIT_BEST_PRACTICES.md`.

Baseline and candidate comparisons must contain the **same journey universe and the same empirical demand weights**. The engine refuses a comparison if candidate demand weights change. This prevents a network from appearing better merely because inconvenient passengers disappeared from the evaluation set.

The result includes:

- demand-weighted GJT improvement;
- the same improvement by origin municipality;
- worst-municipality change;
- demand-weighted missed-connection probability.

These records feed the robust-sensitivity tournament already implemented in `phase2_optimizer_core.py`.

## 3. Why the OD matrix is not the whole model

The engine deliberately separates three outcomes.

### Empirically weighted journey utility

Used only when a defensible trip/demand weight exists, for example validated ISTAT work OD or other future supported demand evidence.

### Population walking access

`PopulationAccessRecord` reports population within declared useful-stop walking thresholds. This comes from the population/walking workstream and is not multiplied by invented trip rates.

### Opportunity accessibility

`OpportunityAccessRecord` reports population able to reach verified opportunity types such as health or school within declared travel-time thresholds. When empirical trip weights are unavailable, these results remain separate rather than being assigned guessed passenger counts.

Thus population, work commuting, S8 interchange and essential/local opportunities can all influence the final decision without pretending they are measurements of the same quantity.

## 4. Equity and hard constraints

Municipal non-regression is explicit. Positive GJT improvement means the candidate is better than baseline. A declared tolerance may be applied, but no hidden equity weight is used.

`build_hard_constraints()` combines:

- road integrity from the routing workstream;
- annual bus-km budget;
- fleet cap;
- minimum recovery requirement;
- upstream evidence validity;
- territorial non-regression.

Only candidates passing all hard constraints are eligible for the robust tournament.

## 5. Epistemic guardrails

Production classes reject `INVALIDATED` and `PLACEHOLDER` evidence.

The unit tests contain small numerical fixtures solely to verify arithmetic and contracts. They are marked `TEST_FIXTURE_ONLY`, never written to project outputs and must never be interpreted as Meratese evidence.

## 6. Integration sequence

When the parallel workstreams hand off their outputs:

1. frozen graph + reduced path matrix generate structural scenario catalogues;
2. stop universe supplies existing/proposed stop sets and field-check status;
3. the service search creates candidate blocks, calendars, headways, spans and timetable phases;
4. the S8 workstream supplies connection opportunities and reliability inputs;
5. the journey evaluator produces baseline/candidate journey components for each sensitivity case;
6. this engine computes operational summaries and passenger comparisons;
7. `phase2_optimizer_core.py` applies hard eligibility, robust utility ranking, lexicographic tie-break and budget frontier;
8. leading candidates return to exact Gate D routing and explicit timetable verification before the final recommendation.

## 7. Current non-claims

This block does **not** yet claim:

- a preferred route;
- a preferred topology;
- a preferred headway;
- a required fleet size;
- a passenger-utility improvement;
- a final budget sweet spot.

Those become model outputs only after validated territorial, stop, timetable and journey inputs are connected.
