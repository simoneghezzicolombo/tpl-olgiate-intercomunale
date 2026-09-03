#!/usr/bin/env python3
"""Materialise the audited Phase-2 candidate-stop universe from frozen Gate B/D evidence."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
import geopandas as gpd
import numpy as np
import pandas as pd
from pyproj import Transformer
from scipy.spatial import cKDTree
from shapely.geometry import Point
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.phase2_stop_core import *
from src.phase2_stop_sources import *
from src.phase2_stop_metrics import *

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--gate-b-dir",required=True); ap.add_argument("--gate-d-dir",required=True)
    ap.add_argument("--boundaries",required=True); ap.add_argument("--osm-pois",required=True); ap.add_argument("--osm-points",required=True)
    ap.add_argument("--od-summary",required=True); ap.add_argument("--output-dir",default="outputs/phase2")
    args=ap.parse_args(); bdir=Path(args.gate_b_dir); ddir=Path(args.gate_d_dir); out=Path(args.output_dir); out.mkdir(parents=True,exist_ok=True)
    transformer=Transformer.from_crs(4326,UTM,always_xy=True); inverse=Transformer.from_crs(UTM,4326,always_xy=True)
    directed,undirected,nodes,ids,walk_tree=load_walk_graph(bdir)
    cells=pd.read_csv(bdir/"population_accessibility.csv",dtype={"PRO_COM_T":str})
    cells["PRO_COM_T"]=cells.PRO_COM_T.astype(str).str.zfill(6)
    stops=pd.read_csv(bdir/"gtfs_core_stops.csv",dtype={"stop_id":str,"PRO_COM_T":str})
    stops["PRO_COM_T"]=stops.PRO_COM_T.astype(str).str.zfill(6)
    feeds=[]
    for fname,label in [("arriva_addabus_2025_2026.zip","ARRIVA_ADDABUS"),("lineelecco_2025_2026.zip","LINEELECCO")]:
        feeds.append(read_gtfs_zip(ddir/"raw"/fname,label))
    route_lookup=stop_route_lookup(feeds)
    stops["official_routes_reference_gtfs"]=stops.stop_id.map(lambda x:"|".join(sorted(route_lookup.get(str(x),set()))))
    stops["official_route_count_reference_gtfs"]=stops.stop_id.map(lambda x:len(route_lookup.get(str(x),set())))
    stops=cluster_existing_stops(stops)
    stops["stop_type"]="EXISTING_OFFICIAL_STOP"
    stops["epistemic_status"]="FACT_OFFICIAL_GTFS_REFERENCE_PERIOD_NOT_CURRENT_SERVICE"
    stops["source"]="GateB artifact gtfs_core_stops.csv + official GTFS route assignment"
    cluster_routes={}
    for cid,g in stops.groupby("physical_cluster_id"):
        rr=set()
        for txt in g.official_routes_reference_gtfs:
            rr.update(filter(None,str(txt).split("|")))
        cluster_routes[cid]=rr
    nearest_stop_dist,nearest_stop_source=multi_source_nearest_stop_distance(undirected,stops)

    catch_rows=[]; catch_summary=[]
    speed=WALK_CONNECTOR_KMH*1000/60
    for cid,g in stops.groupby("physical_cluster_id",sort=True):
        snapped=g[g.snap_ok.astype(bool)]
        if snapped.empty: continue
        rr=snapped.sort_values("snap_distance_m").iloc[0]
        dist=walk_distances_to_stop_node(directed,int(rr.graph_node_id),float(rr.snap_distance_m)/speed,cutoff=12)
        for t in THRESHOLDS:
            mask,total=cell_membership(cells,dist,t)
            catch_summary.append({"physical_cluster_id":cid,"threshold_min":t,
                                  "population_reachable_2025":float(cells.loc[mask,"pop_calibrated_2025"].sum()),
                                  "population_denominator_2025":float(cells.pop_calibrated_2025.sum()),
                                  "cell_count":int(mask.sum()),"epistemic_status":"MODEL_OUTPUT_GATE_B_WALK_GRAPH"})
        mask,total=cell_membership(cells,dist,12)
        for idx in cells.index[mask]:
            catch_rows.append({"physical_cluster_id":cid,"cell_id":cells.at[idx,"cell_id"],"walk_min_to_stop":float(total.at[idx]),
                               "pop_calibrated_2025":float(cells.at[idx,"pop_calibrated_2025"])})
    pd.DataFrame(catch_summary).to_csv(out/"existing_stop_catchment_summary.csv",index=False)
    pd.DataFrame(catch_rows).to_csv(out/"existing_stop_catchment_cells_12min.csv",index=False)

    gap=cells[["cell_id","lat","lon","PRO_COM_T","COMUNE","pop_calibrated_2025","walk_min_to_nearest_gtfs_stop","covered_5min","covered_8min","covered_10min","covered_12min"]].copy()
    for t in THRESHOLDS: gap[f"gap_{t}min"]=~gap[f"covered_{t}min"].astype(bool)
    gap["epistemic_status"]="MODEL_OUTPUT_GATE_B_WALK_GRAPH"
    gap.to_csv(out/"accessibility_gap_cells.csv",index=False)
    gpd.GeoDataFrame(gap,geometry=gpd.points_from_xy(gap.lon,gap.lat),crs=4326).to_file(out/"accessibility_gap_cells.geojson",driver="GeoJSON")

    boundaries_utm=gpd.read_file(args.boundaries).to_crs(UTM)
    dest_anchors=extract_osm_anchors(Path(args.osm_pois),boundaries_utm,transformer)
    settlement_anchors=extract_osm_point_settlements(Path(args.osm_points),boundaries_utm,transformer)
    anchors=pd.concat([dest_anchors,settlement_anchors],ignore_index=True).drop_duplicates("anchor_id")
    anchors=attach_point_to_walk_graph(anchors,walk_tree,ids,transformer)
    anchors["current_walk_min"]=existing_walk_time_for_anchors(anchors,directed,stops)
    anchors["current_gap_10min"]=anchors.current_walk_min.gt(10) | anchors.current_walk_min.isna()
    anchors.to_csv(out/"settlement_destination_anchors.csv",index=False)
    if not anchors.empty:
        gpd.GeoDataFrame(anchors,geometry=gpd.points_from_xy(anchors.lon,anchors.lat),crs=4326).to_file(out/"settlement_destination_anchors.geojson",driver="GeoJSON")

    samples,bounds=sample_bus_eligible_roads(ddir/"osm_gate_d_structural.geojson",Path(args.boundaries))
    slon,slat=inverse.transform(samples.x_utm32.to_numpy(float),samples.y_utm32.to_numpy(float))
    samples["lon"]=slon; samples["lat"]=slat
    sample_att=attach_point_to_walk_graph(pd.DataFrame(samples.drop(columns="geometry")),walk_tree,ids,transformer)
    samples=samples.loc[sample_att.walk_graph_snap_ok.to_numpy()].copy().reset_index(drop=True)

    gap8=cells[~cells.covered_8min.astype(bool)].copy()
    gx,gy=transformer.transform(gap8.lon.to_numpy(float),gap8.lat.to_numpy(float))
    seed_xy=[*np.column_stack([gx,gy])]; seed_labels=[f"POP_GAP8:{cid}" for cid in gap8.cell_id.astype(str)]
    for a in anchors.itertuples(index=False):
        if np.isfinite(a.current_walk_min) and float(a.current_walk_min)<=8: continue
        seed_xy.append(np.array([a.x_utm32,a.y_utm32])); seed_labels.append(f"{a.anchor_type}_GAP8:{a.anchor_id}")
    raw=nearest_seed_samples(samples,np.asarray(seed_xy,float),seed_labels)
    raw_unthinned_count=len(raw)
    raw=spatial_thin(raw,140.0)
    metrics,cellsets=build_candidate_metrics(raw,cells,anchors,directed,ids,walk_tree,transformer,nearest_stop_dist,nearest_stop_source,cluster_routes)
    metrics["pruned_near_existing_stop"]=metrics.nearest_official_stop_walk_network_m.lt(PRUNE_EXISTING_STOP_M)
    has_gain=(metrics.population_additional_8min.gt(1e-9)|metrics.population_additional_10min.gt(1e-9)|
              metrics.settlement_additional_10min_count.gt(0)|metrics.destination_additional_10min_count.gt(0))
    metrics["pruned_no_access_gain"]=~has_gain
    pre=metrics[~metrics.pruned_near_existing_stop & ~metrics.pruned_no_access_gain].copy().reset_index(drop=True)
    pre_sets={i:set() for i in range(len(pre))}
    for i,r in pre.iterrows():
        node=int(r.walk_graph_node_id); dist=walk_distances_to_stop_node(directed,node,float(r.walk_graph_connector_min),12)
        mask,_=cell_membership(cells,dist,10); pre_sets[i]=set(cells.loc[mask,"cell_id"].astype(str))
    final,prune_audit=geometric_overlap_prune(pre,pre_sets)
    final=final.sort_values(["y_utm32","x_utm32","osm_way_id"]).reset_index(drop=True)
    final["candidate_id"]=[f"P2S_{i:04d}" for i in range(1,len(final)+1)]
    final["stop_type"]="PROPOSED_STOP"
    final["physical_status"]="FIELD_CHECK_PENDING"
    final["epistemic_status"]="PROPOSED_STOP/FIELD_CHECK_PENDING"
    final["road_eligibility_status"]="DERIVED_GATE_D_BUS_ELIGIBLE"
    final["candidate_status"]="HYPOTHESIS_NOT_RECOMMENDATION"
    final["potential_interchange_with_reference_gtfs"]=final.nearest_official_stop_walk_network_m.le(300.0) & final.nearby_official_route_count.gt(0)
    final["interchange_evidence_status"]="DERIVED_FROM_REFERENCE_PERIOD_GTFS_PROXIMITY_NOT_CURRENT_SERVICE_GUARANTEE"
    final["discovery_sample_spacing_m_assumption"]=DISCOVERY_SAMPLE_M
    final["candidate_pruning_radius_m_assumption"]=PRUNE_CANDIDATE_RADIUS_M
    final["source_gate_b_commit"]=GATE_B_COMMIT; final["source_gate_d_commit"]=GATE_D_COMPUTATIONAL_COMMIT
    pg=gpd.GeoDataFrame(final.copy(),geometry=gpd.points_from_xy(final.lon,final.lat),crs=4326)
    boundaries=gpd.read_file(args.boundaries).to_crs(4326)
    code_col="PRO_COM_T" if "PRO_COM_T" in boundaries.columns else None
    name_col="COMUNE" if "COMUNE" in boundaries.columns else None
    if code_col and name_col:
        codes=[]; names=[]
        boundaries_metric=boundaries.to_crs(UTM)
        for pnt in pg.geometry:
            hits=boundaries[boundaries.geometry.contains(pnt)]
            if hits.empty:
                pmetric=gpd.GeoSeries([pnt],crs=4326).to_crs(UTM).iloc[0]
                d=boundaries_metric.geometry.distance(pmetric)
                hit=boundaries.loc[[d.idxmin()]].iloc[0]
            else:
                hit=hits.sort_values(code_col).iloc[0]
            codes.append(str(hit[code_col]).zfill(6)); names.append(str(hit[name_col]))
        final["PRO_COM_T"]=codes; final["COMUNE"]=names
    od=pd.read_csv(args.od_summary,dtype={"procom":str}); od["procom"]=od.procom.str.zfill(6)
    odmap=od.set_index("procom")
    final["municipal_2021_resident_work_commuters_context"]=final.PRO_COM_T.map(odmap.resident_commuters)
    final["municipal_2021_outbound_workers_context"]=final.PRO_COM_T.map(odmap.outbound_workers)
    final["od_2021_context_status"]="FACT_ISTAT_2021_WORK_COMMUTING_MUNICIPAL_ONLY_NOT_STOP_DEMAND"
    final.to_csv(out/"proposed_stop_candidates.csv",index=False)
    geo=gpd.GeoDataFrame(final.copy(),geometry=gpd.points_from_xy(final.lon,final.lat),crs=4326)
    geo.to_file(out/"proposed_stop_candidates.geojson",driver="GeoJSON")

    stops.to_csv(out/"existing_official_stops.csv",index=False)
    gpd.GeoDataFrame(stops,geometry=gpd.points_from_xy(stops.stop_lon,stops.stop_lat),crs=4326).to_file(out/"existing_official_stops.geojson",driver="GeoJSON")
    inter=[]
    for cid,g in stops.groupby("physical_cluster_id"):
        routes=cluster_routes.get(cid,set()); names="|".join(sorted(set(g.stop_name.astype(str))))
        inter.append({"physical_cluster_id":cid,"stop_ids":"|".join(sorted(g.stop_id.astype(str))),"stop_names":names,
                      "official_routes_reference_gtfs":"|".join(sorted(routes)),"route_count":len(routes),
                      "interchange_candidate":len(routes)>=2,"epistemic_status":"DERIVED_FROM_OFFICIAL_GTFS_REFERENCE_PERIOD"})
    inter=pd.DataFrame(inter)
    arlate=stops[stops.stop_name.str.contains("arlate",case=False,na=False)]
    arlate_clusters=sorted(set(arlate.physical_cluster_id.astype(str)))
    inter["arlate_hypothesis_note"]=""
    if arlate_clusters:
        mask=inter.physical_cluster_id.isin(arlate_clusters)
        inter.loc[mask,"arlate_hypothesis_note"]=(
            "ARLATE_EXISTING_GTFS_STOP_INTERCHANGE_OPPORTUNITY; reference GTFS routes="+
            inter.loc[mask,"official_routes_reference_gtfs"].astype(str)+
            "; D201/D202 Circolare Meratese absent from validated 2025-2026 GTFS, so no shared-stop claim is made"
        )
    inter.to_csv(out/"interchange_opportunities.csv",index=False)
    prune_audit.to_csv(out/"candidate_pruning_audit.csv",index=False)

    cc=[]
    for r in final.itertuples(index=False):
        dist=walk_distances_to_stop_node(directed,int(r.walk_graph_node_id),float(r.walk_graph_connector_min),10)
        mask,total=cell_membership(cells,dist,10)
        for idx in cells.index[mask]:
            cc.append({"candidate_id":r.candidate_id,"cell_id":cells.at[idx,"cell_id"],"walk_min_to_candidate":float(total.at[idx]),
                       "pop_calibrated_2025":float(cells.at[idx,"pop_calibrated_2025"]),"already_covered_10min":bool(cells.at[idx,"covered_10min"])})
    pd.DataFrame(cc).to_csv(out/"proposed_stop_candidate_catchment_cells_10min.csv",index=False)

    val={
        "status":"PASS_STOP_UNIVERSE_BUILD",
        "scope":"CANDIDATE_STOP_UNIVERSE_NOT_FINAL_NETWORK",
        "gate_b_commit":GATE_B_COMMIT,"gate_d_computational_commit":GATE_D_COMPUTATIONAL_COMMIT,
        "gate_b_population_denominator_2025":float(cells.pop_calibrated_2025.sum()),
        "existing_official_stop_records":int(len(stops)),"existing_physical_stop_clusters":int(stops.physical_cluster_id.nunique()),
        "existing_snapped_stop_records":int(stops.snap_ok.astype(bool).sum()),
        "baseline_coverage_pct":{"5":float(cells.loc[cells.covered_5min.astype(bool),"pop_calibrated_2025"].sum()/cells.pop_calibrated_2025.sum()*100),
                                 "8":float(cells.loc[cells.covered_8min.astype(bool),"pop_calibrated_2025"].sum()/cells.pop_calibrated_2025.sum()*100),
                                 "10":float(cells.loc[cells.covered_10min.astype(bool),"pop_calibrated_2025"].sum()/cells.pop_calibrated_2025.sum()*100),
                                 "12":float(cells.loc[cells.covered_12min.astype(bool),"pop_calibrated_2025"].sum()/cells.pop_calibrated_2025.sum()*100)},
        "osm_settlement_anchors":int((anchors.anchor_type=="SETTLEMENT").sum()) if not anchors.empty else 0,
        "osm_destination_anchors":int((anchors.anchor_type=="DESTINATION").sum()) if not anchors.empty else 0,
        "bus_eligible_discovery_samples_with_gate_b_walk_access":int(len(samples)),
        "raw_seeded_candidates_before_geometry_thin":int(raw_unthinned_count),"raw_seeded_candidates":int(len(raw)),"pre_geometric_pruning_candidates":int(len(pre)),"final_proposed_candidates":int(len(final)),
        "new_stop_epistemic_status":"PROPOSED_STOP/FIELD_CHECK_PENDING",
        "legacy_processed_population_used":False,"legacy_hardcoded_poi_dataset_used":False,"live_overpass_used":False,
        "principal_optimizer_catchment_threshold_min":10,
        "thresholds_reported_min":list(THRESHOLDS),
        "assumptions":{"discovery_sample_m":DISCOVERY_SAMPLE_M,"seed_radius_m":DISCOVERY_SEED_RADIUS_M,
                       "near_existing_prune_m":PRUNE_EXISTING_STOP_M,"candidate_prune_radius_m":PRUNE_CANDIDATE_RADIUS_M,
                       "catchment_jaccard_prune":PRUNE_CATCHMENT_JACCARD},
        "limitations":[
            "Gate B walking/population evidence is limited to the five core municipalities; proposed-stop generation is therefore limited to that audited spatial universe plus the Gate-B boundary buffer.",
            "Official bus GTFS route assignments describe the validated 2025-2026 reference period, not exact current post-2026-06-08 stop service.",
            "OSM settlement/destination anchors are observations, not an exhaustive registry.",
            "No proposed stop is certified physically constructible; every proposal requires field verification.",
            "ISTAT 2021 work OD is municipal context only and is not downscaled to stops."
        ]
    }
    (out/"stop_universe_validation.json").write_text(json.dumps(val,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    owned_prefixes=("existing_","accessibility_","settlement_","proposed_","interchange_","candidate_","stop_universe_")
    targets=sorted(p for p in out.iterdir() if p.is_file() and p.name != "stop_universe_checksums.sha256" and p.name.startswith(owned_prefixes))
    with (out/"stop_universe_checksums.sha256").open("w",encoding="utf-8") as f:
        for p in targets: f.write(f"{sha256(p)}  {p.name}\n")
    print(json.dumps(val,indent=2,ensure_ascii=False))

if __name__=="__main__": main()
