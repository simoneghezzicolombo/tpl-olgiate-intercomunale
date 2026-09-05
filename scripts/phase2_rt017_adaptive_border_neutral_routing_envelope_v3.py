#!/usr/bin/env python3
"""RT-017 real-territory adaptive border-neutral road-routing envelope V3.

The 36 frozen stop places are immutable geographic probes only.  This runner does
not select passenger terminals or a network.  It repeatedly acquires the same
historical OSM epoch over deterministic nested metric envelopes, rebuilds the
restriction-aware bus graph, routes the complete RT-010 directed probe-pair
universe, and freezes the earliest level proven stable by two larger successors.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
from pathlib import Path
import shutil
import time

import pandas as pd
import requests
from pyproj import Transformer
from scipy.spatial import cKDTree

from src.phase2_adaptive_routing_envelope_v3 import (
    BOUNDARY_GUARD_M,
    CONTRACT,
    MAX_SNAP_M,
    choose_smallest_converged_level,
    compare_pair_results,
    derive_levels,
    boundary_clearance_m,
    segment_in_bounds,
)
from src.phase2_complete_directed_pairs_v3 import (
    audit_pair_execution_completeness,
    build_complete_directed_pair_manifest,
)
from src.phase2_frozen_graph import (
    build_adjacency,
    build_turn_rule_index,
    bus_eligibility,
    node_id,
    oneway_direction,
    parse_speed_kmh,
    restriction_aware_one_to_many,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STOPS = ROOT / "outputs/phase2/network_design_method_audit_v3/master_stop_inventory_gpt_v3/existing_stop_places_operational_gpt_v5.csv"
DEFAULT_OUT = ROOT / "outputs/phase2/rt017"
BASELINE_COMMIT = "8a2cd43405dbac04cea56294407bcc7b453c65b4"
# Exact RT-015 commit timestamp: historical Overpass queries therefore replay one
# fixed OSM epoch rather than mutable current data.
OSM_SNAPSHOT_TIMESTAMP = "2026-09-05T13:45:50Z"
EXPECTED_STOP_BLOB_SHA1 = "8d3a4368a6f62bbdf8fe18ee99482aff18e38fe5"
EXPECTED_STOP_COUNT = 36
OVERPASS_ENDPOINTS = (
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass-api.de/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
)
USER_AGENT = "tpl-olgiate-rt017-border-neutral/3.0 (+github.com/simoneghezzicolombo/tpl-olgiate-intercomunale)"
BUS_EXCEPTIONS = {"bus", "psv", "public_service_vehicle"}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def git_blob_sha1(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()


def canonical_json_bytes(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")


def deterministic_gzip(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as handle:
        with gzip.GzipFile(filename="", mode="wb", fileobj=handle, compresslevel=9, mtime=0) as gz:
            gz.write(payload)


def write_df_gzip(path: Path, frame: pd.DataFrame) -> None:
    deterministic_gzip(path, frame.to_csv(index=False, lineterminator="\n").encode("utf-8"))


def split_except(value: object) -> set[str]:
    text = str(value or "").lower().replace(",", ";")
    return {part.strip() for part in text.split(";") if part.strip()}


def envelope_wgs_bounds(level, to_wgs: Transformer) -> tuple[float, float, float, float]:
    corners = [
        to_wgs.transform(level.min_x, level.min_y),
        to_wgs.transform(level.min_x, level.max_y),
        to_wgs.transform(level.max_x, level.min_y),
        to_wgs.transform(level.max_x, level.max_y),
    ]
    lons = [p[0] for p in corners]
    lats = [p[1] for p in corners]
    return min(lats), min(lons), max(lats), max(lons)


def tiles4(bbox: tuple[float, float, float, float]) -> list[tuple[float, float, float, float]]:
    south, west, north, east = bbox
    mid_lat = (south + north) / 2.0
    mid_lon = (west + east) / 2.0
    return [
        (south, west, mid_lat, mid_lon),
        (south, mid_lon, mid_lat, east),
        (mid_lat, west, north, mid_lon),
        (mid_lat, mid_lon, north, east),
    ]


def query_tile(tile: tuple[float, float, float, float]) -> tuple[dict, str]:
    south, west, north, east = tile
    query = f'''[out:json][timeout:180][date:"{OSM_SNAPSHOT_TIMESTAMP}"];
(
  way["highway"]({south:.8f},{west:.8f},{north:.8f},{east:.8f});
  relation["type"="restriction"]({south:.8f},{west:.8f},{north:.8f},{east:.8f});
);
(._;>;);
out meta;'''
    errors: list[str] = []
    for endpoint in OVERPASS_ENDPOINTS:
        for attempt in range(2):
            try:
                response = requests.post(
                    endpoint,
                    data={"data": query},
                    headers={"User-Agent": USER_AGENT},
                    timeout=210,
                )
                response.raise_for_status()
                payload = response.json()
                if not payload.get("elements"):
                    raise ValueError("empty historical Overpass response")
                return payload, endpoint
            except Exception as exc:
                errors.append(f"{endpoint}#{attempt + 1}:{type(exc).__name__}:{exc}")
                time.sleep(1.0)
    raise RuntimeError("historical Overpass tile acquisition failed: " + " | ".join(errors))


def acquire_level_snapshot(bbox: tuple[float, float, float, float]) -> tuple[dict, list[str]]:
    merged: dict[tuple[str, int], dict] = {}
    endpoints: list[str] = []
    for tile in tiles4(bbox):
        payload, endpoint = query_tile(tile)
        endpoints.append(endpoint)
        for element in payload.get("elements", []):
            key = (str(element.get("type")), int(element.get("id")))
            previous = merged.get(key)
            if previous is not None and canonical_json_bytes(previous) != canonical_json_bytes(element):
                raise AssertionError(f"conflicting OSM element versions at fixed epoch: {key}")
            merged[key] = element
    type_order = {"node": 0, "way": 1, "relation": 2}
    elements = sorted(merged.values(), key=lambda e: (type_order.get(str(e.get("type")), 9), int(e.get("id"))))
    return {
        "version": 0.6,
        "generator": "RT-017 fixed-epoch tiled Overpass canonical merge",
        "snapshot_timestamp": OSM_SNAPSHOT_TIMESTAMP,
        "elements": elements,
    }, endpoints


def build_graph_tables(payload: dict, bounds, to_metric: Transformer) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    elements = payload.get("elements", [])
    osm_nodes = {
        int(e["id"]): (float(e["lon"]), float(e["lat"]))
        for e in elements
        if e.get("type") == "node" and "lon" in e and "lat" in e
    }
    projected: dict[int, tuple[float, float]] = {}
    edge_rows: list[dict] = []
    node_rows: dict[str, dict] = {}
    eligible_way_ids: set[str] = set()

    def xy(osm_node_id: int) -> tuple[float, float]:
        if osm_node_id not in projected:
            lon, lat = osm_nodes[osm_node_id]
            projected[osm_node_id] = to_metric.transform(lon, lat)
        return projected[osm_node_id]

    for element in elements:
        if element.get("type") != "way":
            continue
        tags = dict(element.get("tags") or {})
        if "highway" not in tags:
            continue
        row = {"highway": tags.get("highway"), **tags}
        eligible, uncertainty, access_basis = bus_eligibility(row)
        if not eligible:
            continue
        way_id = str(int(element["id"]))
        eligible_way_ids.add(way_id)
        highway = str(tags.get("highway"))
        speed_kmh, speed_status = parse_speed_kmh(tags, highway)
        direction, oneway_uncertainty, oneway_basis = oneway_direction(tags)
        flags = list(uncertainty)
        if oneway_uncertainty:
            flags.append(oneway_uncertainty)
        ids = [int(v) for v in element.get("nodes", []) if int(v) in osm_nodes]
        for segment_index, (a_osm, b_osm) in enumerate(zip(ids[:-1], ids[1:])):
            a_xy, b_xy = xy(a_osm), xy(b_osm)
            if not segment_in_bounds(a_xy, b_xy, bounds):
                continue
            a_id, b_id = node_id(*a_xy), node_id(*b_xy)
            if a_id == b_id:
                continue
            length_m = math.hypot(b_xy[0] - a_xy[0], b_xy[1] - a_xy[1])
            if length_m <= 0:
                continue
            minutes = length_m / (speed_kmh * 1000.0 / 60.0)
            for graph_u, graph_v, suffix in (
                [(a_id, b_id, "F")] if direction == 1 else
                [(b_id, a_id, "R")] if direction == -1 else
                [(a_id, b_id, "F"), (b_id, a_id, "R")]
            ):
                edge_rows.append({
                    "edge_id": f"osm:{way_id}:{segment_index}:{suffix}",
                    "u_node_id": graph_u,
                    "v_node_id": graph_v,
                    "osm_way_id": way_id,
                    "length_m": length_m,
                    "running_minutes_model": minutes,
                    "highway": highway,
                    "speed_kmh": speed_kmh,
                    "speed_status": speed_status,
                    "access_basis": access_basis,
                    "oneway_basis": oneway_basis,
                    "uncertainty_flags": "|".join(sorted(set(flags))),
                })
            for osm_id, nid, coords in [(a_osm, a_id, a_xy), (b_osm, b_id, b_xy)]:
                lon, lat = osm_nodes[osm_id]
                candidate = {"node_id": nid, "x": coords[0], "y": coords[1], "lon": lon, "lat": lat, "osm_node_id": str(osm_id)}
                old = node_rows.get(nid)
                if old is not None and (abs(old["x"] - coords[0]) > 0.02 or abs(old["y"] - coords[1]) > 0.02):
                    raise AssertionError(f"projected graph-node rounding collision: {nid}")
                node_rows[nid] = candidate

    edges = pd.DataFrame(edge_rows)
    if edges.empty:
        raise AssertionError("no bus-eligible graph edges inside adaptive envelope")
    if edges["edge_id"].duplicated().any():
        raise AssertionError("non-unique deterministic edge_id")
    edges = edges.sort_values(["u_node_id", "v_node_id", "osm_way_id", "edge_id"], kind="mergesort").reset_index(drop=True)
    nodes = pd.DataFrame(node_rows.values()).sort_values("node_id", kind="mergesort").reset_index(drop=True)
    graph_node_ids = set(nodes["node_id"].astype(str))

    rule_rows: list[dict] = []
    via_way_count = 0
    bus_exempt_count = 0
    for rel in elements:
        tags = dict(rel.get("tags") or {})
        if rel.get("type") != "relation" or tags.get("type") != "restriction":
            continue
        members = rel.get("members", [])
        by_role = {m.get("role"): m for m in members if m.get("role") in {"from", "via", "to"}}
        from_m, via_m, to_m = by_role.get("from", {}), by_role.get("via", {}), by_role.get("to", {})
        restriction = str(tags.get("restriction") or "").strip().lower()
        if not restriction or not (restriction.startswith("no_") or restriction.startswith("only_")):
            continue
        if split_except(tags.get("except")) & BUS_EXCEPTIONS:
            bus_exempt_count += 1
            continue
        if via_m.get("type") != "node":
            via_way_count += int(via_m.get("type") == "way")
            continue
        try:
            via_osm = int(via_m.get("ref"))
        except (TypeError, ValueError):
            continue
        if via_osm not in osm_nodes:
            continue
        via_xy = xy(via_osm)
        via_node = node_id(*via_xy)
        rule_rows.append({
            "relation_id": str(rel.get("id")),
            "restriction": restriction,
            "from_osm_way_id": str(from_m.get("ref", "")),
            "via_node_id": via_node,
            "via_osm_node_id": str(via_osm),
            "to_osm_way_id": str(to_m.get("ref", "")),
            "via_node_in_graph": str(via_node in graph_node_ids).lower(),
            "epistemic_status": "FACT_OSM_OBSERVATION",
            "epoch_id": f"rt017-{OSM_SNAPSHOT_TIMESTAMP}",
        })
    columns = ["relation_id", "restriction", "from_osm_way_id", "via_node_id", "via_osm_node_id", "to_osm_way_id", "via_node_in_graph", "epistemic_status", "epoch_id"]
    rules = pd.DataFrame(rule_rows, columns=columns)
    if not rules.empty:
        rules = rules.sort_values(["relation_id", "from_osm_way_id", "to_osm_way_id"], kind="mergesort").reset_index(drop=True)
    metadata = {
        "osm_elements": len(elements),
        "osm_nodes_available": len(osm_nodes),
        "bus_eligible_way_count_before_segment_clip": len(eligible_way_ids),
        "graph_nodes": len(nodes),
        "directed_edges": len(edges),
        "bus_applicable_via_node_rules_observed": len(rules),
        "rules_with_via_node_in_graph": int(rules["via_node_in_graph"].eq("true").sum()) if not rules.empty else 0,
        "bus_exempt_restrictions_skipped": bus_exempt_count,
        "via_way_restrictions_not_approximated": via_way_count,
    }
    return nodes, edges, rules, metadata


def snap_probes(stops: pd.DataFrame, nodes: pd.DataFrame, to_metric: Transformer) -> pd.DataFrame:
    coords = nodes[["x", "y"]].astype(float).to_numpy()
    tree = cKDTree(coords)
    rows = []
    for row in stops.itertuples(index=False):
        x, y = to_metric.transform(float(row.lon), float(row.lat))
        distance, index = tree.query([x, y], k=1)
        node = nodes.iloc[int(index)]
        rows.append({
            "routing_terminal_id": f"STOP_PROBE::{row.stop_place_id}",
            "stop_place_id": str(row.stop_place_id),
            "stop_name": str(row.stop_name),
            "probe_x": x,
            "probe_y": y,
            "graph_node_id": str(node.node_id),
            "snap_distance_m": float(distance),
        })
    result = pd.DataFrame(rows).sort_values("routing_terminal_id", kind="mergesort").reset_index(drop=True)
    if len(result) != EXPECTED_STOP_COUNT or result["routing_terminal_id"].duplicated().any():
        raise AssertionError("frozen stop probe universe changed")
    if float(result["snap_distance_m"].max()) > MAX_SNAP_M:
        raise AssertionError(f"routing probe snap exceeds {MAX_SNAP_M} m")
    return result


def path_nodes(source_node: str, edge_ids: list[str], edge_lookup: dict[str, tuple[str, str]]) -> list[str]:
    cursor = str(source_node)
    nodes = [cursor]
    for edge_id in edge_ids:
        u, v = edge_lookup[str(edge_id)]
        if u != cursor:
            raise AssertionError(f"non-contiguous routed edge sequence at {edge_id}")
        nodes.append(v)
        cursor = v
    return nodes


def route_all_pairs(manifest: pd.DataFrame, probes: pd.DataFrame, nodes: pd.DataFrame, edges: pd.DataFrame, rules: pd.DataFrame, bounds) -> pd.DataFrame:
    adjacency = build_adjacency(edges)
    rule_index = build_turn_rule_index(rules)
    terminal_node = dict(zip(probes["routing_terminal_id"], probes["graph_node_id"]))
    node_xy = {str(r.node_id): (float(r.x), float(r.y)) for r in nodes.itertuples(index=False)}
    edge_uv = {str(r.edge_id): (str(r.u_node_id), str(r.v_node_id)) for r in edges.itertuples(index=False)}
    rows: list[dict] = []
    manifest_by_source = {str(k): g.copy() for k, g in manifest.groupby("source_routing_terminal_id", sort=True)}
    for source_terminal in sorted(manifest_by_source):
        source_node = terminal_node[source_terminal]
        group = manifest_by_source[source_terminal]
        target_nodes = {terminal_node[str(v)] for v in group["target_routing_terminal_id"]}
        routed = restriction_aware_one_to_many(adjacency, rule_index, source_node, target_nodes)
        for pair in group.itertuples(index=False):
            target_terminal = str(pair.target_routing_terminal_id)
            target_node = terminal_node[target_terminal]
            result = routed.get(target_node)
            base = {
                "pair_id": str(pair.pair_id),
                "source_routing_terminal_id": source_terminal,
                "target_routing_terminal_id": target_terminal,
                "source_graph_node_id": source_node,
                "target_graph_node_id": target_node,
            }
            if result is None:
                rows.append({**base, "route_found": False, "path_edge_ids": "", "path_node_ids": "", "path_geometry_sha256": "", "running_minutes_model": "", "distance_m": "", "boundary_clearance_m": "", "boundary_sensitive": False})
                continue
            edge_ids = [str(v) for v in result["edge_ids"]]
            pnodes = path_nodes(source_node, edge_ids, edge_uv)
            if pnodes[-1] != target_node:
                raise AssertionError("routed path does not end at requested target")
            coords = [node_xy[n] for n in pnodes]
            geometry_digest = sha256_bytes(canonical_json_bytes([[round(x, 2), round(y, 2)] for x, y in coords]))
            clearance = boundary_clearance_m(coords, bounds)
            rows.append({
                **base,
                "route_found": True,
                "path_edge_ids": ";".join(edge_ids),
                "path_node_ids": ";".join(pnodes),
                "path_geometry_sha256": geometry_digest,
                "running_minutes_model": float(result["running_minutes_model"]),
                "distance_m": float(result["distance_m"]),
                "boundary_clearance_m": clearance,
                "boundary_sensitive": clearance <= BOUNDARY_GUARD_M,
            })
    frame = pd.DataFrame(rows).sort_values(["source_routing_terminal_id", "target_routing_terminal_id"], kind="mergesort").reset_index(drop=True)
    completion = audit_pair_execution_completeness(manifest, frame)
    if not completion["complete"]:
        raise AssertionError(f"RT-010 execution manifest incomplete: {completion}")
    return frame


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stops", type=Path, default=DEFAULT_STOPS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--max-levels", type=int, default=7)
    args = parser.parse_args()
    out = args.output_dir
    out.mkdir(parents=True, exist_ok=True)

    if not args.stops.exists():
        raise FileNotFoundError(args.stops)
    if git_blob_sha1(args.stops) != EXPECTED_STOP_BLOB_SHA1:
        raise AssertionError("36-stop frozen dependency changed byte-for-byte")
    stops = pd.read_csv(args.stops)
    required_stop_cols = {"stop_place_id", "stop_name", "lat", "lon"}
    if required_stop_cols - set(stops.columns) or len(stops) != EXPECTED_STOP_COUNT:
        raise AssertionError("36-stop frozen dependency schema/count changed")

    to_metric = Transformer.from_crs(4326, 32632, always_xy=True)
    to_wgs = Transformer.from_crs(32632, 4326, always_xy=True)
    stop_xy = [to_metric.transform(float(r.lon), float(r.lat)) for r in stops.itertuples(index=False)]
    levels = derive_levels(stop_xy, max_levels=args.max_levels)

    terminals = pd.DataFrame({"routing_terminal_id": [f"STOP_PROBE::{v}" for v in stops["stop_place_id"].astype(str)]})
    manifest_result = build_complete_directed_pair_manifest(terminals, max_directed_pairs=5000)
    if not manifest_result["complete"]:
        raise AssertionError(manifest_result)
    pair_manifest = manifest_result["manifest"]
    if len(pair_manifest) != EXPECTED_STOP_COUNT * (EXPECTED_STOP_COUNT - 1):
        raise AssertionError("complete directed stop-probe pair oracle changed")
    pair_manifest.to_csv(out / "complete_directed_probe_pair_manifest_v3.csv", index=False)

    level_audits: list[dict] = []
    transition_audits: list[dict] = []
    pair_results_by_level: dict[int, pd.DataFrame] = {}
    graph_by_level: dict[int, tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, bytes]] = {}
    snap_by_level: dict[int, pd.DataFrame] = {}
    acquisition_rows: list[dict] = []
    frozen_level = None

    for level in levels:
        bbox_wgs = envelope_wgs_bounds(level, to_wgs)
        payload, endpoints = acquire_level_snapshot(bbox_wgs)
        raw_bytes = canonical_json_bytes(payload)
        raw_sha = sha256_bytes(raw_bytes)
        nodes, edges, rules, graph_meta = build_graph_tables(payload, level.bounds, to_metric)
        probes = snap_probes(stops, nodes, to_metric)
        pair_results = route_all_pairs(pair_manifest, probes, nodes, edges, rules, level.bounds)
        pair_results_by_level[level.level] = pair_results
        snap_by_level[level.level] = probes
        graph_by_level[level.level] = (nodes, edges, rules, raw_bytes)
        pair_results.to_csv(out / f"pair_results_level_{level.level:02d}.csv", index=False)
        probes.to_csv(out / f"probe_snaps_level_{level.level:02d}.csv", index=False)

        routable = int(pair_results["route_found"].astype(bool).sum())
        boundary_sensitive = int(pair_results.loc[pair_results["route_found"].astype(bool), "boundary_sensitive"].astype(bool).sum())
        level_row = {
            "level": level.level,
            "margin_m": level.margin_m,
            "min_x": level.min_x,
            "min_y": level.min_y,
            "max_x": level.max_x,
            "max_y": level.max_y,
            "wgs_south": bbox_wgs[0],
            "wgs_west": bbox_wgs[1],
            "wgs_north": bbox_wgs[2],
            "wgs_east": bbox_wgs[3],
            "raw_osm_sha256": raw_sha,
            "directed_pair_count": len(pair_results),
            "routable_pair_count": routable,
            "all_pairs_routable": routable == len(pair_manifest),
            "boundary_sensitive_pair_count": boundary_sensitive,
            "max_probe_snap_m": float(probes["snap_distance_m"].max()),
            **graph_meta,
        }
        level_audits.append(level_row)
        acquisition_rows.append({
            "level": level.level,
            "margin_m": level.margin_m,
            "snapshot_timestamp": OSM_SNAPSHOT_TIMESTAMP,
            "overpass_endpoints_used": "|".join(endpoints),
            "raw_osm_sha256": raw_sha,
            "canonical_element_count": len(payload["elements"]),
            "query_semantics": "ALL_HIGHWAY_WAYS_PLUS_RESTRICTION_RELATIONS_NO_MUNICIPAL_FILTER",
        })

        if level.level > 0:
            transition = compare_pair_results(pair_results_by_level[level.level - 1], pair_results)
            previous_snaps = snap_by_level[level.level - 1].set_index("routing_terminal_id")["graph_node_id"].astype(str)
            current_snaps = probes.set_index("routing_terminal_id")["graph_node_id"].astype(str)
            snap_stable = previous_snaps.equals(current_snaps)
            transition.update({
                "from_level": level.level - 1,
                "to_level": level.level,
                "snap_node_identity_stable": snap_stable,
            })
            transition["stable"] = bool(transition["stable"] and snap_stable)
            transition_audits.append(transition)

        decision = choose_smallest_converged_level(level_audits, transition_audits)
        if decision.converged:
            frozen_level = int(decision.frozen_level)
            break

    levels_df = pd.DataFrame(level_audits)
    transitions_df = pd.DataFrame(transition_audits)
    acquisitions_df = pd.DataFrame(acquisition_rows)
    levels_df.to_csv(out / "envelope_expansion_audit_v3.csv", index=False)
    transitions_df.to_csv(out / "pair_stabilization_transitions_v3.csv", index=False)
    acquisitions_df.to_csv(out / "osm_acquisition_audit_v3.csv", index=False)

    decision = choose_smallest_converged_level(level_audits, transition_audits)
    if not decision.converged or frozen_level is None:
        validation = {
            "status": "FAIL_RT017_NO_PROVEN_CONVERGENCE",
            "contract": CONTRACT,
            "baseline_commit": BASELINE_COMMIT,
            "osm_snapshot_timestamp": OSM_SNAPSHOT_TIMESTAMP,
            "levels_executed": len(level_audits),
            "reason": decision.reason,
            "stop_place_count_immutable": len(stops),
        }
        (out / "rt017_validation.json").write_bytes(canonical_json_bytes(validation))
        print(json.dumps(validation, indent=2))
        raise SystemExit("RT-017 fail-closed: adaptive road envelope did not converge")

    frozen_nodes, frozen_edges, frozen_rules, frozen_raw = graph_by_level[frozen_level]
    frozen_pairs = pair_results_by_level[frozen_level]
    write_df_gzip(out / "frozen_graph_nodes.csv.gz", frozen_nodes)
    write_df_gzip(out / "frozen_graph_edges.csv.gz", frozen_edges)
    write_df_gzip(out / "frozen_turn_rules.csv.gz", frozen_rules)
    deterministic_gzip(out / "frozen_osm_snapshot.json.gz", frozen_raw)
    frozen_pairs.to_csv(out / "frozen_pair_results_v3.csv", index=False)

    frozen_level_row = next(row for row in level_audits if int(row["level"]) == frozen_level)
    metadata = {
        "status": "PASS_RT017_ADAPTIVE_BORDER_NEUTRAL_ROAD_ENVELOPE_V3",
        "contract": CONTRACT,
        "issue": 49,
        "baseline_branch": "phase2-cross-engine-experiment-manifest-v3",
        "baseline_commit": BASELINE_COMMIT,
        "osm_snapshot_timestamp": OSM_SNAPSHOT_TIMESTAMP,
        "snapshot_semantics": "FIXED_HISTORICAL_OSM_EPOCH_ANCHORED_TO_RT015_COMMIT_TIMESTAMP",
        "municipal_boundaries_used_as_routing_rules": False,
        "municipality_allowlist": False,
        "municipality_blacklist": False,
        "stop_discovery_performed": False,
        "new_stops_created": False,
        "frozen_stop_blob_sha1": git_blob_sha1(args.stops),
        "frozen_stop_sha256": sha256_file(args.stops),
        "frozen_stop_count": len(stops),
        "probe_semantics": "ALL_36_FROZEN_STOP_PLACES_USED_ONLY_AS_ENVELOPE_STABILIZATION_PROBES_NOT_TERMINAL_SELECTION",
        "complete_directed_probe_pairs": len(pair_manifest),
        "frozen_level": frozen_level,
        "frozen_margin_m": float(frozen_level_row["margin_m"]),
        "frozen_metric_bounds": [frozen_level_row[k] for k in ["min_x", "min_y", "max_x", "max_y"]],
        "frozen_wgs84_bounds_south_west_north_east": [frozen_level_row[k] for k in ["wgs_south", "wgs_west", "wgs_north", "wgs_east"]],
        "convergence_reason": decision.reason,
        "required_successive_confirming_expansions": 2,
        "boundary_guard_m": BOUNDARY_GUARD_M,
        "all_pairs_routable_at_frozen_level": bool(frozen_level_row["all_pairs_routable"]),
        "boundary_sensitive_pairs_at_frozen_level": int(frozen_level_row["boundary_sensitive_pair_count"]),
        "turn_rules_in_frozen_graph": len(frozen_rules),
        "digests": {
            "frozen_osm_canonical_sha256": sha256_bytes(frozen_raw),
            "frozen_graph_nodes_gz_sha256": sha256_file(out / "frozen_graph_nodes.csv.gz"),
            "frozen_graph_edges_gz_sha256": sha256_file(out / "frozen_graph_edges.csv.gz"),
            "frozen_turn_rules_gz_sha256": sha256_file(out / "frozen_turn_rules.csv.gz"),
            "frozen_pair_results_sha256": sha256_file(out / "frozen_pair_results_v3.csv"),
            "directed_pair_manifest_sha256": sha256_file(out / "complete_directed_probe_pair_manifest_v3.csv"),
        },
        "claims_not_authorized": ["NETWORK_RECOMMENDATION", "TOPOLOGY_WINNER", "PRIMARY", "RUNNER_UP", "NEW_STOP_HYPOTHESIS"],
    }
    (out / "frozen_routing_envelope_metadata_v3.json").write_bytes(canonical_json_bytes(metadata))
    (out / "rt017_validation.json").write_bytes(canonical_json_bytes(metadata))
    print(json.dumps(metadata, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
