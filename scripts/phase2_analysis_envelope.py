#!/usr/bin/env python3
"""Build the Phase-2 supramunicipal ANALYSIS ENVELOPE without selecting a network."""
from __future__ import annotations

import argparse, gzip, hashlib, io, json, tempfile, zipfile
from pathlib import Path

import geopandas as gpd
import pandas as pd
import requests
from shapely.geometry import LineString, box
from shapely.ops import unary_union

BASELINE = "147ad941579eb7ef17a5a54c19a5f820e5a226d4"
GATE_D_EPOCH = "gate-d-2026-09-03-834d5caa0bfd"
UTM = 32632
CORE = {
    "097010": "Brivio", "097012": "Calco", "097058": "Olgiate Molgora",
    "097074": "Santa Maria Hoè", "097092": "La Valletta Brianza",
}
# Inherited V1 contract: 12 min, 4.8 km/h connector speed, 250 m snap cap.
MAX_WALK_MIN = 12.0
WALK_KMH = 4.8
MAX_SNAP_M = 250.0
EDGE_GUARD_M = MAX_WALK_MIN * (WALK_KMH * 1000.0 / 60.0) + MAX_SNAP_M  # 1210 m
ADJ_TOL_M = 5.0
MUN_URL = "https://www.istat.it/storage/cartografia/confini_amministrativi/non_generalizzati/2026/Limiti01012026.zip"
SEC_URL = "https://www.istat.it/storage/cartografia/basi_territoriali/2021/R03_21.zip"
DBGT_METADATA = "https://geodati.gov.it/geoportale/visualizzazione-metadati/scheda-metadati?metadataid=r_lombar%3A3493af32-587c-4bca-92a4-ea717ea1a617"
DBGT_QUERY = "https://www.cartografia.servizirl.it/arcgis5/rest/services/BaseMap/DBGT_Tema0201_Edificato/MapServer/5/query"
HEADERS = {"User-Agent": "tpl-olgiate-phase2-analysis-envelope/1.0 (+https://github.com/simoneghezzicolombo/tpl-olgiate-intercomunale)"}


def sha_bytes(b): return hashlib.sha256(b).hexdigest()
def sha_file(p):
    h=hashlib.sha256()
    with Path(p).open("rb") as f:
        for c in iter(lambda:f.read(1024*1024),b""): h.update(c)
    return h.hexdigest()

def norm(v):
    s=str(v).strip().removesuffix(".0") if v is not None else ""
    d="".join(c for c in s if c.isdigit())
    return d.zfill(6) if d else ""
def gz_write(path,payload):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("wb") as raw:
        with gzip.GzipFile(fileobj=raw,mode="wb",filename="",mtime=0) as z: z.write(payload)
def gj_bytes(gdf,cols):
    return gdf.sort_values(cols,kind="mergesort").reset_index(drop=True).to_crs(4326).to_json(drop_id=True,ensure_ascii=False).encode()
def get_bytes(url):
    last=None
    for _ in range(4):
        try:
            r=requests.get(url,headers=HEADERS,timeout=240); r.raise_for_status(); return r.content
        except Exception as e: last=e
    raise RuntimeError(f"acquisition failed {url}: {last}")
def read_zip(payload,chooser):
    if len(payload)<10000 or payload[:2]!=b"PK": raise RuntimeError("not a plausible ZIP")
    with tempfile.TemporaryDirectory() as t:
        zpath=Path(t)/"s.zip"; zpath.write_bytes(payload)
        with zipfile.ZipFile(zpath) as z:
            shps=[n for n in z.namelist() if n.lower().endswith(".shp")]; target=chooser(shps)
            if not target: raise RuntimeError(f"no matching shp: {shps[:20]}")
            stem=str(Path(target).with_suffix("")); z.extractall(t,[n for n in z.namelist() if str(Path(n).with_suffix(""))==stem])
        return gpd.read_file(Path(t)/target)
def choose_mun(shps):
    a=[n for n in shps if "com" in Path(n).name.lower() and "wgs84" in n.lower()]
    b=[n for n in shps if "com" in Path(n).name.lower()]
    return sorted(a or b)[0] if (a or b) else None
