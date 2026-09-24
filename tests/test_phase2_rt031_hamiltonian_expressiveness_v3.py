from __future__ import annotations

import pandas as pd
import pytest

from phase2_rt031_hamiltonian_expressiveness_v3 import (
    RT031HamiltonianContractError,
    build_audit,
    find_hamiltonian_cycle,
    find_hamiltonian_path,
    validate_reciprocal_structural_graph,
    verify_witness,
    witness_table,
)


def frame(edges: list[tuple[str, str]]) -> pd.DataFrame:
    return pd.DataFrame([
        {
            "structural_link_id": f"L{i:02d}",
            "terminal_a": a,
            "terminal_b": b,
            "eligibility_status": "RECIPROCAL_BIDIRECTIONAL_CORRIDOR_AVAILABLE",
            "eligible_for_bidirectional_undirected_structure": True,
            "scope": "RECIPROCAL_BIDIRECTIONAL_STRUCTURAL_LINK_INTERFACE_NOT_NETWORK_SELECTION",
        }
        for i, (a, b) in enumerate(edges)
    ])


def graph(edges: list[tuple[str, str]]):
    return validate_reciprocal_structural_graph(frame(edges), expected_vertex_count=None, expected_link_count=None)


def test_path_exists_without_cycle():
    g = graph([("A", "B"), ("B", "C"), ("C", "D")])
    path = find_hamiltonian_path(g)
    cycle = find_hamiltonian_cycle(g)
    assert path.feasible is True
    assert path.ordered_vertices == ("A", "B", "C", "D")
    assert cycle.feasible is False
    verify_witness(g, path, cycle=False)


def test_cycle_exists():
    g = graph([("A", "B"), ("B", "C"), ("C", "D"), ("D", "A")])
    path = find_hamiltonian_path(g)
    cycle = find_hamiltonian_cycle(g)
    assert path.feasible and cycle.feasible
    assert len(path.ordered_vertices) == 4
    assert len(cycle.ordered_vertices) == 4
    assert len(cycle.ordered_link_ids) == 4
    verify_witness(g, cycle, cycle=True)


def test_disconnected_graph_is_infeasible():
    g = graph([("A", "B"), ("C", "D")])
    assert find_hamiltonian_path(g).feasible is False
    assert find_hamiltonian_cycle(g).feasible is False


def test_star_has_no_hamiltonian_path():
    g = graph([("A", "B"), ("A", "C"), ("A", "D")])
    assert find_hamiltonian_path(g).feasible is False
    assert find_hamiltonian_cycle(g).feasible is False


def test_input_row_order_invariant():
    source = frame([("A", "B"), ("B", "C"), ("C", "D"), ("D", "A"), ("A", "C")])
    g1 = validate_reciprocal_structural_graph(source, expected_vertex_count=None, expected_link_count=None)
    g2 = validate_reciprocal_structural_graph(source.iloc[::-1].reset_index(drop=True), expected_vertex_count=None, expected_link_count=None)
    assert find_hamiltonian_path(g1) == find_hamiltonian_path(g2)
    assert find_hamiltonian_cycle(g1) == find_hamiltonian_cycle(g2)


def test_parallel_pair_fails_closed():
    with pytest.raises(RT031HamiltonianContractError, match="parallel structural links"):
        validate_reciprocal_structural_graph(frame([("A", "B"), ("B", "A")]), expected_vertex_count=None, expected_link_count=None)


def test_nonreciprocal_row_fails_closed():
    source = frame([("A", "B")])
    source.loc[0, "eligible_for_bidirectional_undirected_structure"] = False
    with pytest.raises(RT031HamiltonianContractError, match="non-reciprocal"):
        validate_reciprocal_structural_graph(source, expected_vertex_count=None, expected_link_count=None)


def test_audit_is_diagnostic_not_recommendation():
    g = graph([("A", "B"), ("B", "C"), ("C", "A")])
    path, cycle = find_hamiltonian_path(g), find_hamiltonian_cycle(g)
    audit = build_audit(g, path, cycle, reciprocal_link_file_sha256="abc")
    assert audit["status"] == "PASS_HAMILTONIAN_EXPRESSIVENESS_DIAGNOSTIC_NOT_NETWORK_SEARCH_PASS"
    assert all(value is False for value in audit["negative_assertions"].values())
    assert witness_table(path, cycle)["diagnostic_only_not_route_recommendation"].all()
