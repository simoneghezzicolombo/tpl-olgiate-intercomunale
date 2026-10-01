from scripts.phase2_audit_rt031_south_road_probe_v3 import projection, shortest


def edge(eid, u, v, way, minutes=1):
    return {"edge_id": eid, "u_node_id": u, "v_node_id": v,
            "osm_way_id": way, "length_m": "100",
            "running_minutes_model": str(minutes)}


def test_projection_interior_and_shortest_respects_turn():
    assert projection((3, 0), (0, 0), (10, 0)) == (0.3, 0.0)
    edges = {r["edge_id"]: r for r in [
        edge("a", "S", "X", "1"), edge("forbidden", "X", "T", "2"),
        edge("detour1", "X", "Y", "3"), edge("detour2", "Y", "T", "3"),
    ]}
    rules = [{"relation_id": "r", "restriction": "no_left_turn",
              "via_node_id": "X", "from_osm_way_id": "1",
              "to_osm_way_id": "2", "via_node_in_graph": "true"}]
    path = shortest(edges, rules, "S", "T")
    assert path["edge_ids"] == ["a", "detour1", "detour2"]
    assert path["running_minutes_model"] == 3.0


def test_unreachable_is_not_promoted():
    assert shortest({"a": edge("a", "S", "X", "1")}, [], "S", "T") is None
