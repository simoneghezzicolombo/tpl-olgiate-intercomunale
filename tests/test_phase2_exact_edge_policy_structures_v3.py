from itertools import combinations

import pytest

from src.phase2_exact_edge_policy_structures_v3 import (
    enumerate_exact_edge_policy_structures,
)
from src.phase2_network_structure_search_v3 import AbstractLink, classify_connected_structure


def _bruteforce(links, edge_count, groups, membership):
    accepted = set()
    for subset in combinations(links, edge_count):
        try:
            record = classify_connected_structure(subset)
        except ValueError:
            continue
        covered = {
            group
            for terminal in record.vertex_ids
            for group in membership.get(terminal, ())
        }
        if set(groups).issubset(covered):
            accepted.add(record.link_ids)
    return accepted


def _fixture():
    links = [
        AbstractLink("ab", "a", "b"),
        AbstractLink("bc", "b", "c"),
        AbstractLink("cd", "c", "d"),
        AbstractLink("de", "d", "e"),
        AbstractLink("ea", "e", "a"),
        AbstractLink("ac", "a", "c"),
        AbstractLink("cf", "c", "f"),
    ]
    groups = ("A", "B", "C", "D", "E")
    membership = {
        "a": ("A",),
        "b": ("B",),
        "c": ("C",),
        "d": ("D",),
        "e": ("E",),
        "f": ("E",),
    }
    return links, groups, membership


def test_exact_layer_matches_bruteforce_small_graph():
    links, groups, membership = _fixture()
    result = enumerate_exact_edge_policy_structures(
        links,
        exact_edge_count=5,
        required_policy_groups=groups,
        terminal_policy_groups=membership,
    )
    observed = {record.link_ids for record in result["structures"]}
    assert observed == _bruteforce(links, 5, groups, membership)
    assert result["complete"] is True
    assert result["technical_parameters"]["enumeration_cap"] is None


def test_input_order_invariant():
    links, groups, membership = _fixture()
    first = enumerate_exact_edge_policy_structures(
        links,
        exact_edge_count=5,
        required_policy_groups=groups,
        terminal_policy_groups=membership,
    )
    second = enumerate_exact_edge_policy_structures(
        list(reversed(links)),
        exact_edge_count=5,
        required_policy_groups=reversed(groups),
        terminal_policy_groups=membership,
    )
    assert [item.link_ids for item in first["structures"]] == [
        item.link_ids for item in second["structures"]
    ]
    assert first["connected_state_counts_by_edge_count"] == second["connected_state_counts_by_edge_count"]


def test_topology_is_not_a_generation_filter():
    links, groups, membership = _fixture()
    result = enumerate_exact_edge_policy_structures(
        links,
        exact_edge_count=5,
        required_policy_groups=groups,
        terminal_policy_groups=membership,
    )
    classes = {item.topology_class for item in result["structures"]}
    assert "CYCLE" in classes or "UNICYCLIC_BRANCHING" in classes
    assert any(item.cycle_rank == 0 for item in result["structures"])


def test_missing_policy_group_fails_closed():
    links, groups, membership = _fixture()
    membership = dict(membership)
    membership["e"] = ("D",)
    membership["f"] = ("D",)
    with pytest.raises(ValueError, match="required policy groups absent"):
        enumerate_exact_edge_policy_structures(
            links,
            exact_edge_count=5,
            required_policy_groups=groups,
            terminal_policy_groups=membership,
        )


def test_multi_group_terminal_fails_closed():
    links, groups, membership = _fixture()
    membership = dict(membership)
    membership["a"] = ("A", "B")
    with pytest.raises(ValueError, match="exactly one required policy group"):
        enumerate_exact_edge_policy_structures(
            links,
            exact_edge_count=5,
            required_policy_groups=groups,
            terminal_policy_groups=membership,
        )


@pytest.mark.parametrize("edge_count", [0, 8])
def test_invalid_exact_edge_count_fails(edge_count):
    links, groups, membership = _fixture()
    with pytest.raises(ValueError):
        enumerate_exact_edge_policy_structures(
            links,
            exact_edge_count=edge_count,
            required_policy_groups=groups,
            terminal_policy_groups=membership,
        )
