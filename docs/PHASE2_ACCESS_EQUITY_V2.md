# Phase 2 Access and Equity V2

This workstream materialises source-closed population-access evidence for every
Structural Catalog V2 scenario. It is an input to the later passenger GJT,
equity and robustness stages. It does not rank a topology, choose a service
policy, infer demand or produce a recommendation.

## Population universe

The denominator is the validated Stop Universe V2 building-section population
layer:

- 4,348 building-section population units;
- 22,820.839937 located model residents;
- the 93.160063-person POSAS residual remains explicitly unlocated.

A population unit can fall within multiple stop catchments. Scenario coverage
uses a set union and counts each unit exactly once.

## Explicit stops only

Coverage uses only stop anchors explicitly listed in each scenario's public
routes. Anchors merely intercepted by a shortest path are not promoted to
scheduled stops. The rail hub is not assigned a bus-stop catchment by
heuristic proximity.

For `scheduled_extensions`, the output exposes two variants:

- `public`: the base public stop set;
- `public_plus_extensions`: the base set plus explicit extension stops.

The service-policy stage can therefore decide whether the extension variant is
relevant from the already-declared extension share. This workstream itself
does not choose that policy.

## Threshold semantics

The Stop Universe V2 membership tables certify:

- proposed-stop unit membership through 10 minutes;
- existing-stop unit membership through 12 minutes.

Therefore 5, 8 and 10 minute scenario coverage is exact relative to the frozen
membership inputs. The 12 minute scenario field is intentionally named
`conservative_lower_bound`: it combines existing-stop memberships through 12
minutes with proposed-stop memberships only through 10 minutes. It must not be
presented as exact 12-minute proposed-stop coverage.

## Municipality equity

The output preserves separate coverage shares for Brivio, Calco, Olgiate
Molgora, Santa Maria Hoè and La Valletta Brianza and reports the worst-served
municipality at each threshold. This is candidate-network evidence only.

It is not yet the final non-regression test against current service. Current
timetable stop identity is only partially spatially addressable, so the later
baseline comparison must remain restricted to the source-closed overlapping
identity universe rather than filling unresolved stops with nearest-neighbour
or fuzzy matches.

## Prohibitions

This stage:

- does not treat residents as passengers;
- does not downscale ISTAT municipal OD to buildings or stops;
- does not use S8 demand weights;
- does not select a topology, stop set or service policy;
- does not construct an exact timetable;
- does not select a primary or runner-up.

All CSV output is written as deterministic gzip and the workflow rebuilds it
byte-for-byte before persisting evidence.
