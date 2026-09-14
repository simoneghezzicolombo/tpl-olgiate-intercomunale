from decimal import Decimal
import pytest
from src.phase2_rt031_movement_portfolios_v3 import enumerate_portfolios


def walk(sid, stops, cost):
    return dict(stop_set_id=sid, available_stop_ids=stops,
                minimum_found_distance_m=cost, realization_ids=[sid + '_carrier'])


def test_independent_movements_charge_overlap_twice_union_once():
    rows = [walk('a', ['A', 'B'], '3'), walk('b', ['B', 'C'], '4')]
    result = enumerate_portfolios(rows, distance_budget_m=7)
    pair = next(p for p in result['portfolios'] if p['movement_count'] == 2)
    assert pair['available_stop_ids'] == ['A', 'B', 'C']
    assert Decimal(pair['distance_m']) == 7
    assert len(enumerate_portfolios(rows, distance_budget_m='6.999')['portfolios']) == 2


def test_equal_cost_distinct_decompositions_retained():
    rows = [walk('a', ['A'], 2), walk('b', ['B'], 3), walk('c', ['A', 'B'], 5)]
    result = enumerate_portfolios(rows, distance_budget_m=5)
    summary = next(r for r in result['availability_summaries'] if len(r['available_stop_ids']) == 2)
    assert sorted(summary['minimum_distance_witnesses']) == [['a', 'b'], ['c']]
    assert result == enumerate_portfolios(list(reversed(rows)), distance_budget_m=5)
    assert not result['service_equivalence_claimed']


def test_scope_includes_disconnected_components_without_inventing_transfers():
    result = enumerate_portfolios([walk('a', ['A'], 1), walk('b', ['Z'], 1)], distance_budget_m=2)
    assert result['considered_by_movement_count'] == {1: 2, 2: 1}
    assert len(result['portfolios']) == 3
    assert not result['general_multimovement_search_complete']
    assert not result['passenger_service_assigned']


@pytest.mark.parametrize('cost', ['NaN', 'Infinity', '-1', '0'])
def test_bad_distance_rejected(cost):
    with pytest.raises(ValueError):
        enumerate_portfolios([walk('a', ['A'], cost)], distance_budget_m=2)


def test_independent_bruteforce_small_pool():
    rows = [walk(str(i), [str(i % 3), 'common'], str(i + 1)) for i in range(6)]
    result = enumerate_portfolios(rows, distance_budget_m=7)
    expected = {}
    for mask in range(1, 1 << len(rows)):
        picked = [r for i, r in enumerate(rows) if mask & (1 << i)]
        if len(picked) > 2:
            continue
        cost = sum(Decimal(r['minimum_found_distance_m']) for r in picked)
        if cost <= 7:
            expected[tuple(r['stop_set_id'] for r in picked)] = cost
    assert {tuple(r['source_walk_ids']): Decimal(r['distance_m']) for r in result['portfolios']} == expected


def test_duplicate_source_and_stop_fail_closed():
    for rows in ([walk('a', ['A'], 1)] * 2, [walk('a', ['A', 'A'], 1)]):
        with pytest.raises(ValueError):
            enumerate_portfolios(rows, distance_budget_m=4)


def test_threshold_bitmasks_match_native_union_and_equity():
    import numpy as np
    import pandas as pd
    from types import SimpleNamespace
    from scripts.phase2_compare_rt031_movement_portfolios_v3 import threshold_vectors
    from phase2_rt029_v4_metrics import _batch_access_metrics
    substrate = SimpleNamespace(
        population_meta=pd.DataFrame({'population_scope': ['core'] * 4,
            'population_weight_2025': [1., 3., 2., 4.],
            'population_municipality_code': ['x', 'x', 'y', 'y']}),
        stop_index={'A': 0, 'B': 1},
        walk_time_matrix=np.array([[4, 4], [np.inf, 7], [10, np.inf], [np.inf, np.inf]], dtype=np.float32))
    sets = [['A'], ['B'], ['A', 'B']]
    got = threshold_vectors(sets, substrate)
    best = np.column_stack([np.min(substrate.walk_time_matrix[:, [substrate.stop_index[s] for s in stops]], axis=1) for stops in sets])
    w = substrate.population_meta['population_weight_2025'].to_numpy()
    native = _batch_access_metrics(best, w, include_quantiles=False)
    assert np.array_equal(got[:, :3].astype(float), np.column_stack([native[f'share_le_{t}_min'] for t in (5, 8, 10)]))
    from fractions import Fraction
    assert got[2, 2] == Fraction(3, 5)  # unreachable population remains in denominator
    assert got[2, 5] == Fraction(1, 3)  # municipality minimum, not sum of per-route minima


def test_frontier_matches_independent_pairwise_oracle_with_ties():
    import numpy as np
    from scripts.phase2_compare_rt031_movement_portfolios_v3 import pareto_indices
    v = np.array([[0, 1], [1, 0], [1, 1], [1, 1], [0, 0]], dtype=float)
    c = [Decimal(x) for x in ('1', '1', '2', '2', '3')]
    expected = [i for i in range(len(c)) if not any(
        i != j and c[j] <= c[i] and all(v[j] >= v[i]) and
        (c[j] < c[i] or any(v[j] > v[i])) for j in range(len(c)))]
    assert set(pareto_indices(v, c)) == set(expected) == {0, 1, 2, 3}


def test_float_projection_never_decides_near_tie_dominance():
    from fractions import Fraction
    import numpy as np
    from scripts.phase2_compare_rt031_movement_portfolios_v3 import pareto_indices
    a, b = Fraction(1, 2), Fraction(1, 2) + Fraction(1, 10**30)
    assert float(a) == float(b)
    v = np.array([[a, b], [b, a], [a, a]], dtype=object)
    assert set(pareto_indices(v, [Decimal(1)] * 3)) == {0, 1}
