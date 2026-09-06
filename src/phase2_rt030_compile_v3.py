from __future__ import annotations

import hashlib
import numpy as np
import pandas as pd
from pyproj import Transformer

from phase2_rt030_base_v3 import (
    EXPECTED_GRAPH_EPOCH, ROUTE_PROXIMITY_BUFFER_M, RT030ContractError,
    _as_bool, _physical_segment_id, _required, _split, _validate_graph,
    _validate_stop_contract, build_global_stop_segment_attachments,
)
from phase2_rt030_diagnostics_v3 import finalize_rt030

def _validate_realization_join(
    rt023: pd.DataFrame, elementary: pd.DataFrame, graph_edges: pd.DataFrame,
    expected_graph_epoch: str,
) -> pd.DataFrame:
    _required(rt023, ["realization_id", "structural_link_id", "direction", "source_stop_place_id", "target_stop_place_id", "pair_id", "corridor_id", "path_node_ids", "path_geometry_sha256", "edge_count", "graph_epoch_id"], "RT-023 catalog")
    _required(elementary, ["corridor_id", "pair_id", "source_stop_place_id", "target_stop_place_id", "path_edge_ids", "path_node_ids", "path_geometry_sha256", "edge_count", "graph_epoch_id", "elementary_for_structural_reduction"], "elementary corridor evidence")
    r = rt023.copy(); e = elementary.copy()
    if len(r) != 288 or r["realization_id"].astype(str).duplicated().any():
        raise RT030ContractError("RT-023 production catalog must contain exactly 288 unique realizations")
    if set(r["graph_epoch_id"].astype(str)) != {expected_graph_epoch}:
        raise RT030ContractError("RT-023 graph epoch mismatch")
    e = e[e["elementary_for_structural_reduction"].map(_as_bool)].copy()
    if e["corridor_id"].astype(str).duplicated().any():
        raise RT030ContractError("Elementary corridor_id must be unique")
    cols = ["corridor_id", "pair_id", "source_stop_place_id", "target_stop_place_id", "path_edge_ids", "path_node_ids", "path_geometry_sha256", "edge_count", "graph_epoch_id"]
    m = r.merge(e[cols], on="corridor_id", how="left", suffixes=("_rt023", "_up"), validate="one_to_one")
    if m["path_edge_ids"].isna().any():
        raise RT030ContractError("RT-023 corridor missing from certified elementary evidence")
    for field in ["pair_id", "source_stop_place_id", "target_stop_place_id", "path_node_ids", "path_geometry_sha256", "edge_count", "graph_epoch_id"]:
        if not (m[f"{field}_rt023"].astype(str) == m[f"{field}_up"].astype(str)).all():
            raise RT030ContractError(f"RT-023/upstream mismatch for {field}")
    edge_uv = {
        str(eid):(str(u),str(v))
        for eid,u,v in zip(graph_edges["edge_id"],graph_edges["u_node_id"],graph_edges["v_node_id"])
    }
    for row in m.to_dict("records"):
        ns = _split(row["path_node_ids_rt023"]); es = _split(row["path_edge_ids"])
        if len(es) != len(ns) - 1 or len(es) != int(float(row["edge_count_rt023"])):
            raise RT030ContractError(f"Path cardinality mismatch {row['corridor_id']}")
        for i, eid in enumerate(es):
            uv=edge_uv.get(eid)
            if uv is None:
                raise RT030ContractError(f"Unknown path edge {eid}")
            if uv != (ns[i],ns[i+1]):
                raise RT030ContractError(f"Path edge/node directional mismatch {row['corridor_id']} edge {i}")
    return m.sort_values("realization_id", kind="mergesort").reset_index(drop=True)


