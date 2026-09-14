"""Exact one/two independent movement comparison within a supplied witness pool.

This is physical distance / conditional availability aggregation, not service
equivalence or a proof about routes missing from the upstream truncated search.
"""
from decimal import Decimal
from itertools import combinations


def enumerate_portfolios(candidates, *, distance_budget_m):
    budget = Decimal(str(distance_budget_m))
    if not budget.is_finite() or budget <= 0:
        raise ValueError('positive finite budget required')
    source = {}
    for row in candidates:
        sid = row['stop_set_id']
        stops = row['available_stop_ids']
        cost = Decimal(str(row['minimum_found_distance_m']))
        if not isinstance(sid, str) or not sid or sid in source:
            raise ValueError('unique source identity required')
        if not stops or any(not isinstance(s, str) or not s for s in stops) or len(set(stops)) != len(stops):
            raise ValueError('unique nonempty stop identities required')
        if not cost.is_finite() or cost <= 0 or not row.get('realization_ids'):
            raise ValueError('positive witnessed physical distance required')
        source[sid] = (frozenset(stops), cost)
    if not source:
        raise ValueError('empty witness pool')
    # Keep all feasible portfolio identities, including equal-cost alternatives.
    portfolios = []
    summaries = {}
    considered = {1: 0, 2: 0}
    for size in (1, 2):
        for ids in combinations(sorted(source), size):
            considered[size] += 1
            cost = sum((source[s][1] for s in ids), Decimal(0))
            if cost > budget:
                continue
            stops = frozenset().union(*(source[s][0] for s in ids))
            key = tuple(sorted(stops))
            portfolios.append({'source_walk_ids': list(ids), 'movement_count': size,
                               'distance_m': str(cost), 'available_stop_ids': list(key)})
            old = summaries.get(key)
            if old is None or cost < old['cost']:
                summaries[key] = {'cost': cost, 'witnesses': [list(ids)]}
            elif cost == old['cost']:
                old['witnesses'].append(list(ids))
    return {'portfolios': portfolios,
            'availability_summaries': [
                {'available_stop_ids': list(stops), 'distance_m': str(v['cost']),
                 'minimum_distance_witnesses': v['witnesses']}
                for stops, v in sorted(summaries.items())],
            'considered_by_movement_count': considered,
            'pool_size': len(source),
            'domain': 'ALL_SINGLETONS_AND_UNORDERED_DISTINCT_PAIRS_OF_SUPPLIED_WITNESSES',
            'within_pool_enumeration_complete': True,
            'general_multimovement_search_complete': False,
            'passenger_service_assigned': False,
            'service_equivalence_claimed': False}
