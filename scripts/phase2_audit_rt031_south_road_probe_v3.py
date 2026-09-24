"""Pinned, non-decisional road-model probe to a proposed south-Olgiate stop.

Positive paths are conditional model results, never field/vehicle certification.
"""

import argparse
from collections import defaultdict
import csv
import gzip
import hashlib
import heapq
import json
import math
from pathlib import Path

from src.phase2_rt031_rt017_transition_adapter_v3 import FrozenRT017ViaNodeAdapter


EXPECTED = {
    "edges": "466f562f95805cb194cc079c3829d5abcd54a431653cce5364538869909dff19",
    "nodes": "2ab72595b7c52d8a08ccf767a20a9a5fc00b39552b37da01a53f270467a4ca06",
    "rules": "954865ad8972bd20d819e3eb6c4d548102609a4de07b7006ac7e42a61e14ed3a",
    "attachments": "30d64ff20e9b89c31f7878c415dd4c6bb5a0d10f51b24d041e4deb4d57e6571b",
    "successor": "14e39b47c09c4afe0d26d13b7369b906299db15d14690ba0e5d06e11b2fd7b7c",
    "candidates_normalized_newlines": "bf3f5c648803fb0ba03b2f9af2bd4fa02924cb387bb0a752fc3a7a8ee1f14bc0",
}
FS = "FROZEN::L00407"
SOUTH = "P2V2S_0031"
VIRTUAL = "RT031::P2V2S_0031_PROJECTED_ROAD_POINT"


def digest(path, normalize=False):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk.replace(b"\r\n", b"\n") if normalize else chunk)
    return h.hexdigest()


