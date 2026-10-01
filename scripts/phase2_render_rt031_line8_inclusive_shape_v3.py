"""Render a static audit preview of the pinned Linea 8 road-shape GeoJSON."""

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def main(shape_path, roads_path, output_path):
    shape = json.loads(shape_path.read_text(encoding="utf-8"))
    roads = json.loads(roads_path.read_text(encoding="utf-8"))
    paths = [f for f in shape["features"] if f["geometry"]["type"] == "LineString"]
    if len(paths) != 2:
        raise ValueError("expected exactly two directional road paths")
    coords = [point for route in paths for point in route["geometry"]["coordinates"]]
    west, east = min(x for x, _ in coords), max(x for x, _ in coords)
    south, north = min(y for _, y in coords), max(y for _, y in coords)
    pad_x, pad_y = (east - west) * .08, (north - south) * .1
    bounds = (west - pad_x, east + pad_x, south - pad_y, north + pad_y)
    fig, axs = plt.subplots(2, 1, figsize=(13, 9), constrained_layout=True)
    titles = ("Ovest → Est: FS–Santa Maria–Olgiate sud–FS–Calco–Brivio–San Zeno–FS",
              "Est → Ovest: FS–San Zeno–Brivio–Calco–FS–Olgiate sud–Santa Maria–FS")
    for ax, route, title, color in zip(axs, paths, titles, ("#087e8b", "#ce6c30")):
        for feature in roads["features"]:
            props = feature["properties"]
            if props.get("highway") is None:
                continue
            geometry = feature["geometry"]
            segments = ([geometry["coordinates"]] if geometry["type"] == "LineString"
                        else geometry["coordinates"] if geometry["type"] == "MultiLineString"
                        else [])
            for segment in segments:
                if not segment or not any(bounds[0] <= x <= bounds[1]
                                          and bounds[2] <= y <= bounds[3]
                                          for x, y in segment):
                    continue
                ax.plot([point[0] for point in segment],
                        [point[1] for point in segment], color="#d8dce0",
                        linewidth=.45, zorder=1)
        line = route["geometry"]["coordinates"]
        ax.plot([p[0] for p in line], [p[1] for p in line], color=color,
                linewidth=2.4, zorder=3)
        for point in shape["features"][2:]:
            x, y = point["geometry"]["coordinates"]
            kind = point["properties"]["feature_type"]
            if kind == "EXISTING_INVENTORY_STOP_ENCOUNTERED_NOT_BOARDING_CERTIFIED":
                ax.scatter(x, y, s=13, color="#252b31", zorder=4)
            else:
                ax.scatter(x, y, s=75, color="#e33434", marker="*", zorder=5)
                ax.annotate(point["properties"]["name"], (x, y), xytext=(5, 5),
                            textcoords="offset points", fontsize=8, color="#a32020")
        fs = next(point for point in shape["features"][2:]
                  if point["properties"].get("stop_place_id") == "FROZEN::L00407")
        x, y = fs["geometry"]["coordinates"]
        ax.scatter(x, y, s=38, color="#1859ad", zorder=6)
        ax.annotate("Olgiate FS", (x, y), xytext=(5, -12), textcoords="offset points",
                    fontsize=8, color="#1859ad")
        ax.set_xlim(bounds[0], bounds[1])
        ax.set_ylim(bounds[2], bounds[3])
        ax.set_aspect(1 / .7)
        ax.set_xticks([])
        ax.set_yticks([])
        ax.set_title(title, fontsize=11, loc="left")
    fig.suptitle("Linea 8 inclusiva 11/11 · cammini modellati sul grafo, NON itinerario TPL certificato",
                 fontsize=13)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=180)
    plt.close(fig)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--shape", type=Path, required=True)
    parser.add_argument("--roads", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    main(args.shape, args.roads, args.output)
