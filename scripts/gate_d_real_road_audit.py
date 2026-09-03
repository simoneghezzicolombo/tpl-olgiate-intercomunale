#!/usr/bin/env python3
"""Acquire independent Gate D road evidence and audit it against official bus GTFS.

This workstream deliberately does not wait for Gate C to finish. It reads the same
primary GTFS published by Agenzia TPL Como-Lecco-Varese, but all transit-derived
results are marked PROVISIONAL_UNTIL_GATE_C. The purpose is road/geometry audit,
not service-date validation.
"""
from __future__ import annotations

import hashlib
import io
import json
import math
import sys
import zipfile
from pathlib import Path

import geopandas as gpd
import pandas as pd
import requests
from shapely.geometry import LineString

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gate_d_route_integrity as routing

OUT = Path("data/audit_gate_d")
RAW = OUT / "raw"
BBOX = (45.68, 9.31, 45.82, 9.56)  # south, west, north, east; includes Ravellino-Caprino/Celana context
OVERPASS_ENDPOINTS = [
    "https://overpass.private.coffee/api/interpreter",
    "https://overpass-api.de/api/interpreter",
]
ARRIVA_GTFS = (
    "https://www.tplcomoleccovarese.it/atpcolc/images/File%20GTFS%20inv.%202025-2026/"
    "GTFS%20invernale%202025-2026%20-%20Arriva%20Italia%20e%20Addabus.zip"
)
LINEELECCO_GTFS = (
    "https://www.tplcomoleccovarese.it/atpcolc/images/File%20GTFS%20inv.%202025-2026/"
    "GTFS%20invernale%202025-2026%20Linee%20Lecco.zip"
)
TARGET_ROUTES = {"D184", "D185", "D150", "D170"}
HEADERS = {"User-Agent": "tpl-olgiate-gate-d-audit/1.0 (+github.com/simoneghezzicolombo/tpl-olgiate-intercomunale)"}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def download(url: str, target: Path) -> Path:
    if target.exists() and target.stat().st_size > 0:
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    response = requests.get(url, headers=HEADERS, timeout=180)
    response.raise_for_status()
    target.write_bytes(response.content)
    if target.stat().st_size == 0:
        raise IOError(f"Empty download: {url}")
    return target


def acquire_osm() -> tuple[gpd.GeoDataFrame, pd.DataFrame, str, Path]:
    south, west, north, east = BBOX
    query = f"""[out:json][timeout:180];
(
  way[\"highway\"]({south},{west},{north},{east});
  relation[\"type\"=\"restriction\"]({south},{west},{north},{east});
);
(._;>;);
out body;"""
    last_error = None
    for endpoint in OVERPASS_ENDPOINTS:
        try:
            response = requests.post(endpoint, data={"data": query}, headers=HEADERS, timeout=240)
            response.raise_for_status()
            payload = response.json()
            break
        except Exception as exc:  # network fallback is intentional and surfaced in summary
            last_error = exc
    else:
        raise RuntimeError(f"All Overpass endpoints failed: {last_error}")

    RAW.mkdir(parents=True, exist_ok=True)
    raw_path = RAW / "osm_gate_d_context.json"
    raw_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    elements = payload.get("elements", [])
    nodes = {
        int(e["id"]): (float(e["lon"]), float(e["lat"]))
        for e in elements if e.get("type") == "node" and "lon" in e and "lat" in e
    }
    road_rows = []
    for e in elements:
        if e.get("type") != "way" or "highway" not in e.get("tags", {}):
            continue
        coords = [nodes[n] for n in e.get("nodes", []) if n in nodes]
        if len(coords) < 2:
            continue
        tags = e.get("tags", {})
        row = {"osm_way_id": int(e["id"]), "highway": tags.get("highway"), "geometry": LineString(coords)}
        for key in routing.TAG_COLUMNS:
            row[key] = tags.get(key)
        row["other_tags"] = ",".join(
            f'"{k}"=>"{v}"' for k, v in tags.items()
            if k not in {"highway", *routing.TAG_COLUMNS}
        )
        road_rows.append(row)
    roads = gpd.GeoDataFrame(road_rows, crs=4326)
    if roads.empty:
        raise ValueError("Overpass returned no highway ways")
    roads.to_file(OUT / "osm_gate_d_context.geojson", driver="GeoJSON")

    restrictions = []
    for e in elements:
        if e.get("type") != "relation" or e.get("tags", {}).get("type") != "restriction":
            continue
        members = e.get("members", [])
        member = lambda role: next((m for m in members if m.get("role") == role), {})
        restrictions.append({
            "relation_id": int(e["id"]),
            "restriction": e.get("tags", {}).get("restriction", ""),
            "except": e.get("tags", {}).get("except", ""),
            "from_ref": member("from").get("ref"),
            "via_type": member("via").get("type"),
            "via_ref": member("via").get("ref"),
            "to_ref": member("to").get("ref"),
            "epistemic_status": "FACT_OSM_OBSERVATION",
        })
    restriction_df = pd.DataFrame(restrictions)
    restriction_df.to_csv(OUT / "osm_turn_restrictions.csv", index=False)
    return roads, restriction_df, endpoint, raw_path


