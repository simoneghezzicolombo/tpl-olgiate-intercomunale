from itertools import combinations

from src.phase2_edge7_safe_link_reduction_v3 import (
    StructuralLink,
    build_edge7_safe_link_reduction,
    minimum_policy_covering_edges_including_link,
)


def _connected_and_covers(subset, groups, required_groups):
    if not subset:
        return False
    vertices = {x for edge in subset for x in (edge.u, edge.v)}
    adjacency = {v: set() for v in vertices}
    for edge in subset:
        adjacency[edge.u].add(edge.v)
        adjacency[edge.v].add(edge.u)
    start = next(iter(vertices))
    seen = {start}
    stack = [start]
    while stack:
        cur = stack.pop()
        for nxt in adjacency[cur]:
            if nxt not in seen:
                seen.add(nxt)
                stack.append(nxt)
    if seen != vertices:
        return False
    covered = {groups[v][0] for v in vertices}
    return set(required_groups).issubset(covered)


def _bruteforce_min(links, required_link_id, groups, required_groups):
    required = next(edge for edge in links if edge.link_id == required_link_id)
    others = [edge for edge in links if edge.link_id != required_link_id]
    best = None
    for count in range(1, len(links) + 1):
        if count == 1:
            subsets = [(required,)]
        else:
            subsets = ((required, *combo) for combo in combinations(others, count - 1))
        for subset in subsets:
            if _connected_and_covers(subset, groups, required_groups):
                best = count
                break
        if best is not None:
            break
    return best


def _small_graph():
    links = [
        StructuralLink("AB", "A", "B"),
        StructuralLink("BC", "B", "C"),
        StructuralLink("CD", "C", "D"),
        StructuralLink("DE", "D", "E"),
        StructuralLink("AC", "A", "C"),
        StructuralLink("CE", "C", "E"),
        StructuralLink("EX", "E", "X"),
    ]
    groups = {
        "A": ("G1",),
        "B": ("G2",),
        "C": ("G3",),
        "D": ("G4",),
        "E": ("G5",),
        "X": ("G5",),
    }
    required = ("G1", "G2", "G3", "G4", "G5")
    return links, groups, required


def test_exact_dp_matches_bruteforce_for_every_edge():
    links, groups, required = _small_graph()
    for edge in links:
        exact = minimum_policy_covering_edges_including_link(
            links,
            required_link_id=edge.link_id,
            required_policy_groups=required,
            terminal_policy_groups=groups,
        )
        brute = _bruteforce_min(links, edge.link_id, groups, required)
        assert exact == brute, edge.link_id


def test_input_order_invariant():
    links, groups, required = _small_graph()
    a = build_edge7_safe_link_reduction(
        links,
        required_policy_groups=required,
        terminal_policy_groups=groups,
        target_edge_count=5,
    )
    b = build_edge7_safe_link_reduction(
        list(reversed(links)),
        required_policy_groups=tuple(reversed(required)),
        terminal_policy_groups=groups,
        target_edge_count=5,
    )
    assert a["minimum_edge_distribution"] == b["minimum_edge_distribution"]
    assert [(x.link_id, x.minimum_policy_covering_edges_including_link) for x in a["records"]] == [
        (x.link_id, x.minimum_policy_covering_edges_including_link) for x in b["records"]
    ]


def test_budget_exclusion_is_safe_and_explicit():
    links, groups, required = _small_graph()
    result = build_edge7_safe_link_reduction(
        links,
        required_policy_groups=required,
        terminal_policy_groups=groups,
        target_edge_count=4,
    )
    by_id = {x.link_id: x for x in result["records"]}
    assert by_id["EX"].minimum_policy_covering_edges_including_link == 5
    assert by_id["EX"].safely_excludable_from_edge7 is True
    assert by_id["AB"].minimum_policy_covering_edges_including_link <= 4
    assert by_id["AB"].retained_for_edge7_safe_superset is True
    assert all(value is False for value in result["guards"].values())


def test_multi_policy_membership_fails_closed():
    links, groups, required = _small_graph()
    groups["A"] = ("G1", "G2")
    try:
        build_edge7_safe_link_reduction(
            links,
            required_policy_groups=required,
            terminal_policy_groups=groups,
        )
    except ValueError as exc:
        assert "exactly one required policy group" in str(exc)
    else:
        raise AssertionError("expected fail-closed multi-membership error")


def test_parallel_pair_fails_closed():
    links, groups, required = _small_graph()
    links.append(StructuralLink("AB2", "B", "A"))
    try:
        build_edge7_safe_link_reduction(
            links,
            required_policy_groups=required,
            terminal_policy_groups=groups,
        )
    except ValueError as exc:
        assert "parallel/duplicate" in str(exc)
    else:
        raise AssertionError("expected duplicate-pair error")
