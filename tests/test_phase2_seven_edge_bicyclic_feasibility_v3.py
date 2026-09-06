from src.phase2_network_structure_search_v3 import AbstractLink
from src.phase2_seven_edge_bicyclic_feasibility_v3 import (
    enumerate_exact_seven_edge_bicyclic_policy_structures,
)


def _figure_eight_graph():
    edges = [
        AbstractLink("AB", "A", "B"),
        AbstractLink("BC", "B", "C"),
        AbstractLink("AC", "A", "C"),
        AbstractLink("AD", "A", "D"),
        AbstractLink("DE", "D", "E"),
        AbstractLink("EF", "E", "F"),
        AbstractLink("AF", "A", "F"),
    ]
    groups = {
        "A": ("G1",),
        "B": ("G2",),
        "C": ("G3",),
        "D": ("G4",),
        "E": ("G5",),
        "F": ("G5",),
    }
    return edges, groups


def test_exact_figure_eight_is_found_once():
    edges, groups = _figure_eight_graph()
    result = enumerate_exact_seven_edge_bicyclic_policy_structures(
        edges,
        required_policy_groups=("G1", "G2", "G3", "G4", "G5"),
        terminal_policy_groups=groups,
    )
    assert result["complete"] is True
    assert result["structure_count"] == 1
    record = result["structures"][0]
    assert record.edge_count == 7
    assert record.vertex_count == 6
    assert record.cycle_rank == 2
    assert record.topology_class == "BICYCLIC_ARTICULATED"
    assert record.shape_flags == ("FIGURE_EIGHT_LIKE",)
    assert result["duplicated_policy_groups"] == ["G5"]


def test_input_order_invariant():
    edges, groups = _figure_eight_graph()
    a = enumerate_exact_seven_edge_bicyclic_policy_structures(
        edges,
        required_policy_groups=("G1", "G2", "G3", "G4", "G5"),
        terminal_policy_groups=groups,
    )
    b = enumerate_exact_seven_edge_bicyclic_policy_structures(
        list(reversed(edges)),
        required_policy_groups=("G5", "G4", "G3", "G2", "G1"),
        terminal_policy_groups=groups,
    )
    assert [x.link_ids for x in a["structures"]] == [x.link_ids for x in b["structures"]]
    assert a["duplicated_policy_groups"] == b["duplicated_policy_groups"]


def test_dense_induced_graph_skips_seven_edge_subset_that_drops_sixth_terminal():
    edges, groups = _figure_eight_graph()
    # Add two links inside A-E. The induced six-terminal graph now has nine
    # links, so some seven-link combinations are connected on A-E alone and
    # omit F. They are not E=7,V=6 bicyclic candidates and must be skipped.
    edges = edges + [
        AbstractLink("BD", "B", "D"),
        AbstractLink("BE", "B", "E"),
    ]
    result = enumerate_exact_seven_edge_bicyclic_policy_structures(
        edges,
        required_policy_groups=("G1", "G2", "G3", "G4", "G5"),
        terminal_policy_groups=groups,
    )
    assert result["complete"] is True
    assert result["seven_edge_subsets_scanned"] > result["seven_edge_subsets_using_all_six_terminals"]
    assert result["structure_count"] > 0
    assert all(record.vertex_count == 6 for record in result["structures"])
    assert all(record.cycle_rank == 2 for record in result["structures"])


def test_non_single_policy_membership_fails_closed():
    edges, groups = _figure_eight_graph()
    groups["A"] = ("G1", "G2")
    try:
        enumerate_exact_seven_edge_bicyclic_policy_structures(
            edges,
            required_policy_groups=("G1", "G2", "G3", "G4", "G5"),
            terminal_policy_groups=groups,
        )
    except ValueError as exc:
        assert "exactly one required policy group" in str(exc)
    else:
        raise AssertionError("expected fail-closed policy membership error")