def read_gtfs_table(zf: zipfile.ZipFile, name: str) -> pd.DataFrame:
    with zf.open(name) as handle:
        return pd.read_csv(handle, dtype=str)


def hhmmss_minutes(value: str) -> float:
    parts = str(value).split(":")
    return int(parts[0]) * 60 + int(parts[1]) + int(parts[2]) / 60.0


def parse_gtfs(feed_path: Path, feed_label: str) -> tuple[list[dict], list[dict], list[dict]]:
    with zipfile.ZipFile(feed_path) as zf:
        required = {"routes.txt", "trips.txt", "stops.txt", "stop_times.txt", "shapes.txt"}
        missing = required - set(zf.namelist())
        if missing:
            raise ValueError(f"{feed_label} GTFS missing {sorted(missing)}")
        routes = read_gtfs_table(zf, "routes.txt")
        trips = read_gtfs_table(zf, "trips.txt")
        stops = read_gtfs_table(zf, "stops.txt")
        stop_times = read_gtfs_table(zf, "stop_times.txt")
        shapes = read_gtfs_table(zf, "shapes.txt")

    short_col = "route_short_name" if "route_short_name" in routes.columns else "route_long_name"
    target_routes = routes[routes[short_col].isin(TARGET_ROUTES)].copy()
    route_name = dict(zip(target_routes["route_id"], target_routes[short_col]))
    target_trips = trips[trips["route_id"].isin(route_name)].copy()
    if target_trips.empty:
        return [], [], []
    target_trips["route_short_name"] = target_trips["route_id"].map(route_name)

    shape_rows = []
    for shape_id, shape_trips in target_trips.dropna(subset=["shape_id"]).groupby("shape_id"):
        pts = shapes[shapes["shape_id"] == shape_id].copy()
        if pts.empty:
            continue
        pts["shape_pt_sequence"] = pd.to_numeric(pts["shape_pt_sequence"], errors="raise")
        pts = pts.sort_values("shape_pt_sequence")
        geom = LineString(list(zip(pts["shape_pt_lon"].astype(float), pts["shape_pt_lat"].astype(float))))
        route_short = shape_trips["route_short_name"].mode().iat[0]
        directions = ";".join(sorted(set(shape_trips.get("direction_id", pd.Series(dtype=str)).dropna().astype(str))))
        shape_rows.append({
            "feed": feed_label, "route_short_name": route_short, "shape_id": shape_id,
            "direction_ids": directions, "geometry": geom,
            "epistemic_status": "FACT_GTFS_GEOMETRY_PROVISIONAL_UNTIL_GATE_C",
        })

    st = stop_times[stop_times["trip_id"].isin(set(target_trips["trip_id"]))].copy()
    st["stop_sequence"] = pd.to_numeric(st["stop_sequence"], errors="raise")
    runtime_rows = []
    representative_rows = []
    for trip_id, group in st.groupby("trip_id"):
        group = group.sort_values("stop_sequence")
        trip = target_trips[target_trips["trip_id"] == trip_id].iloc[0]
        start = hhmmss_minutes(group.iloc[0]["departure_time"])
        end = hhmmss_minutes(group.iloc[-1]["arrival_time"])
        runtime_rows.append({
            "feed": feed_label, "route_short_name": trip["route_short_name"],
            "trip_id": trip_id, "direction_id": trip.get("direction_id", ""),
            "scheduled_terminal_to_terminal_min": end - start,
            "stop_count": len(group),
            "epistemic_status": "FACT_GTFS_SCHEDULE_PROVISIONAL_UNTIL_GATE_C",
        })
        for _, row in group.iterrows():
            representative_rows.append({
                "feed": feed_label, "route_short_name": trip["route_short_name"],
                "trip_id": trip_id, "direction_id": trip.get("direction_id", ""),
                "stop_sequence": int(row["stop_sequence"]), "stop_id": row["stop_id"],
            })

    used_stop_ids = set(st["stop_id"])
    stop_lookup = stops[stops["stop_id"].isin(used_stop_ids)].copy()
    stop_rows = [
        {
            "feed": feed_label, "stop_id": r["stop_id"], "stop_name": r.get("stop_name", ""),
            "lat": float(r["stop_lat"]), "lon": float(r["stop_lon"]),
            "epistemic_status": "FACT_GTFS_STOP_PROVISIONAL_UNTIL_GATE_C",
        }
        for _, r in stop_lookup.iterrows()
    ]
    return shape_rows, runtime_rows, stop_rows


