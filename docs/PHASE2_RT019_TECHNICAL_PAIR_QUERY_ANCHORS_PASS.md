# RT-019 PASS — Technical pair-query anchors and elementary corridor reduction V3

**Verdict:** PASS

## Validated computational head

`0bfceb4f2392f20421ff534f091e3b8f9ee91b6b`

The earlier head `1c6ac8a081ee4683a273d4c9f5e0b342e2828671` passed compilation and all 14 focused tests but its audit serialization failed because a pandas/numpy boolean was left as a non-built-in scalar in the JSON payload. The subsequent commit normalised audit checks to built-in Python `bool` values. This was an audit-output serialization defect, not a change to routing, pair-completeness or elementarity semantics.

## GitHub Actions evidence

- Workflow: `Phase 2 Elementary Corridor Anchors V3`
- Successful run: `33974808698`
- Job: `101329521389`
- Conclusion: `success`
- Focused tests: **14 passed**
- Compile: PASS
- RT-018 compatibility audit: PASS
- Audit contract validation: PASS
- Deterministic rebuild: PASS
- Anti-bias and lineage guards: PASS
- Artifact upload: PASS

## Artifact evidence

- Artifact ID: `9971993790`
- Artifact name: `phase2-elementary-corridor-anchors-v3-validation`
- Artifact digest: `sha256:a837298ab00d152012c26580d2cd68d8c324cd3ac25c8d46d21fce60d580b9c9`
- Artifact expiry: `2026-12-04T15:26:30Z`

The downloaded artifact was independently opened and inspected after the workflow completed.

## Validated counts

From the real RT-018 stop-attachment compatibility evidence:

- final operational stop places: **36**;
- automatic conventional technical pair-query anchors: **35**;
- automatically excluded special-service stops: **1**;
- complete directed technical pair requests through RT-010: **1,190**;
- unordered pair identities: **595**.

## Validated semantic safeguards

All validation checks are true and the following prohibited claims/actions remain false:

- no service terminus/capolinea selected;
- no route topology selected;
- no figure-eight topology forced;
- no timetable or headway selected;
- no special-service stop automatically included in the conventional anchor universe;
- no interchange logic added;
- no PRIMARY or RUNNER-UP selected.

A pair-query anchor is therefore only a technical exhaustive road-routing source/target identity. Compatibility with RT-010's `routing_terminal_id` field must not be read as service-terminal status.

## Elementary reduction semantics validated

The focused test suite confirms that:

1. exact RT-018 ordered stop occurrences, not Euclidean proximity, determine intermediate-stop status;
2. A→B with no third conventional stop is elementary;
3. A→C with an ordered A/B/C occurrence is decomposable via B;
4. repeated source/target occurrences do not create a false intermediate stop;
5. repeated third-stop occurrences remain explicit and make a corridor decomposable;
6. a special-service interior occurrence does not decompose the default conventional corridor contract;
7. missing endpoint occurrence blocks elementarity;
8. multiple alternatives for the same direction are evaluated individually, so one elementary admitted alternative preserves directional availability;
9. RT-009 reciprocal undirected eligibility still requires elementary admitted availability in both directions;
10. decomposable corridor evidence is retained in the audit rather than deleted.

## Territorial limitation

**RT-019 does not yet authorize a real territorial elementary structural graph.**

The validated audit status remains:

`BLOCKED_PENDING_RT017_PASS_CORRIDOR_CORPUS`

Before territorial use, the final 36-stop layer must be rebound to Agent A's frozen RT-017 border-neutral road graph. Alpha must then rematerialize the 35 conventional pair-query anchors, the 1,190 complete directed pair requests, RT-006 corridor alternatives, RT-018 exact stop occurrences, RT-019 elementary reduction and RT-009 reciprocal structural links on that same frozen graph epoch.

No final network, service pattern or passenger timetable has been selected by RT-019.
