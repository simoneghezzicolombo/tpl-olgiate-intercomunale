# RT031 one/two independent physical movement comparison

This checkpoint extends the existing affordable-walk evidence to independently
operated physical movements under one shared resource envelope. It enumerates
every singleton and unordered pair of distinct witnesses in the pinned pool.
Two is a declared diagnostic dimension, not a normative maximum number of lines.
No candidate is required to visit a named place or share a particular terminus.

## Evidence and domain

Source branch head `0dc76ea21e511308319fd8ceaf4caf82cc4ad165`, run `34547859460`,
artifact `10179715479`, ZIP SHA256
`6787341d383d10f9083d30047e524838007f3b5f2aa31b85635574efcdea6bb2`.
The 780 source walks were physically replayed upstream but the generating search
stopped at 250,000 expansions with `RESOURCE_LIMIT_INCOMPLETE`. They are known
physical witnesses, not a complete or distance-optimal territorial pool.
Their exact ordered realization IDs remain in the source payload pinned by
SHA256 `b80e27f569b78d61a0cce8b0dbd5afd6723629ccf90e8822768ed4d7f3bd5751`.

RT028 matrix artifact `9991182904`, matrix SHA256
`a47bbce413d056db185180173ab2f05dce0463cb626a2c81f4aff64de91b50c1`.
The approved policy file is hash-locked. Budget is 111,419 annual bus-km.
H30 per movement, 32 departures in the half-open 06–22 window, 260 days remain
the same explicit design assumptions as the source experiment. For two movements,
the distance sum, not either individual distance, must be <= 13,391.706730769...
metres. Depot/deadhead/extra movements are not covered by that necessary screen.

## Semantics

Each component is a separately repeated physical movement. Shared roads are
charged for each movement. Stop/population availability is unioned without
double counting. Neither connectedness nor disconnection creates passenger
through-service or transfers. No boarding eligibility or timetable is assigned.
An identical source witness repeated twice is outside the distinct-pair domain;
this checkpoint does not assess doubled frequency or vehicle sharing.

All feasible portfolio identities are exported. Accessibility is computed once
per exact union of available stop identities. A minimum-distance envelope for
each union is valid only for distance and conditional walking coverage. Every
equal-cost decomposition is retained. More expensive decompositions remain in
the full portfolio table: this envelope is not a service-equivalence reduction,
and cannot support runtime/fleet, S8 or passenger-journey optimization.

The six comparison axes are CORE and worst-core-municipality shares at 5/8/10
minutes plus physical distance. There is no weighted score or component-count
objective. The frontier is nondominated only within this declared physical pool
and conditional metric contract, not the approved final policy tournament.
UNREACHABLE population remains in the denominators; municipality identity is
the source ISTAT code.

Population thresholds reuse RT028/RT029 float32 walk-time representation.
Population sums and share comparisons use the exact decimal weight strings
from the RT028 CSV as integer/fraction arithmetic. This avoids batch-dependent
floating-point accumulation creating false dominance. Exact ratios are exported;
float percentages are display values. A monotone float filter accelerates
candidate comparisons, but all potential dominance is confirmed on the exact
ratios. No tolerance or uncertainty band is introduced. Existing RT029 full
walking/municipal/12-minute diagnostics are regenerated on the resulting frontier;
their float summaries do not decide membership in this exact comparison.

## Reproduction and verification

`PYTHONPATH=.:src python -m pytest tests/test_phase2_rt031_movement_portfolios_v3.py -q`

Run `scripts/phase2_compare_rt031_movement_portfolios_v3.py` with `--pool` pointing
to the pinned `physical_walk_search.json`, `--walk-matrix` to the pinned matrix,
and `--out` to an output directory. The dedicated workflow downloads and verifies
both ZIPs, executes this command twice, and compares every output byte.

Tests compare tiny pools with independent subset enumeration, preserve equal-cost
decompositions, distinguish overlap from double resource charging, retain
unreachable denominators, reject malformed inputs and check exact rational
near-ties against independent pairwise dominance. No full upstream search is rerun.

Outputs: all portfolios and availability envelopes (compressed CSV), exact
conditional frontier, frontier walking/municipal diagnostics and a hash manifest
in `audit.json`. Scope and source incompleteness are explicit in that manifest.

## Remaining boundary

The result can demonstrate concrete multi-movement availability that the earlier
single-walk result omitted. It cannot prove optimum coverage, operational
feasibility, passenger continuity, H30 feasibility including dwell/recovery, or
completeness for arbitrary numbers of services. Source-pool expansion and typed
public-service/timetable binding remain necessary before a final recommendation.
PRIMARY/RUNNER-UP authorization remains false.
