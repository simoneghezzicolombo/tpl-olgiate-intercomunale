"""Show the inclusive intermunicipal road path against a conditional peak short loop."""

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


SCENARIO = "OLGIATE_STATALE_CALCO_VIRGILIO"


def main(full_path, short_path, roads_path, output_path):
    full = json.loads(full_path.read_text(encoding="utf-8"))
    short = json.loads(short_path.read_text(encoding="utf-8"))
    roads = json.loads(roads_path.read_text(encoding="utf-8"))
    full_lines = [f for f in full["features"] if f["geometry"]["type"] == "LineString"]
    short_lines = [f for f in short["features"] if f["properties"].get("scenario") == SCENARIO]
    if len(full_lines) != 2 or len(short_lines) != 1:
        raise ValueError("expected two full directions and one nominated peak loop")
    coords = [p for line in full_lines for p in line["geometry"]["coordinates"]]
    west, east = min(p[0] for p in coords), max(p[0] for p in coords)
    south, north = min(p[1] for p in coords), max(p[1] for p in coords)
    pad_x, pad_y = (east - west) * .07, (north - south) * .09
    bounds = (west - pad_x, east + pad_x, south - pad_y, north + pad_y)
    fig, axs = plt.subplots(1, 2, figsize=(15, 4.6), constrained_layout=True)

    for ax in axs:
        for feature in roads["features"]:
            if feature["properties"].get("highway") is None:
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
                ax.plot([p[0] for p in segment], [p[1] for p in segment],
                        color="#d9dee3", linewidth=.35, zorder=1)
        ax.set_xlim(bounds[0], bounds[1])
        ax.set_ylim(bounds[2], bounds[3])
        ax.set_aspect(1 / .7)
        ax.set_xticks([])
        ax.set_yticks([])

    for line in full_lines:
        points = line["geometry"]["coordinates"]
        axs[0].plot([p[0] for p in points], [p[1] for p in points],
                    color="#087e8b", linewidth=2, alpha=.85, zorder=3)
        axs[1].plot([p[0] for p in points], [p[1] for p in points],
                    color="#9aa6ae", linewidth=1.3, alpha=.7, zorder=2)
    points = short_lines[0]["geometry"]["coordinates"]
    axs[1].plot([p[0] for p in points], [p[1] for p in points],
                color="#ce423d", linewidth=3, zorder=4)
    for ax in axs:
        for point in full["features"]:
            if point["geometry"]["type"] != "Point":
                continue
            x, y = point["geometry"]["coordinates"]
            sid = point["properties"].get("stop_place_id")
            if sid == "FROZEN::L00407":
                ax.scatter(x, y, s=45, color="#1859ad", zorder=6)
                ax.annotate("Olgiate FS", (x, y), xytext=(5, -14),
                            textcoords="offset points", fontsize=8, color="#1859ad")
            elif sid == "P2V2S_0031":
                ax.scatter(x, y, s=70, color="#b82e2e", marker="*", zorder=6)
                ax.annotate("Olgiate sud*", (x, y), xytext=(5, 5),
                            textcoords="offset points", fontsize=8)
            elif sid == "PROXY::SAN_ZENO_VIA_CANTU_ROAD_NODE":
                ax.scatter(x, y, s=70, color="#b82e2e", marker="*", zorder=6)
                ax.annotate("San Zeno*", (x, y), xytext=(5, 5),
                            textcoords="offset points", fontsize=8)
    axs[0].set_title("Percorso completo intercomunale · 11/11", loc="left", fontsize=11)
    axs[1].set_title("Rosso: solo rinforzo corto ipotizzato in punta", loc="left", fontsize=11)
    fig.suptitle("Linea 8: il rinforzo corto NON sostituisce il servizio ai cinque comuni\n"
                 "Tracciati stradali modellati, non servizio TPL o fermate certificati (*nuovi siti da verificare)",
                 fontsize=12)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=180)
    plt.close(fig)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--full", required=True, type=Path)
    parser.add_argument("--short", required=True, type=Path)
    parser.add_argument("--roads", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    main(args.full, args.short, args.roads, args.output)
