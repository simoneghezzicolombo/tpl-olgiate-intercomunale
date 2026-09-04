#!/usr/bin/env python3
"""Build static source-closed assets for the Dietro l'analisi scrollytelling.

This script does not recompute Phase 2 decisions. It only transforms two pinned,
already validated evidence bundles into web-friendly visual layers.
"""
from __future__ import annotations

import base64
import gzip
import hashlib
import json
import math
from pathlib import Path
import shutil
import zipfile

import geopandas as gpd
import pandas as pd

ROOT = Path(__file__).resolve().parent
BUILDING_ZIP = Path('/tmp/journey-building-population.zip')
STOP_ZIP = Path('/tmp/journey-stop-universe-v2.zip')
BUILDING_ARTIFACT_ID = 9910900017
BUILDING_ZIP_SHA256 = '4f5f0123ced2b763c2a063258ad724c43ac7f57ede707db3fa76e6a8977688b1'
STOP_ARTIFACT_ID = 9911651930
STOP_ZIP_SHA256 = '25d3dbf52cb428d54a46569b7dbbf9e78dcee6fcf5ee69b9c6e928a367e0a2f9'
CORE = {'097010','097012','097058','097074','097092'}
CHUNK = 220_000


def sha256(path: Path) -> str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''): h.update(block)
    return h.hexdigest()


def verify_zip(path: Path, expected: str) -> None:
    actual=sha256(path)
    if actual != expected: raise RuntimeError(f'{path.name} SHA256 {actual} != {expected}')


def extract_member(z: zipfile.ZipFile, name: str, dst: Path) -> Path:
    dst.parent.mkdir(parents=True,exist_ok=True)
    with z.open(name) as src, dst.open('wb') as out: shutil.copyfileobj(src,out)
    return dst


def compact_geojson(gdf: gpd.GeoDataFrame, props: list[str]) -> bytes:
    fc=json.loads(gdf[props+['geometry']].to_json(drop_id=True))
    return json.dumps(fc,separators=(',',':'),ensure_ascii=False).encode('utf-8')


def gzip_b64_chunks(stem: str, raw: bytes) -> list[Path]:
    for old in ROOT.glob(f'{stem}.gz.*.b64'): old.unlink()
    gz_path=ROOT/f'{stem}.gz'
    with gz_path.open('wb') as raw_out:
        with gzip.GzipFile(filename='',fileobj=raw_out,mode='wb',compresslevel=9,mtime=0) as gz: gz.write(raw)
    b64=base64.b64encode(gz_path.read_bytes()).decode('ascii')
    gz_path.unlink()
    outs=[]
    for i in range(math.ceil(len(b64)/CHUNK)):
        p=ROOT/f'{stem}.gz.{i}.b64'; p.write_text(b64[i*CHUNK:(i+1)*CHUNK],encoding='ascii'); outs.append(p)
    return outs