def choose_sec(shps):
    a=[n for n in shps if "sez" in Path(n).name.lower() and "21" in Path(n).name]
    return sorted(a or shps)[0] if (a or shps) else None
def col(df,names):
    m={c.upper():c for c in df.columns}
    return next((m[n.upper()] for n in names if n.upper() in m),None)

def prep_mun(raw):
    if raw.crs is None: raise RuntimeError("municipalities CRS missing")
    c=col(raw,["PRO_COM_T","PRO_COM"]); n=col(raw,["COMUNE"])
    if not c or not n: raise RuntimeError(f"municipality schema {list(raw.columns)}")
    x=raw[[c,n,"geometry"]].copy(); x["procom"]=x[c].map(norm); x["municipality_name"]=x[n].astype(str).str.strip()
    return x[["procom","municipality_name","geometry"]].drop_duplicates("procom").to_crs(UTM)
def prep_sec(raw):
    if raw.crs is None: raise RuntimeError("sections CRS missing")
    pc=col(raw,["PRO_COM","PRO_COM_T","PROCOM"]); sid=col(raw,["SEZ21_ID","SEZ21","GISTAT_SEZ"])
    pop=col(raw,["POP21"]); edi=col(raw,["EDI21"])
    if not pc or not sid: raise RuntimeError(f"section schema {list(raw.columns)}")
    x=raw.copy(); x["procom"]=x[pc].map(norm); x["section_id"]=x[sid].astype(str).str.replace(r"\.0$","",regex=True)
    x["POP21"]=pd.to_numeric(x[pop],errors="coerce") if pop else pd.NA; x["EDI21"]=pd.to_numeric(x[edi],errors="coerce") if edi else pd.NA
    return x[["procom","section_id","POP21","EDI21","geometry"]].to_crs(UTM)
def rings(m):
    core=m[m.procom.isin(CORE)].copy()
    if set(core.procom)!=set(CORE): raise RuntimeError(f"missing core {set(CORE)-set(core.procom)}")
    cu=unary_union(core.geometry.tolist()); o=m[~m.procom.isin(CORE)].copy(); first=o[o.geometry.distance(cu)<=ADJ_TOL_M].copy()
    fu=unary_union([cu,*first.geometry.tolist()]); rem=o[~o.procom.isin(first.procom)].copy(); second=rem[rem.geometry.distance(fu)<=ADJ_TOL_M].copy()
    su=unary_union([fu,*second.geometry.tolist()]); return core,first,second,cu,fu,su
def candidates(cu,fu,su):
    return {"METRIC_GUARD_ONLY":cu.buffer(EDGE_GUARD_M),"ADJACENCY_1_PLUS_V1_WALK_GUARD":fu.buffer(EDGE_GUARD_M),"ADJACENCY_2_PLUS_V1_WALK_GUARD_SENSITIVITY":su.buffer(EDGE_GUARD_M)}
def load_gz(path):
    with gzip.open(path,"rb") as f: return gpd.read_file(io.BytesIO(f.read())).to_crs(UTM)

def query_buildings(extent):
    b=gpd.GeoSeries([extent],crs=UTM).to_crs(7791).iloc[0].bounds; feats=[]; offset=0
    while True:
        p={"where":"1=1","geometry":",".join(f"{v:.3f}" for v in b),"geometryType":"esriGeometryEnvelope","inSR":"7791","spatialRel":"esriSpatialRelIntersects","outFields":"OBJECTID,CLASSREF,COD_CONS,DATA_FIN,Shape_Area","returnGeometry":"true","outSR":"4326","orderByFields":"OBJECTID ASC","resultOffset":offset,"resultRecordCount":2000,"f":"geojson"}
        r=requests.get(DBGT_QUERY,params=p,headers=HEADERS,timeout=240); r.raise_for_status(); j=r.json()
        if "error" in j: raise RuntimeError(j["error"])
        batch=j.get("features",[]); feats.extend(batch)
        if len(batch)<2000: break
        offset+=len(batch)
        if offset>200000: raise RuntimeError("building pagination safety cap")
    if not feats: raise RuntimeError("no DBGT buildings")
    return gpd.GeoDataFrame.from_features(feats,crs=4326).to_crs(UTM).drop_duplicates("OBJECTID").sort_values("OBJECTID")

