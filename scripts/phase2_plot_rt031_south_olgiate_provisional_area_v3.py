"""Render the provisional south-Olgiate sensitivity envelopes on pinned OSM roads."""

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
from shapely.geometry import box, shape


def draw_geometry(ax, geometry, **style):
    if geometry.is_empty:
        return
    if geometry.geom_type == "LineString":
        x, y = geometry.xy
        ax.plot(x, y, **style)
    elif geometry.geom_type in ("MultiLineString", "GeometryCollection"):
        for part in geometry.geoms:
            if part.geom_type in ("LineString", "MultiLineString"):
                draw_geometry(ax, part, **style)


def main(audit_path, output_path):
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    if audit["contract"] != "RT031_SOUTH_OLGIATE_PROVISIONAL_AREA_SENSITIVITY_V3":
        raise ValueError("unexpected audit")
    roads = json.loads(Path("data/raw/osm/osm_highways_core.geojson").read_text(
        encoding="utf-8"))["features"]
    extent = box(9.3905, 45.7165, 9.409, 45.736)
    fig, ax = plt.subplots(figsize=(9, 9))
    for feature in roads:
        geometry = shape(feature["geometry"])
        if not geometry.intersects(extent):
            continue
        properties = feature["properties"]
        if '"ref"=>"SS342"' in (properties.get("other_tags") or ""):
            draw_geometry(ax, geometry.intersection(extent), color="#a14c26",
                          linewidth=2.4, zorder=3)
        elif properties.get("highway") in ("primary", "secondary", "tertiary",
                                           "residential", "unclassified", "service"):
            draw_geometry(ax, geometry.intersection(extent), color="#c8c9c6",
                          linewidth=0.65, zorder=1)
    outer = shape(audit["areas"]["outer"]["geometry"])
    inner = shape(audit["areas"]["inner"]["geometry"])
    ax.fill(*outer.exterior.xy, color="#60a5b1", alpha=0.13, zorder=2)
    ax.plot(*outer.exterior.xy, color="#277c8c", linewidth=1.7,
            label="Involucro esteso (ipotesi)", zorder=4)
    ax.fill(*inner.exterior.xy, color="#67a85b", alpha=0.18, zorder=2)
    ax.plot(*inner.exterior.xy, color="#4b8a3a", linewidth=1.7,
            label="Involucro interno (ipotesi)", zorder=4)
    points = [
        (9.403662947256066, 45.72918776556806, "Olgiate FS", "#225a9d", "o"),
        (9.397265069842808, 45.72130999924538, "P2V2S_0031", "#b12828", "o"),
        (9.3979736, 45.7221313, "Casa di Comunità¹", "#b12828", "s"),
        (9.3980, 45.7345, "Vecchio POI sportivo²", "#8c6b8b", "x"),
        (9.407099337458824, 45.73522284258008, "Vecchia ancora San Zeno²", "#8c6b8b", "x"),
    ]
    for lon, lat, label, color, marker in points:
        ax.scatter(lon, lat, s=44, c=color, marker=marker, zorder=5)
        ax.annotate(label, (lon, lat), xytext=(5, 5),
                    textcoords="offset points", fontsize=8, color=color)
    ax.set_xlim(extent.bounds[0], extent.bounds[2])
    ax.set_ylim(extent.bounds[1], extent.bounds[3])
    ax.set_aspect(1 / 0.699, adjustable="box")
    ax.set_xlabel("Longitudine")
    ax.set_ylabel("Latitudine")
    ax.set_title("Olgiate a sud della SS342 — perimetri provvisori")
    ax.legend(loc="upper left", fontsize=8, frameon=False)
    fig.text(0.07, 0.015,
             "¹ Fermata speciale, non servizio ordinario certificato. ² Proxy precedenti fuori area.\n"
             "Perimetri di sensibilità, non digitalizzazione della cerchiatura. © OpenStreetMap contributors",
             fontsize=7, va="bottom")
    fig.tight_layout(rect=(0, 0.055, 1, 1))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=170)
    plt.close(fig)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    main(args.audit, args.output)