def main() -> None:
    verify_zip(BUILDING_ZIP,BUILDING_ZIP_SHA256); verify_zip(STOP_ZIP,STOP_ZIP_SHA256)
    work=Path('/tmp/journey-assets'); shutil.rmtree(work,ignore_errors=True); work.mkdir()
    with zipfile.ZipFile(BUILDING_ZIP) as z:
        needed=['building_population_allocations.csv','building_population_sections.csv','building_population_worldpop_heterogeneity.csv','building_population_source_istat_R03_21.zip','source-snapshots/dbgt_footprints_composite_normalized.geojson.gz']
        for n in needed: extract_member(z,n,work/n)
    with zipfile.ZipFile(STOP_ZIP) as z:
        for n in ['accessibility_gap_building_pieces.geojson','proposed_stop_candidates.geojson','existing_official_stops.geojson','stop_universe_v2_validation.json']:
            extract_member(z,n,work/n)

    wp=pd.read_csv(work/'building_population_worldpop_heterogeneity.csv')
    wp_features=[]
    for r in wp.itertuples():
        hw=float(r.cell_width_deg)/2; hh=float(r.cell_height_deg)/2
        wp_features.append({'type':'Feature','properties':{'id':r.cell_id,'pop':round(float(r.pop_calibrated_2025),4),'raw':round(float(r.worldpop_2020_raw),4),'muni':str(r.PRO_COM_T).split('.')[0].zfill(6)},'geometry':{'type':'Polygon','coordinates':[[[r.lon-hw,r.lat-hh],[r.lon+hw,r.lat-hh],[r.lon+hw,r.lat+hh],[r.lon-hw,r.lat+hh],[r.lon-hw,r.lat-hh]]]}})
    worldpop_raw=json.dumps({'type':'FeatureCollection','features':wp_features},separators=(',',':')).encode()

    sec_zip=work/'building_population_source_istat_R03_21.zip'
    sec_geo=gpd.read_file(f'/vsizip/{sec_zip}/SHP/R03_21_WGS84.shp')
    sec_geo['PRO_COM_N']=sec_geo['PRO_COM'].astype(int)
    sec_geo=sec_geo[sec_geo.PRO_COM_N.isin({97010,97012,97058,97074,97092})].copy()
    secs=pd.read_csv(work/'building_population_sections.csv',dtype={'section_id':str,'municipality_code':str})
    secs['section_id']=secs['section_id'].str.replace('.0','',regex=False).str.zfill(12)
    sec_geo['section_id']=sec_geo['SEZ21_ID'].astype(str).str.replace('.0','',regex=False).str.zfill(12)
    pop_lookup=secs.set_index('section_id')['section_population_2025_derived'].to_dict()
    sec_geo['pop2025']=sec_geo['section_id'].map(pop_lookup).fillna(0.0)
    sec_geo['muni']=sec_geo['PRO_COM_N'].map(lambda x:str(x).zfill(6))
    sec_geo=sec_geo.to_crs(32632); sec_geo['geometry']=sec_geo.geometry.simplify(2.0,preserve_topology=True); sec_geo=sec_geo.to_crs(4326)
    sections_raw=compact_geojson(sec_geo,['section_id','muni','pop2025'])

    alloc=pd.read_csv(work/'building_population_allocations.csv',dtype={'municipality_code':str})
    alloc['municipality_code']=alloc['municipality_code'].str.zfill(6)
    a=alloc[alloc.municipality_code.isin(CORE)]
    agg=a.groupby('building_id',as_index=False).agg(pop=('building_piece_population_model','sum'),muni=('municipality_code','first'),pieces=('section_id','nunique'))
    footprints=gpd.read_file(f'/vsigzip/{work / "source-snapshots/dbgt_footprints_composite_normalized.geojson.gz"}')
    buildings=footprints[footprints.building_id.isin(set(agg.building_id))].merge(agg,on='building_id',how='inner')
    buildings=buildings.to_crs(32632); buildings['geometry']=buildings.geometry.simplify(0.5,preserve_topology=True); buildings=buildings.to_crs(4326)
    buildings_raw=compact_geojson(buildings,['building_id','pop','muni','pieces'])

    pieces=json.loads((work/'accessibility_gap_building_pieces.geojson').read_text())
    brows=[]
    for f in pieces['features']:
        p=f['properties']; lon,lat=f['geometry']['coordinates']; walk=p.get('walk_min_to_nearest_existing_stop_v2')
        brows.append([round(lon,6),round(lat,6),round(float(p['building_piece_population_model']),3),None if walk is None else round(float(walk),2),str(p['PRO_COM_T']).zfill(6)])
    cand=json.loads((work/'proposed_stop_candidates.geojson').read_text()); crows=[]
    for f in cand['features']:
        p=f['properties']; lon,lat=f['geometry']['coordinates']
        crows.append([p['candidate_id'],round(lon,6),round(lat,6),str(p['PRO_COM_T']).zfill(6),round(float(p['population_additional_10min']),2),p.get('highway',''),p.get('road_uncertainty_flags','')])
    ex=json.loads((work/'existing_official_stops.geojson').read_text()); erows=[]
    for f in ex['features']:
        p=f['properties']; lon,lat=f['geometry']['coordinates']
        erows.append([p['physical_cluster_id'],p['stop_name'],round(lon,6),round(lat,6),str(p.get('PRO_COM_T','')).zfill(6),p.get('official_routes_reference_gtfs','')])
    v=json.loads((work/'stop_universe_v2_validation.json').read_text())
    meta={'populationTotal':22914.0,'populationLocated':22820.839937434386,'populationResidual':93.16006256561045,'populationUnits':4348,'worldpopCells':len(wp),'sections':len(sec_geo),'buildings':len(buildings),'candidateStops':len(crows),'officialStopRecords':len(erows),'physicalClusters':43,'discoverySamples':3858,'gapSeeds8':1686,'rawSeededBeforeThin':1074,'rawSeeded':320,'preprune':292,'finalCandidates':155,'roadWays':24384,'roadEligibleWays':15872,'roadDeniedWays':8512,'graphNodes':104071,'graphEdges':199217,'coverage':{'5':46.97958635342723,'8':68.46684292749644,'10':77.55600347715396,'12':84.8663356191682},'lineage':{'building':'29203ad64c3e32e6164ef6997933eb5c5ff2d5b1','finalists':'aa16a9934a78be9a3ee1230996fcaf72c5657f92','gateD':'7c220f7586d0f6e5cccd14a2d518be52eb1c4a55','stopUniverseV2Building':v.get('source_building_population_head','')}}
    (ROOT/'journey-data.js').write_text('window.ANALYSIS_JOURNEY_DATA='+json.dumps({'meta':meta,'pieces':brows,'candidates':crows,'existingStops':erows},ensure_ascii=False,separators=(',',':'))+';\n',encoding='utf-8')

    generated=[]
    generated += gzip_b64_chunks('data-worldpop.geojson',worldpop_raw)
    generated += gzip_b64_chunks('data-sections.geojson',sections_raw)
    generated += gzip_b64_chunks('data-buildings.geojson',buildings_raw)
    generated.append(ROOT/'journey-data.js')
    if len(wp)!=4283 or len(sec_geo)!=229 or len(buildings)!=4226 or len(brows)!=4348 or len(crows)!=155 or len(erows)!=67:
        raise RuntimeError(f'journey cardinality contract failed: wp={len(wp)} sections={len(sec_geo)} buildings={len(buildings)} pieces={len(brows)} candidates={len(crows)} stops={len(erows)}')
    manifest={'contract':'PHASE2_ANALYSIS_JOURNEY_VISUAL_ASSETS_V1','decision_output':False,'building_artifact_id':BUILDING_ARTIFACT_ID,'building_artifact_sha256':BUILDING_ZIP_SHA256,'stop_universe_artifact_id':STOP_ARTIFACT_ID,'stop_universe_artifact_sha256':STOP_ZIP_SHA256,'counts':{'worldpop_cells':len(wp),'sections':len(sec_geo),'dbgt_buildings_with_core_population':len(buildings),'building_section_pieces':len(brows),'proposed_candidates_v2':len(crows),'official_stop_records_v2':len(erows)},'files':{p.name:sha256(p) for p in sorted(generated)}}
    (ROOT/'data-manifest.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps(manifest,indent=2))

if __name__=='__main__': main()
