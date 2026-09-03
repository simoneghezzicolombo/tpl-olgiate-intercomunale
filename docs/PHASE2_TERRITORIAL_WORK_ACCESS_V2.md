# Phase 2 Territorial Work Home Access V2

## Why this layer exists

The S8 feeder workstream contains 1,882 workers, but those workers are only one part of the observed 2021 work-commuting universe of the five core municipalities.

The certified ISTAT 2021 profile contains 8,754 resident workers:

- 1,315 working in their municipality of residence;
- 1,055 working in another one of the five core municipalities;
- 1,882 working in a municipality directly served by S8;
- 4,502 working in another external municipality.

This layer makes the broader territorial work-demand context explicit without pretending that municipal OD identifies a building, stop or route.

## Two different quantities

### Model-capacity upper bound

For each municipality and walking threshold, Access/Equity V2 provides the number of modeled residents covered by the public stop set. The maximum possible number of resident workers that could fit inside that covered-resident count is:

`min(observed resident workers, modeled covered residents)`

The scenario value sums this quantity across the five municipalities.

This is a **capacity upper bound** only. The resident population is itself a dasymetric model output and the workers are not spatially observed, so the result is not an observed worker-access count and not a statistical confidence interval. The unconditional observed lower bound remains zero.

### Population-proportional sensitivity

A separate sensitivity applies each municipality's resident walking-coverage share to its observed worker counts:

`worker count × modeled resident coverage share`

This is explicitly labelled:

`EXPLICIT_ASSUMPTION_WORKERS_DISTRIBUTED_LIKE_MODELED_RESIDENTS_WITHIN_EACH_ORIGIN_MUNICIPALITY`

It is calculated for all resident workers and separately for SELF, OTHER_CORE, CORE_LOCAL, S8_DIRECT and OTHER_EXTERNAL workers. Those sensitivity categories are additive because the same municipality-level assumption is applied to mutually exclusive observed OD categories.

The sensitivity is useful for comparing how different stop sets would expose the broader work-demand universe if workers were spatially distributed like residents. It must never be relabelled as observed 2021 worker accessibility.

## What this still does not say

Both quantities concern the **home endpoint only**. They do not establish that the work endpoint is reachable by the candidate bus network, that a worker would choose public transport, that a particular route would be used or that a full door-to-door trip is competitive.

The work matrix also excludes complete school, healthcare, shopping, services and leisure demand. Those purposes remain separate until evidence-backed inputs exist.

## Downstream use

The audited output is suitable as an additional territorial-demand context dimension in Pre-GJT screening. The model-capacity upper bound may be retained as a conservative capacity envelope. The population-proportional estimate may be used only as a declared sensitivity scenario, never as the empirical baseline and never as route-level passenger demand.
