#!/usr/bin/env python3
"""Convert the ATP Como-Lecco-Varese official D184/D185 KML files to deterministic GeoJSON.

The browser must render the authority-published route geometry itself, not a stop-to-stop
polyline and not a GTFS reconstruction. The two KML inputs are downloaded by CI from the
ATP open-data page and are kept outside the repository; this script records their hashes
and materializes a compact, deterministic browser asset plus a provenance manifest.
"""
from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import json
import re
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent
OUT_PREFIX = "current-routes-kml.geojson.gz.b64."
SOURCE_URLS = {
    "D184": "https://www.tplcomoleccovarese.it/atpcolc/images/Fil%20KML%202025/Urbano%20e%20interurbano%20Lecco/D184.kml",
    "D185": "https://www.tplcomoleccovarese.it/atpcolc/images/Fil%20KML%202025/Urbano%20e%20interurbano%20Lecco/D185.kml",
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def parse_coordinate_text(text: str | None) -> list[list[float]]:
    coords: list[list[float]] = []
    if not text:
        return coords
    for token in re.split(r"\s+", text.strip()):
        if not token:
            continue
        parts = token.split(",")
        if len(parts) < 2:
            continue
        try:
            lon, lat = float(parts[0]), float(parts[1])
        except ValueError:
            continue
        point = [lon, lat]
        if not coords or coords[-1] != point:
            coords.append(point)
    return coords


def parse_gx_track(track: ET.Element) -> list[list[float]]:
    coords: list[list[float]] = []
    for child in track.iter():
        if local_name(child.tag) != "coord" or not child.text:
            continue
        parts = child.text.split()
        if len(parts) < 2:
            continue
        try:
            point = [float(parts[0]), float(parts[1])]
        except ValueError:
            continue
        if not coords or coords[-1] != point:
            coords.append(point)
    return coords


def placemark_name(parent_map: dict[ET.Element, ET.Element], elem: ET.Element) -> str | None:
    current = elem
    while current in parent_map:
        current = parent_map[current]
        if local_name(current.tag) == "Placemark":
            for child in current:
                if local_name(child.tag) == "name" and child.text:
                    return child.text.strip()
            return None
    return None


def extract_lines(path: Path, route: str) -> tuple[list[dict], dict]:
    raw = path.read_bytes()
    root = ET.fromstring(raw)
    parent_map = {child: parent for parent in root.iter() for child in parent}
    lines: list[tuple[list[list[float]], str | None, str]] = []

    for elem in root.iter():
        kind = local_name(elem.tag)
        coords: list[list[float]] = []
        source_geom = kind
        if kind == "LineString":
            for child in elem.iter():
                if local_name(child.tag) == "coordinates":
                    coords = parse_coordinate_text(child.text)
                    if coords:
                        break
        elif kind == "Track":
            coords = parse_gx_track(elem)
        else:
            continue
        if len(coords) >= 2:
            lines.append((coords, placemark_name(parent_map, elem), source_geom))

    if not lines:
        raise RuntimeError(f"{route}: no LineString/gx:Track geometry found in {path}")

    features = []
    for index, (coords, name, source_geom) in enumerate(lines, start=1):
        # Catch accidental HTML/error pages parsed as XML and wildly unrelated geometry.
        for lon, lat in coords:
            if not (7.0 <= lon <= 11.0 and 44.0 <= lat <= 47.0):
                raise RuntimeError(f"{route}: coordinate outside northern-Italy sanity bounds: {(lon, lat)}")
        features.append(
            {
                "type": "Feature",
                "properties": {
                    "route": route,
                    "source": "OFFICIAL_ATP_KML_2025",
                    "source_file": path.name,
                    "component": index,
                    "placemark": name,
                    "source_geometry": source_geom,
                    "coordinate_count": len(coords),
                },
                "geometry": {"type": "LineString", "coordinates": coords},
            }
        )

    stats = {
        "source_file": path.name,
        "source_url": SOURCE_URLS[route],
        "bytes": len(raw),
        "sha256": sha256_bytes(raw),
        "line_components": len(features),
        "coordinates": sum(f["properties"]["coordinate_count"] for f in features),
    }
    return features, stats


def deterministic_gzip(data: bytes) -> bytes:
    return gzip.compress(data, compresslevel=9, mtime=0)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--d184", required=True, type=Path)
    parser.add_argument("--d185", required=True, type=Path)
    parser.add_argument("--chunk-chars", type=int, default=500_000)
    args = parser.parse_args()

    all_features: list[dict] = []
    sources: dict[str, dict] = {}
    for route, path in (("D184", args.d184), ("D185", args.d185)):
        features, stats = extract_lines(path, route)
        all_features.extend(features)
        sources[route] = stats

    geojson = {
        "type": "FeatureCollection",
        "name": "D184_D185_official_ATP_KML_2025",
        "features": all_features,
    }
    geojson_bytes = json.dumps(geojson, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    encoded = base64.b64encode(deterministic_gzip(geojson_bytes)).decode("ascii")

    for old in ROOT.glob(f"{OUT_PREFIX}*"):
        old.unlink()
    chunks = []
    for index, start in enumerate(range(0, len(encoded), args.chunk_chars)):
        name = f"{OUT_PREFIX}{index}"
        payload = encoded[start : start + args.chunk_chars]
        (ROOT / name).write_text(payload, encoding="ascii")
        chunks.append(
            {
                "file": name,
                "chars": len(payload),
                "sha256": sha256_bytes(payload.encode("ascii")),
            }
        )

    manifest = {
        "contract": "CURRENT_ROUTE_BASELINE_OFFICIAL_ATP_KML_V1",
        "decision_output": False,
        "authority": "Agenzia per il Trasporto Pubblico Locale del bacino di Como, Lecco e Varese",
        "open_data_page": "https://www.tplcomoleccovarese.it/atpcolc/zf/index.php/servizi-aggiuntivi/index/index/idtesto/134",
        "semantics": "Official authority-published KML route geometry. No stop-to-stop reconstruction and no screen-space offsets.",
        "routes": sources,
        "geojson": {
            "feature_count": len(all_features),
            "coordinate_count": sum(f["properties"]["coordinate_count"] for f in all_features),
            "sha256": sha256_bytes(geojson_bytes),
            "gzip_base64_chunks": chunks,
        },
    }
    (ROOT / "current-routes-kml-source.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    for route in ("D184", "D185"):
        if sources[route]["coordinates"] < 20:
            raise RuntimeError(f"{route}: suspiciously sparse official KML ({sources[route]['coordinates']} coordinates)")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
