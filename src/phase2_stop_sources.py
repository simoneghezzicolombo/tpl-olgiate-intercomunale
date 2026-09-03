"""Frozen real-source extraction and bus-eligible discovery for Phase 2 stop universe."""
from __future__ import annotations
import json
from collections import defaultdict
from pathlib import Path
import geopandas as gpd
import numpy as np
import pandas as pd
from pyproj import Transformer
from scipy.spatial import cKDTree
from shapely.geometry import LineString, Point
from src.phase2_stop_core import *

def extract_osm_anchors(path: Path, boundaries_utm: gpd.GeoDataFrame, transformer: Transformer) -> pd.DataFrame:
    payload=json.loads(path.read_text(encoding="utf-8"))
    rows=[]
    for el in payload.get("elements",[]):
        tags=el.get("tags") or {}
        lon=lat=None
        if "lon" in el and "lat" in el:
            lon=float(el["lon"]); lat=float(el["lat"])
        elif isinstance(el.get("center"),dict) and {"lon","lat"} <= set(el["center"]):
            lon=float(el["center"]["lon"]); lat=float(el["center"]["lat"])
        if lon is None: continue
        place=str(tags.get("place","")).lower()
        kind=None; category=None
        if place in SETTLEMENT_PLACE_TYPES:
            kind="SETTLEMENT"; category=place
        else:
            amenity=str(tags.get("amenity","")).lower(); shop=str(tags.get("shop","")).lower(); leisure=str(tags.get("leisure","")).lower(); tourism=str(tags.get("tourism","")).lower()
            if amenity in MAJOR_AMENITIES: kind="DESTINATION"; category=f"amenity:{amenity}"
            elif shop in MAJOR_SHOPS: kind="DESTINATION"; category=f"shop:{shop}"
            elif leisure in MAJOR_LEISURE: kind="DESTINATION"; category=f"leisure:{leisure}"
            elif tourism in MAJOR_TOURISM: kind="DESTINATION"; category=f"tourism:{tourism}"
        if not kind: continue
        x,y=transformer.transform(lon,lat)
        p=Point(x,y)
        if not boundaries_utm.geometry.union_all().buffer(CORE_BUFFER_M).contains(p): continue
        rows.append({
            "anchor_id":f"OSM_{el.get('type','x')}_{el.get('id')}","anchor_type":kind,
            "name":str(tags.get("name") or tags.get("addr:city") or f"OSM {category} {el.get('id')}"),
            "category":category,"lat":lat,"lon":lon,
            "epistemic_status":"FACT_OSM_OBSERVATION","source":"data/raw/osm/osm_pois_core.json",
        })
    return pd.DataFrame(rows).drop_duplicates("anchor_id")


def extract_osm_point_settlements(path: Path, boundaries_utm: gpd.GeoDataFrame, transformer: Transformer) -> pd.DataFrame:
    points=gpd.read_file(path).to_crs(4326)
    core=boundaries_utm.geometry.union_all().buffer(CORE_BUFFER_M)
    rows=[]
    for _,row in points.iterrows():
        place=str(row.get("place") or "").strip().lower()
        if place not in SETTLEMENT_PLACE_TYPES: continue
        geom=row.geometry
        if geom is None or geom.is_empty or not isinstance(geom,Point): continue
        x,y=transformer.transform(float(geom.x),float(geom.y))
        if not core.contains(Point(x,y)): continue
        rows.append({"anchor_id":f"OSM_POINT_{row.get('osm_id')}","anchor_type":"SETTLEMENT",
                     "name":str(row.get("name") or f"OSM {place} {row.get('osm_id')}"),"category":place,
                     "lat":float(geom.y),"lon":float(geom.x),"epistemic_status":"FACT_OSM_OBSERVATION",
                     "source":"data/raw/osm/osm_points_core.geojson"})
    return pd.DataFrame(rows).drop_duplicates("anchor_id")

def attach_point_to_walk_graph(frame: pd.DataFrame, tree: cKDTree, ids: np.ndarray, transformer: Transformer):
    if frame.empty:
        for c in ["walk_graph_node_id","walk_graph_connector_m","walk_graph_connector_min","walk_graph_snap_ok"]: frame[c]=[]
        return frame
    xs,ys=transformer.transform(frame.lon.to_numpy(float),frame.lat.to_numpy(float))
    d,idx=tree.query(np.column_stack([xs,ys]),k=1)
    frame=frame.copy(); frame["x_utm32"]=xs; frame["y_utm32"]=ys
    frame["walk_graph_node_id"]=ids[idx].astype(int); frame["walk_graph_connector_m"]=d
    frame["walk_graph_connector_min"]=d/(WALK_CONNECTOR_KMH*1000/60)
    frame["walk_graph_snap_ok"]=d<=MAX_STOP_SNAP_M
    return frame


