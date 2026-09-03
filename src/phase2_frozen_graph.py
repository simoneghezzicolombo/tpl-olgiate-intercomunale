"""Phase 2 frozen Gate D graph materialisation.

This module is intentionally source-closed: it consumes the exact Gate D PASS
artifact snapshot and official GTFS files already committed in the repository.
It never calls Overpass or substitutes a live OSM epoch.
"""
from __future__ import annotations

import csv
import gzip
import hashlib
import heapq
import io
import json
import math
import re
import shutil
import zipfile
from collections import Counter, defaultdict, deque
from pathlib import Path
from typing import Iterable

import geopandas as gpd
import networkx as nx
import pandas as pd
from pyproj import Transformer
from scipy.spatial import cKDTree
from shapely.geometry import LineString

GATE_D_COMPUTATIONAL_COMMIT = "7c220f7586d0f6e5cccd14a2d518be52eb1c4a55"
GATE_D_CLOSURE_HEAD = "7826b53bc4ac72cfbe93ebc7dd3ef0efe7898e1e"
GATE_D_CI_RUN = 33746091690
GATE_D_ARTIFACT_ID = 9891607118
GATE_D_ARTIFACT_ZIP_SHA256 = "6fbc06d74d5ba970bc980e4cde6234245e0753c22386f703ea313c6a4de9206a"
OSM_RAW_SHA256 = "834d5caa0bfd6e9f4a1400ef5d2f5083ed0da60ba51c0331f59fcbcb5d4b097c"
OSM_STRUCTURAL_SHA256 = "9032fa1fa2f8a22fd5cfcf81ad7366269d062cb7c27ffbfd57bfba754a1b51ce"
TURN_RESTRICTIONS_SHA256 = "6cf56e36d095af9b2612924d4210d31207d37c0f7a8dc4592c0d5b929dbda8d6"
ANCHOR_EVIDENCE_SHA256 = "c3ab598a43bfb83f31f086d6a14f29d92941969a349ef9087b5e6d87fe10b3d1"
ARRIVA_GTFS_SHA256 = "f890c393b909a40ae9500ab5acba71166cdfc5af3d42be92f55a92d92927553b"
LINEELECCO_GTFS_SHA256 = "f9b902807a2b213caea8e97c7501bdbfcbe1f3fe6d97f21f947ac2ecc6063271"
TRENORD_GTFS_SHA256 = "b4296f145b42ccb35c26085470ff4b3fd5dffe533251c0aab312312a73820ad6"
EXPECTED_NODE_COUNT = 104_071
EXPECTED_EDGE_COUNT = 199_217
EXPECTED_HIGHWAY_WAYS = 24_384
EXPECTED_BUS_ELIGIBLE_WAYS = 15_872
EXPECTED_RELATIONS_TOTAL = 575
EXPECTED_BUS_APPLICABLE_NODE_RESTRICTIONS = 566
EXPECTED_VIA_WAY_NOT_APPROXIMATED = 8
EXPECTED_MISSING_VIA_COORDS = 1
FROZEN_BBOX = (45.68, 9.31, 45.82, 9.56)  # south, west, north, east
EPOCH_ID = f"gate-d-2026-09-03-{OSM_RAW_SHA256[:12]}"

DEFAULT_SPEED_KMH = {
    "motorway": 60.0,
    "trunk": 50.0,
    "primary": 40.0,
    "secondary": 35.0,
    "tertiary": 30.0,
    "unclassified": 25.0,
    "residential": 22.0,
    "living_street": 12.0,
    "service": 15.0,
}
BUS_HIGHWAYS = set(DEFAULT_SPEED_KMH)
ACCESS_DENY = {"no", "private", "agricultural", "forestry"}
EXPLICIT_ALLOW = {"yes", "designated", "permissive"}
CONDITIONAL_ACCESS = {"destination", "customers", "delivery"}
TAG_COLUMNS = {
    "maxspeed", "oneway", "junction", "access", "bus", "psv", "lanes",
    "width", "maxwidth", "maxheight", "maxweight", "vehicle",
    "motor_vehicle", "oneway:bus", "oneway:psv",
}
SEMANTIC_COLUMNS = [
    "highway", "access", "vehicle", "motor_vehicle", "bus", "psv",
    "oneway", "oneway:bus", "oneway:psv", "junction", "maxspeed",
    "lanes", "width", "maxwidth", "maxheight", "maxweight",
]
EVIDENCE_ROUTES = {"D148", "D150", "D155", "D170", "D184", "D185"}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def deterministic_gzip_bytes(data: bytes, compresslevel: int = 9) -> bytes:
    buffer = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=buffer, compresslevel=compresslevel, mtime=0) as gz:
        gz.write(data)
    return buffer.getvalue()


def write_deterministic_gzip(path: Path, data: bytes) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = deterministic_gzip_bytes(data)
    path.write_bytes(payload)
    return sha256_bytes(payload)


def read_maybe_gzip(path: Path) -> bytes:
    data = path.read_bytes()
    return gzip.decompress(data) if path.suffix == ".gz" else data


def canonical_json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def csv_bytes(rows: Iterable[dict], fieldnames: list[str]) -> bytes:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, lineterminator="\n", extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({key: row.get(key, "") for key in fieldnames})
    return buffer.getvalue().encode("utf-8")


def parse_other_tags(value) -> dict[str, str]:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return {}
    return dict(re.findall(r'"([^\"]+)"=>"([^\"]*)"', str(value)))


def row_tags(row) -> dict[str, str]:
    tags = parse_other_tags(row.get("other_tags"))
    for key in TAG_COLUMNS:
        value = row.get(key)
        if value is not None and not (isinstance(value, float) and math.isnan(value)):
            text = str(value).strip()
            if text and text.lower() != "nan":
                tags[key] = text
    return tags


