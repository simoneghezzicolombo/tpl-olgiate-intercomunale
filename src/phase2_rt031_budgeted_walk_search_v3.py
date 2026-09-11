"""Budget-bounded physical closed-walk labels; availability is not public service.

Exact state dominance only for additive distance and union of available stop IDs,
under certified pairwise history locality. Root realization is retained, so cycle
rotation is not implicitly a service-equivalence quotient. Resource truncation is
explicit and never becomes an exhaustive search claim.
"""
from decimal import Decimal
import heapq
from src.phase2_rt031_rt023_pairwise_compatibility_v3 import LEGAL, ILLEGAL


def search_walks(catalog, pairs, weights, stop_sets, *, budget_m, max_expansions,
                 history_locality_certified, atomic_legality_certified):
    if history_locality_certified is not True or atomic_legality_certified is not True:
        raise ValueError('certified physical scope required')
    if type(max_expansions) is not int or max_expansions<=0:
        raise ValueError('positive explicit execution budget required')
    budget=Decimal(str(budget_m))
    if not budget.is_finite() or budget<=0:raise ValueError('positive finite distance budget required')
    ids=sorted(catalog)
    if not ids:raise ValueError('nonempty carrier catalog required')
    costs={r:Decimal(str(weights[r])) for r in ids}
    if any(not c.is_finite() or c<=0 for c in costs.values()):raise ValueError('positive finite weights required')
    stop_ids=sorted(set().union(*(set(stop_sets[r]) for r in ids)))
    bits={s:1<<i for i,s in enumerate(stop_ids)}
    masks={r:sum(bits[s] for s in set(stop_sets[r])) for r in ids}
    index={}
    for p in pairs:
        key=(p['left_realization_id'],p['right_realization_id'])
        if key in index or p['status'] not in (LEGAL,ILLEGAL):raise ValueError('duplicate/unknown pairwise evidence')
        index[key]=p['status']
    adjacent={}
    for r in ids:
        compatible=[]
        for s in ids:
            if catalog[r]['target_stop_id']!=catalog[s]['source_stop_id']:continue
            if (r,s) not in index:raise ValueError('missing relevant pairwise evidence')
            if index[r,s]==LEGAL:compatible.append(s)
        adjacent[r]=compatible
    # All atomic roots enter one global cost queue. No named locality is forced.
    best={};queue=[]
    for root in ids:
        if costs[root]<=budget:
            key=(root,root,masks[root]);best[key]=costs[root]
            heapq.heappush(queue,(costs[root],root,root,masks[root],(root,)))
    results={};expanded=0
    while queue and expanded<max_expansions:
        d,root,last,mask,path=heapq.heappop(queue)
        if d!=best[root,last,mask]:continue
        expanded+=1
        if root in adjacent[last]:
            # Preserve exact rooted witness; per-mask minimum is a physical
            # distance/availability summary only, not a service quotient.
            old=results.get(mask)
            if old is None or (d,path)<old:
                results[mask]=(d,path)
        for nxt in adjacent[last]:
            nd=d+costs[nxt]
            if nd>budget:continue
            nm=mask|masks[nxt];key=(root,nxt,nm)
            if key not in best or nd<best[key]:
                best[key]=nd
                heapq.heappush(queue,(nd,root,nxt,nm,path+(nxt,)))
    exhaustive=not queue
    rows=[]
    for mask,(distance,path) in sorted(results.items()):
        rows.append(dict(available_stop_ids=[s for s in stop_ids if mask&bits[s]],
            minimum_found_distance_m=str(distance),realization_ids=list(path),
            distance_optimality_certified=exhaustive,public_service_assigned=False))
    return dict(contract='RT031_BUDGETED_PHYSICAL_CLOSED_WALK_SEARCH_V3',
        scope='ONE_CLOSED_PHYSICAL_WALK_DISTANCE_AND_AVAILABLE_STOP_UNION_ONLY',
        status='EXHAUSTIVE_WITHIN_DECLARED_PHYSICAL_DOMAIN' if exhaustive else 'RESOURCE_LIMIT_INCOMPLETE',
        exhaustive=exhaustive,expanded_states=expanded,execution_expansion_limit=max_expansions,
        retained_label_count=len(best),pending_heap_entries=len(queue),
        distance_budget_m=str(budget),root_realization_count=len(ids),
        elementary_edge_cap=None,random_search=False,named_locality_forced=False,
        service_equivalence_claimed=False,production_search_pass=False,
        found_stop_set_count=len(rows),candidates=rows)
