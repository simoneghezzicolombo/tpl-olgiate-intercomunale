import pandas as pd

from src.phase2_corridor_reciprocity_v3 import (
    build_reciprocal_structural_links,
    structural_link_id,
)


def pairs(rows):
    return pd.DataFrame(
        rows,
        columns=[
            "pair_id",
            "source_routing_terminal_id",
            "target_routing_terminal_id",
            "gate_d_route_found",
        ],
    )


def corridors(rows):
    return pd.DataFrame(
        rows,
        columns=[
            "pair_id",
            "corridor_id",
            "admissible_for_corridor_pool",
            "running_minutes_model",
            "distance_m",
        ],
    )


def test_reciprocal_pair_emits_one_undirected_link():
    result = build_reciprocal_structural_links(
        pairs([
            ("P_AB", "A", "B", True),
            ("P_BA", "B", "A", True),
        ]),
        corridors([
            ("P_AB", "C1", True, 8.0, 5000.0),
            ("P_AB", "C2", True, 9.0, 5200.0),
            ("P_BA", "C3", True, 8.5, 5100.0),
        ]),
    )
    assert len(result["pair_audit"]) == 1
    assert len(result["structural_links"]) == 1
    row = result["structural_links"].iloc[0]
    assert row["structural_link_id"] == structural_link_id("A", "B")
    assert row["eligibility_status"] == "RECIPROCAL_BIDIRECTIONAL_CORRIDOR_AVAILABLE"
    assert row["a_to_b_admitted_corridor_count"] == 2
    assert row["b_to_a_admitted_corridor_count"] == 1
    assert row["a_to_b_min_running_minutes_model"] == 8.0
    assert row["b_to_a_min_running_minutes_model"] == 8.5


def test_unrequested_reverse_is_unknown_not_infeasible():
    result = build_reciprocal_structural_links(
        pairs([("P_AB", "A", "B", True)]),
        corridors([("P_AB", "C1", True, 8.0, 5000.0)]),
    )
    row = result["pair_audit"].iloc[0]
    assert row["eligibility_status"] == "UNTESTED_DIRECTION"
    assert bool(row["a_to_b_requested"]) is True
    assert bool(row["b_to_a_requested"]) is False
    assert result["structural_links"].empty
    assert result["metadata"]["directional_absence_semantics"] == "NOT_REQUESTED_IS_UNKNOWN_NOT_INFEASIBLE"


def test_reverse_without_gate_d_route_is_ineligible_with_exact_reason():
    result = build_reciprocal_structural_links(
        pairs([
            ("P_AB", "A", "B", True),
            ("P_BA", "B", "A", False),
        ]),
        corridors([("P_AB", "C1", True, 8.0, 5000.0)]),
    )
    row = result["pair_audit"].iloc[0]
    assert row["eligibility_status"] == "NO_GATE_D_ROUTE_IN_DIRECTION"
    assert result["structural_links"].empty


def test_gate_d_both_directions_but_no_admitted_reverse_is_ineligible():
    result = build_reciprocal_structural_links(
        pairs([
            ("P_AB", "A", "B", True),
            ("P_BA", "B", "A", True),
        ]),
        corridors([
            ("P_AB", "C1", True, 8.0, 5000.0),
            ("P_BA", "C2", False, 7.5, 4900.0),
        ]),
    )
    row = result["pair_audit"].iloc[0]
    assert row["eligibility_status"] == "NO_ADMITTED_CORRIDOR_IN_DIRECTION"
    assert row["b_to_a_admitted_corridor_count"] == 0
    assert result["structural_links"].empty


def test_input_direction_order_does_not_change_unordered_link_identity_or_status():
    p1 = pairs([
        ("P_AB", "A", "B", True),
        ("P_BA", "B", "A", True),
    ])
    c1 = corridors([
        ("P_AB", "C1", True, 8.0, 5000.0),
        ("P_BA", "C2", True, 8.5, 5100.0),
    ])
    first = build_reciprocal_structural_links(p1, c1)["pair_audit"].iloc[0]
    second = build_reciprocal_structural_links(
        p1.iloc[::-1].reset_index(drop=True),
        c1.iloc[::-1].reset_index(drop=True),
    )["pair_audit"].iloc[0]
    assert first["structural_link_id"] == second["structural_link_id"]
    assert first["terminal_a"] == second["terminal_a"] == "A"
    assert first["terminal_b"] == second["terminal_b"] == "B"
    assert first["eligibility_status"] == second["eligibility_status"]


def test_multiple_corridor_variants_do_not_create_parallel_structural_links():
    result = build_reciprocal_structural_links(
        pairs([
            ("P_AB", "A", "B", True),
            ("P_BA", "B", "A", True),
        ]),
        corridors([
            ("P_AB", "C1", True, 8.0, 5000.0),
            ("P_AB", "C2", True, 8.2, 5100.0),
            ("P_AB", "C3", True, 9.0, 5300.0),
            ("P_BA", "C4", True, 8.1, 5050.0),
            ("P_BA", "C5", True, 8.6, 5200.0),
        ]),
    )
    assert len(result["structural_links"]) == 1


def test_duplicate_ordered_pair_requests_are_rejected():
    try:
        build_reciprocal_structural_links(
            pairs([
                ("P1", "A", "B", True),
                ("P2", "A", "B", True),
            ]),
            corridors([]),
        )
    except ValueError as exc:
        assert "ordered terminal pair" in str(exc)
    else:
        raise AssertionError("duplicate ordered pair request should fail")


def test_unknown_corridor_pair_id_is_rejected():
    try:
        build_reciprocal_structural_links(
            pairs([("P_AB", "A", "B", True)]),
            corridors([("UNKNOWN", "C1", True, 8.0, 5000.0)]),
        )
    except ValueError as exc:
        assert "unknown pair_id" in str(exc)
    else:
        raise AssertionError("unknown pair reference should fail")
