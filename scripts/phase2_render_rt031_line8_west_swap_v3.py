"""Static map: inclusive reference and bounded west waypoint-order shortcut."""

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def main(baseline_path, swap_path, roads_path, output_path):
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    swap = json.loads(swap_path.read_text(encoding="utf-8"))
    roads = json.loads(roads_path.read_text(encoding="utf-8"))
    base_lines = [f for f in baseline["features"] if f["geometry"]["type"] == "LineString"]
    swap_lines = [f for f in swap["features"] if f["geometry"]["type"] == "LineString"]
    if len(base_lines) != 2 or len(swap_lines) != 2:
        raise ValueError("expected two modeled directions for each geometry")
    all_coords = [p for f in base_lines for p in f["geometry"]["coordinates"]]
    west, east = min(p[0] for p in all_coords), max(p[0] for p in all_coords)
    south, north = min(p[1] for p in all_coords), max(p[1] for p in all_coords)
    full_bounds = (west - (east - west) * .06, east + (east - west) * .06,
                   south - (north - south) * .09, north + (north - south) * .09)
    named = {f["properties"].get("stop_place_id"): f["geometry"]["coordinates"]
             for f in swap["features"] if f["geometry"]["type"] == "Point"}
    targets = [named[sid] for sid in ("FROZEN::300879", "ASF::PEREGO_VIA_STATALE_79")]
    if len(targets) != 2:
        raise ValueError("swap target points missing")
    local_west, local_east = min(p[0] for p in targets), max(p[0] for p in targets)
    local_south, local_north = min(p[1] for p in targets), max(p[1] for p in targets)
    # Include surrounding road context around both sourced stop coordinates.
    local_bounds = (local_west - .014, local_east + .014,
                    local_south - .009, local_north + .009)
    fig, axs = plt.subplots(1, 2, figsize=(15, 5), constrained_layout=True)
    for ax, bounds, title in zip(axs, (full_bounds, local_bounds),
                                 ("Intera Linea 8", "Dettaglio Rovagnate–Perego")):
        for feature in roads["features"]:
            if feature["properties"].get("highway") is None:
                continue
            geometry = feature["geometry"]
            segments = ([geometry["coordinates"]] if geometry["type"] == "LineString"
                        else geometry["coordinates"] if geometry["type"] == "MultiLineString"
                        else [])
            for segment in segments:
                if segment and any(bounds[0] <= x <= bounds[1] and bounds[2] <= y <= bounds[3]
                                   for x, y in segment):
                    ax.plot([p[0] for p in segment], [p[1] for p in segment],
                            color="#d9dee3", linewidth=.35, zorder=1)
        for lines, color, width, label in ((base_lines, "#929aa1", 2.8, "11/11 attuale"),
                                           (swap_lines, "#087e8b", 1.8, "Ordine invertito")):
            for index, line in enumerate(lines):
                points = line["geometry"]["coordinates"]
                ax.plot([p[0] for p in points], [p[1] for p in points],
                        color=color, linewidth=width, alpha=.9, zorder=3 if color == "#929aa1" else 4,
                        label=label if index == 0 else None)
        for sid, label in (("FROZEN::300879", "Rovagnate"),
                           ("ASF::PEREGO_VIA_STATALE_79", "Perego"),
                           ("FROZEN::L00407", "Olgiate FS")):
            if sid not in named:
                continue
            x, y = named[sid]
            if bounds[0] <= x <= bounds[1] and bounds[2] <= y <= bounds[3]:
                ax.scatter(x, y, s=30, color="#252b31", zorder=5)
                ax.annotate(label, (x, y), xytext=(5, 5), textcoords="offset points",
                            fontsize=8, color="#252b31")
        ax.set_xlim(bounds[0], bounds[1])
        ax.set_ylim(bounds[2], bounds[3])
        ax.set_aspect(1 / .7)
        ax.set_xticks([])
        ax.set_yticks([])
        ax.set_title(title, loc="left", fontsize=11)
        ax.legend(loc="lower left", fontsize=8, frameon=False)
    fig.suptitle("Linea 8 · prova di inversione Rovagnate/Perego: −1,562 km per coppia dei versi\n"
                 "Cammini su grafo, non itinerario o fermate TPL certificati", fontsize=12)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=180)
    plt.close(fig)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", required=True, type=Path)
    parser.add_argument("--swap", required=True, type=Path)
    parser.add_argument("--roads", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    main(args.baseline, args.swap, args.roads, args.output)
