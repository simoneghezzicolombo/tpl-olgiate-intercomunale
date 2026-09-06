from src.phase2_minimum_policy_backbone_v3 import (
    PASS_STATUS,
    enumerate_exact_minimum_policy_backbones,
)
from src.phase2_network_structure_search_v3 import (
    AbstractLink,
    enumerate_connected_structures,
)


GROUPS = ("A", "B", "C", "D", "E")


def membership(vertices):
    return {vertex: (vertex.split("_")[0],) for vertex in vertices}


def test_exact_minimum_matches_exhaustive_oracle_on_small_graph():
    links = [
        AbstractLink("AB", "A_1", "B_1"),
        AbstractLink("BC", "B_1", "C_1"),
        AbstractLink("CD", "C_1", "D_1"),
        AbstractLink("DE", "D_1", "E_1"),
        AbstractLink("AC", "A_1", "C_1"),
        AbstractLink("CE", "C_1", "E_1"),
    ]
    m = membership({x for link in links for x in (link.u, link.v)})
    exact = enumerate_exact_minimum_policy_backbones(
        links, required_policy_groups=GROUPS, terminal_policy_groups=m
    )
    oracle = enumerate_connected_structures(
        links,
        required_policy_groups=GROUPS,
        terminal_policy_groups=m,
        min_edges=4,
        max_edges=4,
        max_subsets_scanned=10000,
        max_structures=10000,
    )
    assert exact["status"] == PASS_STATUS
    assert exact["complete"] is True
    assert {s.link_ids for s in exact["structures"]} == {s.link_ids for s in oracle["structures"]}


def test_input_order_invariance_and_deterministic_records():
    links = [
        AbstractLink("AB", "A_1", "B_1"),
        AbstractLink("BC", "B_1", "C_1"),
        AbstractLink("CD", "C_1", "D_1"),
        AbstractLink("DE", "D_1", "E_1"),
        AbstractLink("AE", "A_1", "E_1"),
    ]
    m = membership({x for link in links for x in (link.u, link.v)})
    first = enumerate_exact_minimum_policy_backbones(
        links, required_policy_groups=GROUPS, terminal_policy_groups=m
    )
    second = enumerate_exact_minimum_policy_backbones(
        list(reversed(links)),
        required_policy_groups=reversed(GROUPS),
        terminal_policy_groups=m,
    )
    assert [s.link_ids for s in first["structures"]] == [s.link_ids for s in second["structures"]]
    assert first["derived_minimum_edge_count"] == 4


def test_multiple_terminals_per_group_are_exhaustive_without_topology_prior():
    links = [
        AbstractLink("A1B", "A_1", "B_1"),
        AbstractLink("A2B", "A_2", "B_1"),
        AbstractLink("BC", "B_1", "C_1"),
        AbstractLink("CD", "C_1", "D_1"),
        AbstractLink("DE", "D_1", "E_1"),
    ]
    vertices = {x for link in links for x in (link.u, link.v)}
    m = membership(vertices)
    out = enumerate_exact_minimum_policy_backbones(
        links, required_policy_groups=GROUPS, terminal_policy_groups=m
    )
    assert len(out["structures"]) == 2
    assert {s.vertex_ids for s in out["structures"]} == {
        ("A_1", "B_1", "C_1", "D_1", "E_1"),
        ("A_2", "B_1", "C_1", "D_1", "E_1"),
    }


def test_four_edges_covering_five_single_groups_are_necessarily_tree_rank_zero():
    links = [
        AbstractLink("AB", "A_1", "B_1"),
        AbstractLink("BC", "B_1", "C_1"),
        AbstractLink("CD", "C_1", "D_1"),
        AbstractLink("DE", "D_1", "E_1"),
    ]
    m = membership({x for link in links for x in (link.u, link.v)})
    out = enumerate_exact_minimum_policy_backbones(
        links, required_policy_groups=GROUPS, terminal_policy_groups=m
    )
    assert len(out["structures"]) == 1
    assert out["structures"][0].cycle_rank == 0
    assert out["technical_parameters"]["search_scope"] == "EXACT_MINIMUM_POLICY_BACKBONES_ONLY"


def test_ambiguous_or_missing_required_group_membership_fails_closed():
    import pytest
    links = [
        AbstractLink("AB", "A_1", "B_1"),
        AbstractLink("BC", "B_1", "C_1"),
        AbstractLink("CD", "C_1", "D_1"),
        AbstractLink("DE", "D_1", "E_1"),
    ]
    m = membership({x for link in links for x in (link.u, link.v)})
    m["A_1"] = ("A", "B")
    with pytest.raises(ValueError, match="exactly one required policy group"):
        enumerate_exact_minimum_policy_backbones(
            links, required_policy_groups=GROUPS, terminal_policy_groups=m
        )
