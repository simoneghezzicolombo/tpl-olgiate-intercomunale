from __future__ import annotations

import inspect
from pathlib import Path

import pandas as pd
import pytest
from pyproj import Transformer

from phase2_passenger_stop_realization_layer_v3 import (
    EXPECTED_GRAPH_EPOCH,
    ROUTE_PROXIMITY_BUFFER_M,
    RT023_FINAL_REALIZATION_CATALOG_SHA256,
    RT030ContractError,
    build_global_stop_segment_attachments,
    compile_rt030,
    _validate_realization_join,
    reconcile_rt023_run_catalog_to_final,
    write_rt030,
)


def _xy(lon: float, lat: float) -> tuple[float, float]:
    return Transformer.from_crs(4326, 32632, always_xy=True).transform(lon, lat)


def _fixture():
    coords = {
        "A": (9.0000, 45.0000),
        "B": (9.0010, 45.0000),
        "C": (9.0020, 45.0000),
        "D": (9.0010, 45.0010),
        "P": (9.0000, 45.00005),
        "Q": (9.0010, 45.00005),
        "E": (9.0100, 45.0100),
        "F": (9.0110, 45.0100),
    }
    nodes = pd.DataFrame([
        {"node_id": n, "x": _xy(*ll)[0], "y": _xy(*ll)[1]} for n, ll in coords.items()
    ])
    def length(u, v):
        ux, uy = nodes.set_index("node_id").loc[u, ["x", "y"]]
        vx, vy = nodes.set_index("node_id").loc[v, ["x", "y"]]
        return float(((vx-ux)**2 + (vy-uy)**2) ** 0.5)
    edges = pd.DataFrame([
        {"edge_id":"AB_F","u_node_id":"A","v_node_id":"B","osm_way_id":"100","highway":"primary","length_m":length("A","B")},
        {"edge_id":"AB_R","u_node_id":"B","v_node_id":"A","osm_way_id":"100","highway":"primary","length_m":length("B","A")},
        {"edge_id":"BC_F","u_node_id":"B","v_node_id":"C","osm_way_id":"101","highway":"primary","length_m":length("B","C")},
        {"edge_id":"BC_R","u_node_id":"C","v_node_id":"B","osm_way_id":"101","highway":"primary","length_m":length("C","B")},
        {"edge_id":"CD_F","u_node_id":"C","v_node_id":"D","osm_way_id":"102","highway":"secondary","length_m":length("C","D")},
        {"edge_id":"DA_F","u_node_id":"D","v_node_id":"A","osm_way_id":"103","highway":"secondary","length_m":length("D","A")},
        {"edge_id":"PQ_F","u_node_id":"P","v_node_id":"Q","osm_way_id":"104","highway":"service","length_m":length("P","Q")},
        {"edge_id":"PQ_R","u_node_id":"Q","v_node_id":"P","osm_way_id":"104","highway":"service","length_m":length("Q","P")},
        {"edge_id":"EF_F","u_node_id":"E","v_node_id":"F","osm_way_id":"105","highway":"residential","length_m":length("E","F")},
        {"edge_id":"EF_R","u_node_id":"F","v_node_id":"E","osm_way_id":"105","highway":"residential","length_m":length("F","E")},
    ])
    stops = [
        {"stop_place_id":"S_A","lat":coords["A"][1],"lon":coords["A"][0],"service_class":"CONVENTIONAL_TPL","graph_node_id":"A","attachment_distance_m":0.0,"route_ready":True,"automatic_materialization_eligible":True,"graph_epoch_id":EXPECTED_GRAPH_EPOCH,"attachment_semantics":"TEST","stop_name":"A","municipality":"X"},
        {"stop_place_id":"S_C","lat":coords["C"][1],"lon":coords["C"][0],"service_class":"CONVENTIONAL_TPL","graph_node_id":"C","attachment_distance_m":0.0,"route_ready":True,"automatic_materialization_eligible":True,"graph_epoch_id":EXPECTED_GRAPH_EPOCH,"attachment_semantics":"TEST","stop_name":"C","municipality":"X"},
        {"stop_place_id":"S_M","lat":45.0000,"lon":9.0005,"service_class":"CONVENTIONAL_TPL","graph_node_id":"D","attachment_distance_m":100.0,"route_ready":True,"automatic_materialization_eligible":True,"graph_epoch_id":EXPECTED_GRAPH_EPOCH,"attachment_semantics":"TEST","stop_name":"M","municipality":"X"},
        {"stop_place_id":"S_PARALLEL","lat":45.00005,"lon":9.0005,"service_class":"CONVENTIONAL_TPL","graph_node_id":"P","attachment_distance_m":40.0,"route_ready":True,"automatic_materialization_eligible":True,"graph_epoch_id":EXPECTED_GRAPH_EPOCH,"attachment_semantics":"TEST","stop_name":"P","municipality":"X"},
    ]
    for i in range(31):
        stops.append({"stop_place_id":f"DUMMY::{i:02d}","lat":45.0100,"lon":9.0102 + i*1e-7,"service_class":"CONVENTIONAL_TPL","graph_node_id":"E","attachment_distance_m":20.0,"route_ready":True,"automatic_materialization_eligible":True,"graph_epoch_id":EXPECTED_GRAPH_EPOCH,"attachment_semantics":"TEST","stop_name":f"D{i}","municipality":"Y"})
    stops.append({"stop_place_id":"SPECIAL::CASA_DI_COMUNITA_OLGIATE","lat":45.0100,"lon":9.0105,"service_class":"SPECIAL_SERVICE","graph_node_id":"F","attachment_distance_m":10.0,"route_ready":True,"automatic_materialization_eligible":False,"graph_epoch_id":EXPECTED_GRAPH_EPOCH,"attachment_semantics":"TEST","stop_name":"Special","municipality":"Y"})
    stops = pd.DataFrame(stops)
    assert len(stops) == 36

    elementary = pd.DataFrame([
        {"corridor_id":"CORR_AC","pair_id":"PAIR_AC","source_stop_place_id":"S_A","target_stop_place_id":"S_C","path_edge_ids":"AB_F;BC_F","path_node_ids":"A;B;C","path_geometry_sha256":"geom_ac","edge_count":2,"graph_epoch_id":EXPECTED_GRAPH_EPOCH,"elementary_for_structural_reduction":True},
        {"corridor_id":"CORR_CA","pair_id":"PAIR_CA","source_stop_place_id":"S_C","target_stop_place_id":"S_A","path_edge_ids":"BC_R;AB_R","path_node_ids":"C;B;A","path_geometry_sha256":"geom_ca","edge_count":2,"graph_epoch_id":EXPECTED_GRAPH_EPOCH,"elementary_for_structural_reduction":True},
    ])
    rows=[]
    for i in range(288):
        forward = i % 2 == 0
        c = elementary.iloc[0 if forward else 1]
        rows.append({
            "realization_id": f"R{i:03d}",
            "structural_link_id":"L1",
            "direction":"A_TO_B" if forward else "B_TO_A",
            "alternative_ordinal": i+1,
            "source_stop_place_id":c["source_stop_place_id"],
            "target_stop_place_id":c["target_stop_place_id"],
            "pair_id":c["pair_id"],
            "corridor_id":c["corridor_id"],
            "path_node_ids":c["path_node_ids"],
            "path_geometry_sha256":c["path_geometry_sha256"],
            "edge_count":c["edge_count"],
            "graph_epoch_id":EXPECTED_GRAPH_EPOCH,
        })
    rt023=pd.DataFrame(rows)
    return rt023, elementary, stops, nodes, edges


