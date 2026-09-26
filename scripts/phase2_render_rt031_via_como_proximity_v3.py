"""Static street-context preview of the conditional Via Como proximity screen."""

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def main(baseline_path, swap_path, proximity_path, roads_path, output_path):
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    swap = json.loads(swap_path.read_text(encoding="utf-8"))
    proximity = json.loads(proximity_path.read_text(encoding="utf-8"))
    roads = json.loads(roads_path.read_text(encoding="utf-8"))
    if proximity["contract"] != "RT031_VIA_COMO_STOP_TO_WEST_SWAP_ROAD_PROXIMITY_V3":
        raise ValueError("proximity contract drift")
    x, y = proximity["stop_place_lon_lat"]
    nearest = proximity["comparisons"]["west_swap"][
        "forward_west_then_east"]["nearest_route_point_lon_lat"]
    distance = proximity["comparisons"]["west_swap"][
        "forward_west_then_east"]["planar_straight_line_distance_m"]
    center = ((x + nearest[0]) / 2, (y + nearest[1]) / 2)
    bounds = (center[0] - .0024, center[0] + .0024,
              center[1] - .0016, center[1] + .0016)
    fig, ax = plt.subplots(figsize=(8, 5), constrained_layout=True)
    for feature in roads["features"]:
        if feature["properties"].get("highway") is None:
            continue
        geometry = feature["geometry"]
        segments = ([geometry["coordinates"]] if geometry["type"] == "LineString"
                    else geometry["coordinates"] if geometry["type"] == "MultiLineString"
                    else [])
        for segment in segments:
            if segment and any(bounds[0] <= px <= bounds[1] and bounds[2] <= py <= bounds[3]
                               for px, py in segment):
                ax.plot([p[0] for p in segment], [p[1] for p in segment],
                        color="#d5dce1", linewidth=1, zorder=1)
    for source, color, width, label in ((baseline, "#929aa1", 3, "Tracciato 11/11"),
                                        (swap, "#087e8b", 2.6, "Ordine Rovagnate/Perego invertito")):
        lines = [f for f in source["features"] if f["geometry"]["type"] == "LineString"]
        if len(lines) != 2:
            raise ValueError("modeled direction geometry missing")
        for index, feature in enumerate(lines):
            points = feature["geometry"]["coordinates"]
            ax.plot([p[0] for p in points], [p[1] for p in points],
                    color=color, linewidth=width, alpha=.85,
                    label=label if index == 0 else None, zorder=3)
    ax.plot([x, nearest[0]], [y, nearest[1]], color="#b52b2b", linestyle="--",
            linewidth=1.5, zorder=4)
    ax.scatter(x, y, s=90, color="#b52b2b", marker="o", label="Via Como attuale",
               zorder=5)
    ax.scatter(*nearest, s=85, color="#b88a15", marker="x",
               label="Punto stradale più vicino, NON fermata", zorder=6)
    ax.set_xlim(bounds[0], bounds[1])
    ax.set_ylim(bounds[2], bounds[3])
    ax.set_aspect(1 / .7)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.legend(loc="upper left", fontsize=8, frameon=False)
    ax.set_title(f"Via Como: {distance:.1f} m in linea d'aria dal nuovo cammino\n"
                 "Non prova accesso pedonale o fermata sicura nei due versi", fontsize=11)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=180)
    plt.close(fig)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for key in ("baseline", "swap", "proximity", "roads", "output"):
        parser.add_argument("--" + key, required=True, type=Path)
    args = parser.parse_args()
    main(args.baseline, args.swap, args.proximity, args.roads, args.output)
