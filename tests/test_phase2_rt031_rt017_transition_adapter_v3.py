from src.phase2_rt031_rt017_transition_adapter_v3 import FrozenRT017ViaNodeAdapter


def edge(e, u, v, w):
    return {"edge_id": e, "u_node_id": u, "v_node_id": v, "osm_way_id": w}


def rule(r, k, via, fw, tw, ing=True):
    return {"relation_id": r, "restriction": k, "via_node_id": via,
            "from_osm_way_id": fw, "to_osm_way_id": tw,
            "via_node_in_graph": str(ing).lower()}


def test_no_turn_and_unrestricted():
    a = FrozenRT017ViaNodeAdapter(
        [edge("a", "A", "X", "1"), edge("b", "X", "B", "2"), edge("c", "X", "C", "3")],
        [rule("r", "no_left_turn", "X", "1", "2")], unresolved_external_via_way_count=2)
    assert a.oracle(("a",), "b") is False
    assert a.oracle(("a",), "c") is True
    assert a.audit.global_transition_completeness is False


def test_only_turn():
    a = FrozenRT017ViaNodeAdapter(
        [edge("a", "A", "X", "1"), edge("b", "X", "B", "2"), edge("c", "X", "C", "3")],
        [rule("r", "only_right_turn", "X", "1", "2")])
    assert a.oracle(("a",), "b") is True
    assert a.oracle(("a",), "c") is False


def test_u_turn_uses_previous_node():
    a = FrozenRT017ViaNodeAdapter(
        [edge("a", "A", "X", "1"), edge("back", "X", "A", "1"), edge("fwd", "X", "B", "1")],
        [rule("r", "no_u_turn", "X", "1", "1")])
    assert a.oracle(("a",), "back") is False
    assert a.oracle(("a",), "fwd") is True


def test_inactive_outside_graph_rule_does_not_govern_graph_transition():
    a = FrozenRT017ViaNodeAdapter(
        [edge("a", "A", "X", "1"), edge("b", "X", "B", "2")],
        [rule("r", "no_left_turn", "X", "1", "2", False)])
    assert a.oracle(("a",), "b") is True
    assert a.audit.active_rule_count == 0
    assert a.audit.inactive_rule_count == 1


def test_unknown_edge_is_unknown_not_allowed():
    a = FrozenRT017ViaNodeAdapter([edge("a", "A", "X", "1")], [])
    assert a.oracle(("a",), "missing") is None


def test_disconnected_is_infeasible():
    a = FrozenRT017ViaNodeAdapter(
        [edge("a", "A", "X", "1"), edge("b", "Y", "B", "2")], [])
    assert a.oracle(("a",), "b") is False


def test_history_signature_is_preserved():
    a = FrozenRT017ViaNodeAdapter(
        [edge("z", "Z", "A", "9"), edge("a", "A", "X", "1"), edge("b", "X", "B", "2")],
        [rule("r", "no_left_turn", "X", "1", "2")])
    assert a.oracle(("z", "a"), "b") is False
