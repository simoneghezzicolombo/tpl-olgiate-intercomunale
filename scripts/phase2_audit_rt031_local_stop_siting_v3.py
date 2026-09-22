"""Audit every Olgiate proposed stop against caller places and pinned RT031 paths.

This is a siting inventory, not a stop recommendation. Straight-line distances
are descriptive, never pedestrian access or evidence of a safe boarding point.
"""

import argparse
import csv
import gzip
import hashlib
import json
import math
from pathlib import Path
import re


EXPECTED = {
    "typed": "c0169f3e39e1132853c2e8324d00bbb3030dbf5219c65889eee6ae4acf31b32e",
    "edges": "466f562f95805cb194cc079c3829d5abcd54a431653cce5364538869909dff19",
    "nodes": "2ab72595b7c52d8a08ccf767a20a9a5fc00b39552b37da01a53f270467a4ca06",
    "corridors": "71d0728898e1b36a8b496763e512886c59775528908c0609a6f8b553a060e189",
    "patterns": "44fd5d95717ea99d8bee205fa1949c978b44074af4134420ac59bc8a0769684e",
    "candidates": "bf3f5c648803fb0ba03b2f9af2bd4fa02924cb387bb0a752fc3a7a8ee1f14bc0",
    "poi": "5592e7ee0860f7acc71b42922b7e5f0986a5eb2357c52dc1025f5b51a303a672",
    "anchors": "c3ab598a43bfb83f31f086d6a14f29d92941969a349ef9087b5e6d87fe10b3d1",
    "roads": "2a1082b10f5a6560bdf69e8dc344541d3a892f751054316ea582fef32fe6b4c4",
}
VIA_CANTU_OSM_WAY_ID = "581532442"
REPO_TEXT_KEYS = frozenset({"candidates", "poi", "anchors", "roads"})


def sha256(path, normalize_newlines=False):
    if normalize_newlines:
        return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def csv_rows(path):
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def haversine_m(lat_a, lon_a, lat_b, lon_b):
    a, b = math.radians(lat_a), math.radians(lat_b)
    dlat, dlon = b - a, math.radians(lon_b - lon_a)
    q = math.sin(dlat / 2) ** 2 + math.cos(a) * math.cos(b) * math.sin(dlon / 2) ** 2
    return 2 * 6371000 * math.asin(min(1.0, math.sqrt(q)))


def nearest_node_distance_m(nodes, ids, lat, lon):
    return round(min(haversine_m(lat, lon, float(nodes[n]["lat"]),
                                 float(nodes[n]["lon"])) for n in ids), 1)