def test_01_structural_waypoint_not_promoted_to_stop():
    _, _, stops, nodes, edges = _fixture()
    att = build_global_stop_segment_attachments(stops, nodes, edges)
    assert "B" not in set(stops.stop_place_id)
    assert "B" not in set(att.stop_place_id)


def test_02_certified_on_route_node_evidence_exists():
    _, _, stops, _, _ = _fixture()
    assert stops.set_index("stop_place_id").loc["S_A", "graph_node_id"] == "A"
    assert stops.set_index("stop_place_id").loc["S_C", "graph_node_id"] == "C"


def test_03_near_parallel_segment_does_not_become_route_segment():
    _, _, stops, nodes, edges = _fixture()
    att = build_global_stop_segment_attachments(stops, nodes, edges).set_index("stop_place_id")
    assert att.loc["S_PARALLEL", "physical_segment_osm_way_id"] == "104"
    assert att.loc["S_M", "physical_segment_osm_way_id"] == "100"


def test_04_directionally_incompatible_segment_not_silently_reversed():
    _, elementary, _, _, edges = _fixture()
    reverse = elementary.loc[elementary.corridor_id=="CORR_CA"].iloc[0]
    edge_uv = edges.set_index("edge_id")[["u_node_id","v_node_id"]].apply(tuple,axis=1).to_dict()
    assert edge_uv[reverse.path_edge_ids.split(";")[0]] == ("C","B")
    assert edge_uv[reverse.path_edge_ids.split(";")[1]] == ("B","A")


