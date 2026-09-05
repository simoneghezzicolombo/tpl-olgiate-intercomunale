# RT-016 — Border-neutral catchment population V3: PASS

Status: **PASS**

## Validated computational head

`3eaa227fc7a3cd3f82a9c3161ac4827bc32b862a`

## CI evidence

- Workflow run: `33971396163`
- Job: `101320433178`
- Conclusion: `success`
- Unit tests: **18 passed**
- Controlled audit verdict: **PASS**
- Validation artifact: `9971024216`
- Artifact digest: `sha256:2937c60aec0280ae1837bc3f763103d5ac45acd2e3b93a949cc75235b1152fe9`

## Contract proven by the controlled audit

All ten audit checks passed:

1. default 12-minute / 4.8 km/h envelope equals 960 m;
2. municipalities are discovered geometrically, without a hand-picked neighbour list;
3. municipalities outside the envelope are excluded;
4. the five-municipality core set remains separate and preserved;
5. external municipalities remain a separate spillover set;
6. calibration of an external envelope fragment uses the full-municipality WorldPop sum, so the fragment is not inflated to the municipality's complete POSAS total;
7. population units covered by multiple stops are deduplicated;
8. core covered population remains a separate quantity;
9. external spillover population remains a separate quantity;
10. total catchment population is exactly core covered population plus external spillover population.

## Real-data materialization contract

`scripts/phase2_build_border_neutral_catchment_population_v3.py` is the real-data materializer. It is designed to consume the already validated Gate A/B inputs:

- official ISTAT 2026 municipal boundaries;
- national WorldPop 2020 100 m raster;
- official ISTAT POSAS 2025 municipality totals;
- validated Gate B core population cells.

The Gate B core cells are preserved rather than regenerated. External municipalities are discovered from geometry and external cells are calibrated with each municipality's full WorldPop mass before restricting to the catchment envelope.

## Scope boundary

This 960 m buffer around the five-municipality core is sufficient to prevent administrative-border truncation for passenger stops located inside the core. If a future candidate contains a passenger stop outside the core, the envelope must be rematerialized from that explicit stop/service geometry using the same contract.

RT-016 does not add interchange logic, does not create or relocate passenger stops and does not change the parallel stop-source completeness work.

## Decision semantics

External spillover is an additional measurable benefit. It cannot satisfy or replace the five core municipal service obligations and is not automatically promoted to a mandatory Pareto dimension by this RT.