def acquire(src,graph_manifest):
    src.mkdir(parents=True,exist_ok=True)
    mz=get_bytes(MUN_URL); m=prep_mun(read_zip(mz,choose_mun)); s,w,n,e=map(float,graph_manifest["bbox_south_west_north_east"])
    gb=gpd.GeoSeries([box(w,s,e,n)],crs=4326).to_crs(UTM).iloc[0]; m=m[m.intersects(gb.buffer(EDGE_GUARD_M))].copy()
    _,_,_,cu,fu,su=rings(m); cs=candidates(cu,fu,su); selected=cs["ADJACENCY_1_PLUS_V1_WALK_GUARD"]
    comparison=unary_union([selected.buffer(EDGE_GUARD_M),cs["ADJACENCY_2_PLUS_V1_WALK_GUARD_SENSITIVITY"]])
    sz=get_bytes(SEC_URL); sec=prep_sec(read_zip(sz,choose_sec)); sec=sec[sec.intersects(comparison)].copy()
    bld=query_buildings(comparison.envelope); bld=bld[bld.intersects(comparison)].copy()
    if sec.empty or bld.empty: raise RuntimeError("empty official context source")
    paths={"municipalities_context.geojson.gz":m,"census_sections_context.geojson.gz":sec,"dbgt_buildings_context.geojson.gz":bld}
    for name,g in paths.items(): gz_write(src/name,gj_bytes(g,["procom"] if name.startswith("municip") else (["procom","section_id"] if name.startswith("census") else ["OBJECTID"])))
    man={"workstream":"phase2-analysis-envelope","baseline_commit":BASELINE,"source_state":"FROZEN_AFTER_PRIMARY_ACQUISITION","municipalities":{"url":MUN_URL,"zip_sha256":sha_bytes(mz),"epistemic_status":"FACT_OFFICIAL_ISTAT_2026_BOUNDARIES"},"census_sections":{"url":SEC_URL,"zip_sha256":sha_bytes(sz),"epistemic_status":"FACT_OFFICIAL_ISTAT_2021_CENSUS_SECTIONS"},"buildings":{"metadata_url":DBGT_METADATA,"query_url":DBGT_QUERY,"layer":"EDIFC_CR_EDF_ME (ID 5)","license":"CC-BY-4.0","epistemic_status":"FACT_OFFICIAL_REGIONE_LOMBARDIA_DBGT_BUILDING_FOOTPRINT"},"graph_epoch":{"epoch_id":graph_manifest["epoch_id"],"raw_osm_sha256":graph_manifest["raw_osm_sha256"],"epistemic_status":"DERIVED_FROM_FROZEN_GATE_D_PASS"},"frozen_source_files_sha256":{k:sha_file(src/k) for k in paths},"acquisition_extent_policy":"UNION(ADJACENCY_2_SENSITIVITY, SELECTED_ANALYSIS_ENVELOPE_BUFFERED_BY_EDGE_GUARD)","live_refresh_policy":"Any refresh creates a new snapshot and requires explicit checksum comparison; never silently replace this one."}
    (src/"source_manifest.json").write_text(json.dumps(man,ensure_ascii=False,sort_keys=True,separators=(",",":"))+"\n",encoding="utf-8")
def verify_src(src):
    m=json.loads((src/"source_manifest.json").read_text(encoding="utf-8"))
    for f,h in m["frozen_source_files_sha256"].items():
        if sha_file(src/f)!=h: raise AssertionError(f"source checksum mismatch {f}")
    return m

def assign(points,muns):
    j=gpd.sjoin(points[["geometry"]],muns[["procom","municipality_name","geometry"]],how="left",predicate="within")
    return j[~j.index.duplicated()][["procom","municipality_name"]].reindex(points.index)
