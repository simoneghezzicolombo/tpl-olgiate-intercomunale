from itertools import product
from decimal import Decimal
import pytest
from src.phase2_rt031_budgeted_walk_search_v3 import search_walks
from src.phase2_rt031_rt023_pairwise_compatibility_v3 import LEGAL


def fixture():
    cat={'a':dict(source_stop_id='A',target_stop_id='B'),
         'b':dict(source_stop_id='B',target_stop_id='A'),
         'c':dict(source_stop_id='B',target_stop_id='C'),
         'd':dict(source_stop_id='C',target_stop_id='B')}
    pairs=[dict(left_realization_id=a,right_realization_id=b,status=LEGAL) for a in cat for b in cat
           if cat[a]['target_stop_id']==cat[b]['source_stop_id']]
    stops={r:{v['source_stop_id'],v['target_stop_id']} for r,v in cat.items()}
    return cat,pairs,dict.fromkeys(cat,1),stops


def test_matches_independent_bounded_walk_enumeration_with_repeated_edges():
    cat,pairs,w,stops=fixture()
    got=search_walks(cat,pairs,w,stops,budget_m=6,max_expansions=10000,
        history_locality_certified=True,atomic_legality_certified=True)
    brute={}
    arcs={(p['left_realization_id'],p['right_realization_id']) for p in pairs}
    for n in range(1,7):
        for path in product(cat,repeat=n):
            if all(p in arcs for p in zip(path,path[1:]+path[:1])):
                key=frozenset().union(*(stops[r] for r in path))
                brute[key]=min(brute.get(key,n),n)
    assert got['exhaustive']
    assert {frozenset(r['available_stop_ids']):Decimal(r['minimum_found_distance_m']) for r in got['candidates']}==brute
    all_stops=next(r for r in got['candidates'] if len(r['available_stop_ids'])==3)
    assert len(all_stops['realization_ids'])==4  # branching out-and-back is allowed


def test_truncation_cannot_claim_optimality_or_production_pass():
    cat,pairs,w,stops=fixture()
    got=search_walks(cat,pairs,w,stops,budget_m=6,max_expansions=1,
        history_locality_certified=True,atomic_legality_certified=True)
    assert got['status']=='RESOURCE_LIMIT_INCOMPLETE'
    assert not got['production_search_pass']


def test_missing_pair_fails_closed():
    cat,pairs,w,stops=fixture()
    with pytest.raises(ValueError):search_walks(cat,pairs[1:],w,stops,budget_m=6,max_expansions=10,
        history_locality_certified=True,atomic_legality_certified=True)