def route_shape_metrics(shape_gdf: gpd.GeoDataFrame, roads: gpd.GeoDataFrame) -> pd.DataFrame:
    if shape_gdf.empty:
        return pd.DataFrame()
    shapes_m = shape_gdf.to_crs(32632)
    roads_m = roads.to_crs(32632)
    eligible = []
    for _, row in roads_m.iterrows():
        ok, _ = routing.bus_eligibility(row)
        if ok:
            eligible.append(row.geometry)
    if not eligible:
        raise ValueError("No bus-eligible OSM geometry for GTFS comparison")
    road_buffer = gpd.GeoSeries(eligible, crs=32632).buffer(30).union_all()
    rows = []
    for _, row in shapes_m.iterrows():
        length = float(row.geometry.length)
        within = float(row.geometry.intersection(road_buffer).length)
        rows.append({
            "feed": row["feed"], "route_short_name": row["route_short_name"],
            "shape_id": row["shape_id"], "gtfs_shape_km": length / 1000.0,
            "osm_busroad_coverage_30m_pct": 100.0 * within / length if length else 0.0,
            "distance_status": "DERIVED_FROM_FACT_GTFS_GEOMETRY",
            "coverage_status": "DERIVED_OSM_GTFS_SPATIAL_MATCH",
        })
    return pd.DataFrame(rows)


