from itertools import product
from decimal import Decimal
import pytest
from src.phase2_rt031_complete_chain_distance_v3 import optimize_chain
from src.phase2_rt031_rt023_pairwise_compatibility_v3 import LEGAL, ILLEGAL, UNKNOWN


def run(layers, statuses, distances, closed=False, **flags):
    by = {(str(i), 'F'): [{'realization_id': r} for r in ids] for i, ids in enumerate(layers)}
    rows = [dict(left_realization_id=a, right_realization_id=b, status=s) for (a,b),s in statuses.items()]
    return optimize_chain(list(by), by, rows, distances, closed=closed,
                          atomic_legality_certified=flags.get('atomic', True),
                          history_locality_certified=flags.get('history', True))


@pytest.mark.parametrize('closed',[False,True])
def test_exhaustive_independent_product_oracle(closed):
    layers = [('a','b'),('c','d'),('e','f')]
    distances = dict(zip('abcdef', [1,4,3,2,5,1]))
    pairs = [(a,b) for l,r in zip(layers,layers[1:]) for a in l for b in r]
    if closed: pairs += [(a,b) for a in layers[-1] for b in layers[0]]
    # Exhaust every possible compatibility graph, independently brute-force all routes.
    for mask in range(1 << len(pairs)):
        statuses = {p: LEGAL if mask & (1 << i) else ILLEGAL for i,p in enumerate(pairs)}
        feasible = []
        for seq in product(*layers):
            arcs = list(zip(seq,seq[1:])) + ([(seq[-1],seq[0])] if closed else [])
            if all(statuses[p] == LEGAL for p in arcs):
                feasible.append((sum(distances[r] for r in seq),seq))
        got = run(layers,statuses,distances,closed)
        assert got['compatible_sequence_count'] == len(feasible)
        if feasible:
            best = min(feasible)
            assert (Decimal(got['minimum_distance_m']),tuple(got['realization_ids'])) == best
        else: assert got['minimum_distance_m'] is None


def test_cycle_seam_cannot_be_omitted():
    states = {('a','b'):LEGAL, ('b','a'):ILLEGAL}
    assert run([['a'],['b']],states,{'a':1,'b':1})['compatible_sequence_count'] == 1
    assert run([['a'],['b']],states,{'a':1,'b':1},True)['compatible_sequence_count'] == 0


@pytest.mark.parametrize('status',[None,UNKNOWN])
def test_unknown_is_not_infeasible_or_optimal(status):
    rows = {} if status is None else {('a','b'):status}
    got = run([['a'],['b']],rows,{'a':1,'b':1})
    assert not got['exact'] and got['compatible_sequence_count'] is None


@pytest.mark.parametrize('flag',['atomic','history'])
def test_uncertified_scope(flag):
    assert not run([['a']],{}, {'a':1}, **{flag:False})['exact']


def test_repeated_traversals_count_each_occurrence():
    got = run([['a'],['b'],['a']],{('a','b'):LEGAL,('b','a'):LEGAL},{'a':'1.2','b':'2.3'})
    assert got['minimum_distance_m'] == '4.7'
    assert got['realization_ids'] == ['a','b','a']


@pytest.mark.parametrize('distance',['NaN','Infinity',0,-1])
def test_bad_distance(distance):
    with pytest.raises(ValueError): run([['a']],{}, {'a':distance})