def _modal_access(tags: dict[str, str], key: str):
    raw = str(tags.get(key, "")).strip().lower()
    if not raw:
        return None, [], "absent"
    if raw in ACCESS_DENY:
        return False, [], f"{key}:{raw}"
    if raw in EXPLICIT_ALLOW:
        return True, [], f"{key}:{raw}"
    if raw in CONDITIONAL_ACCESS:
        return True, [f"conditional_{key}={raw}"], f"{key}:{raw}"
    return False, [f"unparsed_{key}={raw}"], f"{key}:{raw}"


def oneway_direction(tags: dict[str, str]) -> tuple[int, str | None, str]:
    for key in ("oneway:bus", "oneway:psv"):
        raw = str(tags.get(key, "")).strip().lower()
        if not raw:
            continue
        if raw in {"no", "0", "false"}:
            return 0, None, key
        if raw in {"yes", "1", "true"}:
            return 1, None, key
        if raw == "-1":
            return -1, None, key
        return 0, f"unparsed_{key}={raw}", key
    raw = str(tags.get("oneway", "")).strip().lower()
    if raw in {"yes", "1", "true"}:
        return 1, None, "oneway"
    if raw == "-1":
        return -1, None, "oneway"
    if raw in {"no", "0", "false", ""}:
        if not raw and str(tags.get("junction", "")).strip().lower() == "roundabout":
            return 1, None, "junction=roundabout"
        return 0, None, "oneway" if raw else "default_bidirectional"
    return 0, f"unparsed_oneway={raw}", "oneway"


def bus_eligibility(row) -> tuple[bool, list[str], str]:
    """Exact Gate D v4 modal precedence, with an audit explanation."""
    highway = str(row.get("highway") or "")
    if highway not in BUS_HIGHWAYS:
        return False, [f"highway={highway or 'missing'}"], "highway_not_bus_eligible"

    tags = row_tags(row)
    uncertainty: list[str] = []
    bus_decision, bus_notes, bus_basis = _modal_access(tags, "bus")
    uncertainty.extend(bus_notes)
    if "bus" in tags and bus_decision is False:
        return False, bus_notes or ["explicit_bus_restriction"], bus_basis
    if bus_decision is True:
        specific_allow = True
        basis = bus_basis
    else:
        psv_decision, psv_notes, psv_basis = _modal_access(tags, "psv")
        uncertainty.extend(psv_notes)
        if "psv" in tags and psv_decision is False:
            return False, psv_notes or ["explicit_psv_restriction"], psv_basis
        specific_allow = psv_decision is True
        basis = psv_basis if psv_decision is True else "generic_access"

    if not specific_allow:
        for key in ("access", "vehicle", "motor_vehicle"):
            value = str(tags.get(key, "")).strip().lower()
            if value in ACCESS_DENY:
                return False, [f"explicit_{key}_restriction"], f"{key}:{value}"
            if value in CONDITIONAL_ACCESS:
                uncertainty.append(f"conditional_{key}={value}")
                basis = f"{key}:{value}"

    for key in ("maxheight", "maxweight", "maxwidth", "width", "lanes"):
        if key not in tags:
            uncertainty.append(f"missing_{key}")
    _, oneway_uncertainty, _ = oneway_direction(tags)
    if oneway_uncertainty:
        uncertainty.append(oneway_uncertainty)
    return True, sorted(set(uncertainty)), basis


def parse_speed_kmh(tags: dict[str, str], highway: str) -> tuple[float, str]:
    raw = tags.get("maxspeed")
    if raw:
        match = re.search(r"(\d+(?:\.\d+)?)", raw)
        if match:
            speed = float(match.group(1))
            if "mph" in raw.lower():
                speed *= 1.609344
            return max(8.0, speed * 0.70), "MODEL_OUTPUT_FROM_OSM_MAXSPEED"
    return DEFAULT_SPEED_KMH[highway], "ASSUMPTION_BY_HIGHWAY_CLASS"


def endpoint_key(x: float, y: float) -> tuple[float, float]:
    return round(float(x), 2), round(float(y), 2)


def node_id(x: float, y: float) -> str:
    return f"n:{x:.2f}:{y:.2f}"


def _text(value) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return ""
    text = str(value).strip()
    return "" if text.lower() == "nan" else text


def normalize_way_id_text(value) -> str:
    """Match Gate D normalize_way_id semantics, then serialize stably."""
    text = _text(value)
    if not text:
        return ""
    try:
        return str(int(float(text)))
    except (TypeError, ValueError):
        return text


def bootstrap_sources(artifact_dir: Path, source_dir: Path) -> dict:
    """Persist the exact PASS artifact sources in deterministic compressed form."""
    raw = artifact_dir / "raw" / "osm_gate_d_context.json"
    structural = artifact_dir / "osm_gate_d_structural.geojson"
    restrictions = artifact_dir / "osm_turn_restrictions_routable.csv"
    restriction_summary = artifact_dir / "osm_turn_restrictions_summary.json"
    anchors = artifact_dir / "structural_anchor_evidence.csv"
    required = [raw, structural, restrictions, restriction_summary, anchors]
    for path in required:
        if not path.exists() or path.stat().st_size == 0:
            raise FileNotFoundError(path)

    observed = {
        "raw_osm": sha256_file(raw),
        "structural_geojson": sha256_file(structural),
        "turn_restrictions": sha256_file(restrictions),
        "anchor_evidence": sha256_file(anchors),
    }
    expected = {
        "raw_osm": OSM_RAW_SHA256,
        "structural_geojson": OSM_STRUCTURAL_SHA256,
        "turn_restrictions": TURN_RESTRICTIONS_SHA256,
        "anchor_evidence": ANCHOR_EVIDENCE_SHA256,
    }
    if observed != expected:
        raise AssertionError(f"Gate D source checksum mismatch: observed={observed} expected={expected}")

    source_dir.mkdir(parents=True, exist_ok=True)
    gzip_hashes = {
        "osm_gate_d_context.json.gz": write_deterministic_gzip(source_dir / "osm_gate_d_context.json.gz", raw.read_bytes()),
        "osm_gate_d_structural.geojson.gz": write_deterministic_gzip(source_dir / "osm_gate_d_structural.geojson.gz", structural.read_bytes()),
        "osm_turn_restrictions_routable.csv.gz": write_deterministic_gzip(source_dir / "osm_turn_restrictions_routable.csv.gz", restrictions.read_bytes()),
    }
    shutil.copyfile(restriction_summary, source_dir / "osm_turn_restrictions_summary.json")
    shutil.copyfile(anchors, source_dir / "structural_anchor_evidence.csv")

    manifest = source_manifest(gzip_hashes=gzip_hashes)
    (source_dir / "source_manifest.json").write_bytes(canonical_json_bytes(manifest))
    return manifest


