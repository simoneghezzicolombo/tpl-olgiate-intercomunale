# Phase 2 — RT-003 Current-Service Baseline Limitation

## Status

**FORMALISED LIMITATION. NOT RESOLVED BY INFERENCE.**

The current-service accessibility evidence is intentionally incomplete and is valid only as a **certified localisable lower bound**.

The current certified snapshot contains:

- D184/D185 timetable rows considered: **51**;
- spatially localisable rows: **12**;
- unresolved or unlocalised rows: **39**;
- exactly localisable current physical clusters: **7**;
- population accessibility lower bound at 5 minutes: approximately **7.69%**;
- at 8 minutes: approximately **15.03%**;
- at 10 minutes: approximately **19.24%**;
- worst-municipality lower bound at the declared thresholds: **0**.

These values do not reconstruct the full current network. They quantify only what the certified current-stop identity and spatial evidence can prove without inventing identities or positions.

## Correct interpretation of non-regression

A candidate that passes a current-service non-regression test against this artifact proves only:

> the candidate is not worse than the **certified localisable lower bound** under the tested metric.

It does **not** prove:

> no municipality is worse than under the complete real current D184/D185 service.

Because the worst-municipality lower bound is zero, the current safeguard can be mathematically non-binding. A PASS must therefore never be translated into a stronger real-world claim.

## Prohibited repairs

RT-003 must not be closed by manufacturing spatial certainty. In particular, do not use:

- fuzzy stop-name matching as identity proof;
- forced nearest-coordinate matching;
- guessed stop placement;
- inferred adjacency across unresolved current-service rows;
- the project station bridge as proof that a different historical station identity was retained.

The 39 unresolved/unlocalised rows remain unresolved unless new certified evidence independently resolves them.

## Required final-report language

Until stronger current-service localisation evidence exists, every final decision report using territorial non-regression must state substantively:

> Territorial non-regression was checked only against the certified localisable current-service lower bound. It does not establish non-regression against a complete spatial reconstruction of the real current D184/D185 service.

This limitation is independent of Stage E operational robustness and must remain visible even after the exact timetable and robustness workstreams pass.
