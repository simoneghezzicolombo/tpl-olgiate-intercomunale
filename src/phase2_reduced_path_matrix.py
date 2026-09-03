"""Build the Phase 2 routing-anchor universe and directed reduced path matrix.

The module joins two already validated Phase 2 workstreams:

- the source-closed frozen Gate D road graph;
- the candidate-stop universe.

It does not generate a topology, choose a stop, refresh OSM, invent demand or
certify a proposed stop physically. Proposed stops remain field-check pending.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import csv
from hashlib import sha256
import json
from pathlib import Path
from typing import Iterable

import pandas as pd

from src.phase2_frozen_graph import (
    EPOCH_ID,
    _nearest_nodes,
    build_adjacency,
    build_turn_rule_index,
    restriction_aware_one_to_many,
)


HUB_ID = "rail:S01514"
ROUTE_READY_SNAP_M = 75.0
REVIEW_SNAP_M = 250.0


def sha256_path(path: Path) -> str:
    h = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _write_csv(path: Path, rows: Iterable[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n", extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def load_frozen_graph_inputs(frozen_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    nodes = pd.read_csv(frozen_dir / "graph_nodes.csv.gz", dtype=str)
    edges = pd.read_csv(frozen_dir / "graph_edges.csv.gz", dtype=str)
    rules = pd.read_csv(frozen_dir / "turn_rules.csv.gz", dtype=str)
    anchors = pd.read_csv(frozen_dir / "anchor_universe.csv.gz", dtype=str)
    required = {
        "nodes": (nodes, {"node_id", "x_m_epsg32632", "y_m_epsg32632", "epoch_id"}),
        "edges": (edges, {"edge_id", "u_node_id", "v_node_id", "length_m", "running_minutes_model", "uncertainty_flags", "highway", "epoch_id"}),
        "rules": (rules, {"via_node_id", "from_osm_way_id", "to_osm_way_id", "via_node_in_graph", "epoch_id"}),
        "anchors": (anchors, {"anchor_id", "graph_node_id", "snap_distance_m", "included_in_reduced_graph", "epoch_id"}),
    }
    for label, (frame, columns) in required.items():
        missing = sorted(columns - set(frame.columns))
        if missing:
            raise ValueError(f"Frozen {label} input missing columns: {missing}")
        epochs = set(frame["epoch_id"].dropna().astype(str))
        if epochs != {EPOCH_ID}:
            raise ValueError(f"Frozen {label} epoch mismatch: {sorted(epochs)}")
    return nodes, edges, rules, anchors


def _snap_status(distance_m: float) -> str:
    if distance_m <= ROUTE_READY_SNAP_M:
        return "ROUTE_READY_LE_75M"
    if distance_m <= REVIEW_SNAP_M:
        return "REVIEW_75_250M"
    return "OUTSIDE_250M"


def build_source_anchor_records(
    *,
    nodes: pd.DataFrame,
    frozen_anchors: pd.DataFrame,
    existing_stops: pd.DataFrame,
    proposed_stops: pd.DataFrame,
) -> pd.DataFrame:
    """Create source anchors without inventing coordinates.

    Existing physical clusters use the official GTFS member with the smallest
    snap distance to the frozen graph as their deterministic representative.
    Proposed stops retain their audited candidate coordinates.
    """
    hub = frozen_anchors.loc[frozen_anchors["anchor_id"] == HUB_ID]
    if len(hub) != 1:
        raise ValueError(f"Expected exactly one frozen hub anchor {HUB_ID}")
    hub_row = hub.iloc[0]
    if str(hub_row["included_in_reduced_graph"]).strip().lower() != "true":
        raise ValueError("Frozen rail hub is not included in the reduced graph")

    required_existing = {
        "stop_id", "stop_name", "stop_lat", "stop_lon", "physical_cluster_id",
        "epistemic_status", "COMUNE",
    }
    missing = sorted(required_existing - set(existing_stops.columns))
    if missing:
        raise ValueError(f"Existing-stop input missing columns: {missing}")
    required_proposed = {
        "candidate_id", "lat", "lon", "epistemic_status", "physical_status",
        "candidate_status", "COMUNE", "highway", "road_uncertainty_flags",
    }
    missing = sorted(required_proposed - set(proposed_stops.columns))
    if missing:
        raise ValueError(f"Proposed-stop input missing columns: {missing}")

    source_rows: list[dict] = [{
        "source_anchor_id": HUB_ID,
        "source_kind": "HUB_RAIL",
        "source_record_id": "S01514",
        "source_name": "Olgiate-Calco-Brivio",
        "municipality": "Olgiate Molgora",
        "lon": float(hub_row["lon"]),
        "lat": float(hub_row["lat"]),
        "graph_node_id": str(hub_row["graph_node_id"]),
        "snap_distance_m": float(hub_row["snap_distance_m"]),
        "snap_status": _snap_status(float(hub_row["snap_distance_m"])),
        "evidence_status": "FACT",
        "physical_status": "OFFICIAL_RAIL_STATION",
        "candidate_status": "NOT_PROPOSED",
        "highway": "",
        "road_uncertainty_flags": "",
    }]

    existing = existing_stops.copy()
    existing["stop_lat_num"] = pd.to_numeric(existing["stop_lat"], errors="raise")
    existing["stop_lon_num"] = pd.to_numeric(existing["stop_lon"], errors="raise")
    nearest_ids, distances = _nearest_nodes(
        nodes,
        existing["stop_lon_num"].tolist(),
        existing["stop_lat_num"].tolist(),
    )
    existing["frozen_graph_node_id"] = nearest_ids
    existing["frozen_snap_distance_m"] = distances
    existing["stop_id_sort"] = existing["stop_id"].astype(str)
    existing = existing.sort_values(
        ["physical_cluster_id", "frozen_snap_distance_m", "stop_id_sort"],
        kind="mergesort",
    )
    representatives = existing.groupby("physical_cluster_id", sort=True, as_index=False).first()
    for row in representatives.itertuples(index=False):
        distance = float(row.frozen_snap_distance_m)
        source_rows.append({
            "source_anchor_id": f"existing:{row.physical_cluster_id}",
            "source_kind": "EXISTING_PHYSICAL_STOP_CLUSTER",
            "source_record_id": str(row.stop_id),
            "source_name": str(row.stop_name),
            "municipality": str(row.COMUNE),
            "lon": float(row.stop_lon_num),
            "lat": float(row.stop_lat_num),
            "graph_node_id": str(row.frozen_graph_node_id),
            "snap_distance_m": distance,
            "snap_status": _snap_status(distance),
            "evidence_status": "FACT",
            "physical_status": "EXISTING_OFFICIAL_STOP_CLUSTER",
            "candidate_status": "NOT_PROPOSED",
            "highway": "",
            "road_uncertainty_flags": "",
        })

    proposed = proposed_stops.copy()
    proposed["lat_num"] = pd.to_numeric(proposed["lat"], errors="raise")
    proposed["lon_num"] = pd.to_numeric(proposed["lon"], errors="raise")
    nearest_ids, distances = _nearest_nodes(
        nodes,
        proposed["lon_num"].tolist(),
        proposed["lat_num"].tolist(),
    )
    proposed["frozen_graph_node_id"] = nearest_ids
    proposed["frozen_snap_distance_m"] = distances
    for row in proposed.sort_values("candidate_id", kind="mergesort").itertuples(index=False):
        if str(row.epistemic_status) != "PROPOSED_STOP/FIELD_CHECK_PENDING":
            raise ValueError(f"Proposed stop {row.candidate_id} lost field-check epistemic status")
        if str(row.physical_status) != "FIELD_CHECK_PENDING":
            raise ValueError(f"Proposed stop {row.candidate_id} lost physical field-check status")
        distance = float(row.frozen_snap_distance_m)
        source_rows.append({
            "source_anchor_id": str(row.candidate_id),
            "source_kind": "PROPOSED_STOP",
            "source_record_id": str(row.candidate_id),
            "source_name": str(row.candidate_id),
            "municipality": str(row.COMUNE),
            "lon": float(row.lon_num),
            "lat": float(row.lat_num),
            "graph_node_id": str(row.frozen_graph_node_id),
            "snap_distance_m": distance,
            "snap_status": _snap_status(distance),
            "evidence_status": "PROPOSED_STOP/FIELD_CHECK_PENDING",
            "physical_status": str(row.physical_status),
            "candidate_status": str(row.candidate_status),
            "highway": str(row.highway),
            "road_uncertainty_flags": str(row.road_uncertainty_flags),
        })

    frame = pd.DataFrame(source_rows)
    if frame["source_anchor_id"].duplicated().any():
        raise ValueError("Duplicate source anchor IDs")
    frame["route_ready"] = frame["snap_distance_m"].astype(float) <= ROUTE_READY_SNAP_M
    frame["epoch_id"] = EPOCH_ID
    return frame.sort_values(["source_kind", "source_anchor_id"], kind="mergesort").reset_index(drop=True)


def collapse_routing_anchors(source_anchors: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Collapse exact same frozen graph nodes while preserving source membership."""
    priority = {"HUB_RAIL": 0, "EXISTING_PHYSICAL_STOP_CLUSTER": 1, "PROPOSED_STOP": 2}
    source = source_anchors.copy()
    source["routing_anchor_id"] = ""
    source["collapse_reason"] = "NOT_ROUTE_READY"
    route_ready = source[source["route_ready"]].copy()
    if route_ready.empty:
        raise ValueError("No route-ready source anchors")

    routing_rows: list[dict] = []
    for graph_node_id, group in route_ready.groupby("graph_node_id", sort=True):
        records = group.to_dict("records")
        representative = sorted(
            records,
            key=lambda row: (priority[row["source_kind"]], float(row["snap_distance_m"]), row["source_anchor_id"]),
        )[0]
        routing_id = representative["source_anchor_id"]
        member_ids = sorted(row["source_anchor_id"] for row in records)
        member_kinds = sorted(set(row["source_kind"] for row in records))
        municipalities = sorted({row["municipality"] for row in records if row["municipality"]})
        routing_rows.append({
            "anchor_id": routing_id,
            "evidence_status": representative["evidence_status"],
            "enabled": "true",
            "graph_node_id": graph_node_id,
            "source_kind": representative["source_kind"],
            "source_members": ";".join(member_ids),
            "source_member_count": len(member_ids),
            "source_member_kinds": ";".join(member_kinds),
            "municipalities": ";".join(municipalities),
            "representative_snap_distance_m": f"{float(representative['snap_distance_m']):.6f}",
            "epoch_id": EPOCH_ID,
        })
        mask = source["source_anchor_id"].isin(member_ids)
        source.loc[mask, "routing_anchor_id"] = routing_id
        source.loc[mask, "collapse_reason"] = (
            "UNIQUE_GRAPH_NODE" if len(member_ids) == 1 else "COLLAPSED_SAME_FROZEN_GRAPH_NODE"
        )

    routing = pd.DataFrame(routing_rows).sort_values("anchor_id", kind="mergesort").reset_index(drop=True)
    if HUB_ID not in set(routing["anchor_id"]):
        raise ValueError("Rail hub disappeared during routing-anchor collapse")
    return routing, source