def source_manifest(gzip_hashes: dict[str, str] | None = None) -> dict:
    return {
        "epoch_id": EPOCH_ID,
        "gate": "D",
        "gate_d_computational_commit": GATE_D_COMPUTATIONAL_COMMIT,
        "gate_d_closure_head": GATE_D_CLOSURE_HEAD,
        "gate_d_ci_run": GATE_D_CI_RUN,
        "gate_d_artifact_id": GATE_D_ARTIFACT_ID,
        "gate_d_artifact_zip_sha256": GATE_D_ARTIFACT_ZIP_SHA256,
        "bbox_south_west_north_east": list(FROZEN_BBOX),
        "raw_osm_sha256": OSM_RAW_SHA256,
        "structural_geojson_sha256": OSM_STRUCTURAL_SHA256,
        "turn_restrictions_sha256": TURN_RESTRICTIONS_SHA256,
        "anchor_evidence_sha256": ANCHOR_EVIDENCE_SHA256,
        "expected_highway_ways": EXPECTED_HIGHWAY_WAYS,
        "expected_bus_eligible_ways": EXPECTED_BUS_ELIGIBLE_WAYS,
        "expected_graph_nodes": EXPECTED_NODE_COUNT,
        "expected_directed_edges": EXPECTED_EDGE_COUNT,
        "source_archive_gzip_sha256": gzip_hashes or {},
        "epistemic_status": "FROZEN_DERIVATIVE_OF_GATE_D_PASS",
        "live_osm_refresh_allowed": False,
        "graph_source_role": "osm_gate_d_structural.geojson is the exact Gate D structural derivative used to build the PASS graph; raw OSM is retained for epoch provenance/checksum.",
        "structural_override_note": "Gate D structuralization of Ponte di Brivio is preserved from the validated artifact; Phase 2 does not re-interpret current OSM construction tags.",
        "refresh_policy": "Any OSM refresh creates a new epoch and requires explicit comparison/revalidation before replacing this graph.",
    }


def verify_source_dir(source_dir: Path) -> dict:
    manifest_path = source_dir / "source_manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(manifest_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("epoch_id") != EPOCH_ID or manifest.get("raw_osm_sha256") != OSM_RAW_SHA256:
        raise AssertionError("Frozen source manifest is not the Gate D PASS epoch")

    raw = read_maybe_gzip(source_dir / "osm_gate_d_context.json.gz")
    structural = read_maybe_gzip(source_dir / "osm_gate_d_structural.geojson.gz")
    restrictions = read_maybe_gzip(source_dir / "osm_turn_restrictions_routable.csv.gz")
    anchors = (source_dir / "structural_anchor_evidence.csv").read_bytes()
    checks = {
        "raw_osm": sha256_bytes(raw),
        "structural_geojson": sha256_bytes(structural),
        "turn_restrictions": sha256_bytes(restrictions),
        "anchor_evidence": sha256_bytes(anchors),
    }
    expected = {
        "raw_osm": OSM_RAW_SHA256,
        "structural_geojson": OSM_STRUCTURAL_SHA256,
        "turn_restrictions": TURN_RESTRICTIONS_SHA256,
        "anchor_evidence": ANCHOR_EVIDENCE_SHA256,
    }
    if checks != expected:
        raise AssertionError(f"Frozen source archive checksum mismatch: {checks}")
    return manifest


def load_structural_roads(source_dir: Path) -> gpd.GeoDataFrame:
    payload = read_maybe_gzip(source_dir / "osm_gate_d_structural.geojson.gz")
    return gpd.read_file(io.BytesIO(payload))