def existing_walk_time_for_anchors(anchors, directed, existing_stop_nodes):
    rg=directed.reverse(copy=True); super_node=min(rg.nodes)-1
    while super_node in rg: super_node-=1
    rg.add_node(super_node)
    speed=WALK_CONNECTOR_KMH*1000/60
    best_by_node={}
    for r in existing_stop_nodes.itertuples(index=False):
        if not bool(r.snap_ok): continue
        n=int(r.graph_node_id); connector=float(r.snap_distance_m)/speed
        best_by_node[n]=min(best_by_node.get(n,float("inf")),connector)
    for n,d in best_by_node.items(): rg.add_edge(super_node,n,walk_min=d)
    dist=nx.single_source_dijkstra_path_length(rg,super_node,weight="walk_min")
    out=[]
    for r in anchors.itertuples(index=False):
        if not bool(r.walk_graph_snap_ok): out.append(np.nan); continue
        net=dist.get(int(r.walk_graph_node_id),np.nan)
        out.append(float(net)+float(r.walk_graph_connector_min) if np.isfinite(net) else np.nan)
    return out


def sample_bus_eligible_roads(roads_path: Path, boundaries_path: Path):
    roads=gpd.read_file(roads_path).to_crs(UTM)
    boundaries=gpd.read_file(boundaries_path).to_crs(UTM)
    core=boundaries.geometry.union_all().buffer(CORE_BUFFER_M)
    rows=[]
    for _, row in roads.iterrows():
        eligible,uncertainty=bus_eligibility(row)
        if not eligible: continue
        highway=str(row.get("highway") or "")
        if highway in STOP_SITING_UNSUPPORTED_HIGHWAYS: continue
        geom=row.geometry
        if geom is None or geom.is_empty: continue
        clipped=geom.intersection(core)
        parts=list(clipped.geoms) if hasattr(clipped,"geoms") else [clipped]
        for part in parts:
            if not isinstance(part,LineString) or part.length<=0: continue
            distances=np.arange(DISCOVERY_SAMPLE_M/2, part.length, DISCOVERY_SAMPLE_M)
            if len(distances)==0: distances=np.array([part.length/2])
            for i,d in enumerate(distances):
                p=part.interpolate(float(d))
                rows.append({"osm_way_id":str(row.get("osm_way_id")),"highway":highway,
                             "road_uncertainty_flags":"|".join(uncertainty),"sample_index":i,
                             "x_utm32":p.x,"y_utm32":p.y,"geometry":p})
    samples=gpd.GeoDataFrame(rows,geometry="geometry",crs=UTM)
    if samples.empty: raise ValueError("No Gate-D bus-eligible road samples inside Gate-B core")
    return samples,boundaries


def nearest_seed_samples(samples: gpd.GeoDataFrame, seeds_xy: np.ndarray, seed_labels: list[str]):
    tree=cKDTree(np.column_stack([samples.x_utm32,samples.y_utm32]))
    evidence=defaultdict(list)
    for xy,label in zip(seeds_xy,seed_labels):
        d,idx=tree.query(xy,k=min(3,len(samples)),distance_upper_bound=DISCOVERY_SEED_RADIUS_M)
        d=np.atleast_1d(d); idx=np.atleast_1d(idx)
        for dd,ii in zip(d,idx):
            if np.isfinite(dd) and int(ii)<len(samples): evidence[int(ii)].append(label)
    chosen=samples.iloc[sorted(evidence)].copy()
    chosen["discovery_evidence"]=["|".join(sorted(set(evidence[i]))) for i in sorted(evidence)]
    chosen["discovery_seed_count"]=[len(set(evidence[i])) for i in sorted(evidence)]
    return chosen.reset_index(drop=True)


def spatial_thin(frame: pd.DataFrame, radius_m: float) -> pd.DataFrame:
    """Deterministic non-transitive spatial thinning; not an attractiveness ranking."""
    if frame.empty:
        return frame.copy()
    f=frame.sort_values(["y_utm32","x_utm32","osm_way_id","sample_index"]).reset_index(drop=True)
    kept=[]; kept_xy=[]
    r2=radius_m*radius_m
    for i,row in f.iterrows():
        x=float(row.x_utm32); y=float(row.y_utm32)
        if all((x-kx)**2+(y-ky)**2 >= r2 for kx,ky in kept_xy):
            kept.append(i); kept_xy.append((x,y))
    return f.iloc[kept].copy().reset_index(drop=True)
