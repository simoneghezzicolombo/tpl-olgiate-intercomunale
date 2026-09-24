import pandas as pd
import pytest

from phase2_macro_structure_decoupling_v3 import (
    RT031ContractError,
    build_link_endpoint_map,
    compile_macro_structures,
    contract_structure,
)


def realizations(edges):
    rows = []
    for lid, a, b in edges:
        rows += [
            {"structural_link_id": lid, "source_stop_place_id": a, "target_stop_place_id": b},
            {"structural_link_id": lid, "source_stop_place_id": b, "target_stop_place_id": a},
        ]
    return pd.DataFrame(rows)


def endpoint_map(edges):
    return build_link_endpoint_map(realizations(edges))


def test_long_path_contracts_to_one_macro_edge_without_deleting_passenger_vertices():
    edges = [("L1", "A", "B"), ("L2", "B", "C"), ("L3", "C", "D"), ("L4", "D", "E")]
    r = contract_structure("S", [e[0] for e in edges], ["A", "B", "C", "D", "E"], endpoint_map(edges))
    assert r.macro_topology_class == "PATH_CORE"
    assert r.macro_node_count == 2
    assert r.macro_edge_count == 1
    assert r.degree_two_vertex_count == 3
    assert set(r.macro_edge_links[0]) == {"L1", "L2", "L3", "L4"}
    assert set(r.macro_edges[0]) == {"A", "B", "C", "D", "E"}


def test_y_branch_preserves_branch_and_contracts_each_arm():
    edges = [("L1", "C", "A"), ("L2", "C", "B"), ("L3", "C", "D"), ("L4", "D", "E")]
    r = contract_structure("Y", [e[0] for e in edges], ["A", "B", "C", "D", "E"], endpoint_map(edges))
    assert r.macro_topology_class == "TREE_BRANCHING_CORE"
    assert r.branch_degree_sequence == (3,)
    assert r.macro_node_count == 4
    assert r.macro_edge_count == 3
    assert r.degree_two_vertex_count == 1


def test_unicyclic_branch_yields_cycle_macro_edge_without_arbitrary_terminal():
    edges = [("L1", "X", "A"), ("L2", "A", "B"), ("L3", "B", "C"), ("L4", "C", "A")]
    r = contract_structure("U", [e[0] for e in edges], ["X", "A", "B", "C"], endpoint_map(edges))
    assert r.cycle_rank == 1
    assert r.macro_topology_class == "CYCLIC_BRANCHING_CORE"
    assert r.branch_degree_sequence == (3,)
    assert r.macro_edge_count == 2
    assert any(chain[0] == chain[-1] for chain in r.macro_edges)


def test_pure_cycle_has_canonical_single_cycle_core():
    edges = [("L1", "A", "B"), ("L2", "B", "C"), ("L3", "C", "D"), ("L4", "D", "A")]
    r = contract_structure("C", [e[0] for e in edges], ["A", "B", "C", "D"], endpoint_map(edges))
    assert r.pure_cycle is True
    assert r.macro_topology_class == "PURE_CYCLE_CORE"
    assert r.macro_node_count == 0
    assert r.macro_edge_count == 1
    assert len(r.macro_edge_links[0]) == 4


def test_input_link_order_does_not_change_contraction():
    edges = [("L1", "A", "B"), ("L2", "B", "C"), ("L3", "C", "D")]
    m = endpoint_map(edges)
    a = contract_structure("S", ["L1", "L2", "L3"], ["A", "B", "C", "D"], m)
    b = contract_structure("S", ["L3", "L1", "L2"], ["D", "B", "A", "C"], m)
    assert a == b


def test_disconnected_structure_fails_closed():
    edges = [("L1", "A", "B"), ("L2", "C", "D")]
    with pytest.raises(RT031ContractError):
        contract_structure("BAD", ["L1", "L2"], ["A", "B", "C", "D"], endpoint_map(edges))


def test_declared_structure_counts_are_recomputed_not_trusted():
    edges = [("L1", "A", "B"), ("L2", "B", "C")]
    structures = pd.DataFrame([{
        "structure_id": "S",
        "link_ids": "L1;L2",
        "vertex_ids": "A;B;C",
        "edge_count": 2,
        "vertex_count": 99,
        "cycle_rank": 0,
    }])
    with pytest.raises(RT031ContractError):
        compile_macro_structures(structures, realizations(edges))
