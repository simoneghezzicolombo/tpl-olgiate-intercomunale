# RT-031 typed composition: bounded checkpoint

Epistemic status: DERIVED on explicitly controlled fixtures. Production gate OPEN.
Parent: #79. Base: `8f138f8ea7ac2c1f39e76a79201125f041d69cd5`.
Implements the bounded composition step requested by the Astra architecture review
at `660ed30af9f66cb8567a2c04989ff4d0fc5db091` and its 2026-09-06 deep red-team.

## What this checkpoint establishes

`src/phase2_rt031_typed_composition_v3.py` consumes an explicitly finite ordered
decomposition with directional alternatives. It preserves complete edge occurrence
history, typed service events, pickup/dropoff, public/deadhead segments, route
labels, applicability, attachment provenance and separate passenger/vehicle
continuity. It never reverses evidence or merges prefixes. Lazy Cartesian
iteration avoids materializing the input product; it does not solve the production
search scalability problem. A caller resource limit is always INCOMPLETE.

Finite forbidden edge sequences are checked across any number of boundaries.
An optional transition oracle receives the full prefix. Restriction completeness
and operating context must be explicit; incomplete/unknown evidence cannot become
an exact compatible-domain guarantee. This is a bounded restriction model, not a
claim that the territorial RT-017 conditional/via-way corpus has been imported.

Existing `contract_structure` remains the pure topology quotient. Ordered service
events remain on the directed carrier, including degree-2 timing/compulsory-alight
points. Macro summaries are not dedup keys: the tests distinguish theta/barbell
incidence and retain parallel edges and self-loops. Label-preserving payload
hashing includes the entire composition and evidence. It is a composition identity,
not a whole-network canonical isomorphism key. No cycle rotation or reversal is
treated as equivalent.

Boundary events are merged only using explicit one-to-one correspondence and
matching carrier position, stop, eligibility and operational role. All source
records remain traceable. Identical stop IDs alone never merge real visits.
Attachment matching here verifies certified node-position evidence supplied to
the adapter; production RT-030 segment-offset mapping still needs certification.

Identity-level guaranteed/possible sets are exact only over a nonempty, fully
checked compatible domain with known identity coverage. Empty domains yield no
vacuous guarantee. Public eligibility is checked. Supported onboard event pairs
are computed per realization, with no cross-alternative union presented as a
joint journey promise. Unknown service state gives incomplete passenger relations
even when the road carrier is legal. No timetable reachability is claimed.

Directed pattern traversal length preserves repetitions; unique physical carrier
length is separate. Labels do not multiply a movement. Vehicle-run distance stays
null because run assignment/multiplicity is not supplied. No annual bus-km inferred.

## Verification

Run from repository root:

```sh
PYTHONPATH=.:src python -m pytest tests/test_phase2_rt031_typed_composition_v3.py tests/test_phase2_macro_structure_decoupling_v3.py -q
PYTHONPATH=. python scripts/phase2_audit_rt031_typed_composition_v3.py --out /tmp/rt031-a.json
PYTHONPATH=. python scripts/phase2_audit_rt031_typed_composition_v3.py --out /tmp/rt031-b.json
cmp /tmp/rt031-a.json /tmp/rt031-b.json
```

Tests execute all three red-team counterexamples, with an independent exhaustive
full-tuple oracle for the forbidden-history example. They also cover subdivision,
full macro incidence, deadhead, unknown continuity, repeated visits, exact
boundary provenance, compatibility-filtered intersections, incomplete/empty
domains, resource exhaustion and invalid direction/epoch/attachment evidence.
They are author checks, not an independent Agent A certification.

## Remaining production gates

1. Bind the transition oracle to pinned RT-017 evidence, including unsupported
   conditional/via-way restrictions as UNKNOWN; prove complete relevant history.
2. Map RT-023/030 atomic segment attachments and boundary occurrence correspondence
   onto composed directed carriers with exact lineage, offsets and eligibility.
3. Bind full service multigraph incidence to route/pattern decomposition and
   operational applicability, without inferring vehicle runs or through-service.
4. Obtain independent adversarial review, especially an event-reachability oracle.
5. Complete D184/D185 physical/service calibration only from certified evidence.
6. Declare production search domain, equivalence, repetitions, objectives and
   stopping authority before any territorial search. Current cycle-rank dominance
   bounds do not automatically survive service-semantic objective changes.

RT-029 remains unchanged. No network winner, new Pareto, E7/E8 enumeration, stop
target, locality forcing or production A–F certification is introduced.
