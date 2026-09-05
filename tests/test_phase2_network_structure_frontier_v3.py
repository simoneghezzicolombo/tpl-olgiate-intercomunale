from src.phase2_network_structure_frontier_v3 import (
    enumerate_connected_structures_frontier,
)
from src.phase2_network_structure_search_v3 import (
    AbstractLink,
    CAP_STATUS,
    enumerate_connected_structures,
)


def k5_links():
    nodes = ["A", "B", "C", "D", "E"]
    links = []
    counter = 0
    for index, u in enumerate(nodes):
        for v in nodes[index + 1 :]:
            counter += 1
            links.append(AbstractLink(f"L{counter:02}", u, v))
    return links


def ladder_links(columns=5):
    links = []
    counter = 0
    for row in ["T", "B"]:
        for index in range(columns - 1):
            counter += 1
            links.append(
                AbstractLink(
                    f"L{counter:02}",
                    f"{row}{index}",
                    f"{row}{index + 1}",
                )
            )
    for index in range(columns):
        counter += 1
        links.append(
            AbstractLink(f"L{counter:02}", f"T{index}", f"B{index}")
        )
    return links


def signature(result):
    return [
        (item.link_ids, item.topology_class, item.shape_flags)
        for item in result["structures"]
    ]


def test_frontier_exactly_matches_rt007_exhaustive_oracle_on_k5():
    links = k5_links()
    exhaustive = enumerate_connected_structures(
        links,
        max_edges=6,
        max_subsets_scanned=2_000,
        max_structures=2_000,
    )
    frontier = enumerate_connected_structures_frontier(
        links,
        max_edges=6,
        max_states=2_000,
        max_structures=2_000,
    )
    assert exhaustive["complete"] is True
    assert frontier["complete"] is True
    assert exhaustive["structure_count"] == 792
    assert frontier["structure_count"] == 792
    assert frontier["states_expanded"] == 792
    assert signature(frontier) == signature(exhaustive)


def test_frontier_matches_oracle_with_generic_hub_and_five_groups():
    links = k5_links()
    membership = {vertex: [f"G_{vertex}"] for vertex in "ABCDE"}
    kwargs = dict(
        required_terminal_ids=["A"],
        required_policy_groups=[f"G_{vertex}" for vertex in "ABCDE"],
        terminal_policy_groups=membership,
        max_edges=6,
        max_structures=2_000,
    )
    exhaustive = enumerate_connected_structures(
        links,
        max_subsets_scanned=2_000,
        **kwargs,
    )
    frontier = enumerate_connected_structures_frontier(
        links,
        max_states=2_000,
        **kwargs,
    )
    assert exhaustive["structure_count"] == 552
    assert frontier["structure_count"] == 552
    assert signature(frontier) == signature(exhaustive)


def test_sparse_ladder_avoids_disconnected_subset_scans_materially():
    links = ladder_links(5)
    exhaustive = enumerate_connected_structures(
        links,
        max_edges=7,
        max_subsets_scanned=10_000,
        max_structures=10_000,
    )
    frontier = enumerate_connected_structures_frontier(
        links,
        max_edges=7,
        max_states=10_000,
        max_structures=10_000,
    )
    assert exhaustive["subsets_scanned"] == 5_811
    assert exhaustive["structure_count"] == 978
    assert frontier["states_expanded"] == 978
    assert frontier["structure_count"] == 978
    assert signature(frontier) == signature(exhaustive)
    assert frontier["states_expanded"] / exhaustive["subsets_scanned"] < 0.20


def test_frontier_state_cap_fails_closed_without_partial_pool():
    result = enumerate_connected_structures_frontier(
        k5_links(),
        max_edges=6,
        max_states=20,
        max_structures=2_000,
    )
    assert result["status"] == CAP_STATUS
    assert result["complete"] is False
    assert result["structures"] == []
    assert result["partial_structure_count"] >= 0


def test_frontier_is_deterministic_under_reversed_input_order():
    kwargs = dict(max_edges=6, max_states=2_000, max_structures=2_000)
    first = enumerate_connected_structures_frontier(k5_links(), **kwargs)
    second = enumerate_connected_structures_frontier(reversed(k5_links()), **kwargs)
    assert first["status"] == second["status"]
    assert signature(first) == signature(second)