def rows(path):
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def projection(point, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    t = max(0.0, min(1.0, ((point[0] - a[0]) * dx + (point[1] - a[1]) * dy)
                           / (dx * dx + dy * dy)))
    return t, math.hypot(point[0] - a[0] - t * dx,
                         point[1] - a[1] - t * dy)


def shortest(edges, rules, source, target):
    """Dijkstra over last directed edge; represented via-node turns are checked."""
    adapter = FrozenRT017ViaNodeAdapter(edges.values(), rules,
                                       unresolved_external_via_way_count=2)
    outgoing = defaultdict(list)
    for eid, edge in edges.items():
        outgoing[edge["u_node_id"]].append(eid)
    for values in outgoing.values():
        values.sort()
    start = (source, "")
    best = {start: (0.0, 0.0)}
    previous = {}
    heap = [(0.0, 0.0, source, "")]
    finish = None
    while heap:
        minutes, meters, node, last = heapq.heappop(heap)
        state = (node, last)
        if (minutes, meters) != best[state]:
            continue
        if node == target:
            finish = state
            break
        for eid in outgoing.get(node, ()):
            if last and adapter.decision((last,), eid)["allowed"] is not True:
                continue
            edge = edges[eid]
            nxt = (edge["v_node_id"], eid)
            cost = (minutes + float(edge["running_minutes_model"]),
                    meters + float(edge["length_m"]))
            if nxt not in best or cost < best[nxt]:
                best[nxt] = cost
                previous[nxt] = (state, eid)
                heapq.heappush(heap, (*cost, *nxt))
    if finish is None:
        return None
    path = []
    cursor = finish
    while cursor != start:
        cursor, eid = previous[cursor]
        path.append(eid)
    path.reverse()
    ways = sorted({edges[eid]["osm_way_id"] for eid in path})
    return {"distance_m": round(best[finish][1], 3),
            "running_minutes_model": round(best[finish][0], 6),
            "edge_ids": path, "osm_way_ids": ways,
            "via_node_rules_rejected_on_selected_path": False}


def main(paths, output):
    for label, path in paths.items():
        if digest(path, label.endswith("normalized_newlines")) != EXPECTED[label]:
            raise ValueError(f"pinned source drift: {label}")
    edges = {row["edge_id"]: row for row in rows(paths["edges"])}
    nodes = {row["node_id"]: row for row in rows(paths["nodes"])}
    rules = rows(paths["rules"])
    attachment = next(row for row in rows(paths["attachments"])
                      if row["stop_place_id"] == FS)
    if attachment["route_ready"] != "True":
        raise ValueError("FS attachment drift")
    candidate = next(row for row in rows(paths["candidates_normalized_newlines"])
                     if row["candidate_id"] == SOUTH)
    if (candidate["physical_status"] != "FIELD_CHECK_PENDING"
            or candidate["osm_way_id"] != "40627763"):
        raise ValueError("south stop candidate drift")
    point = (float(candidate["x_utm32"]), float(candidate["y_utm32"]))
    segment_options = []
    for row in edges.values():
        if row["osm_way_id"] != candidate["osm_way_id"]:
            continue
        a, b = nodes[row["u_node_id"]], nodes[row["v_node_id"]]
        t, distance = projection(point, (float(a["x"]), float(a["y"])),
                                 (float(b["x"]), float(b["y"])))
        segment_options.append((distance, row["edge_id"], t))
    segment_options.sort()
    if not segment_options or segment_options[0][0] > 1.0:
        raise ValueError("candidate not on frozen bus graph way")
    nearest = segment_options[0]
    first = edges[nearest[1]]
    pair = {first["u_node_id"], first["v_node_id"]}
    segment_edges = [row for row in edges.values()
                     if row["osm_way_id"] == candidate["osm_way_id"]
                     and {row["u_node_id"], row["v_node_id"]} == pair]
    if len(segment_edges) != 2 or len({row["u_node_id"] for row in segment_edges}) != 2:
        raise ValueError("candidate segment directional identity ambiguous")
    for row in segment_edges:
        a, b = nodes[row["u_node_id"]], nodes[row["v_node_id"]]
        t, distance = projection(point, (float(a["x"]), float(a["y"])),
                                 (float(b["x"]), float(b["y"])))
        if distance > 1.0 or not 0 < t < 1:
            raise ValueError("projected road point not inside bidirectional model segment")
        for suffix, u, v, share in (("IN", row["u_node_id"], VIRTUAL, t),
                                    ("OUT", VIRTUAL, row["v_node_id"], 1 - t)):
            eid = row["edge_id"] + "::" + suffix
            edges[eid] = {**row, "edge_id": eid, "u_node_id": u, "v_node_id": v,
                          "length_m": str(float(row["length_m"]) * share),
                          "running_minutes_model": str(float(row["running_minutes_model"]) * share)}
    fs_node = attachment["graph_node_id"]
    trips = {"FS_TO_SOUTH": shortest(edges, rules, fs_node, VIRTUAL),
             "SOUTH_TO_FS": shortest(edges, rules, VIRTUAL, fs_node)}
    if any(value is None for value in trips.values()):
        raise ValueError("one model direction is unreachable")
    successor = json.loads(paths["successor"].read_text(encoding="utf-8"))
    if (successor["status"] != "PASS_RT031_SUCCESSOR_VIA_WAY_IRRELEVANT_TO_RT023_COMPOSED_DOMAIN"
            or successor["successor_via_way_relation_count"] != 2
            or successor["future_new_carrier_search_covered"] is not False):
        raise ValueError("successor restriction evidence drift")
    via_ways = {way for relation in successor["successor_via_way_relations"]
                for way in relation["via_way_ids"]}
    if any(via_ways & set(trip["osm_way_ids"]) for trip in trips.values()):
        raise ValueError("new path crosses known successor via-way restriction")
    payload = {
        "contract": "RT031_SOUTH_OLGIATE_PINNED_ROAD_MODEL_PROBE_V3",
        "status": "NON_DECISIONAL_CONDITIONAL_MODEL_PATHS_NOT_FIELD_CERTIFIED",
        "input_sha256": EXPECTED,
        "candidate_id": SOUTH,
        "candidate_physical_status": "FIELD_CHECK_PENDING",
        "candidate_projection_to_pinned_way_m": round(nearest[0], 6),
        "candidate_way_id": candidate["osm_way_id"],
        "candidate_segment_model_bidirectional": True,
        "fs_attachment_node_id": fs_node,
        "trips": trips,
        "known_successor_via_way_relation_ids": sorted(
            relation["relation_id"] for relation in successor["successor_via_way_relations"]),
        "known_successor_via_way_overlap_with_trips": False,
        "via_node_restrictions_checked": True,
        "new_carrier_global_restriction_completeness_certified": False,
        "bus_suitability_field_certified": False,
        "directional_boarding_events_certified": False,
        "route_insertion_into_one_line_certified": False,
        "runtime_excludes_dwell_recovery_and_traffic_variation": True,
        "network_selected": False,
        "primary_selection_authorised": False,
        "runner_up_selection_authorised": False,
        "decision_budget_km": None,
        "uncertainty_band_min": None,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n",
                      encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for label in EXPECTED:
        parser.add_argument(f"--{label}", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    main({label: getattr(args, label) for label in EXPECTED}, args.output)
