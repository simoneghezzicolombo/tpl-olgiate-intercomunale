"""Export and map the shorter-road diagnostic, without promoting it to service."""

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from scripts.phase2_audit_rt031_south_road_probe_v3 import EXPECTED, VIRTUAL, rows
from scripts.phase2_probe_rt031_unique_line_v3 import build_graph


def main(paths, geojson_output, image_output):
    audit = json.loads(paths["audit"].read_text(encoding="utf-8"))
    if (audit["contract"] != "RT031_LINE8_FIXED_WAYPOINT_DISTANCE_OBJECTIVE_AUDIT_V3"
            or audit["network_selected"] is not False):
        raise ValueError("distance audit contract drift")
    target = audit["variants"]["full_retention_west_order"]["meters"]
    reference = audit["variants"]["full_retention_west_order"]["minutes"]
    if not target["represented_road_feasible"] or not reference["represented_road_feasible"]:
        raise ValueError("represented road feasibility drift")
    edges, nodes, _, attachments = build_graph(paths)
    candidate = next(row for row in rows(paths["candidates_normalized_newlines"])
                     if row["candidate_id"] == "P2V2S_0031")
    coords = {nid: [float(row["lon"]), float(row["lat"])] for nid, row in nodes.items()}
    coords[VIRTUAL] = [float(candidate["lon"]), float(candidate["lat"])]
    features = []
    for variant, value in (("fastest", reference), ("shortest_km", target)):
        for direction, path in value["road_path_edge_ids"].items():
            vertex_ids = [edges[path[0]]["u_node_id"]]
            for eid in path:
                if edges[eid]["u_node_id"] != vertex_ids[-1]:
                    raise ValueError("disconnected route witness")
                vertex_ids.append(edges[eid]["v_node_id"])
            if vertex_ids[0] != vertex_ids[-1]:
                raise ValueError("route witness not closed at FS")
            expected = value[direction + "_complete_cycle_distance_m"]
            if abs(sum(float(edges[eid]["length_m"]) for eid in path) - expected) > .01:
                raise ValueError("route witness distance drift")
            features.append({"type": "Feature", "properties": {
                "feature_type": "MODELED_ROAD_PATH_NOT_APPROVED_TPL_ROUTE",
                "variant": variant, "direction": direction, "distance_m": expected},
                "geometry": {"type": "LineString", "coordinates": [coords[n] for n in vertex_ids]}})
    fast_stops = set(reference["both_direction_encountered_stop_ids_not_boarding_guaranteed"])
    short_stops = set(target["both_direction_encountered_stop_ids_not_boarding_guaranteed"])
    for sid in sorted(fast_stops):
        row = attachments[sid]
        features.append({"type": "Feature", "properties": {
            "feature_type": "INVENTORY_ATTACHMENT_NOT_BOARDING_CERTIFIED",
            "stop_place_id": sid, "name": row["stop_name"],
            "encountered_in_shorter_road_both_directions": sid in short_stops},
            "geometry": {"type": "Point", "coordinates": [float(row["lon"]), float(row["lat"])]}})
    road_screen = json.loads(paths["road_screen"].read_text(encoding="utf-8"))
    if road_screen["contract"] != "RT031_UNIQUE_LINE_ROAD_SCREEN_V3":
        raise ValueError("road screen contract drift")
    for name, point in (("Olgiate sud (ipotesi)", coords[VIRTUAL]),
                        ("San Zeno (proxy)", [road_screen["north_proxy"]["lon"],
                                               road_screen["north_proxy"]["lat"]])):
        features.append({"type": "Feature", "properties": {
            "feature_type": "UNAPPROVED_STOP_NEED", "name": name},
            "geometry": {"type": "Point", "coordinates": point}})
    geojson = {"type": "FeatureCollection", "name": "RT031_LINE8_FASTEST_VS_SHORTEST_KM_ROAD_DIAGNOSTIC_V3",
               "properties": {"status": "NON_DECISIONAL_NOT_A_STOP_OR_SERVICE_PLAN",
                              "network_selected": False,
                              "primary_selection_authorised": False,
                              "runner_up_selection_authorised": False},
               "features": features}
    geojson_output.parent.mkdir(parents=True, exist_ok=True)
    geojson_output.write_text(json.dumps(geojson, ensure_ascii=False, sort_keys=True,
                                         separators=(",", ":")) + "\n", encoding="utf-8")

    roads = json.loads(paths["roads"].read_text(encoding="utf-8"))
    fig, ax = plt.subplots(figsize=(10.5, 8), constrained_layout=True)
    for feature in roads["features"]:
        geom = feature["geometry"]
        segments = ([geom["coordinates"]] if geom["type"] == "LineString" else
                    geom["coordinates"] if geom["type"] == "MultiLineString" else [])
        for segment in segments:
            if len(segment) > 1:
                ax.plot([p[0] for p in segment], [p[1] for p in segment],
                        color="#e1e5e8", linewidth=.45, zorder=1)
    for variant, color, width, label in (("fastest", "#67737f", 2.6, "Più veloce: 25/25 identità"),
                                         ("shortest_km", "#087e8b", 1.8,
                                          "Meno km: 22/25 identità")):
        lines = [f for f in features if f["geometry"]["type"] == "LineString"
                 and f["properties"]["variant"] == variant]
        for i, line in enumerate(lines):
            points = line["geometry"]["coordinates"]
            ax.plot([p[0] for p in points], [p[1] for p in points],
                    color=color, linewidth=width, alpha=.95,
                    zorder=2 if variant == "fastest" else 3,
                    label=label if i == 0 else None)
    for feature in features:
        if feature["properties"].get("feature_type") != "INVENTORY_ATTACHMENT_NOT_BOARDING_CERTIFIED":
            continue
        x, y = feature["geometry"]["coordinates"]
        props = feature["properties"]
        if not props["encountered_in_shorter_road_both_directions"]:
            ax.scatter(x, y, marker="x", color="#c53030", s=65, linewidth=2,
                       zorder=5, label="Identità non più incontrata" if
                       props["stop_place_id"] == sorted(fast_stops - short_stops)[0] else None)
            ax.annotate(props["name"], (x, y), xytext=(5, 5),
                        textcoords="offset points", fontsize=8, color="#9f2424")
    fs = attachments["FROZEN::L00407"]
    ax.scatter(float(fs["lon"]), float(fs["lat"]), color="#176a3a", s=65,
               zorder=6, label="Olgiate FS")
    for feature in features:
        if feature["properties"].get("feature_type") != "UNAPPROVED_STOP_NEED":
            continue
        x, y = feature["geometry"]["coordinates"]
        ax.scatter(x, y, marker="D", facecolor="white", edgecolor="#7a4f9a",
                   s=55, linewidth=1.5, zorder=7)
        ax.annotate(feature["properties"]["name"], (x, y), xytext=(6, -13),
                    textcoords="offset points", fontsize=8, color="#6b3e86")
    all_points = [p for f in features if f["geometry"]["type"] == "LineString"
                  for p in f["geometry"]["coordinates"]]
    west, east = min(p[0] for p in all_points), max(p[0] for p in all_points)
    south, north = min(p[1] for p in all_points), max(p[1] for p in all_points)
    ax.set_xlim(west - .003, east + .003)
    ax.set_ylim(south - .002, north + .002)
    ax.set_aspect(1 / .7)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_title("Linea 8: strada più veloce vs strada più corta in km\n"
                 "Stessi waypoint; fermate e servizio non certificati", loc="left")
    ax.legend(loc="lower left", fontsize=9, frameon=True)
    image_output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(image_output, dpi=180)
    plt.close(fig)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for key in (*EXPECTED, "audit", "roads", "road_screen"):
        parser.add_argument("--" + key, required=True, type=Path)
    parser.add_argument("--geojson_output", required=True, type=Path)
    parser.add_argument("--image_output", required=True, type=Path)
    args = parser.parse_args()
    main({key: getattr(args, key) for key in (*EXPECTED, "audit", "roads", "road_screen")},
         args.geojson_output, args.image_output)