def main(inputs, typed_path, output):
    paths = {
        "typed": typed_path,
        "edges": inputs / "rt017" / "frozen_graph_edges.csv.gz",
        "nodes": inputs / "rt017" / "frozen_graph_nodes.csv.gz",
        "corridors": inputs / "rt022" / "corridor_evidence.csv",
        "patterns": inputs / "rt030" / "rt030_realization_passenger_stop_patterns.csv",
        "candidates": Path("outputs/phase2/stop_universe_v2/proposed_stop_candidates.csv"),
        "poi": Path("data/processed/poi_dataset.csv"),
        "anchors": Path("data/phase2/frozen_gate_d/source/structural_anchor_evidence.csv"),
        "roads": Path("data/raw/osm/osm_highways_core.geojson"),
    }
    if any(sha256(path, key in REPO_TEXT_KEYS) != EXPECTED[key]
           for key, path in paths.items()):
        raise ValueError("pinned stop-siting source drift")
    typed = json.loads(typed_path.read_text(encoding="utf-8"))
    if (typed.get("contract") != "RT031_HUB_SPLIT_TYPED_ONE_LINE_V3"
            or typed.get("network_selected") is not False
            or typed.get("timetable_assigned") is not False):
        raise ValueError("typed contract drift")
    poi = next(row for row in csv_rows(paths["poi"])
               if row["nome"] == "Centro Sportivo Comunale Olgiate Molgora")
    anchor = next(row for row in csv_rows(paths["anchors"])
                  if row["anchor_id"] == "SAN_ZENO")
    if anchor["epistemic_status"] != "ASSUMPTION":
        raise ValueError("San Zeno anchor semantics changed")
    targets = {
        "centro_sportivo_legacy_approximate_poi": (float(poi["lat"]), float(poi["lon"])),
        "san_zeno_gate_d_assumption_anchor": (float(anchor["lat"]), float(anchor["lon"])),
    }
    roads = {str(feature["properties"]["osm_id"]): feature["properties"]
             for feature in json.loads(paths["roads"].read_text(encoding="utf-8"))["features"]}
    candidates = sorted((r for r in csv_rows(paths["candidates"])
                         if r["COMUNE"] == "Olgiate Molgora"),
                        key=lambda r: r["candidate_id"])
    if any(r["physical_status"] != "FIELD_CHECK_PENDING" for r in candidates):
        raise ValueError("proposed stop physical-status drift")
    patterns = {r["realization_id"]: r for r in csv_rows(paths["patterns"])}
    corridors = {r["corridor_id"]: r for r in csv_rows(paths["corridors"])}
    edges = {r["edge_id"]: r for r in csv_rows(paths["edges"])}
    nodes = {r["node_id"]: r for r in csv_rows(paths["nodes"])}
    route = {}
    route_node_sets = {}
    route_way_sets = {}
    for name, line in sorted(typed["directional_patterns"].items()):
        edge_ids = [eid for rid in line["realization_ids"]
                    for eid in corridors[patterns[rid]["corridor_id"]]
                    ["path_edge_ids"].split(";")]
        way_edges = [eid for eid in edge_ids
                     if edges[eid]["osm_way_id"] == VIA_CANTU_OSM_WAY_ID]
        route_nodes = {nid for eid in edge_ids
                       for nid in (edges[eid]["u_node_id"], edges[eid]["v_node_id"])}
        route_node_sets[name] = route_nodes
        route_way_sets[name] = {edges[eid]["osm_way_id"] for eid in edge_ids}
        cantu_nodes = {nid for eid in way_edges
                       for nid in (edges[eid]["u_node_id"], edges[eid]["v_node_id"])}
        route[name] = {
            "traverses_san_zeno_via_cesare_cantu_osm_way": bool(way_edges),
            "via_cantu_edge_count": len(way_edges),
            "nearest_route_graph_node_straight_m_to_targets": {
                key: nearest_node_distance_m(nodes, route_nodes, *coords)
                for key, coords in targets.items()},
            "nearest_via_cantu_graph_node_straight_m_to_san_zeno_anchor": (
                nearest_node_distance_m(nodes, cantu_nodes,
                                        *targets["san_zeno_gate_d_assumption_anchor"])
                if cantu_nodes else None),
            "san_zeno_boarding_event_certified": False,
            "centro_sportivo_boarding_event_certified": False,
        }
    options = []
    for row in candidates:
        lat, lon = float(row["lat"]), float(row["lon"])
        road = roads.get(row["osm_way_id"], {})
        sidewalk_match = re.search(r'"sidewalk"=>"([^"]+)"',
                                   road.get("other_tags") or "")
        options.append({
            "candidate_id": row["candidate_id"],
            "osm_way_id": row["osm_way_id"],
            "road_name": road.get("name"),
            "osm_sidewalk_tag": sidewalk_match.group(1) if sidewalk_match else None,
            "highway": row["highway"],
            "road_uncertainty_flags": row["road_uncertainty_flags"],
            "physical_status": row["physical_status"],
            "distance_to_targets_straight_m": {
                key: round(haversine_m(lat, lon, *coords), 1)
                for key, coords in targets.items()},
            "population_additional_10min_v2_existing_official_stop_baseline":
                row["population_additional_10min"],
            "walk_graph_snap_ok": row["walk_graph_snap_ok"],
            "walk_graph_connector_m": row["walk_graph_connector_m"],
            "nearest_route_graph_node_straight_m_by_variant": {
                name: nearest_node_distance_m(nodes, ids, lat, lon)
                for name, ids in route_node_sets.items()},
            "osm_way_traversed_by_variant": {
                name: row["osm_way_id"] in ids
                for name, ids in route_way_sets.items()},
            "on_san_zeno_via_cesare_cantu_osm_way":
                row["osm_way_id"] == VIA_CANTU_OSM_WAY_ID,
        })
    payload = {
        "contract": "RT031_OLGIATE_STOP_SITING_INVENTORY_V3",
        "status": "NON_DECISIONAL_ALL_OLGIATE_PROPOSED_CANDIDATES",
        "input_sha256": EXPECTED,
        "repo_text_sha256_normalizes_crlf_to_lf": True,
        "target_coordinate_semantics": {
            "centro_sportivo_legacy_approximate_poi": "LEGACY_APPROXIMATE_POI_NOT_SITE_PIN",
            "san_zeno_gate_d_assumption_anchor": "DESIGN_ASSUMPTION_NOT_BOARDING_POINT",
        },
        "oratorio_exact_venue_resolved": False,
        "all_olgiate_proposed_candidate_count": len(options),
        "candidate_options": options,
        "hub_split_route_proximity": route,
        "via_cantu_way_has_existing_proposed_candidate": any(
            o["on_san_zeno_via_cesare_cantu_osm_way"] for o in options),
        "distance_is_straight_line_not_pedestrian_access": True,
        "additional_population_is_v2_existing_official_stop_baseline_not_rt031_marginal": True,
        "field_check_required_for_every_candidate": True,
        "directional_boarding_points_certified": False,
        "new_stop_selected": False,
        "network_selected": False,
        "primary_selection_authorised": False,
        "runner_up_selection_authorised": False,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes((json.dumps(payload, ensure_ascii=False, sort_keys=True,
                                   separators=(",", ":")) + "\n").encode("utf-8"))
    print(json.dumps({"candidate_count": len(options),
                      "via_cantu_candidate": payload["via_cantu_way_has_existing_proposed_candidate"],
                      "route_via_cantu": {name: value["traverses_san_zeno_via_cesare_cantu_osm_way"]
                                          for name, value in route.items()}}, sort_keys=True))
    return payload


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--typed", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    main(args.inputs, args.typed, args.output)