def roads_inventory(selected,cu,muns,gdir):
    nd=pd.read_csv(gdir/"graph_nodes.csv.gz",dtype={"node_id":str}); ed=pd.read_csv(gdir/"graph_edges.csv.gz",dtype=str)
    xy=nd.set_index("node_id")[["x_m_epsg32632","y_m_epsg32632"]].astype(float).to_dict("index"); rows=[]
    for r in ed.itertuples(index=False):
        a=xy[str(r.u_node_id)]; b=xy[str(r.v_node_id)]; line=LineString([(a["x_m_epsg32632"],a["y_m_epsg32632"]),(b["x_m_epsg32632"],b["y_m_epsg32632"])] )
        if not line.intersects(selected): continue
        p=line.interpolate(.5,normalized=True); rows.append({"edge_id":r.edge_id,"osm_way_id":r.osm_way_id,"length_m":float(r.length_m),"mid_x":p.x,"mid_y":p.y,"analysis_role":"CORE" if p.within(cu) else "CONTEXT","crosses_analysis_boundary":bool(line.crosses(selected.boundary) or not selected.covers(line)),"epoch_id":r.epoch_id})
    out=pd.DataFrame(rows); pts=gpd.GeoDataFrame(out.copy(),geometry=gpd.points_from_xy(out.mid_x,out.mid_y),crs=UTM); a=assign(pts,muns); out["procom"]=a.procom.values; out["municipality_name"]=a.municipality_name.values
    return out.sort_values("edge_id")
