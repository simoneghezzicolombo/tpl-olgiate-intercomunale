# Affordable physical walk exploration and conditional accessibility

Base: 163ce18c1237221cc66d59ff196e2927db35a2b4, PR #80.

## Declared computational domain

The search considers a single closed walk of the 288 frozen RT023 atomic
realizations. Every root realization is initialized; no municipality, station or
named locality is forced. All represented pairwise restrictions and atomic
legality must be certified. Repeated vertices/edges, backtracking, branching
excursions and arbitrary walk lengths are permitted within a positive distance
budget. There is no elementary E6/E7 cap or random search.

The distance envelope is the broadest one in the already documented frequent
service grid: approved 111,419 annual bus-km / (32 departures * 260 assumed days),
or approximately 13.392 km per complete movement. H30, the half-open 06–22
window and 260 days remain explicit design assumptions, not a final timetable
or observed operating calendar. Added depot movements can consume further budget.

Each state retains (root realization, last realization, union of available stop
IDs). Only a higher-distance path to that exact state is discarded. This is
valid for additive physical distance and available-stop union under the scoped
history-locality proof. Root identity preserves closing-seam context; the search
does not assert cycle rotations are equivalent public services. Every found
witness is independently replayed through the full-history physical composer.

Positive atom lengths and a finite distance cap give a finite physical domain.
The implementation has an explicit computational limit of 250,000 expanded
states for this run. This is not a restriction on the mathematical candidate
set. If labels remain, the result is RESOURCE_LIMIT_INCOMPLETE and no exhaustive
frontier, global optimality, completeness or production-search PASS is claimed.
Re-running with a larger execution limit may reveal additional alternatives.
The queue explores shorter physical walks first; partial coverage is not neutral
with respect to unexplored longer walks, and must not become final selection.

## Linked conditional access comparison

Each found stop-availability set is evaluated with the certified RT028 matrix
(artifact 9991182904) and existing RT029 access/equity aggregation. Full CORE,
EXTERNAL, ALL and municipal 5/8/10/12-minute outputs are exported. These mean
walking accessibility **if** the available stops become publicly served. They
are not a proof of pickup/dropoff, boarding attachment or an onboard journey.
A physical route's stop occurrence availability cannot assign those rights.

A descriptive nondominated set among the evaluated walks uses the six existing
CORE/worst-municipality 5/8/10-minute axes and exact physical distance. No scalar
score is used. This is an evaluated-set physical/conditional-access comparison,
not the final policy tournament or an operational service Pareto frontier.
The 12-minute metrics and external population remain visible diagnostics.

## Boundaries still requiring implementation/evidence

This domain is a single physical movement, not the general linked multi-component
public network/service/movement domain requested by RT031. Reusing label
dominance for timing, pickup/dropoff, repeated passenger events, transfers,
frequency allocation or multi-component networks would require a new proof and
richer state. No such lossless compression is asserted here.

The output retains actual realization IDs and distances, available stop sets,
conditional resource consumption, full access tables, truncation status and
input hashes. These provide concrete affordable geometric alternatives for
calibration and service assignment. No PRIMARY, RUNNER-UP or final recommendation
is selected. Independent review of the scope/dominance proof and operational
calibration remain open.

## Report-only operational model bridge

For each retained physical witness the runner also sums the frozen edge field
`running_minutes_model` over every traversal. It does not replace these with a
new assumed mean speed. Those source models depend on OSM maxspeed/highway
assumptions; they are not observed journey times and exclude dwell. The existing
5/10/15-minute recovery sensitivities yield a report-only model fleet lower bound
ceil((source running model + recovery)/30). No dwell, driver duties, deadhead,
vehicle block plan or calibrated timetable is silently included.

These runtime/fleet columns are descriptive for the selected geometric witness.
They are not added to label dominance or conditional-frontier objectives: the
physical state compression is not lossless for runtime/service optimization and
may discard a longer but faster alternative. No fleet-feasibility or final
operational superiority is inferred from these lower bounds.