def _path_uncertainty(edge_ids: list[str], edge_lookup: dict[str, dict]) -> tuple[str, int, int, int]:
    uncertain_edges = 0
    unknown_edges = 0
    service_edges = 0
    for edge_id in edge_ids:
        meta = edge_lookup[edge_id]
        flags = str(meta.get("uncertainty_flags", "")).strip()
        if flags:
            uncertain_edges += 1
            tokens = [token.strip().lower() for token in flags.split("|") if token.strip()]
            if any(token.startswith("conditional_") or token.startswith("unparsed_") for token in tokens):
                unknown_edges += 1
        if str(meta.get("highway", "")).strip().lower() == "service":
            service_edges += 1
    if unknown_edges:
        status = "UNKNOWN"
    elif uncertain_edges:
        status = "QUANTIFIED"
    else:
        status = "RESOLVED"
    return status, uncertain_edges, unknown_edges, service_edges


def build_path_matrix(
    *,
    routing_anchors: pd.DataFrame,
    edges: pd.DataFrame,
    rules: pd.DataFrame,
) -> tuple[pd.DataFrame, dict]:
    if routing_anchors["graph_node_id"].duplicated().any():
        raise ValueError("Routing anchors must be unique by frozen graph node")
    by_node = dict(zip(routing_anchors["graph_node_id"].astype(str), routing_anchors["anchor_id"].astype(str)))
    unique_nodes = sorted(by_node)
    adjacency = build_adjacency(edges)
    rule_index = build_turn_rule_index(rules)
    edge_lookup = {
        str(row.edge_id): {
            "uncertainty_flags": str(row.uncertainty_flags),
            "highway": str(row.highway),
        }
        for row in edges.itertuples(index=False)
    }

    rows: list[dict] = []
    source_runs = 0
    targets_all = set(unique_nodes)
    for source_node in unique_nodes:
        source_runs += 1
        routes = restriction_aware_one_to_many(
            adjacency,
            rule_index,
            source_node,
            targets_all - {source_node},
        )
        for target_node in unique_nodes:
            if target_node == source_node:
                continue
            route = routes.get(target_node)
            if route is None:
                continue
            status, uncertain_edges, unknown_edges, service_edges = _path_uncertainty(route["edge_ids"], edge_lookup)
            rows.append({
                "origin": by_node[source_node],
                "destination": by_node[target_node],
                "distance_km": f"{float(route['distance_m']) / 1000.0:.9f}",
                "runtime_min": f"{float(route['running_minutes_model']):.9f}",
                "uncertainty": status,
                "origin_graph_node_id": source_node,
                "destination_graph_node_id": target_node,
                "edge_count": len(route["edge_ids"]),
                "uncertain_edge_count": uncertain_edges,
                "unknown_access_edge_count": unknown_edges,
                "service_road_edge_count": service_edges,
                "turn_restrictions": "ENFORCED_GATE_D_VIA_NODE",
                "distance_status": "DERIVED_FROM_FROZEN_GATE_D_PASS",
                "runtime_status": "MODEL_OUTPUT",
                "epoch_id": EPOCH_ID,
            })

    matrix = pd.DataFrame(rows)
    if matrix.empty:
        raise ValueError("Reduced path matrix is empty")
    matrix = matrix.sort_values(["origin", "destination"], kind="mergesort").reset_index(drop=True)
    pair_count_possible = len(unique_nodes) * (len(unique_nodes) - 1)
    lookup = {(row.origin, row.destination): float(row.distance_km) for row in matrix.itertuples(index=False)}
    asymmetry_pairs = 0
    seen = set()
    for (a, b), value in lookup.items():
        key = tuple(sorted((a, b)))
        if key in seen or (b, a) not in lookup:
            continue
        seen.add(key)
        if abs(value - lookup[(b, a)]) > 1e-9:
            asymmetry_pairs += 1
    info = {
        "routing_anchor_count": len(routing_anchors),
        "unique_graph_node_count": len(unique_nodes),
        "one_to_many_dijkstra_runs": source_runs,
        "ordered_path_rows": len(matrix),
        "ordered_path_rows_possible": pair_count_possible,
        "path_matrix_completeness": len(matrix) / pair_count_possible if pair_count_possible else 0.0,
        "missing_ordered_pairs": pair_count_possible - len(matrix),
        "directionally_asymmetric_unordered_pairs": asymmetry_pairs,
        "uncertainty_counts": dict(sorted(Counter(matrix["uncertainty"]).items())),
        "cache_strategy": "ONE_RESTRICTION_AWARE_ONE_TO_MANY_DIJKSTRA_PER_UNIQUE_ROUTING_SOURCE_NODE",
    }
    return matrix, info


