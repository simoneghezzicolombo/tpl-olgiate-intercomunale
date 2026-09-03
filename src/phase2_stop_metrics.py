"""Walking-network candidate metrics and deterministic pruning for Phase 2."""
from __future__ import annotations
import math
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree
from src.phase2_stop_core import *
from src.phase2_stop_sources import *

def build_candidate_metrics(cands, cells, anchors, directed, ids, tree, transformer, nearest_stop_dist, nearest_stop_source, cluster_routes):
    cands=attach_point_to_walk_graph(pd.DataFrame(cands.drop(columns="geometry")),tree,ids,transformer)
    cands=cands[cands.walk_graph_snap_ok].copy().reset_index(drop=True)
    candidate_cellsets={}
    rows=[]
    for i,r in cands.iterrows():
        node=int(r.walk_graph_node_id); stop_conn=float(r.walk_graph_connector_min)
        dist=walk_distances_to_stop_node(directed,node,stop_conn,cutoff=max(THRESHOLDS))
        vals=dict(r)
        for t in THRESHOLDS:
            mask,total=cell_membership(cells,dist,t)
            pop=float(cells.loc[mask,"pop_calibrated_2025"].sum())
            current=cells[f"covered_{t}min"].astype(bool)
            added=mask & ~current
            overlap=mask & current
            vals[f"population_reachable_{t}min"]=pop
            vals[f"population_additional_{t}min"]=float(cells.loc[added,"pop_calibrated_2025"].sum())
            vals[f"existing_catchment_overlap_population_{t}min"]=float(cells.loc[overlap,"pop_calibrated_2025"].sum())
            vals[f"existing_catchment_overlap_pct_{t}min"]=float(cells.loc[overlap,"pop_calibrated_2025"].sum()/pop*100) if pop>0 else 0.0
            if t==10: candidate_cellsets[i]=set(cells.loc[mask,"cell_id"].astype(str))
        nd=nearest_stop_dist.get(node,float("inf"))+float(r.walk_graph_connector_m)
        vals["nearest_official_stop_walk_network_m"]=float(nd)
        vals["nearest_official_stop_cluster_id"]=nearest_stop_source.get(node,"")
        routes=cluster_routes.get(vals["nearest_official_stop_cluster_id"],set())
        vals["nearby_official_routes"]="|".join(sorted(routes))
        vals["nearby_official_route_count"]=len(routes)
        for atype in ("SETTLEMENT","DESTINATION"):
            total_cov=add_cov=0; added_names=[]
            for a in anchors[anchors.anchor_type.eq(atype)].itertuples(index=False):
                if not bool(a.walk_graph_snap_ok): continue
                network=dist.get(int(a.walk_graph_node_id),np.nan)
                wt=float(network)+float(a.walk_graph_connector_min) if np.isfinite(network) else np.nan
                if np.isfinite(wt) and wt<=10:
                    total_cov+=1
                    if not np.isfinite(a.current_walk_min) or float(a.current_walk_min)>10:
                        add_cov+=1; added_names.append(str(a.name))
            key=atype.lower()
            vals[f"{key}_coverage_10min_count"]=total_cov
            vals[f"{key}_additional_10min_count"]=add_cov
            vals[f"{key}_additional_10min_names"]="|".join(sorted(set(added_names)))
        rows.append(vals)
    return pd.DataFrame(rows),candidate_cellsets


def geometric_overlap_prune(metrics: pd.DataFrame, cellsets: dict[int,set[str]]):
    """Greedy spatial/catchment compression in coordinate order, without utility scoring."""
    if metrics.empty: return metrics.copy(), pd.DataFrame()
    m=metrics.copy().sort_values(["y_utm32","x_utm32","osm_way_id","sample_index"]).reset_index(drop=True)
    keep=[]; audit=[]
    for i,row in m.iterrows():
        x,y=float(row.x_utm32),float(row.y_utm32); A=cellsets.get(i,set())
        redundant_with=None; reason=None
        for j in keep:
            other=m.loc[j]; dx=x-float(other.x_utm32); dy=y-float(other.y_utm32); d=math.hypot(dx,dy)
            if d < PRUNE_CANDIDATE_RADIUS_M:
                redundant_with=j; reason="CANDIDATE_SPACING_REDUNDANCY"; break
            if d < PRUNE_CATCHMENT_RADIUS_M:
                B=cellsets.get(j,set()); union=A|B
                jac=len(A&B)/len(union) if union else 1.0
                if jac>=PRUNE_CATCHMENT_JACCARD:
                    redundant_with=j; reason="TEN_MIN_CATCHMENT_REDUNDANCY"; break
        if redundant_with is None:
            keep.append(i); audit.append({"preprune_row":i,"representative_preprune_row":i,"pruned":False,"reason":"RETAINED_SPATIAL_ORDER"})
        else:
            audit.append({"preprune_row":i,"representative_preprune_row":redundant_with,"pruned":True,"reason":reason})
    return m.iloc[keep].copy().reset_index(drop=True),pd.DataFrame(audit)