def public_constraints() -> pd.DataFrame:
    rows = [
        {
            "constraint_id": "BRIVIO_BRIDGE_CLOSURE_2026",
            "road": "SS342 Ponte di Brivio",
            "constraint": "complete_closure",
            "value": "closed to all traffic from 2026-05-04; estimated duration about 15 months",
            "source": "Provincia di Lecco",
            "source_url": "https://www.provincia.lecco.it/2026/04/23/chiusura-ponte-di-brivio-le-modifiche-alle-linee-bus/",
            "epistemic_status": "FACT_TEMPORARY_CONSTRAINT",
            "gate_d_use": "Current-2026 routes must not cross the bridge; structural post-works scenarios must remain separate.",
        },
        {
            "constraint_id": "BRIVIO_D185_DETOUR_2026",
            "road": "D185 via Olginate / Ponte Cesare Cantu",
            "constraint": "official_temporary_bus_detour",
            "value": "about +12 km; estimated +30 to +40 minutes",
            "source": "Provincia di Lecco / Agenzia TPL",
            "source_url": "https://www.tplcomoleccovarese.it/atpcolc/po/mostra_news.php?area=H&id=1137",
            "epistemic_status": "FACT_TEMPORARY_SERVICE_CONSTRAINT",
            "gate_d_use": "Calibration/diagnostic fact only; not a hardcoded candidate-route metric.",
        },
        {
            "constraint_id": "OLGIATE_CALCO_RAIL_OVERPASS_33T_30KMH",
            "road": "SP ex SS342 pk 26+500 to 26+800",
            "constraint": "mass_and_speed_limit",
            "value": "max mass 33 t; 50 m spacing over 3.5 t; max speed 30 km/h; stated until subsequent revocation",
            "source": "Provincia di Lecco",
            "source_url": "https://www.provincia.lecco.it/documento/58-sp-ex-ss-342-limitazioni-sul-sovrappasso-ferroviario-tra-olgiate-molgora-e-calco/",
            "epistemic_status": "FACT_OFFICIAL_ORDER_CURRENT_VALIDITY_TO_REVERIFY",
            "gate_d_use": "Constraint registry; current validity must be rechecked before final operational recommendation.",
        },
    ]
    return pd.DataFrame(rows)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    roads, restrictions, endpoint, raw_osm = acquire_osm()
    graph = routing.build_bus_graph(roads)

    arriva = download(ARRIVA_GTFS, RAW / "arriva_addabus_2025_2026.zip")
    lineelecco = download(LINEELECCO_GTFS, RAW / "lineelecco_2025_2026.zip")
    shape_rows, runtime_rows, stop_rows = [], [], []
    for path, label in [(arriva, "ARRIVA_ADDABUS"), (lineelecco, "LINEE_LECCO")]:
        s, r, st = parse_gtfs(path, label)
        shape_rows.extend(s); runtime_rows.extend(r); stop_rows.extend(st)

    shape_gdf = gpd.GeoDataFrame(shape_rows, crs=4326) if shape_rows else gpd.GeoDataFrame(columns=["geometry"], geometry="geometry", crs=4326)
    if not shape_gdf.empty:
        shape_gdf.to_file(OUT / "official_gtfs_route_shapes.geojson", driver="GeoJSON")
    runtimes = pd.DataFrame(runtime_rows)
    stops = pd.DataFrame(stop_rows).drop_duplicates(["feed", "stop_id"])
    runtimes.to_csv(OUT / "official_gtfs_trip_runtimes.csv", index=False)
    stops.to_csv(OUT / "official_gtfs_stops.csv", index=False)
    shape_metrics = route_shape_metrics(shape_gdf, roads)
    shape_metrics.to_csv(OUT / "gtfs_osm_shape_audit.csv", index=False)
    constraints = public_constraints()
    constraints.to_csv(OUT / "public_road_constraints.csv", index=False)

    found_routes = sorted(set(shape_metrics.get("route_short_name", pd.Series(dtype=str))))
    summary = {
        "epistemic_status": "PROVISIONAL_BLOCKED_BY_GATE_B_AND_GATE_C",
        "osm_endpoint_used": endpoint,
        "osm_bbox": {"south": BBOX[0], "west": BBOX[1], "north": BBOX[2], "east": BBOX[3]},
        "osm_raw_sha256": sha256(raw_osm),
        "osm_highway_ways": int(len(roads)),
        "bus_graph_nodes": int(graph.number_of_nodes()),
        "bus_graph_directed_edges": int(graph.number_of_edges()),
        "osm_turn_restrictions": int(len(restrictions)),
        "gtfs_routes_found": found_routes,
        "gtfs_unique_shapes": int(len(shape_metrics)),
        "gtfs_trip_records": int(len(runtimes)),
        "gtfs_stops": int(len(stops)),
        "arriva_gtfs_sha256": sha256(arriva),
        "lineelecco_gtfs_sha256": sha256(lineelecco),
        "public_constraints_registered": int(len(constraints)),
        "turn_restriction_enforcement": "NOT_YET_ENFORCED_IN_SHORTEST_PATH; relations are audited and exported",
        "note": "GTFS evidence is primary-source but remains PROVISIONAL_UNTIL_GATE_C for service-date/operator interpretation.",
    }
    (OUT / "gate_d_real_audit_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    if not TARGET_ROUTES.issubset(set(found_routes)):
        missing = sorted(TARGET_ROUTES - set(found_routes))
        raise AssertionError(f"Official GTFS audit did not find target routes: {missing}")
    if shape_metrics.empty or (shape_metrics["gtfs_shape_km"] <= 0).any():
        raise AssertionError("Invalid official GTFS shape lengths")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