def build(src,out,gdir,gmanifest,forbid_live):
    gm=json.loads(Path(gmanifest).read_text(encoding="utf-8")); assert gm["epoch_id"]==GATE_D_EPOCH
    acquired=False
    if not (src/"source_manifest.json").exists():
        if forbid_live: raise RuntimeError("source-closed build requested but source snapshot missing")
        acquire(src,gm); acquired=True
    sm=verify_src(src); m=load_gz(src/"municipalities_context.geojson.gz"); secall=load_gz(src/"census_sections_context.geojson.gz"); bldall=load_gz(src/"dbgt_buildings_context.geojson.gz")
    m["procom"]=m.procom.map(norm); core,first,second,cu,fu,su=rings(m); cs=candidates(cu,fu,su)
    s,w,n,e=map(float,gm["bbox_south_west_north_east"]); gb=gpd.GeoSeries([box(w,s,e,n)],crs=4326).to_crs(UTM).iloc[0]
    support={name:bool(gb.covers(g.buffer(MAX_SNAP_M)) and g.covers(cu.buffer(EDGE_GUARD_M-1e-6))) for name,g in cs.items()}
    preference=["ADJACENCY_2_PLUS_V1_WALK_GUARD_SENSITIVITY","ADJACENCY_1_PLUS_V1_WALK_GUARD","METRIC_GUARD_ONLY"]
    selected_name=next((name for name in preference if support.get(name)),None)
    if selected_name is None: raise AssertionError({"source_supported_rules":support,"reason":"No tested envelope contains the V1 core guard and remains inside frozen Gate D plus probe"})
    selected=cs[selected_name]; acquisition=selected.buffer(EDGE_GUARD_M)
    graph_ok=bool(gb.covers(selected.buffer(MAX_SNAP_M))); core_ok=bool(selected.covers(cu.buffer(EDGE_GUARD_M-1e-6))); first_ok=bool(selected.covers(fu.buffer(EDGE_GUARD_M-1e-6)))
    if not all([graph_ok,core_ok]): raise AssertionError({"graph":graph_ok,"core":core_ok,"first":first_ok})
    fset=set(first.procom); sset=set(second.procom); rows=[]
    for r in m.itertuples(index=False):
        ov=r.geometry.intersection(selected).area
        if ov<=0: continue
        role="CORE" if r.procom in CORE else "CONTEXT"; order=0 if role=="CORE" else (1 if r.procom in fset else (2 if r.procom in sset else None))
        rows.append({"procom":r.procom,"municipality_name":r.municipality_name,"analysis_role":role,"adjacency_order_from_core":order,"municipality_area_m2":r.geometry.area,"analysis_overlap_m2":ov,"analysis_overlap_pct":ov/r.geometry.area*100,"equity_scope":"DECISION_CORE_EQUITY_OBLIGATION" if role=="CORE" else "CONTEXT_ONLY_NO_EQUAL_EQUITY_OBLIGATION"})
    mi=pd.DataFrame(rows).sort_values(["analysis_role","adjacency_order_from_core","municipality_name"],na_position="last")
    names=m.set_index("procom").municipality_name.to_dict(); sec=secall[secall.intersects(selected)].copy(); sec["municipality_name"]=sec.procom.map(names); sec["analysis_role"]=sec.procom.map(lambda c:"CORE" if c in CORE else "CONTEXT"); sec["section_area_m2"]=sec.area; sec["analysis_overlap_m2"]=sec.geometry.map(lambda g:g.intersection(selected).area); sec["analysis_overlap_pct"]=sec.analysis_overlap_m2/sec.section_area_m2*100; sec["touches_analysis_boundary"]=sec.geometry.intersects(selected.boundary); sec["population_epistemic_note"]="FACT_ISTAT_2021_FULL_SECTION_VALUE_NOT_AREA_PRORATED"
    bld=bldall[bldall.intersects(selected)].copy(); cent=bld.geometry.centroid; bp=gpd.GeoDataFrame(index=bld.index,geometry=cent,crs=UTM); bm=assign(bp,m); bld["procom"]=bm.procom.values; bld["municipality_name"]=bm.municipality_name.values; bld["analysis_role"]=bld.procom.map(lambda c:"CORE" if c in CORE else "CONTEXT"); bld["intersects_core"]=bld.geometry.intersects(cu); bld["touches_analysis_boundary"]=bld.geometry.intersects(selected.boundary); bld["footprint_area_m2_geometry"]=bld.area; c4326=gpd.GeoSeries(cent,crs=UTM).to_crs(4326); bld["centroid_lon"]=c4326.x.values; bld["centroid_lat"]=c4326.y.values
    roads=roads_inventory(selected,cu,m,gdir); anchors=pd.read_csv(gdir/"anchor_universe.csv.gz",dtype={"anchor_id":str}); ag=gpd.GeoDataFrame(anchors.copy(),geometry=gpd.points_from_xy(pd.to_numeric(anchors.lon),pd.to_numeric(anchors.lat)),crs=4326).to_crs(UTM); ag=ag[ag.intersects(selected)].copy(); am=assign(ag,m); ag["procom"]=am.procom.values; ag["municipality_name"]=am.municipality_name.values; ag["analysis_role"]=ag.procom.map(lambda c:"CORE" if c in CORE else "CONTEXT"); ag["equity_scope"]=ag.analysis_role.map(lambda x:"DECISION_CORE" if x=="CORE" else "CONTEXT_ONLY")
    comp=[]
    for name,g in cs.items(): comp.append({"rule":name,"area_km2":g.area/1e6,"municipalities_intersected":int(m.intersects(g).sum()),"census_sections_intersected":int(secall.intersects(g).sum()),"buildings_intersected":int(bldall.intersects(g).sum()),"official_gtfs_bus_stops_intersected":int(((ag if False else gpd.GeoDataFrame(anchors.copy(),geometry=gpd.points_from_xy(pd.to_numeric(anchors.lon),pd.to_numeric(anchors.lat)),crs=4326).to_crs(UTM)).anchor_class.eq("OFFICIAL_GTFS_BUS_STOP") & (gpd.GeoDataFrame(anchors.copy(),geometry=gpd.points_from_xy(pd.to_numeric(anchors.lon),pd.to_numeric(anchors.lat)),crs=4326).to_crs(UTM).intersects(g))).sum()),"contains_core_v1_guard":bool(g.covers(cu.buffer(EDGE_GUARD_M-1e-6))),"contains_full_first_order_shell_with_guard":bool(g.covers(fu.buffer(EDGE_GUARD_M-1e-6))),"within_frozen_graph_bbox_plus_probe":bool(gb.covers(g.buffer(MAX_SNAP_M))),"selected":name==selected_name})
    out.mkdir(parents=True,exist_ok=True); mi.to_csv(out/"municipalities_intersected.csv",index=False); pd.DataFrame(comp).to_csv(out/"envelope_rule_comparison.csv",index=False); sec.drop(columns="geometry").sort_values(["procom","section_id"]).to_csv(out/"census_sections_intersected.csv.gz",index=False,compression={"method":"gzip","mtime":0}); bcols=[c for c in ["OBJECTID","CLASSREF","COD_CONS","DATA_FIN","Shape_Area","procom","municipality_name","analysis_role","intersects_core","touches_analysis_boundary","footprint_area_m2_geometry","centroid_lon","centroid_lat"] if c in bld.columns]; bld[bcols].sort_values("OBJECTID").to_csv(out/"buildings_intersected.csv.gz",index=False,compression={"method":"gzip","mtime":0}); roads.to_csv(out/"roads_intersected.csv.gz",index=False,compression={"method":"gzip","mtime":0}); ag.drop(columns="geometry").sort_values("anchor_id").to_csv(out/"stops_and_anchors_intersected.csv",index=False)
    geoms=gpd.GeoDataFrame([{"feature_role":"DECISION_CORE","epistemic_status":"FACT_OFFICIAL_ISTAT_2026_BOUNDARIES_UNION","geometry":cu},{"feature_role":"CONTEXT_FIRST_ORDER_MUNICIPAL_SHELL","epistemic_status":"DERIVED_SPATIAL_ADJACENCY_FROM_OFFICIAL_ISTAT_2026","geometry":unary_union(first.geometry.tolist())},{"feature_role":"ANALYSIS_ENVELOPE","epistemic_status":"DERIVED_RULE_WITH_EXPLICIT_V1_GUARD_ASSUMPTIONS","geometry":selected},{"feature_role":"SOURCE_ACQUISITION_GUARD","epistemic_status":"DERIVED_OUTER_GUARD_NOT_EQUITY_AREA","geometry":acquisition}],crs=UTM).to_crs(4326); (out/"analysis_envelope.geojson").write_text(geoms.to_json(drop_id=True),encoding="utf-8"); cg=gpd.GeoDataFrame([{"rule":k,"selected":k==selected_name,"geometry":v} for k,v in cs.items()],crs=UTM).to_crs(4326); (out/"candidate_envelopes.geojson").write_text(cg.to_json(drop_id=True),encoding="utf-8")
    edge={"selected_rule":selected_name,"edge_guard_m":EDGE_GUARD_M,"edge_guard_formula":"12 min * (4.8 km/h * 1000 / 60) + 250 m = 1210 m","guard_status":"DERIVED_FROM_V1_ACCESSIBILITY_ASSUMPTION_CONTRACT","core_guard_contained":core_ok,"first_order_shell_guard_contained":first_ok,"frozen_graph_probe_m":MAX_SNAP_M,"selected_plus_probe_within_frozen_gate_d_bbox":graph_ok,"selected_to_frozen_bbox_boundary_min_m":float(selected.boundary.distance(gb.boundary)),"sections_touching_analysis_boundary":int(sec.touches_analysis_boundary.sum()),"buildings_touching_analysis_boundary":int(bld.touches_analysis_boundary.sum()),"road_edges_crossing_analysis_boundary":int(roads.crosses_analysis_boundary.sum()),"outer_source_guard_m":EDGE_GUARD_M,"outer_source_guard_purpose":"Source completeness only; never equal equity obligation."}; (out/"edge_effect_audit.json").write_text(json.dumps(edge,ensure_ascii=False,sort_keys=True,indent=2)+"\n",encoding="utf-8")
    val={"status":"PASS_ANALYSIS_ENVELOPE","workstream":"phase2-analysis-envelope","baseline_commit":BASELINE,"decision_core_municipalities":CORE,"selected_rule":selected_name,"rule_epistemic_status":"ASSUMPTION_RULE_EXPLICIT_AND_TOPOLOGY_NEUTRAL","selection_principle":"Largest nested topology-neutral rule among the tested candidates that contains the inherited V1 core walk+snap guard and remains fully supported by the frozen Gate D source with a 250 m probe. Wider unsupported rules remain explicit sensitivity results rather than being forced into the primary envelope.","edge_guard_m":EDGE_GUARD_M,"source_acquisition_outer_guard_m":EDGE_GUARD_M,"first_order_context_codes":sorted(first.procom.astype(str)),"second_order_sensitivity_codes":sorted(second.procom.astype(str)),"municipalities_intersected":mi[["procom","municipality_name","analysis_role","adjacency_order_from_core"]].to_dict("records"),"counts":{"municipalities":len(mi),"census_sections":len(sec),"buildings":len(bld),"frozen_road_edges":len(roads),"anchor_records":len(ag),"official_bus_stop_records":int((ag.anchor_class=="OFFICIAL_GTFS_BUS_STOP").sum()),"rail_anchor_records":int((ag.anchor_class=="OFFICIAL_RAIL_STATION").sum())},"core_context_contract":{"CORE":"Five-municipality decision/equity denominator unless later policy explicitly changes it.","CONTEXT":"External residents/buildings/stops provide edge-safe context, not equal municipal equity obligations.","SOURCE_GUARD":"Acquisition-only outer margin, not an analysis constituency."},"prohibitions":{"topology_selected":False,"final_stop_selected":False,"headway_selected":False,"manual_external_municipality_whitelist_used":False,"np_random_used":False,"synthetic_data_used":False,"v1_outputs_modified":False},"source_manifest_sha256":sha_file(src/"source_manifest.json"),"source_snapshot_state":sm["source_state"],"acquisition_used_this_run":acquired,"frozen_gate_d_epoch":gm["epoch_id"],"edge_effect_audit":edge}; (out/"analysis_envelope_validation.json").write_text(json.dumps(val,ensure_ascii=False,sort_keys=True,indent=2)+"\n",encoding="utf-8")
    contract={"analysis_geometry":"analysis_envelope.geojson feature_role=ANALYSIS_ENVELOPE","source_acquisition_geometry":"analysis_envelope.geojson feature_role=SOURCE_ACQUISITION_GUARD","building_source_snapshot":str(src/"dbgt_buildings_context.geojson.gz"),"census_section_source_snapshot":str(src/"census_sections_context.geojson.gz"),"municipality_source_snapshot":str(src/"municipalities_context.geojson.gz"),"road_source":str(gdir/"graph_edges.csv.gz"),"stop_source":str(gdir/"anchor_universe.csv.gz"),"clipping_rule":"Use full source features intersecting SOURCE_ACQUISITION_GUARD; classify analytical membership against ANALYSIS_ENVELOPE; preserve CORE/CONTEXT; never area-prorate POP21 at outer edge.","next_workstream_requirement":"Building-population allocation must preserve provenance and must not treat CONTEXT population as an equal core equity denominator by default."}; (out/"source_cutline_contract.json").write_text(json.dumps(contract,ensure_ascii=False,sort_keys=True,indent=2)+"\n",encoding="utf-8")
    targets=sorted(p for p in out.iterdir() if p.is_file() and p.name!="analysis_envelope_checksums.sha256"); (out/"analysis_envelope_checksums.sha256").write_text("\n".join(f"{sha_file(p)}  {p.name}" for p in targets)+"\n",encoding="utf-8")
    return val

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--source-dir",default="data/phase2/analysis_envelope/source"); ap.add_argument("--output-dir",default="outputs/phase2/analysis_envelope"); ap.add_argument("--graph-dir",default="outputs/phase2/frozen_gate_d"); ap.add_argument("--graph-manifest",default="data/phase2/frozen_gate_d/source/source_manifest.json"); ap.add_argument("--forbid-live",action="store_true"); a=ap.parse_args(); v=build(Path(a.source_dir),Path(a.output_dir),Path(a.graph_dir),Path(a.graph_manifest),a.forbid_live); print(json.dumps({"status":v["status"],"selected_rule":v["selected_rule"],"counts":v["counts"],"acquisition_used_this_run":v["acquisition_used_this_run"]},ensure_ascii=False,indent=2))
if __name__=="__main__": main()
