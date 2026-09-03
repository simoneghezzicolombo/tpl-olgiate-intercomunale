#!/usr/bin/env python3
"""Gate D structural candidate audit with authoritative rail-station anchoring.

The first structural candidate implementation correctly derived road geometry from
OSM but exposed a source conflict: the official bus GTFS contains two D184/D185
records labelled as the Olgiate station roughly half a kilometre apart. Averaging
those coordinates would manufacture a location that exists in neither source.

This wrapper therefore uses the official Trenord GTFS stop S01514
(Olgiate-Calco-Brivio) as the FACT interchange anchor. Bus GTFS station records are
retained only as diagnostic interchange evidence. All other behaviour is inherited
from gate_d_structural_candidates.py.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gate_d_structural_candidates as base

RAIL_STOPS = Path("data/raw/gtfs/rail_trenord/stops.txt")
RAIL_STATION_ID = "S01514"
BUS_STATION_ALIASES = {
    base._normal("Olgiate Molgora - stazione f.s."),
    base._normal("Olgiate Molgora (stazione f.s.)"),
}

# Replace only the ambiguous station anchor. No coordinate is hard-coded here.
base.ANCHOR_SPECS["FS"] = {
    "type": "rail_gtfs_stop",
    "stop_id": RAIL_STATION_ID,
}


def resolve_rail_station_anchor(key: str, spec: dict) -> dict:
    if not RAIL_STOPS.exists() or RAIL_STOPS.stat().st_size == 0:
        raise FileNotFoundError(RAIL_STOPS)
    stops = pd.read_csv(RAIL_STOPS, dtype=str)
    required = {"stop_id", "stop_name", "stop_lat", "stop_lon"}
    missing = required - set(stops.columns)
    if missing:
        raise ValueError(f"Trenord stops schema missing {sorted(missing)}")
    matches = stops[stops["stop_id"] == spec["stop_id"]].copy()
    if len(matches) != 1:
        raise ValueError(
            f"{key}: expected exactly one Trenord stop {spec['stop_id']}, found {len(matches)}"
        )
    row = matches.iloc[0]
    return {
        "anchor_id": key,
        "lon": float(row["stop_lon"]),
        "lat": float(row["stop_lat"]),
        "epistemic_status": "FACT",
        "source_type": "OFFICIAL_TRENORD_GTFS_STATION",
        "source_detail": str(row["stop_name"]),
        "official_routes_serving": "S8_RAIL_INTERCHANGE",
        "source_ids": str(row["stop_id"]),
    }


def bus_station_diagnostic(feeds: list[dict], rail_anchor: dict) -> pd.DataFrame:
    rows = []
    rail_gdf = gpd.GeoDataFrame(
        [{"geometry": gpd.points_from_xy([rail_anchor["lon"]], [rail_anchor["lat"]])[0]}],
        geometry="geometry",
        crs=4326,
    ).to_crs(32632)
    rail_point = rail_gdf.geometry.iloc[0]

    for feed in feeds:
        stops = feed["stops"].copy()
        matches = stops[stops["stop_name"].map(base._normal).isin(BUS_STATION_ALIASES)].copy()
        for _, stop in matches.iterrows():
            lon = float(stop["stop_lon"])
            lat = float(stop["stop_lat"])
            point = gpd.GeoSeries(gpd.points_from_xy([lon], [lat]), crs=4326).to_crs(32632).iloc[0]
            served = sorted(base.stop_routes(feed, {str(stop["stop_id"])}))
            rows.append({
                "rail_stop_id": RAIL_STATION_ID,
                "rail_stop_name": rail_anchor["source_detail"],
                "bus_feed": feed["feed_label"],
                "bus_stop_id": str(stop["stop_id"]),
                "bus_stop_name": str(stop["stop_name"]),
                "bus_routes_serving": ";".join(served),
                "distance_to_official_rail_station_m": float(point.distance(rail_point)),
                "epistemic_status": "DERIVED_GTFS_CROSS_SOURCE_DIAGNOSTIC",
            })
    result = pd.DataFrame(rows)
    if result.empty:
        raise ValueError("No bus GTFS station records found for interchange diagnostic")
    return result.sort_values(["bus_feed", "bus_stop_id"]).reset_index(drop=True)


def resolve_anchors(feeds: list[dict], roads: gpd.GeoDataFrame) -> pd.DataFrame:
    rows = []
    rail_anchor = None
    for key, spec in base.ANCHOR_SPECS.items():
        if spec["type"] == "rail_gtfs_stop":
            row = resolve_rail_station_anchor(key, spec)
            rail_anchor = row
            rows.append(row)
        elif spec["type"] == "gtfs_stop":
            rows.append(base.resolve_gtfs_anchor(key, spec, feeds))
        elif spec["type"] == "osm_named_road":
            rows.append(base.resolve_osm_road_anchor(key, spec, roads))
        else:
            raise ValueError(f"Unknown anchor type: {spec['type']}")
    if rail_anchor is None:
        raise AssertionError("Structural candidate set has no official rail station anchor")
    diagnostic = bus_station_diagnostic(feeds, rail_anchor)
    base.OUT.mkdir(parents=True, exist_ok=True)
    diagnostic.to_csv(base.OUT / "station_anchor_diagnostic.csv", index=False)
    return pd.DataFrame(rows)


# base.main resolves this global from its own module, so patch the resolver explicitly.
base.resolve_anchors = resolve_anchors


def main() -> int:
    return base.main()


if __name__ == "__main__":
    raise SystemExit(main())
