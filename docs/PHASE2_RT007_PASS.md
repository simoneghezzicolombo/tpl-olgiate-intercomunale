# RT-007 PASS · Network Structure Search V3

Verdict: **PASS as algorithmic infrastructure**  
Canonical issue: **#27**  
Branch: `phase2-network-structure-search-v3`  
Base: `phase2-efficient-alternative-corridors-v3`

## Validated contract

RT-007 validates a deterministic abstract network-structure search layer that sits between the restriction-aware corridor library and later territorial/passenger-stop evaluation.

The core accepts only generic terminal IDs, generic unordered terminal-pair links, optional required terminal IDs and optional generic policy-group memberships. It contains no settlement names, no passenger-stop records, no road geometry and no topology winner logic.

Connected edge subsets are generated first. Topology is classified only after generation.

## CI evidence

GitHub Actions run: `33965220687`  
Head commit validated: `2c5fd6760939666ec9ab5b0f352745754a4ff19d`  
Job: `101304033313`  
Artifact: `9969200285`  
Artifact digest: `sha256:ae695cd597957222e8b5b72dcc836113ba8dce5a462f14f0d8448f76bd5eb87f`

All workflow stages passed:

- Python compilation;
- RT-007 unit tests;
- controlled abstract-graph audit;
- audit-contract validation;
- geography / stop / decision leakage guards;
- anti-random guard;
- whitespace check;
- evidence upload.

## Controlled-fixture result

Fixture semantics:

`CONTROLLED_ABSTRACT_FIXTURE_NOT_TERRITORIAL_DATA`

The complete five-vertex abstract graph was enumerated through six selected edges:

- subsets scanned: **847**;
- connected structures retained: **792**;
- PATH: **160**;
- TREE_BRANCHING: **85**;
- CYCLE: **37**;
- UNICYCLIC_BRANCHING: **270**;
- BICYCLIC_ARTICULATED: **135**;
- BICYCLIC_NONARTICULATED: **100**;
- MULTICYCLIC: **5**;
- structures flagged `FIGURE_EIGHT_LIKE`: **15**.

The exact connected-subgraph count is asserted in tests so a later hidden topology filter changes the expected result and fails CI.

A second test requires one generic terminal plus five generic policy groups and still verifies that path, cycle, branching-tree, unicyclic and bicyclic classes all remain possible. Therefore group coverage does not itself prescribe a figure-eight or any other topology.

## Fail-closed behavior

Enumeration controls are explicitly technical:

`TECHNICAL_ENUMERATION_CONTROLS_NOT_POLICY_WEIGHTS`

If the search reaches a subset or output cap before exhausting the requested search space, it returns:

`BLOCKED_ENUMERATION_CAP_REACHED_FAIL_CLOSED`

and does not expose the partial pool as usable candidate evidence.

## Explicit non-claims

This PASS does not authorize:

- a territorial route candidate;
- a complete passenger-stop pattern;
- a topology recommendation;
- a figure-eight recommendation;
- a timetable or headway;
- PRIMARY or RUNNER-UP;
- any comparison against the current-service accessibility baseline.

## Next dependency

A real territorial network search must wait for a corrected upstream routing-terminal universe. Once available, that universe can be mapped into the generic RT-007 interface without changing the structural generator.

The next independent algorithmic task is scalability: determine how to search larger terminal-pair graphs without silently returning a lexicographically truncated subset and without introducing topology-specific heuristics or a composite score.
