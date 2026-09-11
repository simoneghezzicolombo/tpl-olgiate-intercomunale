# RT-031 linked service network and historical calibration

Continuation of #79 / PR #80 at physical checkpoint
`737391a439e043c933b229da5dc13c6027bc1bb6`. Scope: address independent-review B1
(whole-network identity) and C1 (physical status versus service completeness).

## Linked network contract

`src/phase2_rt031_service_network_v3.py` binds explicit directed macro incidence
to ordered RT-023 atom occurrences and RT-030 source visits. It calls the existing
physical composer; it does not replace its restriction or relevance proofs.
Keyed input rows may be reordered, but the ordering inside expansions, patterns
and event sequences remains significant. Parallel macro edges, self-loops and
repeated traversals retain identity. Unused macro incidence and inconsistent
endpoints are rejected. Full bound payloads and their hashes must match.

Service components are explicitly declared finite scenarios. Each event points
to an exact atomic occurrence and has separately declared pickup, dropoff,
passenger-through, vehicle-through, event kind and evidence. Fractional RT-030
positions survive through the existing occurrence binder. Two boundary records
at the same physical location remain distinct; nothing derives same-service-event
equivalence from location correspondence. Timing and compulsory-alight events
survive the topology quotient.

Component-level onboard event pairs require physical legality, matching declared
applicability, public traversal and explicit passenger continuity at intervening
events. They are not timetable journeys. Unknown context or physical legality
emits no positive onboard pair. Public/deadhead and unknown service state never
become passenger traversal rights. Cross-component transfer relations stay null.
Patterns are labels/subsequences referencing a component's declared events; they
do not override its eligibility or manufacture a union of alternative variants.
Different operating variants require separately declared components/contexts.

An explicitly declared movement references one entire component and a positive
integer multiplicity or UNKNOWN. Two public labels may reference one component
and one movement without doubling its distance. Two separately declared movement
instances do double traversal distance. Missing assignments, multiplicities,
context or vehicle continuity leave movement distance null. Distances here are
scenario traversal distances, never annual bus-km, cycle times or schedules.

The whole-network hash includes incidence, exact expansions, component/event
semantics, applicability, pattern membership, movement instances, multiplicities
and evidence. It is a conservative label-preserving identity, not graph-isomorphism
deduplication. No equivalent-state compression is introduced.

Outputs keep distinct namespaces:

- `physical_composition_status`: existing scoped road legality;
- `service_definition_complete` per component: whether supplied service fields/context
  are known, not a claim that those choices are observed or recommended;
- `service_relations_complete`: a complete definition plus certified physical
  composition within its declared scope; unknown road legality keeps this false;
- `movement_assignment_complete`: whether explicit movement accounting is supported;
- `production_rt031_pass=false`: this bounded representation checkpoint does not
  certify a real operating network or authorize search.

All positive service/movement scenarios in this checkpoint are controlled tests.
No real RT-023 atom has been assigned a public service, pickup/dropoff, through
continuity, movement, frequency or timetable by this work.

## Historical D184/D185 inventory

`scripts/phase2_audit_rt031_historical_service_calibration_v3.py` pins eight existing
Arriva GTFS source files by SHA256. This is the historical feed version 20251217,
dated 2026-01-01 through 2026-06-08. It is not evidence of current September service.

The complete route-specific inventory preserves every published trip and stop-time
row, including stop identity, sequence, pickup/dropoff, times, direction, shape,
block and calendar references. It does not collapse trips with the same stop list.
Shape manifests preserve ordered-source hashes, not an invented road match.

Verified historical results:

- 42 trips: D184 15, D185 27;
- 541 stop occurrences, all preserved;
- 18 direction/shape/pickup/dropoff profiles and 18 referenced shapes present;
- no repeated stop IDs inside these 42 source trips (controlled tests still cover revisits);
- two trips have a nonempty block ID; no onboard interlining is inferred from it;
- all published pickup/dropoff codes in this subset are 0, retained literally.

Full trip-payload SHA256:
`e4a7ca44c10cdcac9142f5ce35e5392a3e907e9bb728bfa42c7e6e956364671c`.
Shape-manifest SHA256:
`5bb5184e72b3b19e5b4be9994b0cc94ce2aa2e16ed9ac2afd9b5a348251775b9`.

Physical turn/attachment calibration and historical-to-frozen stop mapping remain
OPEN. A GTFS shape is not certified RT-017 edge history, and a historical stop ID
is not a current frozen stop identity. Neither count nor spacing becomes a target.

## Reproduce

```sh
PYTHONPATH=.:src python -m pytest tests/test_phase2_rt031_service_network_v3.py tests/test_phase2_rt031_historical_service_calibration_v3.py -q
PYTHONPATH=. python scripts/phase2_audit_rt031_historical_service_calibration_v3.py --out /tmp/history-a
PYTHONPATH=. python scripts/phase2_audit_rt031_historical_service_calibration_v3.py --out /tmp/history-b
diff -r /tmp/history-a /tmp/history-b
```

Next external review should attack whole-network collisions, interlining versus
separate movements, service-event provenance and unknown applicability. Production
declarations still need an evidence-backed operating domain, real calibration,
repetition/equivalence rules, objective semantics and authorized stopping criteria.
RT-029 remains unchanged; no new search, Pareto, locality forcing or winner.
