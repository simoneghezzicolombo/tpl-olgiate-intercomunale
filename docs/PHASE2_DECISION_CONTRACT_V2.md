# Phase 2 final decision contract V2

## Why a V2 contract is necessary

The original finalizer expected a complete demand-weighted GJT candidate table. Subsequent audited work established that the municipal ISTAT 2021 work OD matrix cannot be downscaled to stops, buildings or routes without unsupported submunicipal allocation assumptions. The 1,882 S8-addressable workers likewise cannot be assigned to individual bus routes as observed passenger demand.

The original Phase 2 specification explicitly allows **demand-weighted GJT improvement or accessibility utility** in the final decision rule. V2 therefore uses only accessibility and service evidence that is empirically supported at its actual spatial resolution. `scripts/phase2_finalize_tournament.py` remains historical machinery and is not authorised to materialise the V2 recommendation unless a genuinely supported complete GJT table later becomes available.

## Decision question remains unchanged

Phase 2 must still answer which bus design centred on Olgiate-Calco-Brivio FS maximises practical usefulness for the largest possible number of people under realistic operating resources and is robust enough to recommend.

No topology family is privileged. The unrestricted tournament remains open to one line, multiple loops, radials, trunk/branch structures, interlining, scheduled extensions and blank-slate structures. A later one-public-line constrained tournament may be run as a policy sensitivity, but it is not imposed on the primary computational search.

## Primary budget and budget sensitivity

The **reference decision envelope is 111,419 annual bus-km**, following the Phase 2 service-design specification. This is the main decision run, not the largest available envelope.

The following materialised envelopes remain mandatory sensitivities:

- -20%: 89,135.2 bus-km/year;
- -10%: 100,277.1;
- reference: 111,419.0;
- +10%: 122,560.9;
- +20%: 133,702.8;
- +30%: 144,844.7.

A higher-budget plan may become the substantive recommendation only if the final report explicitly demonstrates a material accessibility/service benefit and quantifies the incremental resource requirement.

## Passenger-facing service plan identity

A service plan is defined by:

- topology/scenario;
- uniform clockface headway in the current V2 sweep;
- service span;
- annual service calendar/day count;
- scheduled-extension share where applicable.

Recovery values of 5/10/15 minutes are **robustness sensitivities of the same passenger-facing plan**, not three different service products. The tournament reports the fleet lower-bound range and uses the 15-minute recovery case as the conservative fleet descriptor. This does not turn 15 minutes into an observed or politically selected recovery rule.

## Evidence axes

The plan-level tournament must retain separate evidence axes rather than hide them inside a weighted score:

1. **Resident access**: located population within the certified 10-minute walking catchment.
2. **Territorial equity**: coverage share of the worst-served municipality.
3. **Territorial work-OD addressability**: municipal work-commuting mass structurally addressable by the public route geometry, explicitly an upper bound and not ridership.
4. **Service availability**: headway, span and annual service days.
5. **Operating resources**: annual bus-km and fleet lower bound under recovery sensitivity.
6. **S8 feeder compatibility**: route-unweighted transfer-envelope evidence at the matching headway/span. It is a feeder quality layer only. The 1,882-worker reference is not allocated to routes.

Scheduled-extension scenarios must preserve base-public and extension-only evidence separately until an explicit timetable determines which trips actually serve the extension.

## No weighted composite

V2 must not create a formula such as `0.4 population + 0.2 OD + 0.2 S8 + 0.2 cost`.

Screening uses dominance/frontier logic and explicit service classes. Any final tie-break must remain visible and lexicographic.

## Service-frequency sensitivity

The unrestricted tournament retains 15, 20, 30 and 60 minute headways.

In parallel, V2 reports a **frequent/useful-service sensitivity** restricted to headways of 30 minutes or better. This is not used to delete hourly candidates. It exists because the normative best-practices reference explicitly warns that hourly-or-worse service is qualitatively different from frequent service and should not be treated as a linear half-value version of 30-minute service.

If unrestricted and <=30-minute tournaments select different finalists, the difference is a policy trade-off that must be reported.

## Final recommendation eligibility

A PRIMARY or RUNNER-UP cannot be materialised from topology/service envelopes alone. Finalists must additionally receive:

- an explicit trip timetable;
- joint, not independently optimised, S8 clock phase;
- both bus-to-rail and rail-to-bus connection checks where the route supports them;
- vehicle blocks and simultaneous fleet requirement;
- runtime/dwell/recovery perturbation checks;
- exact full-graph reroute and road/stop uncertainty review;
- current-baseline and municipal non-regression comparison to the extent supported by the certified baseline.

Until those checks exist, an output is a **SHORTLIST/FRONTIER**, not a final recommendation.

## Required V2 outputs

The workstream must materialise at least:

- plan-level candidate/frontier evidence for every budget envelope;
- reference-budget unrestricted shortlist;
- reference-budget <=30-minute shortlist;
- exact timetable candidates for the shortlists;
- robustness results;
- PRIMARY and RUNNER-UP only after the exact-timetable gate;
- route geometry and map-ready lineage for later final visualisation.
