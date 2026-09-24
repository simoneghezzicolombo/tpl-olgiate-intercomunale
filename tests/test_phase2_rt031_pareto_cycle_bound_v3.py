import pandas as pd
import pytest
from phase2_rt031_pareto_cycle_bound_v3 import derive, CycleBoundError


def fixture(interiors):
    edges = [("L1", "A", "B"), ("L2", "B", "C"), ("L3", "A", "C")]
    links = pd.DataFrame(edges, columns=["structural_link_id", "terminal_a", "terminal_b"])
    patterns, realizations = [], []
    for link_id, a, b in edges:
        seq = [a] + list(interiors.get(link_id, [])) + [b]
        for direction, stops in (("A_TO_B", seq), ("B_TO_A", list(reversed(seq)))):
            patterns.append({"realization_id": link_id + direction, "structural_link_id": link_id, "direction": direction, "alternative_ordinal": 1, "ordered_passenger_stop_ids": ";".join(stops)})
            realizations.append({"structural_link_id": link_id, "direction": direction, "distance_m": 10.0})
    return links, pd.DataFrame(patterns), pd.DataFrame(realizations)


def test_zero_interiors_implies_zero_cycle_rank_bound():
    l, p, r = fixture({})
    _, audit = derive(l, p, r, expected_vertices=3, expected_links=3)
    assert audit["safe_pareto_cycle_rank_upper_bound"] == 0


def test_two_global_interiors_imply_two_bound():
    l, p, r = fixture({"L1": ["X"], "L2": ["Y"]})
    _, audit = derive(l, p, r, expected_vertices=3, expected_links=3)
    assert audit["safe_pareto_cycle_rank_upper_bound"] == 2


def test_same_interior_on_multiple_edges_counts_once():
    l, p, r = fixture({"L1": ["X"], "L2": ["X"]})
    _, audit = derive(l, p, r, expected_vertices=3, expected_links=3)
    assert audit["safe_pareto_cycle_rank_upper_bound"] == 1


def test_nonpositive_burden_fails_closed():
    l, p, r = fixture({})
    r.loc[r.structural_link_id == "L1", "distance_m"] = 0.0
    with pytest.raises(CycleBoundError, match="strictly positive"):
        derive(l, p, r, expected_vertices=3, expected_links=3)


def test_input_order_invariance():
    l, p, r = fixture({"L1": ["X"], "L2": ["Y"]})
    t1, a1 = derive(l, p, r, expected_vertices=3, expected_links=3)
    t2, a2 = derive(l.iloc[::-1], p.iloc[::-1], r.iloc[::-1], expected_vertices=3, expected_links=3)
    pd.testing.assert_frame_equal(t1, t2)
    assert a1 == a2
