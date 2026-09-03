# Gate F deterministic assembly manifest

A mathematically valid Pareto result can still be misleading if the scenario table was edited after assembly or if an upstream fragment was silently replaced. Gate F therefore fingerprints the complete B/C/D/E input chain.

`gate_f_build_inputs.py` writes `outputs/gate_f/assembly_manifest.json` after constructing the canonical scenario table. The manifest records SHA256 hashes for:

- scenario catalog;
- Gate B fragment;
- Gate C fragment;
- Gate D road-eligibility fragment;
- Gate E service-math fragment;
- assembled `gate_f_scenario_metrics.csv`;
- exclusions audit.

It also records baseline ID, exact eligible/excluded scenario IDs and a comparison-scope audit of topology families.

The Gate F Pareto runner verifies every recorded hash before allowing a definitive PASS. If the manifest is missing, an otherwise PASS result is downgraded to `PROVISIONAL / BLOCKED_UNVERIFIED_ASSEMBLY_MANIFEST`. If a manifest exists but any hash fails, execution is refused.

## Anti-cherry-picking scope audit

The manifest reports how many topology families are represented. Fewer than two non-baseline eligible topology families emits `FEWER_THAN_TWO_NONBASELINE_TOPOLOGY_FAMILIES`.

This is deliberately a **warning, not an automatic failure**. A legitimate Gate D result could conclude that only one alternative family is road-feasible. Conversely, merely having two labels does not prove that the scenario search was complete. Final Gate F review must substantively verify that serious alternatives were considered and that inconvenient scenarios were not omitted.

Topology labels never enter the Pareto mathematics.