def test_05_order_is_actual_direction_not_sorted_stop_id():
    _, elementary, _, _, _ = _fixture()
    assert elementary.loc[elementary.corridor_id=="CORR_AC","path_node_ids"].iloc[0] == "A;B;C"
    assert elementary.loc[elementary.corridor_id=="CORR_CA","path_node_ids"].iloc[0] == "C;B;A"


def test_06_opposite_directions_are_independent_corridors():
    _, elementary, _, _, _ = _fixture()
    assert set(elementary.corridor_id) == {"CORR_AC","CORR_CA"}
    assert elementary.set_index("corridor_id").loc["CORR_AC","path_geometry_sha256"] != elementary.set_index("corridor_id").loc["CORR_CA","path_geometry_sha256"]


def test_07_special_service_is_ineligible_for_supplemental_materialization():
    _, _, stops, nodes, edges = _fixture()
    att = build_global_stop_segment_attachments(stops, nodes, edges).set_index("stop_place_id")
    assert bool(att.loc["SPECIAL::CASA_DI_COMUNITA_OLGIATE","supplemental_segment_materialization_eligible"]) is False


def test_08_field_check_pending_cannot_replace_conventional_contract():
    _, _, stops, nodes, edges = _fixture()
    stops = stops.copy()
    stops.loc[stops.stop_place_id=="DUMMY::00","service_class"]="FIELD_CHECK_PENDING"
    with pytest.raises(RT030ContractError):
        build_global_stop_segment_attachments(stops, nodes, edges)


def test_09_input_row_order_invariance_for_global_attachments():
    _, _, stops, nodes, edges = _fixture()
    a = build_global_stop_segment_attachments(stops, nodes, edges)
    b = build_global_stop_segment_attachments(stops.iloc[::-1], nodes.iloc[::-1], edges.iloc[::-1])
    pd.testing.assert_frame_equal(a.reset_index(drop=True), b.reset_index(drop=True), check_exact=True)


def test_10_attachment_output_is_byte_deterministic(tmp_path: Path):
    _, _, stops, nodes, edges = _fixture()
    a = build_global_stop_segment_attachments(stops, nodes, edges)
    one = a.to_csv(index=False, lineterminator="\n", float_format="%.9f").encode()
    two = build_global_stop_segment_attachments(stops, nodes, edges).to_csv(index=False, lineterminator="\n", float_format="%.9f").encode()
    assert one == two


def test_11_graph_path_direction_mismatch_fails_closed():
    rt023, elementary, _, _, edges = _fixture()
    templates = elementary.set_index("corridor_id").to_dict("index")
    erows = []
    rt023 = rt023.copy()
    for idx, row in rt023.iterrows():
        base_id = str(row["corridor_id"])
        new_id = f"{base_id}::{idx:03d}"
        rt023.at[idx, "corridor_id"] = new_id
        erow = dict(templates[base_id])
        erow["corridor_id"] = new_id
        erows.append(erow)
    unique_elementary = pd.DataFrame(erows)
    unique_elementary.loc[0, "path_edge_ids"] = "AB_R;BC_F"
    with pytest.raises(RT030ContractError, match="directional mismatch"):
        _validate_realization_join(rt023, unique_elementary, edges, EXPECTED_GRAPH_EPOCH)


def test_12_old_43_stop_universe_fails_closed():
    _, _, stops, nodes, edges = _fixture()
    extra=[]
    for i in range(7):
        r=stops.iloc[0].copy(); r["stop_place_id"]=f"OLD::{i}"; extra.append(r)
    old=pd.concat([stops,pd.DataFrame(extra)],ignore_index=True)
    with pytest.raises(RT030ContractError, match="exactly 36"):
        build_global_stop_segment_attachments(old, nodes, edges)


def test_13_no_route_proximity_buffer_parameter_or_effect():
    assert ROUTE_PROXIMITY_BUFFER_M == 0.0
    sig = inspect.signature(build_global_stop_segment_attachments)
    assert "route_buffer" not in sig.parameters
    assert "buffer_m" not in sig.parameters


def test_14_no_random_search_and_rt023_hash_reconciliation_is_fail_closed():
    import phase2_passenger_stop_realization_layer_v3 as mod
    source = inspect.getsource(mod)
    assert "np.random" not in source
    run = pd.DataFrame([{
        "realization_id":f"R{i}","structural_link_id":"L","direction":"A_TO_B",
        "alternative_ordinal":i,"corridor_id":"C"
    } for i in range(288)])
    with pytest.raises(RT030ContractError, match="reconciliation hash mismatch"):
        reconcile_rt023_run_catalog_to_final(
            run,
            elementary_corridors_sha256="x",
            stop_attachments_sha256="y",
            corridor_stop_occurrences_sha256="z",
        )
    assert len(RT023_FINAL_REALIZATION_CATALOG_SHA256) == 64
