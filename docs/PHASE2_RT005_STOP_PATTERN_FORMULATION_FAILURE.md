# RT-005 — Stop-pattern formulation failure

## Verdict

**BLOCKING. The current four finalists are not decision-ready real-world route proposals.**

The current lineage is computationally reproducible and the Stage D/E/F and Finalist Simplicity Diagnostic V3 PASS verdicts remain valid for the mathematical problem that was actually solved. RT-005 identifies that the solved problem is not a sufficient representation of the intended local-bus planning problem.

This is a formulation failure, not a numerical-reproducibility failure.

## Failure mechanism

The Phase 2 structural search represents a public route as a short sequence of routing anchors. The structural catalog permits only a small number of intermediate anchors per loop. Downstream Access Equity V2 then interprets the non-hub anchors appearing in those route sequences as the scenario's **explicit passenger stop set** and computes walking coverage from that set.

The finalist diagnostic correctly describes its route sequences as:

`ORDERED_CERTIFIED_ANCHORS_ONLY_NO_ROUTED_GEOMETRY`

However, because upstream accessibility treated those same explicit anchors as passenger stops, the optimizer was allowed to reward networks with only a handful of explicit stops if the selected stop catchments performed well numerically.

Consequences visible in the four finalists include:

- very sparse public stop patterns;
- entire study municipalities absent from the explicit stop set;
- important settlements not represented as required service points;
- proposed candidate points with technical IDs and `FIELD_CHECK_PENDING` status surviving into finalists;
- no guarantee that an anchor corresponds to a sensible roadside boarding location;
- no requirement to insert normal intermediate passenger stops along a routed corridor;
- no stop-spacing contract derived from a realistic local-bus pattern;
- runtime and accessibility evaluated for a stop pattern that is too sparse to represent the intended service.

## Why this invalidates the current decision layer

A network can be optimal for the implemented objective and still be a poor answer to the planning question if the feasible set is misspecified.

The intended question is not:

> Which small set of catchment anchors connected to Olgiate-Calco-Brivio FS produces attractive aggregate metrics?

It is closer to:

> Which realistic, operable local-bus corridors and passenger stop patterns can connect the five municipalities and their principal settlements to each other and to the S8 node, within the budget and robustness constraints?

The current lineage does not encode the second question strongly enough.

Therefore:

- the four current finalists become **negative regression fixtures**, not candidate recommendations;
- PRIMARY / RUNNER-UP remain blocked;
- no geographic route visualization may present the finalist anchor sequence as a complete passenger stop pattern;
- downstream timetable/robustness results must be recomputed after the stop-pattern formulation is corrected.

## V3 redesign contract

The corrected lineage must explicitly separate three objects.

### 1. Corridor geometry / structural waypoints

Waypoints exist to define where a route travels. They are not automatically passenger stops.

Required fields include:

- corridor/route ID;
- ordered structural waypoints;
- routed road geometry with provenance;
- bus-accessibility status of road segments;
- unresolved field checks;
- turn/width/grade restrictions where available.

### 2. Passenger stop pattern

Passenger stops are a separate ordered list attached to a routed corridor.

A stop may be:

- an existing official physical stop/cluster;
- a proposed stop candidate with a human-readable place identity and roadside plausibility;
- the S8 interchange node.

The stop pattern must include all served intermediate stops, not only the structural waypoints used to construct the route.

### 3. Timetable / operations

Runtime must be recomputed from the corrected corridor and full passenger stop pattern, including stop dwell assumptions. Accessibility, annual kilometres, exact timetable, block feasibility, S8 integration and robustness must then be rebuilt downstream.

## Territorial-service safeguards

The first V3 implementation must enforce the following before a scenario can reach timetable optimization.

### Hard municipality guard

Every one of the five study municipalities must contain at least one explicit passenger stop served by the scenario, unless a named human-approved exception is recorded in the scenario metadata:

- Olgiate Molgora
- Calco
- Brivio
- Santa Maria Hoè
- La Valletta Brianza

A municipality cannot count as served only because a catchment from a stop in another municipality reaches some of its population.

### Settlement/service-area audit

The model must materialize coverage diagnostics for named territorial areas rather than leaving them implicit in aggregate municipality shares. At minimum the audit must explicitly report the status of:

- Olgiate Molgora centre / station area;
- San Zeno;
- Calco centre;
- Calco Alta / Calco Superiore question;
- Arlate;
- Brivio centre;
- Beverate;
- Santa Maria Hoè;
- Perego / Rovagnate in La Valletta Brianza;
- Mondonico / Monticello where relevant to the chosen corridor.

These names are an **audit list**, not an instruction that every location must necessarily be served by every final route. A location may be excluded only with an explicit reason such as road infeasibility, excessive detour/runtime or a documented alternative service strategy.

### Stop identity and plausibility guard

A final candidate stop may not remain a bare technical ID. Before a scenario can become a finalist it must have:

- human-readable locality/road identity;
- municipality;
- coordinates;
- source/provenance;
- existing vs proposed status;
- roadside boarding plausibility status;
- field-check status;
- reason for inclusion.

A `FIELD_CHECK_PENDING` stop may be evaluated in sensitivity work, but it cannot silently function as an unquestioned final boarding point.

### Stop-density / spacing guard

V3 must benchmark stop spacing against the frozen ordinary D184/D185 network and the actual routed corridor. It must not use an arbitrary global fixed stop count.

The implementation should report, by route:

- route length;
- passenger stop count;
- median and maximum inter-stop distance;
- current-network benchmark distribution for comparable ordinary local patterns;
- any gap above the chosen admissible threshold;
- whether the route behaves as an ordinary local service or an intentionally limited-stop service.

Any limited-stop designation requires an explicit policy justification and cannot be inferred from optimizer convenience.

### Existing-stop reuse guard

Where a proposed corridor passes close to a suitable existing official stop, V3 must test reuse before creating a new candidate stop. New stops are allowed, but duplicate or poorly placed candidates should not win merely because their catchment geometry is numerically attractive.

## Rebuild order

RT-005 requires the following dependency order:

1. corridor / stop-pattern model V3;
2. territorial and stop-plausibility audit;
3. accessibility/equity rebuild;
4. service-policy and budget filtering;
5. exact timetable rebuild;
6. robustness rebuild;
7. finalist diagnostic;
8. only then a renewed human decision layer and geographic explorer.

No current finalist metric may be carried forward as if it were still candidate evidence after step 1 changes the stop pattern.

## Acceptance conditions for closing RT-005

RT-005 can close only when a source-closed validation demonstrates all of the following:

- corridor waypoints and passenger stops are separate data structures;
- all five study municipalities satisfy the municipality guard or have explicit human exceptions;
- named settlement/service-area audit is materialized;
- every finalist stop has human-readable identity and plausibility metadata;
- stop spacing/density is reported against a frozen current-network benchmark;
- full passenger stop patterns are used for accessibility and runtime;
- downstream timetable and robustness evidence has been rebuilt from those patterns;
- deterministic rebuild and anti-invention guards pass;
- the site consumes only the corrected V3 output for proposed-network geography.