def materialize_graph(source_dir: Path, output_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    verify_source_dir(source_dir)
    roads = load_structural_roads(source_dir)
    if roads.crs is None:
        raise ValueError("Frozen Gate D structural roads have no CRS")
    roads = roads.to_crs(32632).explode(index_parts=False, ignore_index=True)
    roads = roads.assign(_stable_order=range(len(roads))).sort_values(["osm_way_id", "_stable_order"], kind="mergesort").reset_index(drop=True)

    node_xy: dict[str, tuple[float, float]] = {}
    edge_rows: list[dict] = []
    eligible_ways = 0
    denied_ways = 0
    edge_counter: Counter[tuple[int | str, int, str, str]] = Counter()

    for feature_seq, row in roads.iterrows():
        geom = row.geometry
        if not isinstance(geom, LineString) or geom.is_empty or len(geom.coords) < 2:
            continue
        eligible, uncertainty, eligibility_basis = bus_eligibility(row)
        if not eligible:
            denied_ways += 1
            continue
        eligible_ways += 1
        tags = row_tags(row)
        highway = str(row.get("highway"))
        speed_kmh, speed_status = parse_speed_kmh(tags, highway)
        direction, oneway_uncertainty, direction_source = oneway_direction(tags)
        if oneway_uncertainty and oneway_uncertainty not in uncertainty:
            uncertainty = sorted(set([*uncertainty, oneway_uncertainty]))
        osm_way_id = _text(row.get("osm_way_id"))
        coords = list(geom.coords)
        for segment_seq, (start_xy, end_xy) in enumerate(zip(coords[:-1], coords[1:]), start=1):
            start = endpoint_key(*start_xy)
            end = endpoint_key(*end_xy)
            length_m = math.hypot(end_xy[0] - start_xy[0], end_xy[1] - start_xy[1])
            if length_m <= 0:
                continue
            running_minutes = length_m / (speed_kmh * 1000.0 / 60.0)
            for direction_label, u, v, allowed in (
                ("F", start, end, direction >= 0),
                ("R", end, start, direction <= 0),
            ):
                if not allowed:
                    continue
                uid, vid = node_id(*u), node_id(*v)
                node_xy[uid] = u
                node_xy[vid] = v
                key_base = (osm_way_id, segment_seq, uid, vid)
                parallel_index = edge_counter[key_base]
                edge_counter[key_base] += 1
                edge_id = f"e:{osm_way_id}:{segment_seq}:{direction_label}:{parallel_index}:{uid}>{vid}"
                record = {
                    "edge_id": edge_id,
                    "u_node_id": uid,
                    "v_node_id": vid,
                    "osm_way_id": osm_way_id,
                    "source_feature_seq": int(feature_seq),
                    "segment_seq": int(segment_seq),
                    "direction": direction_label,
                    "direction_source": direction_source,
                    "length_m": f"{length_m:.9f}",
                    "speed_kmh_model": f"{speed_kmh:.9f}",
                    "speed_status": speed_status,
                    "running_minutes_model": f"{running_minutes:.12f}",
                    "eligibility_basis": eligibility_basis,
                    "uncertainty_flags": "|".join(uncertainty),
                    "epoch_id": EPOCH_ID,
                }
                for key in SEMANTIC_COLUMNS:
                    record[key.replace(":", "_")] = _text(tags.get(key))
                edge_rows.append(record)

    transformer = Transformer.from_crs(32632, 4326, always_xy=True)
    node_rows = []
    for nid, (x, y) in sorted(node_xy.items(), key=lambda item: item[0]):
        lon, lat = transformer.transform(x, y)
        node_rows.append({
            "node_id": nid,
            "x_m_epsg32632": f"{x:.2f}",
            "y_m_epsg32632": f"{y:.2f}",
            "lon_wgs84": f"{lon:.9f}",
            "lat_wgs84": f"{lat:.9f}",
            "epoch_id": EPOCH_ID,
        })

    edges = pd.DataFrame(edge_rows).sort_values("edge_id", kind="mergesort").reset_index(drop=True)
    nodes = pd.DataFrame(node_rows)
    if len(nodes) != EXPECTED_NODE_COUNT or len(edges) != EXPECTED_EDGE_COUNT:
        raise AssertionError(
            f"Gate D graph cardinality mismatch: nodes={len(nodes)}, edges={len(edges)}; "
            f"expected {EXPECTED_NODE_COUNT}/{EXPECTED_EDGE_COUNT}"
        )
    if eligible_ways != EXPECTED_BUS_ELIGIBLE_WAYS:
        raise AssertionError(f"Bus-eligible way count changed: {eligible_ways}")

    node_fields = list(nodes.columns)
    edge_fields = list(edges.columns)
    nodes_gz = output_dir / "graph_nodes.csv.gz"
    edges_gz = output_dir / "graph_edges.csv.gz"
    write_deterministic_gzip(nodes_gz, csv_bytes(nodes.to_dict("records"), node_fields))
    write_deterministic_gzip(edges_gz, csv_bytes(edges.to_dict("records"), edge_fields))

    graph = nx.DiGraph()
    graph.add_nodes_from(nodes["node_id"])
    graph.add_edges_from(zip(edges["u_node_id"], edges["v_node_id"]))
    weak_components = list(nx.weakly_connected_components(graph))
    strong_components = list(nx.strongly_connected_components(graph))
    directed_pairs = set(zip(edges["u_node_id"].astype(str), edges["v_node_id"].astype(str)))
    one_way_only = sum(1 for u, v in directed_pairs if (v, u) not in directed_pairs)
    metadata = {
        "epoch_id": EPOCH_ID,
        "source_osm_raw_sha256": OSM_RAW_SHA256,
        "source_structural_geojson_sha256": OSM_STRUCTURAL_SHA256,
        "graph_nodes": len(nodes),
        "graph_directed_edges": len(edges),
        "highway_ways_input": len(roads),
        "bus_eligible_ways": eligible_ways,
        "bus_denied_ways": denied_ways,
        "weak_components": len(weak_components),
        "largest_weak_component_nodes": max(map(len, weak_components)),
        "strong_components": len(strong_components),
        "largest_strong_component_nodes": max(map(len, strong_components)),
        "directed_edges_without_reverse_match": int(one_way_only),
        "graph_nodes_sha256": sha256_file(nodes_gz),
        "graph_edges_sha256": sha256_file(edges_gz),
        "distance_crs": "EPSG:32632",
        "epistemic_status": "DERIVED_FROM_FROZEN_GATE_D_PASS",
    }
    return nodes, edges, metadata


def materialize_turn_rules(source_dir: Path, nodes: pd.DataFrame, output_dir: Path) -> tuple[pd.DataFrame, dict]:
    raw = read_maybe_gzip(source_dir / "osm_turn_restrictions_routable.csv.gz")
    restrictions = pd.read_csv(io.BytesIO(raw), dtype=str)
    summary = json.loads((source_dir / "osm_turn_restrictions_summary.json").read_text(encoding="utf-8"))
    if int(summary["relations_total"]) != EXPECTED_RELATIONS_TOTAL:
        raise AssertionError("Turn-restriction relation count changed")
    if int(summary["bus_applicable_node_restrictions"]) != EXPECTED_BUS_APPLICABLE_NODE_RESTRICTIONS:
        raise AssertionError("Bus-applicable via-node restriction count changed")
    if int(summary["via_way_restrictions_not_approximated"]) != EXPECTED_VIA_WAY_NOT_APPROXIMATED:
        raise AssertionError("Via-way limitation changed")
    if int(summary["missing_via_node_coordinates"]) != EXPECTED_MISSING_VIA_COORDS:
        raise AssertionError("Missing via-node coordinate count changed")

    node_ids = set(nodes["node_id"])
    transformer = Transformer.from_crs(4326, 32632, always_xy=True)
    rows = []
    for _, row in restrictions.iterrows():
        applies = str(row.get("applies_to_bus", "")).lower() in {"true", "1", "yes"}
        via_type = str(row.get("via_type", ""))
        restriction = str(row.get("restriction", "")).strip().lower()
        if not applies or via_type != "node" or not (restriction.startswith("no_") or restriction.startswith("only_")):
            continue
        required_values = {
            "via_lon": _text(row.get("via_lon")),
            "via_lat": _text(row.get("via_lat")),
            "from_ref": normalize_way_id_text(row.get("from_ref")),
            "to_ref": normalize_way_id_text(row.get("to_ref")),
        }
        if not all(required_values.values()):
            continue
        x, y = transformer.transform(float(required_values["via_lon"]), float(required_values["via_lat"]))
        via_key = endpoint_key(x, y)
        via_node_id = node_id(*via_key)
        rows.append({
            "relation_id": normalize_way_id_text(row.get("relation_id")),
            "restriction": restriction,
            "from_osm_way_id": required_values["from_ref"],
            "via_node_id": via_node_id,
            "via_osm_node_id": normalize_way_id_text(row.get("via_ref")),
            "to_osm_way_id": required_values["to_ref"],
            "via_node_in_graph": str(via_node_id in node_ids).lower(),
            "epistemic_status": _text(row.get("epistemic_status")) or "FACT_OSM_OBSERVATION",
            "epoch_id": EPOCH_ID,
        })
    rules = pd.DataFrame(rows).sort_values(["relation_id", "from_osm_way_id", "to_osm_way_id"], kind="mergesort").reset_index(drop=True)
    distinct_keys = int(rules[["via_node_id", "from_osm_way_id"]].drop_duplicates().shape[0])
    graph_keys = int(rules.loc[rules["via_node_in_graph"] == "true", ["via_node_id", "from_osm_way_id"]].drop_duplicates().shape[0])
    if len(rules) != 564 or distinct_keys != 551 or graph_keys != 535:
        raise AssertionError(
            "Gate D loaded turn-rule structure changed: "
            f"rows={len(rules)}, keys={distinct_keys}, graph_keys={graph_keys}; expected 564/551/535"
        )
    output = output_dir / "turn_rules.csv.gz"
    write_deterministic_gzip(output, csv_bytes(rules.to_dict("records"), list(rules.columns)))
    info = {
        "bus_applicable_node_restrictions_source": EXPECTED_BUS_APPLICABLE_NODE_RESTRICTIONS,
        "rules_serialized_after_required_field_filter": len(rules),
        "distinct_rule_keys": distinct_keys,
        "rule_keys_on_graph": graph_keys,
        "via_way_restrictions_not_approximated": EXPECTED_VIA_WAY_NOT_APPROXIMATED,
        "missing_via_node_coordinates": EXPECTED_MISSING_VIA_COORDS,
        "turn_rules_sha256": sha256_file(output),
        "epistemic_status": "DERIVED_FROM_GATE_D_VALIDATED_OSM_RESTRICTIONS",
    }
    return rules, info


def _read_gtfs_table(zip_path: Path, member: str) -> pd.DataFrame:
    with zipfile.ZipFile(zip_path) as zf:
        if member not in zf.namelist():
            raise ValueError(f"{zip_path}: missing {member}")
        return pd.read_csv(zf.open(member), dtype=str)


def _route_membership(zip_path: Path) -> dict[str, set[str]]:
    routes = _read_gtfs_table(zip_path, "routes.txt")
    trips = _read_gtfs_table(zip_path, "trips.txt")
    stop_times = _read_gtfs_table(zip_path, "stop_times.txt")[["trip_id", "stop_id"]]
    short_col = "route_short_name" if "route_short_name" in routes.columns else "route_long_name"
    route_names = dict(zip(routes["route_id"], routes[short_col]))
    trip_route = dict(zip(trips["trip_id"], trips["route_id"]))
    memberships: dict[str, set[str]] = defaultdict(set)
    for trip_id, stop_id in stop_times.itertuples(index=False):
        route_id = trip_route.get(trip_id)
        route_name = route_names.get(route_id)
        if route_name:
            memberships[str(stop_id)].add(str(route_name))
    return memberships


def _nearest_nodes(nodes: pd.DataFrame, lon: list[float], lat: list[float]) -> tuple[list[str], list[float]]:
    xy = nodes[["x_m_epsg32632", "y_m_epsg32632"]].astype(float).to_numpy()
    tree = cKDTree(xy)
    transformer = Transformer.from_crs(4326, 32632, always_xy=True)
    px, py = transformer.transform(lon, lat)
    distances, positions = tree.query(list(zip(px, py)), k=1)
    ids = nodes.iloc[positions]["node_id"].tolist()
    return ids, [float(value) for value in distances]


def materialize_anchors(
    source_dir: Path,
    nodes: pd.DataFrame,
    edges: pd.DataFrame,
    output_dir: Path,
    arriva_zip: Path,
    lineelecco_zip: Path,
) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    expected_bus_gtfs = {
        arriva_zip: ARRIVA_GTFS_SHA256,
        lineelecco_zip: LINEELECCO_GTFS_SHA256,
    }
    for path, expected_sha in expected_bus_gtfs.items():
        if not path.exists() or path.stat().st_size == 0:
            raise FileNotFoundError(path)
        observed_sha = sha256_file(path)
        if observed_sha != expected_sha:
            raise AssertionError(f"GTFS checksum mismatch for {path}: {observed_sha} != {expected_sha}")

    south, west, north, east = FROZEN_BBOX
    anchor_rows = []
    feed_specs = [("ARRIVA_ADDABUS", arriva_zip), ("LINEE_LECCO", lineelecco_zip)]
    for feed_label, zip_path in feed_specs:
        stops = _read_gtfs_table(zip_path, "stops.txt")
        memberships = _route_membership(zip_path)
        stops["stop_lat_num"] = pd.to_numeric(stops["stop_lat"], errors="raise")
        stops["stop_lon_num"] = pd.to_numeric(stops["stop_lon"], errors="raise")
        selected = stops[
            stops["stop_lat_num"].between(south, north)
            & stops["stop_lon_num"].between(west, east)
        ].copy()
        for row in selected.itertuples(index=False):
            routes = sorted(memberships.get(str(row.stop_id), set()))
            anchor_rows.append({
                "anchor_id": f"gtfs:{feed_label}:{row.stop_id}",
                "anchor_class": "OFFICIAL_GTFS_BUS_STOP",
                "source_record_id": str(row.stop_id),
                "source_name": str(row.stop_name),
                "lon": float(row.stop_lon_num),
                "lat": float(row.stop_lat_num),
                "routes_serving": ";".join(routes),
                "epistemic_status": "FACT_OFFICIAL_GTFS_REFERENCE_PERIOD_STRUCTURAL",
                "source_detail": feed_label,
                "proposed_stop_status": "NOT_PROPOSED",
                "seed_precompute": False,
            })

    gate_d_anchors = pd.read_csv(source_dir / "structural_anchor_evidence.csv")
    station = gate_d_anchors[gate_d_anchors["anchor_id"].astype(str) == "FS"].copy()
    if len(station) != 1:
        raise AssertionError("Gate D PASS rail anchor FS not resolved exactly")
    r = station.iloc[0]
    if _text(r.get("source_ids")) != "S01514" or _text(r.get("source_detail")) != "Olgiate-Calco-Brivio":
        raise AssertionError("Gate D PASS rail anchor identity changed")
    anchor_rows.append({
        "anchor_id": "rail:S01514",
        "anchor_class": "OFFICIAL_RAIL_STATION",
        "source_record_id": "S01514",
        "source_name": "Olgiate-Calco-Brivio",
        "lon": float(r["lon"]),
        "lat": float(r["lat"]),
        "routes_serving": _text(r.get("official_routes_serving")) or "S8_RAIL_INTERCHANGE",
        "epistemic_status": "FACT_OFFICIAL_TRENORD_GTFS_STATION_FROZEN_GATE_D",
        "source_detail": _text(r.get("source_type")),
        "proposed_stop_status": "NOT_PROPOSED",
        "seed_precompute": True,
    })

    for row in gate_d_anchors.to_dict("records"):
        aid = str(row["anchor_id"])
        if aid == "FS":
            continue  # rail:S01514 is the exact source record, not a duplicate alias.
        anchor_rows.append({
            "anchor_id": f"gate_d:{aid}",
            "anchor_class": "GATE_D_VALIDATED_ANCHOR" if str(row["epistemic_status"]) == "FACT" else "GATE_D_DESIGN_ANCHOR_ASSUMPTION",
            "source_record_id": _text(row.get("source_ids")) or aid,
            "source_name": _text(row.get("source_detail")) or aid,
            "lon": float(row["lon"]),
            "lat": float(row["lat"]),
            "routes_serving": _text(row.get("official_routes_serving")),
            "epistemic_status": str(row["epistemic_status"]),
            "source_detail": _text(row.get("source_type")),
            "proposed_stop_status": "NOT_PROPOSED",
            "seed_precompute": True,
        })

    anchors = pd.DataFrame(anchor_rows).drop_duplicates(subset=["anchor_id"], keep="first")
    nearest_ids, distances = _nearest_nodes(nodes, anchors["lon"].tolist(), anchors["lat"].tolist())
    anchors["graph_node_id"] = nearest_ids
    anchors["snap_distance_m"] = distances
    anchors["snap_status"] = anchors["snap_distance_m"].map(
        lambda d: "ROUTE_READY_LE_75M" if d <= 75.0 else ("REVIEW_75_250M" if d <= 250.0 else "OUTSIDE_250M")
    )
    anchors["included_in_reduced_graph"] = anchors["snap_distance_m"] <= 250.0
    anchors["epoch_id"] = EPOCH_ID
    anchors = anchors.sort_values(["anchor_class", "anchor_id"], kind="mergesort").reset_index(drop=True)

    anchor_output = output_dir / "anchor_universe.csv.gz"
    anchor_records = anchors.copy()
    for col in ["lon", "lat", "snap_distance_m"]:
        anchor_records[col] = anchor_records[col].map(lambda v: f"{float(v):.9f}")
    for col in ["seed_precompute", "included_in_reduced_graph"]:
        anchor_records[col] = anchor_records[col].map(lambda v: str(bool(v)).lower())
    write_deterministic_gzip(anchor_output, csv_bytes(anchor_records.to_dict("records"), list(anchor_records.columns)))

    reduced = anchors[anchors["included_in_reduced_graph"]].copy()
    connectivity_graph = nx.Graph()
    connectivity_graph.add_nodes_from(nodes["node_id"].astype(str))
    connectivity_graph.add_edges_from(zip(edges["u_node_id"].astype(str), edges["v_node_id"].astype(str)))
    component_sets = sorted(nx.connected_components(connectivity_graph), key=lambda values: (-len(values), min(values)))
    component_rank = {node: rank for rank, values in enumerate(component_sets, start=1) for node in values}
    grouped = []
    for graph_node_id, group in reduced.groupby("graph_node_id", sort=True):
        classes = sorted(set(group["anchor_class"].astype(str)))
        ids = sorted(group["anchor_id"].astype(str))
        epistemic = sorted(set(group["epistemic_status"].astype(str)))
        grouped.append({
            "reduced_node_id": f"r:{graph_node_id}",
            "graph_node_id": graph_node_id,
            "anchor_ids": ";".join(ids),
            "anchor_classes": ";".join(classes),
            "epistemic_statuses": ";".join(epistemic),
            "contains_rail_anchor": str("rail:S01514" in ids).lower(),
            "contains_seed_anchor": str(bool(group["seed_precompute"].any())).lower(),
            "weak_component_rank": component_rank[str(graph_node_id)],
            "in_largest_weak_component": str(component_rank[str(graph_node_id)] == 1).lower(),
            "epoch_id": EPOCH_ID,
        })
    reduced_nodes = pd.DataFrame(grouped).sort_values("reduced_node_id").reset_index(drop=True)
    reduced_output = output_dir / "reduced_transfer_nodes.csv.gz"
    write_deterministic_gzip(reduced_output, csv_bytes(reduced_nodes.to_dict("records"), list(reduced_nodes.columns)))

    info = {
        "official_bus_stop_records_in_frozen_bbox": int((anchors["anchor_class"] == "OFFICIAL_GTFS_BUS_STOP").sum()),
        "gate_d_named_anchors": int(anchors["anchor_class"].str.startswith("GATE_D").sum()),
        "rail_anchors": int((anchors["anchor_class"] == "OFFICIAL_RAIL_STATION").sum()),
        "anchors_total": len(anchors),
        "anchors_route_ready_le_75m": int((anchors["snap_status"] == "ROUTE_READY_LE_75M").sum()),
        "anchors_review_75_250m": int((anchors["snap_status"] == "REVIEW_75_250M").sum()),
        "anchors_outside_250m": int((anchors["snap_status"] == "OUTSIDE_250M").sum()),
        "reduced_unique_graph_nodes": len(reduced_nodes),
        "reduced_nodes_in_largest_weak_component": int((reduced_nodes["in_largest_weak_component"] == "true").sum()),
        "reduced_nodes_outside_largest_weak_component": int((reduced_nodes["in_largest_weak_component"] != "true").sum()),
        "anchor_universe_sha256": sha256_file(anchor_output),
        "reduced_transfer_nodes_sha256": sha256_file(reduced_output),
        "proposed_stops_present": 0,
        "epistemic_note": "Gate D ASSUMPTION anchors remain labelled as assumptions; no proposed stop is created by this workstream.",
    }
    return anchors, reduced_nodes, info


def build_adjacency(edges: pd.DataFrame):
    adjacency: dict[str, list[tuple[str, float, float, str, str]]] = defaultdict(list)
    for row in edges.itertuples(index=False):
        adjacency[str(row.u_node_id)].append((
            str(row.v_node_id), float(row.length_m), float(row.running_minutes_model), str(row.osm_way_id), str(row.edge_id)
        ))
    for key in adjacency:
        adjacency[key].sort(key=lambda item: (item[0], item[3], item[4]))
    return adjacency


def build_turn_rule_index(rules: pd.DataFrame) -> dict[tuple[str, str], list[dict]]:
    index: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in rules.itertuples(index=False):
        if str(row.via_node_in_graph).lower() != "true":
            continue
        index[(str(row.via_node_id), str(row.from_osm_way_id))].append({
            "restriction": str(row.restriction),
            "to_way": str(row.to_osm_way_id),
            "relation_id": str(row.relation_id),
        })
    for key in index:
        index[key].sort(key=lambda item: (item["restriction"], item["to_way"], item["relation_id"]))
    return index


def transition_allowed(rules, via_node: str, previous_node: str | None, incoming_way: str | None, outgoing_node: str, outgoing_way: str) -> bool:
    if incoming_way is None:
        return True
    for rule in rules.get((via_node, incoming_way), []):
        kind = rule["restriction"]
        to_way = rule["to_way"]
        if kind == "no_u_turn":
            if outgoing_way == to_way and outgoing_node == previous_node:
                return False
        elif kind == "only_u_turn":
            if not (outgoing_way == to_way and outgoing_node == previous_node):
                return False
        elif kind.startswith("no_"):
            if outgoing_way == to_way:
                return False
        elif kind.startswith("only_"):
            if outgoing_way != to_way:
                return False
    return True


def restriction_aware_one_to_many(adjacency, rules, source: str, targets: set[str]) -> dict[str, dict]:
    """One stateful Dijkstra per source; stop after all requested targets settle."""
    if not targets:
        return {}
    start_state = (source, None, None)
    dist = {start_state: 0.0}
    dist_m = {start_state: 0.0}
    previous = {}
    heap = [(0.0, 0.0, source, "", "", start_state)]
    settled_targets: dict[str, tuple] = {}
    while heap and len(settled_targets) < len(targets):
        current_min, current_m, _, _, _, state = heapq.heappop(heap)
        if current_min != dist.get(state):
            continue
        node, previous_node, incoming_way = state
        if node in targets and node not in settled_targets:
            settled_targets[node] = state
        for outgoing_node, length_m, minutes, outgoing_way, edge_id in adjacency.get(node, []):
            if not transition_allowed(rules, node, previous_node, incoming_way, outgoing_node, outgoing_way):
                continue
            next_state = (outgoing_node, node, outgoing_way)
            next_min = current_min + minutes
            next_m = current_m + length_m
            old = dist.get(next_state)
            if old is None or next_min < old - 1e-12 or (abs(next_min - old) <= 1e-12 and next_m < dist_m[next_state] - 1e-9):
                dist[next_state] = next_min
                dist_m[next_state] = next_m
                previous[next_state] = (state, edge_id)
                heapq.heappush(heap, (next_min, next_m, outgoing_node, outgoing_way, edge_id, next_state))

    result = {}
    for target, state in settled_targets.items():
        edges_rev = []
        cursor = state
        while cursor != start_state:
            prev_state, edge_id = previous[cursor]
            edges_rev.append(edge_id)
            cursor = prev_state
        result[target] = {
            "running_minutes_model": dist[state],
            "distance_m": dist_m[state],
            "edge_ids": list(reversed(edges_rev)),
        }
    return result


def materialize_seed_paths(
    anchors: pd.DataFrame,
    edges: pd.DataFrame,
    rules: pd.DataFrame,
    output_dir: Path,
) -> tuple[pd.DataFrame, dict]:
    seed = anchors[(anchors["seed_precompute"]) & (anchors["included_in_reduced_graph"])].copy()
    seed = seed.sort_values("anchor_id", kind="mergesort")
    adjacency = build_adjacency(edges)
    rule_index = build_turn_rule_index(rules)
    rows = []
    by_node: dict[str, list[str]] = defaultdict(list)
    for row in seed.itertuples(index=False):
        by_node[str(row.graph_node_id)].append(str(row.anchor_id))
    unique_nodes = sorted(by_node)
    target_set = set(unique_nodes)
    source_runs = 0
    for source_node in unique_nodes:
        source_runs += 1
        routes = restriction_aware_one_to_many(adjacency, rule_index, source_node, target_set - {source_node})
        for target_node in unique_nodes:
            if target_node == source_node:
                route = {"running_minutes_model": 0.0, "distance_m": 0.0, "edge_ids": []}
            else:
                route = routes.get(target_node)
                if route is None:
                    continue
            for source_anchor in sorted(by_node[source_node]):
                for target_anchor in sorted(by_node[target_node]):
                    if source_anchor == target_anchor:
                        continue
                    rows.append({
                        "source_anchor_id": source_anchor,
                        "target_anchor_id": target_anchor,
                        "source_graph_node_id": source_node,
                        "target_graph_node_id": target_node,
                        "distance_m": f"{route['distance_m']:.6f}",
                        "running_minutes_model": f"{route['running_minutes_model']:.9f}",
                        "edge_count": len(route["edge_ids"]),
                        "path_edge_ids": ";".join(route["edge_ids"]),
                        "turn_restrictions": "ENFORCED_GATE_D_VIA_NODE",
                        "distance_status": "DERIVED_FROM_FROZEN_GATE_D_PASS",
                        "running_time_status": "MODEL_OUTPUT",
                        "epoch_id": EPOCH_ID,
                    })
    paths = pd.DataFrame(rows).sort_values(["source_anchor_id", "target_anchor_id"], kind="mergesort").reset_index(drop=True)
    out = output_dir / "reduced_transfer_seed_paths.csv.gz"
    write_deterministic_gzip(out, csv_bytes(paths.to_dict("records"), list(paths.columns)))

    asymmetry_pairs = 0
    lookup = {(r.source_anchor_id, r.target_anchor_id): float(r.distance_m) for r in paths.itertuples(index=False)}
    seen = set()
    max_diff = 0.0
    max_pair = None
    for (a, b), value in lookup.items():
        if (b, a) not in lookup or tuple(sorted((a, b))) in seen:
            continue
        seen.add(tuple(sorted((a, b))))
        diff = abs(value - lookup[(b, a)])
        if diff > 1e-6:
            asymmetry_pairs += 1
        if diff > max_diff:
            max_diff = diff
            max_pair = [a, b]
    info = {
        "seed_anchor_records": len(seed),
        "seed_unique_graph_nodes": len(unique_nodes),
        "one_to_many_dijkstra_runs": source_runs,
        "ordered_seed_path_records": len(paths),
        "directionally_asymmetric_anchor_pairs": asymmetry_pairs,
        "max_directional_distance_difference_m": max_diff,
        "max_asymmetry_anchor_pair": max_pair,
        "seed_paths_sha256": sha256_file(out),
        "cache_strategy": "ONE_RESTRICTION_AWARE_ONE_TO_MANY_DIJKSTRA_PER_UNIQUE_NEW_SOURCE_NODE; NEVER_PER_SCENARIO_LEG",
        "extension_contract": "Later proposed stops append anchors, snap to the same epoch graph and trigger only the missing source-node runs.",
    }
    return paths, info


def materialize_all(
    source_dir: Path,
    output_dir: Path,
    arriva_zip: Path,
    lineelecco_zip: Path,
) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    frozen_manifest = verify_source_dir(source_dir)
    nodes, edges, graph_info = materialize_graph(source_dir, output_dir)
    rules, restriction_info = materialize_turn_rules(source_dir, nodes, output_dir)
    anchors, reduced_nodes, anchor_info = materialize_anchors(
        source_dir, nodes, edges, output_dir, arriva_zip, lineelecco_zip
    )
    paths, path_info = materialize_seed_paths(anchors, edges, rules, output_dir)
    validation = {
        "phase": 2,
        "workstream": "FROZEN_GATE_D_GRAPH_AND_REDUCED_TRANSFER_GRAPH",
        "epoch_id": EPOCH_ID,
        "gate_d": frozen_manifest,
        "graph": graph_info,
        "turn_restrictions": restriction_info,
        "anchors": anchor_info,
        "reduced_transfer_graph": path_info,
        "prohibitions": {
            "live_overpass_used": False,
            "synthetic_coordinates_used": False,
            "np_random_used": False,
            "topology_selected": False,
            "headway_optimised": False,
        },
        "epistemic_contract": {
            "graph": "DERIVED_FROM_FROZEN_GATE_D_PASS",
            "official_gtfs_stops": "FACT_OFFICIAL_GTFS_REFERENCE_PERIOD_STRUCTURAL",
            "gate_d_assumption_anchors": "ASSUMPTION_PRESERVED_NOT_PROMOTED_TO_FACT",
            "proposed_stops": "NOT_CREATED_IN_THIS_WORKSTREAM",
        },
    }
    validation_path = output_dir / "graph_validation.json"
    validation_path.write_bytes(canonical_json_bytes(validation))
    return validation
