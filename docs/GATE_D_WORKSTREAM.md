# Gate D workstream: road / route integrity

## Verdict

**PROVISIONAL / BLOCKED_BY_GATE_B_AND_GATE_C**

Baseline: `antigravity-real-data` commit `549198743e7265b333da565ce6990f9241cfd1fd`.
Work branch: `gate-d-workstream`.

Gate A is externally recorded as PASS. At the baseline used here, Gate B is still the next checkpoint in `AGENT_STATUS.md`, so Gate D cannot receive a final PASS. Gate C is also not yet an externally validated upstream source for transit stop/pattern inputs.

## Independent audit finding

The previous `scripts/08_candidate_routes.py` was not a routing pipeline. It contained manually authored values for route kilometres, runtimes, population coverage, OD capture and qualitative recommendation labels for eight variants, including a preselected "Raccomandata" / "PARETO-OTTIMALE" figure-8. These values are **INVALIDATED** and cannot support Gate D, E or F.

## Corrections introduced

1. `scripts/08_candidate_routes.py` now fails closed instead of regenerating invalid legacy route metrics.
2. `scripts/gate_d_route_integrity.py` builds a directed graph from the real OSM highway GeoJSON, projects geometry to EPSG:32632 before measuring length, respects explicit OSM access restrictions and oneway tags, and routes ordered candidate waypoints over the graph.
3. Candidate waypoint coordinates must carry an explicit epistemic status: `FACT`, `RECONSTRUCTED` or `ASSUMPTION`.
4. Route distance and geometry are labelled `DERIVED_OSM`.
5. Pure running time is labelled `MODEL OUTPUT`; where `maxspeed` is absent, road-class speed is explicitly `ASSUMPTION_BY_HIGHWAY_CLASS`. Even where OSM `maxspeed` exists, the generated running time is not promoted to observed fact.
6. Missing width, lanes, maxheight, maxweight and maxwidth attributes are retained as uncertainty flags; affected routed kilometres contribute to `uncertain_road_km` rather than being silently treated as proven bus-compatible.
7. Tests now reject the old hard-coded metric/recommendation tokens, verify oneway directionality, reject footways and private roads, require epistemic statuses and ensure missing maxspeed remains an explicit assumption.

## What is and is not verified

Verified in code/audit:
- the previous Gate D candidate results were hard-coded and invalid;
- the replacement computes metric lengths only after projection to EPSG:32632;
- graph construction is directional and excludes explicit access restrictions;
- candidate definitions cannot smuggle in precomputed km or runtime because the routing script only accepts ordered waypoint inputs;
- modelled speed provenance is separated from OSM-derived distance provenance.

Not yet verified, therefore blocking final PASS:
- execution of the full real-road route pipeline against validated Gate C candidate stop/pattern inputs;
- network completeness outside the current OSM core bbox for candidates reaching Ravellino, Cisano, Caprino/Celana or other external territory;
- actual bus suitability of narrow roads, turning radii, bridge load/height constraints and other physical constraints where OSM tags are absent;
- observed/calibrated bus running times against official GTFS trip times or another observed source;
- route topology alternatives generated without embedding a preference for the figure-8;
- road closures or temporary deviations separated from ordinary network conditions.

## Epistemic status

- OSM highway geometry: `FACT` upstream / `DERIVED` extract.
- Routed geometry and route-km: `DERIVED`.
- Candidate waypoints: `FACT`, `RECONSTRUCTED` or `ASSUMPTION` per input row.
- Running time: `MODEL OUTPUT`.
- Default road-class speeds: `ASSUMPTION`.
- Missing physical road constraints: `FIELD CHECK` / uncertainty, never treated as confirmed suitability.
- All numbers formerly embedded in the legacy candidate list: `INVALIDATED`.

## Exact closure criteria for Gate D

A final Gate D PASS requires all of the following:

1. Gate B road/spatial inputs are externally PASS or the Gate D result remains explicitly blocked by Gate B.
2. Gate C provides validated official GTFS stop/pattern inputs for the relevant lines, or every non-GTFS candidate waypoint is explicitly `ASSUMPTION`.
3. At least the existing D184/D185 baseline and each serious candidate topology are routed end-to-end on the real directed road graph with no disconnected manual geometry patches.
4. The OSM acquisition extent covers every routed candidate plus a defensible context buffer.
5. Route-km and geometry are reproducible and tests demonstrate failure on wrong CRS, illegal direction, explicit access restriction and disconnected candidates.
6. Physical uncertainties that can determine bus feasibility are either resolved from authoritative road data / field verification or quantified as `uncertain_road_km` and kept out of definitive feasibility claims.
7. Running-time calibration is compared with real scheduled/observed bus travel times; any residual speed model remains clearly `MODEL OUTPUT`.
8. No route is called recommended, optimal, feasible or infeasible merely because a manually chosen constant says so; those conclusions must be downstream products of measured constraints and Gate E/F trade-offs.