def materialize_reduced_path_matrix(
    *,
    frozen_dir: Path,
    existing_stops_path: Path,
    proposed_stops_path: Path,
    output_dir: Path,
) -> dict:
    nodes, edges, rules, frozen_anchors = load_frozen_graph_inputs(frozen_dir)
    existing = pd.read_csv(existing_stops_path, dtype=str)
    proposed = pd.read_csv(proposed_stops_path, dtype=str)
    source = build_source_anchor_records(
        nodes=nodes,
        frozen_anchors=frozen_anchors,
        existing_stops=existing,
        proposed_stops=proposed,
    )
    routing, membership = collapse_routing_anchors(source)
    matrix, path_info = build_path_matrix(routing_anchors=routing, edges=edges, rules=rules)

    output_dir.mkdir(parents=True, exist_ok=True)
    routing_path = output_dir / "routing_anchor_universe.csv"
    membership_path = output_dir / "routing_anchor_membership.csv"
    matrix_path = output_dir / "reduced_path_matrix.csv"
    validation_path = output_dir / "reduced_path_matrix_validation.json"

    _write_csv(routing_path, routing.to_dict("records"), list(routing.columns))
    membership_out = membership.copy()
    for col in ["lon", "lat", "snap_distance_m"]:
        membership_out[col] = membership_out[col].map(lambda value: f"{float(value):.9f}")
    membership_out["route_ready"] = membership_out["route_ready"].map(lambda value: str(bool(value)).lower())
    _write_csv(membership_path, membership_out.to_dict("records"), list(membership_out.columns))
    _write_csv(matrix_path, matrix.to_dict("records"), list(matrix.columns))

    source_counts = dict(sorted(Counter(source["source_kind"]).items()))
    snap_counts = dict(sorted(Counter(source["snap_status"]).items()))
    validation = {
        "status": "PASS",
        "contract": "PHASE2_REDUCED_STOP_PATH_MATRIX_V1",
        "epoch_id": EPOCH_ID,
        "hub_anchor_id": HUB_ID,
        "source_anchor_count": len(source),
        "source_anchor_counts": source_counts,
        "source_snap_status_counts": snap_counts,
        "route_ready_source_anchors": int(source["route_ready"].sum()),
        "collapsed_same_graph_node_source_anchors": int((membership["collapse_reason"] == "COLLAPSED_SAME_FROZEN_GRAPH_NODE").sum()),
        **path_info,
        "lineage": {
            "frozen_graph_validation": str(frozen_dir / "graph_validation.json"),
            "frozen_graph_validation_sha256": sha256_path(frozen_dir / "graph_validation.json"),
            "existing_stops": str(existing_stops_path),
            "existing_stops_sha256": sha256_path(existing_stops_path),
            "proposed_stops": str(proposed_stops_path),
            "proposed_stops_sha256": sha256_path(proposed_stops_path),
            "routing_anchor_universe_sha256": sha256_path(routing_path),
            "routing_anchor_membership_sha256": sha256_path(membership_path),
            "reduced_path_matrix_sha256": sha256_path(matrix_path),
        },
        "prohibitions": {
            "live_osm_used": False,
            "random_generation_used": False,
            "topology_selected": False,
            "proposed_stop_physically_certified": False,
            "headway_or_timetable_selected": False,
        },
        "epistemic_note": (
            "The path matrix makes candidate locations routable on the frozen Gate D epoch. "
            "It does not turn PROPOSED_STOP/FIELD_CHECK_PENDING into a verified physical stop."
        ),
    }
    validation_path.write_text(json.dumps(validation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return validation
