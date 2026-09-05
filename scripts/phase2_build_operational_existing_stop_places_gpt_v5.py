#!/usr/bin/env python3
"""Build the practical existing-stop layer used by downstream network design.

User-facing contract: one row = one existing stop location / stop place. Directional
A/R records are intentionally collapsed. This is NOT a boarding-point inventory.

The layer prefers current ASF geometry when available, folds verified frozen aliases
into the same stop place, preserves unmatched frozen physical stop locations as
reference evidence, adds the manually confirmed Scagnello stop, and keeps the special
Casa di Comunita service stop in a separate service class.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import unicodedata
from collections import defaultdict
from pathlib import Path

import pandas as pd

CORE = {"Brivio", "Calco", "La Valletta Brianza", "Olgiate Molgora", "Santa Maria Hoè"}
EXCLUDE_FROZEN = {"300397", "L00397", "300407"}

FROZEN_TO_ASF = {
    "300803": "OLGIATE MOLGORA SCARPONE", "L00803": "OLGIATE MOLGORA SCARPONE",
    "300728": "OLGIATE MOLGORA VIA STATALE", "L00728": "OLGIATE MOLGORA VIA STATALE",
    "300729": "CALCO VIA GARIBALDI", "L00729": "CALCO VIA GARIBALDI",
    "300089": "CALCO LARGO POMEA", "L00089": "CALCO LARGO POMEA",
    "300528": "ARLATE BIVIO PER IL PAESE", "L00528": "ARLATE BIVIO PER IL PAESE",
    "300886": "IMBERSAGO LOCALITA CAZZULINO", "L00886": "IMBERSAGO LOCALITA CAZZULINO",
    "300406": "BRIVIO BAR CRISTALLO", "L00406": "BRIVIO BAR CRISTALLO",
    "300087": "VACCAREZZA CARTELLO PAESE", "L00087": "VACCAREZZA CARTELLO PAESE",
    "L00063": "BRIVIO VIA COMO PENSILINA",
    "300872": "PEREGO VIA STATALE 79", "L00872": "PEREGO VIA STATALE 79",
    "300804": "ROVAGNATE STRADA STATALE AGIP", "L00804": "ROVAGNATE STRADA STATALE AGIP",
    "300878": "ROVAGNATE SS ANG V LOMBARDIA", "L00878": "ROVAGNATE SS ANG V LOMBARDIA",
    "300871": "ROVAGNATE FRAZIONE ALDUNO", "L00871": "ROVAGNATE FRAZIONE ALDUNO",
    "300902": "SANTA MARIA HOE VIA COMO", "L00902": "SANTA MARIA HOE VIA COMO",
    "300207": "S MARIA HOE SP 58 ANG VIA CENISIO", "L00207": "S MARIA HOE SP 58 ANG VIA CENISIO",
    "300903": "SANTA MARIA HOE VIA GIOVANNI XXIII",
}

DISPLAY = {
    "OLGIATE MOLGORA SCARPONE": "Olgiate Molgora - Scarpone",
    "OLGIATE MOLGORA VIA STATALE": "Olgiate Molgora - Via Statale",
    "CALCO VIA GARIBALDI": "Calco - Via Virgilio",
    "CALCO LARGO POMEA": "Calco - Via Nazionale (edicola)",
    "ARLATE BIVIO PER IL PAESE": "Arlate - Bivio per il Paese",
    "IMBERSAGO LOCALITA CAZZULINO": "Imbersago - Località Cazzulino / Arlate Fiorista",
    "BRIVIO BAR CRISTALLO": "Brivio - Via Como (pizzeria / Bar Cristallo)",
    "VACCAREZZA CARTELLO PAESE": "Brivio - Vaccarezza",
    "BRIVIO VIA COMO PENSILINA": "Brivio / Via V. Emanuele (Capolinea)",
    "PEREGO VIA STATALE 79": "Perego - Statale / Via S. Caterina",
    "ROVAGNATE STRADA STATALE AGIP": "Rovagnate - Statale / AGIP",
    "ROVAGNATE SS ANG V LOMBARDIA": "Rovagnate - Statale / Via Lombardia",
    "ROVAGNATE FRAZIONE ALDUNO": "Santa Maria Hoè - Alduno",
    "SANTA MARIA HOE VIA COMO": "Santa Maria Hoè - Via Como / Alpino",
    "S MARIA HOE SP 58 ANG VIA CENISIO": "Santa Maria Hoè - SP58 / Via Cenisio",
    "SANTA MARIA HOE VIA GIOVANNI XXIII": "Santa Maria Hoè - Via Giovanni XXIII / Tremonte-Via Leopardi",
}


def text(v) -> str:
    return "" if pd.isna(v) else str(v).strip()


def norm(v: str) -> str:
    s = unicodedata.normalize("NFKD", text(v)).encode("ascii", "ignore").decode("ascii").upper()
    s = re.sub(r"\bS\s*\.?\s*S\s*\.?\b", "SS", s)
    s = re.sub(r"[^A-Z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def hav(lat1, lon1, lat2, lon2) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2-lat1), math.radians(lon2-lon1)
    a = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2*r*math.atan2(math.sqrt(a), math.sqrt(max(0.0, 1-a)))


def suffix(native: str) -> str:
    n = text(native).upper()
    if re.fullmatch(r"3\d{5}", n): return n[-5:]
    if re.fullmatch(r"L\d{5}", n): return n[1:]
    return ""


def centroid(rows):
    return sum(float(r["lat"]) for r in rows)/len(rows), sum(float(r["lon"]) for r in rows)/len(rows)


def build(args):
    m = pd.read_csv(args.master, dtype=str)
    core = m[m["physical_municipality_exact"].isin(CORE)].copy()
    asf = core[core.source_family.eq("ASF_OPERATOR_OTP")].copy()
    frozen = core[core.source_family.eq("FROZEN_GTFS_REFERENCE")].copy()
    special = core[core.source_family.eq("SPECIAL_SERVICE_EVIDENCE")].copy()

    asf["place_key"] = asf.source_stop_name.map(norm)
    places = []
    for key, g in asf.groupby("place_key", sort=True):
        rows = g.to_dict("records")
        lat, lon = centroid(rows)
        places.append({
            "stop_place_id": f"ASF::{key.replace(' ', '_')}",
            "stop_name": DISPLAY.get(key, text(g.iloc[0].source_stop_name)),
            "municipality": text(g.iloc[0].physical_municipality_exact),
            "lat": round(lat, 7), "lon": round(lon, 7),
            "source_families": "ASF_OPERATOR_OTP",
            "source_native_ids": "|".join(sorted(g.source_record_native_id.astype(str))),
            "known_routes": "C146",
            "existence_confidence": "HIGH_CURRENT_OPERATOR",
            "service_class": "CONVENTIONAL_TPL",
            "notes": "Directions collapsed intentionally; representative coordinate is the mean of available ASF positions.",
        })

    scag_lat = (45.71691647047958 + 45.71682017362495) / 2
    scag_lon = (9.40827705210095 + 9.408055828737293) / 2
    places.append({
        "stop_place_id": "MANUAL::CALCO_SCAGNELLO",
        "stop_name": "Calco - Via Statale / Via Scagnello (Esselunga)",
        "municipality": "Calco",
        "lat": round(scag_lat, 7), "lon": round(scag_lon, 7),
        "source_families": "GOOGLE_MAPS_MANUAL|ASF_C146_OBSERVED",
        "source_native_ids": "CALCOA04|CALCOR04",
        "known_routes": "C146",
        "existence_confidence": "HIGH_MANUAL_CURRENT",
        "service_class": "CONVENTIONAL_TPL",
        "notes": "One location; travel directions intentionally ignored.",
    })

    mapped = set(FROZEN_TO_ASF)
    work = frozen[~frozen.source_record_native_id.isin(EXCLUDE_FROZEN | mapped)].copy()
    work.loc[work.source_record_native_id.eq("300063"), "source_stop_name"] = "Brivio - Via Bergamo (Scuola Materna)"
    work.loc[work.source_record_native_id.isin(["300527", "L00527"]), "source_stop_name"] = "Brivio - Via Provinciale Beverate (Elettroadda)"

    recs = work.to_dict("records")
    parent = list(range(len(recs)))
    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]; i = parent[i]
        return i
    def union(i,j):
        a,b=find(i),find(j)
        if a!=b: parent[b]=a

    for i in range(len(recs)):
        for j in range(i+1, len(recs)):
            a,b=recs[i],recs[j]
            if a["physical_municipality_exact"] != b["physical_municipality_exact"]: continue
            d=hav(float(a["lat"]),float(a["lon"]),float(b["lat"]),float(b["lon"]))
            same_suffix = suffix(a["source_record_native_id"]) and suffix(a["source_record_native_id"]) == suffix(b["source_record_native_id"])
            same_name = norm(a["source_stop_name"]) == norm(b["source_stop_name"])
            # At stop-place resolution, very close frozen points are treated as one useful
            # location even if operator labels differ. This deliberately ignores A/R detail.
            if (same_suffix and d <= 100) or (same_name and d <= 100) or d <= 30:
                union(i,j)

    groups=defaultdict(list)
    for i,r in enumerate(recs): groups[find(i)].append(r)
    for rows in groups.values():
        lat,lon=centroid(rows)
        names=[text(r["source_stop_name"]) for r in rows]
        ids=sorted(text(r["source_record_native_id"]) for r in rows)
        place_name=max(set(names), key=names.count)
        if set(ids) == {"300805", "L00904"}:
            place_name = "Santa Maria Hoè - Tremonte / Via Trento"
        if ids == ["L00407"]:
            place_name = "Olgiate-Calco-Brivio FS"
        muni=text(rows[0]["physical_municipality_exact"])
        places.append({
            "stop_place_id": f"FROZEN::{ids[0]}",
            "stop_name": place_name,
            "municipality": muni,
            "lat": round(lat,7), "lon": round(lon,7),
            "source_families": "FROZEN_GTFS_REFERENCE",
            "source_native_ids": "|".join(ids),
            "known_routes": "|".join(sorted({x for r in rows for x in text(r.get("route_id","")).split("|") if x})),
            "existence_confidence": "MEDIUM_OFFICIAL_REFERENCE",
            "service_class": "CONVENTIONAL_TPL",
            "notes": "Existing stop location retained from official reference; direction ignored and current service may differ.",
        })

    for r in special.to_dict("records"):
        places.append({
            "stop_place_id": "SPECIAL::CASA_DI_COMUNITA_OLGIATE",
            "stop_name": text(r["source_stop_name"]),
            "municipality": text(r["physical_municipality_exact"]),
            "lat": round(float(r["lat"]),7), "lon": round(float(r["lon"]),7),
            "source_families": "SPECIAL_SERVICE_EVIDENCE",
            "source_native_ids": text(r["source_record_native_id"]),
            "known_routes": text(r["route_id"]),
            "existence_confidence": "HIGH_CURRENT_SPECIAL_SERVICE",
            "service_class": "SPECIAL_SERVICE",
            "notes": "Kept separate from ordinary TPL stops.",
        })

    out=pd.DataFrame(places).sort_values(["municipality","stop_name","lat"]).reset_index(drop=True)
    out.insert(0,"operational_stop_no", range(1,len(out)+1))
    outdir=Path(args.output_dir); outdir.mkdir(parents=True, exist_ok=True)
    out.to_csv(outdir/"existing_stop_places_operational_gpt_v5.csv", index=False)
    geo={"type":"FeatureCollection","features":[]}
    for r in out.to_dict("records"):
        props={k:v for k,v in r.items() if k not in {"lat","lon"}}
        geo["features"].append({"type":"Feature","geometry":{"type":"Point","coordinates":[float(r["lon"]),float(r["lat"])]},"properties":props})
    (outdir/"existing_stop_places_operational_gpt_v5.geojson").write_text(json.dumps(geo,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    validation={
        "status":"PASS_OPERATIONAL_STOP_PLACE_LAYER",
        "row_semantics":"ONE_ROW_PER_EXISTING_STOP_PLACE_DIRECTION_IGNORED",
        "stop_places_count":int(len(out)),
        "by_municipality":{str(k):int(v) for k,v in out.groupby("municipality").size().items()},
        "directional_boarding_points_exposed":False,
        "routing_terminal_selected":False,
        "scagnello_included":bool(out.stop_name.str.contains("Scagnello",case=False).any()),
        "excluded_known_obsolete_frozen_ids":sorted(EXCLUDE_FROZEN),
    }
    (outdir/"existing_stop_places_operational_validation_gpt_v5.json").write_text(json.dumps(validation,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")


def parse_args():
    p=argparse.ArgumentParser()
    p.add_argument("--master",default="outputs/phase2/network_design_method_audit_v3/master_stop_inventory_gpt_v3/master_stop_source_records_municipalized_gpt_v3.csv")
    p.add_argument("--output-dir",default="outputs/phase2/network_design_method_audit_v3/master_stop_inventory_gpt_v3")
    return p.parse_args()

if __name__ == "__main__": build(parse_args())
