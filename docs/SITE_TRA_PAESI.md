# Tra Paesi — site contract

## Purpose

`Tra Paesi` is the public-facing decision explorer for Phase 2. Its job is to make a complex decision understandable without turning the methodology into a hidden score.

The first screen must answer three questions in under a minute:

1. What problem are we trying to solve?
2. What are the four finalist configurations?
3. What actually changes between any two of them?

## Human decision model

The four finalists are presented as a 2 × 2, not as four unrelated cards:

- topology: `two_independent_loops` vs `interlined_figure8`
- service span: `16h` vs `18h30`

No topology is labelled simpler or better until the certified finalist simplicity diagnostic supports that statement.

## Epistemic guards

The site must not:

- create a weighted composite score;
- declare a PRIMARY or RUNNER-UP before the finalizer;
- treat current D184/D185 continuity as a selection criterion;
- invent route geometry from stop coordinates;
- infer empirical delay probabilities from the engineering sensitivity grid;
- visually compare baseline V4 coverage and finalist coverage as if they were directly interchangeable unless a certified comparison interface establishes semantic comparability.

## Current-service source

Baseline: `PHASE 2 — CURRENT-SERVICE BASELINE V4`, PASS.

Evidence commit:

`95d99b52bff4558c6ab40b5514fa6d09ba3b1e50`

CI run:

`33900806778`

The site currently uses the certified V4 municipality coverage values and the certified physical-stop count. The current-service baseline is presented as `Da dove partiamo`, not as a fifth finalist.

## Finalist source

The public 2 × 2 currently uses only already-established span-level metrics from Final Policy Dry Run V3. Topology-specific structural differences are intentionally left pending.

The site must consume the A workstream only after that workstream is PASS. Desired source-closed fields per finalist are:

- stable finalist identifier and topology family;
- service span;
- public route identifier(s);
- ordered public stop sequence;
- certified stop/anchor coordinates where available;
- first departures and exact clockface departures;
- route overlap;
- public return to the station;
- technical closure, separately labelled if present;
- Stage F engineering robustness summary.

If certified road geometry is absent, the geographic layer may show certified points and the schematic layer may show stop order, but no road-following polyline may be invented.

## Visual hierarchy

1. **Hero:** the decision is two questions, not four boxes.
2. **Oggi:** territorial inequality in the current network, with walking-threshold switch.
3. **La scelta:** topology × service-span matrix.
4. **Cosa cambia davvero?:** compare any two finalists and suppress identical dimensions.
5. **Decision rules:** explain access, equity, robustness and simplicity without a master score.
6. **Evidence:** provenance and status are available but secondary to comprehension.

## Naming

Working public name: **Tra Paesi**.

The name is deliberately municipality-neutral and avoids framing the project around Merate or any single administrative centre.
