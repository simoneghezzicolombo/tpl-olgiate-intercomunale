from src.phase2_network_structure_search_v3 import (
    AbstractLink,
    CAP_STATUS,
    classify_connected_structure,
    enumerate_connected_structures,
)


def k5_links():
    nodes = ["A", "B", "C", "D", "E"]
    links = []
    counter = 0
    for i, u in enumerate(nodes):
        for v in nodes[i + 1 :]:
            counter += 1
            links.append(AbstractLink(f"L{counter:02}", u, v))
    return links


def test_path_classification():
    result = classify_connected_structure(
        [
            AbstractLink("L1", "A", "B"),
            AbstractLink("L2", "B", "C"),
            AbstractLink("L3", "C", "D"),
        ]
    )
    assert result.topology_class == "PATH"
    assert result.cycle_rank == 0
    assert result.leaf_count == 2
    assert result.max_degree == 2


def test_cycle_classification():
    result = classify_connected_structure(
        [
            AbstractLink("L1", "A", "B"),
            AbstractLink("L2", "B", "C"),
            AbstractLink("L3", "C", "A"),
        ]
    )
    assert result.topology_class == "CYCLE"
    assert result.cycle_rank == 1
    assert result.leaf_count == 0


def test_branching_tree_classification():
    result = classify_connected_structure(
        [
            AbstractLink("L1", "H", "A"),
            AbstractLink("L2", "H", "B"),
            AbstractLink("L3", "H", "C"),
        ]
    )
    assert result.topology_class == "TREE_BRANCHING"
    assert result.cycle_rank == 0
    assert result.max_degree == 3
    assert result.branch_vertex_count == 1


def test_figure_eight_is_post_generation_shape_flag():
    result = classify_connected_structure(
        [
            AbstractLink("L1", "H", "A"),
            AbstractLink("L2", "A", "B"),
            AbstractLink("L3", "B", "H"),
            AbstractLink("L4", "H", "C"),
            AbstractLink("L5", "C", "D"),
            AbstractLink("L6", "D", "H"),
        ]
    )
    assert result.topology_class == "BICYCLIC_ARTICULATED"
    assert result.cycle_rank == 2
    assert result.articulation_vertex_ids == ("H",)
    assert result.shape_flags == ("FIGURE_EIGHT_LIKE",)


def test_same_generator_emits_multiple_topology_families():
    result = enumerate_connected_structures(
        k5_links(),
        max_edges=6,
        max_subsets_scanned=2_000,
        max_structures=2_000,
    )
    assert result["complete"] is True
    classes = {item.topology_class for item in result["structures"]}
    assert {
        "PATH",
        "CYCLE",
        "TREE_BRANCHING",
        "UNICYCLIC_BRANCHING",
        "BICYCLIC_ARTICULATED",
        "BICYCLIC_NONARTICULATED",
    }.issubset(classes)
    assert any(
        "FIGURE_EIGHT_LIKE" in item.shape_flags for item in result["structures"]
    )


def test_required_terminal_and_policy_groups_are_generic_hard_guards():
    result = enumerate_connected_structures(
        k5_links(),
        required_terminal_ids=["A"],
        required_policy_groups=["G1", "G2"],
        terminal_policy_groups={"A": ["G1"], "E": ["G2"]},
        max_edges=4,
        max_subsets_scanned=2_000,
        max_structures=2_000,
    )
    assert result["complete"] is True
    assert result["structures"]
    for structure in result["structures"]:
        assert "A" in structure.vertex_ids
        assert "E" in structure.vertex_ids


def test_missing_required_group_fails_closed():
    try:
        enumerate_connected_structures(
            k5_links(),
            required_policy_groups=["MISSING"],
            terminal_policy_groups={"A": ["G1"]},
        )
    except ValueError as exc:
        assert "required policy groups absent" in str(exc)
    else:
        raise AssertionError("missing required policy group should fail")


def test_enumeration_cap_returns_no_partial_pool():
    result = enumerate_connected_structures(
        k5_links(),
        max_edges=6,
        max_subsets_scanned=5,
        max_structures=2_000,
    )
    assert result["status"] == CAP_STATUS
    assert result["complete"] is False
    assert result["structures"] == []
    assert result["partial_structure_count"] >= 0


def test_parallel_terminal_pair_is_rejected():
    try:
        enumerate_connected_structures(
            [
                AbstractLink("L1", "A", "B"),
                AbstractLink("L2", "B", "A"),
            ]
        )
    except ValueError as exc:
        assert "parallel terminal pair" in str(exc)
    else:
        raise AssertionError("parallel pair should fail")


def test_deterministic_output():
    kwargs = dict(
        max_edges=5,
        max_subsets_scanned=2_000,
        max_structures=2_000,
    )
    first = enumerate_connected_structures(reversed(k5_links()), **kwargs)
    second = enumerate_connected_structures(k5_links(), **kwargs)
    assert first["status"] == second["status"]
    assert [item.link_ids for item in first["structures"]] == [
        item.link_ids for item in second["structures"]
    ]
    assert [item.topology_class for item in first["structures"]] == [
        item.topology_class for item in second["structures"]
    ]