def compile_rt030(
    *, rt023_realizations: pd.DataFrame, elementary_corridors: pd.DataFrame,
    stop_attachments: pd.DataFrame, graph_nodes: pd.DataFrame, graph_edges: pd.DataFrame,
    expected_graph_epoch: str = EXPECTED_GRAPH_EPOCH, lineage: dict[str, str] | None = None,
    rt023_lineage_reconciliation: dict | None = None,
) -> RT030Result:
    stops = _validate_stop_contract(stop_attachments, expected_graph_epoch)
    nodes, edges = _validate_graph(graph_nodes, graph_edges)
    merged = _validate_realization_join(rt023_realizations, elementary_corridors, edges, expected_graph_epoch)
    segatt = build_global_stop_segment_attachments(stops, nodes, edges, expected_graph_epoch=expected_graph_epoch)

    eligible = stops[(stops["service_class"].astype(str) == "CONVENTIONAL_TPL") & stops["automatic_materialization_eligible"].map(_as_bool)].copy()
    stop_by_node: dict[str, list[str]] = {}
    for node, g in eligible.groupby(eligible["graph_node_id"].astype(str)):
        stop_by_node[str(node)] = sorted(g["stop_place_id"].astype(str).tolist())
    seg_by_stop = segatt.set_index("stop_place_id")
    stop_meta = eligible.set_index("stop_place_id")
    node_xy = nodes.set_index("node_id")[["x", "y"]].astype(float)
    transformer = Transformer.from_crs(4326, 32632, always_xy=True)
    stop_xy = {sid: transformer.transform(float(stop_meta.loc[sid, "lon"]), float(stop_meta.loc[sid, "lat"])) for sid in stop_meta.index}
    edge_info = {
        str(eid):(str(u),str(v),_physical_segment_id(str(u),str(v)),float(length_m))
        for eid,u,v,length_m in zip(
            edges["edge_id"],edges["u_node_id"],edges["v_node_id"],edges["length_m"]
        )
    }
    node_xy_dict={str(idx):(float(row["x"]),float(row["y"])) for idx,row in nodes.set_index("node_id").iterrows()}
    eligible_seg = {
        sid:(str(seg_by_stop.loc[sid,"physical_segment_id"]), float(seg_by_stop.loc[sid,"attachment_edge_distance_m"]))
        for sid in stop_meta.index.astype(str)
        if _as_bool(seg_by_stop.loc[sid,"supplemental_segment_materialization_eligible"])
    }

    occ_rows=[]; pat_rows=[]
    for row in merged.to_dict("records"):
        rid=str(row["realization_id"]); ns=_split(row["path_node_ids_rt023"]); es=_split(row["path_edge_ids"])
        evidence=[]
        edge_lengths=[edge_info[eid][3] for eid in es]
        cumulative=[0.0]
        for length_m in edge_lengths:
            cumulative.append(cumulative[-1] + float(length_m))
        for pos,node in enumerate(ns):
            for sid in stop_by_node.get(node,[]):
                evidence.append((
                    float(pos), float(cumulative[pos]), sid,
                    "CERTIFIED_ATTACHMENT_NODE_ON_ORDERED_PATH", node, "", np.nan, 0.0
                ))
        node_present={sid for _,_,sid,*_ in evidence}
        path_segment_positions={}
        for i,eid in enumerate(es):
            u,v,psid,length_m=edge_info[eid]
            path_segment_positions.setdefault(psid,[]).append((i,eid,u,v,length_m))
        for sid,(wanted,edge_distance) in eligible_seg.items():
            if sid in node_present or wanted not in path_segment_positions:
                continue
            px,py=stop_xy[sid]
            for i,eid,u,v,length_m in path_segment_positions[wanted]:
                ux,uy=node_xy_dict[u]; vx,vy=node_xy_dict[v]
                dx=vx-ux; dy=vy-uy; l2=dx*dx+dy*dy
                t=max(0.0,min(1.0,((px-ux)*dx+(py-uy)*dy)/l2))
                route_distance=float(cumulative[i]) + float(t) * float(length_m)
                evidence.append((
                    float(i)+float(t), route_distance, sid,
                    "CERTIFIED_GLOBAL_NEAREST_PHYSICAL_SEGMENT_ON_ORDERED_PATH",
                    "",eid,edge_distance,0.0
                ))
        evidence.sort(key=lambda z:(z[0],z[2],z[3]))
        clean=[]
        for ev in evidence:
            same=[j for j,x in enumerate(clean) if x[2]==ev[2] and abs(x[0]-ev[0])<=1e-9]
            if same:
                j=same[0]
                if ev[3].startswith("CERTIFIED_ATTACHMENT_NODE"):
                    clean[j]=ev
            else:
                clean.append(ev)
        clean.sort(key=lambda z:(z[0],z[2],z[3]))
        seq_ids=[x[2] for x in clean]
        src=str(row["source_stop_place_id_rt023"]); tgt=str(row["target_stop_place_id_rt023"])
        if src not in seq_ids or tgt not in seq_ids:
            raise RT030ContractError(f"Realization endpoints not materialized: {rid}")
        if seq_ids.index(src) > seq_ids.index(tgt):
            raise RT030ContractError(f"Endpoint order invalid: {rid}")
        for seq,ev in enumerate(clean,1):
            pos,route_distance,sid,etype,nodeid,eid,edist,buf=ev
            occ_rows.append({
                "realization_id":rid,"structural_link_id":str(row["structural_link_id"]),"direction":str(row["direction"]),
                "pair_id":str(row["pair_id_rt023"]),"corridor_id":str(row["corridor_id"]),"graph_epoch_id":expected_graph_epoch,
                "stop_sequence":seq,"ordinal_position":seq,"path_position":pos,"distance_from_path_start_m":route_distance,
                "stop_place_id":sid,"stop_name":str(stop_meta.loc[sid].get("stop_name","")),
                "municipality":str(stop_meta.loc[sid].get("municipality","")),"evidence_type":etype,
                "materialization_reason":(
                    "RT018_CERTIFIED_ATTACHMENT_NODE_ENCOUNTERED_ON_EXACT_ORDERED_PATH"
                    if etype == "CERTIFIED_ATTACHMENT_NODE_ON_ORDERED_PATH" else
                    "ROUTE_INDEPENDENT_GLOBAL_NEAREST_PHYSICAL_SEGMENT_TRAVERSED_BY_EXACT_ORDERED_PATH"
                ),
                "certified_attachment_node_id":str(stop_meta.loc[sid,"graph_node_id"]),
                "certified_attachment_node_distance_m":float(stop_meta.loc[sid,"attachment_distance_m"]),
                "path_node_id":nodeid,"path_edge_id":eid,
                "path_geometry_sha256":str(row["path_geometry_sha256_rt023"]),
                "path_edge_ids_sha256":hashlib.sha256(str(row["path_edge_ids"]).encode()).hexdigest(),
                "global_nearest_physical_segment_id":str(seg_by_stop.loc[sid,"physical_segment_id"]),
                "global_nearest_physical_segment_osm_way_id":str(seg_by_stop.loc[sid,"physical_segment_osm_way_id"]),
                "attachment_edge_distance_m":float(seg_by_stop.loc[sid,"attachment_edge_distance_m"]),
                "route_proximity_buffer_m":buf,
            })
        supplemental=sum(1 for x in clean if x[3].startswith("CERTIFIED_GLOBAL"))
        pat_rows.append({
            "realization_id":rid,"structural_link_id":str(row["structural_link_id"]),"direction":str(row["direction"]),
            "alternative_ordinal":int(row["alternative_ordinal"]),"pair_id":str(row["pair_id_rt023"]),"corridor_id":str(row["corridor_id"]),
            "graph_epoch_id":expected_graph_epoch,"path_geometry_sha256":str(row["path_geometry_sha256_rt023"]),
            "path_edge_ids_sha256":hashlib.sha256(str(row["path_edge_ids"]).encode()).hexdigest(),
            "source_endpoint_stop_id":src,"target_endpoint_stop_id":tgt,
            "path_distance_m":float(cumulative[-1]),
            "ordered_passenger_stop_ids":";".join(seq_ids),"passenger_stop_count":len(seq_ids),
            "intermediate_stop_count":max(0,len(seq_ids)-2),"exact_node_evidence_count":len(clean)-supplemental,
            "supplemental_physical_segment_evidence_count":supplemental,
            "passenger_stop_realization_semantics":"EXACT_NODE_OR_ROUTE_INDEPENDENT_GLOBAL_NEAREST_PHYSICAL_SEGMENT_ON_EXACT_PATH",
            "route_proximity_buffer_m":ROUTE_PROXIMITY_BUFFER_M,
        })
    occurrences=pd.DataFrame(occ_rows).sort_values(["realization_id","stop_sequence"],kind="mergesort").reset_index(drop=True)
    patterns=pd.DataFrame(pat_rows).sort_values("realization_id",kind="mergesort").reset_index(drop=True)
    return finalize_rt030(
        patterns=patterns, occurrences=occurrences, segatt=segatt,
        expected_graph_epoch=expected_graph_epoch, lineage=lineage,
        rt023_lineage_reconciliation=rt023_lineage_reconciliation,
    )
