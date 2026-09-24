"""Phase 2 Reduced Path Matrix V2 adapter.

The frozen Gate-D routing engine is reused without changing the V1 benchmark.
This adapter consumes the validated Stop Universe V2 and preserves the stronger
source-level epistemic lineage introduced there, including the distinction
between exact official GTFS stop records and a derived context-only GTFS
cluster centroid.
"""
from __future__ import annotations

from collections import Counter
import json
from pathlib import Path

import pandas as pd

from src.phase2_frozen_graph import EPOCH_ID, _nearest_nodes
from src.phase2_reduced_path_matrix import (
    HUB_ID,
    ROUTE_READY_SNAP_M,
    _snap_status,
    _write_csv,
    build_path_matrix,
    collapse_routing_anchors,
    load_frozen_graph_inputs,
    sha256_path,
)

STOP_UNIVERSE_V2_PERSISTED_HEAD = "a578ebc81b8534e3919a6e56a76a478f6c6d0d2f"
STOP_UNIVERSE_V2_COMPUTATIONAL_HEAD = "1efbb01e95bb6a9eb87e4e998b62fd91e34b900c"
STOP_UNIVERSE_V2_RUN_ID = 33802506823
STOP_UNIVERSE_V2_ARTIFACT_ID = 9911651930
STOP_UNIVERSE_V2_ARTIFACT_SHA256 = "25d3dbf52cb428d54a46569b7dbbf9e78dcee6fcf5ee69b9c6e928a367e0a2f9"


def _group_existing_evidence(group: pd.DataFrame) -> tuple[str, str]:
    """Return epistemic status and provenance scope for one physical cluster.

    A cluster may contain multiple official GTFS stop records. If any record is
    a context-only derived centroid, the cluster cannot be promoted to exact
    point FACT evidence. In the current validated V2 universe the context
    centroid is a singleton cluster, but the conservative rule is explicit.
    """
    statuses = sorted(set(group["epistemic_status"].astype(str)))
    scopes = sorted(set(group["source_scope"].astype(str)))
    if "ANALYSIS_ENVELOPE_GATE_D_GTFS_CLUSTER_CENTROID" in scopes:
        return (
            "DERIVED_OFFICIAL_GTFS_REFERENCE_PERIOD_CLUSTER_CENTROID",
            "|".join(scopes),
        )
    if any(not status.startswith("FACT_OFFICIAL_GTFS_") for status in statuses):
        raise ValueError(f"Unexpected existing-stop epistemic statuses: {statuses}")
    return "|".join(statuses), "|".join(scopes)


def build_source_anchor_records_v2(
    *,
    nodes: pd.DataFrame,
    frozen_anchors: pd.DataFrame,
    existing_stops: pd.DataFrame,
    proposed_stops: pd.DataFrame,
) -> pd.DataFrame:
    """Create V2 routing source anchors without inventing coordinates."""
    hub = frozen_anchors.loc[frozen_anchors["anchor_id"] == HUB_ID]
    if len(hub) != 1:
        raise ValueError(f"Expected exactly one frozen hub anchor {HUB_ID}")
    hub_row = hub.iloc[0]
    if str(hub_row["included_in_reduced_graph"]).strip().lower() != "true":
        raise ValueError("Frozen rail hub is not included in the reduced graph")

    required_existing = {
        "stop_id", "stop_name", "stop_lat", "stop_lon", "physical_cluster_id",
        "epistemic_status", "source_scope", "COMUNE",
    }
    missing = sorted(required_existing - set(existing_stops.columns))
    if missing:
        raise ValueError(f"V2 existing-stop input missing columns: {missing}")
    required_proposed = {
        "candidate_id", "lat", "lon", "epistemic_status", "physical_status",
        "candidate_status", "COMUNE", "highway", "road_uncertainty_flags",
        "source_building_population_head", "population_spatial_model",
    }
    missing = sorted(required_proposed - set(proposed_stops.columns))
    if missing:
        raise ValueError(f"V2 proposed-stop input missing columns: {missing}")

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
        "evidence_status": "FACT_FROZEN_GATE_D_RAIL_ANCHOR",
        "source_scope": "FROZEN_GATE_D_RAIL_ANCHOR",
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
    for cluster_id, group in existing.groupby("physical_cluster_id", sort=True):
        representative = group.iloc[0]
        evidence_status, source_scope = _group_existing_evidence(group)
        distance = float(representative["frozen_snap_distance_m"])
        source_rows.append({
            "source_anchor_id": f"existing:{cluster_id}",
            "source_kind": "EXISTING_PHYSICAL_STOP_CLUSTER",
            "source_record_id": str(representative["stop_id"]),
            "source_name": str(representative["stop_name"]),
            "municipality": str(representative["COMUNE"]),
            "lon": float(representative["stop_lon_num"]),
            "lat": float(representative["stop_lat_num"]),
            "graph_node_id": str(representative["frozen_graph_node_id"]),
            "snap_distance_m": distance,
            "snap_status": _snap_status(distance),
            "evidence_status": evidence_status,
            "source_scope": source_scope,
            "physical_status": "EXISTING_OFFICIAL_STOP_CLUSTER",
            "candidate_status": "NOT_PROPOSED",
            "highway": "",
            "road_uncertainty_flags": "",
        })

    proposed = proposed_stops.copy()
    if not proposed["source_building_population_head"].astype(str).eq(
        "29203ad64c3e32e6164ef6997933eb5c5ff2d5b1"
    ).all():
        raise ValueError("V2 proposed stops do not all trace to the validated building-population HEAD")
    if not proposed["population_spatial_model"].astype(str).eq(
        "DASYMETRIC_BUILDING_SECTION_INTERSECTION_V2"
    ).all():
        raise ValueError("V2 proposed stops lost building-population spatial-model lineage")

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
        if str(row.candidate_status) != "HYPOTHESIS_NOT_RECOMMENDATION":
            raise ValueError(f"Proposed stop {row.candidate_id} was promoted beyond hypothesis status")
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
            "source_scope": "STOP_UNIVERSE_V2_PROPOSED",
            "physical_status": str(row.physical_status),
            "candidate_status": str(row.candidate_status),
            "highway": str(row.highway),
            "road_uncertainty_flags": str(row.road_uncertainty_flags),
        })

    frame = pd.DataFrame(source_rows)
    if frame["source_anchor_id"].duplicated().any():
        raise ValueError("Duplicate V2 source anchor IDs")
    frame["route_ready"] = frame["snap_distance_m"].astype(float) <= ROUTE_READY_SNAP_M
    frame["epoch_id"] = EPOCH_ID
    return frame.sort_values(["source_kind", "source_anchor_id"], kind="mergesort").reset_index(drop=True)


def materialize_reduced_path_matrix_v2(
    *,
    frozen_dir: Path,
    existing_stops_path: Path,
    proposed_stops_path: Path,
    stop_universe_validation_path: Path,
    output_dir: Path,
) -> dict:
    stop_validation = json.loads(stop_universe_validation_path.read_text(encoding="utf-8"))
    if stop_validation.get("status") != "PASS_STOP_UNIVERSE_V2_BUILD":
        raise ValueError("Stop Universe V2 upstream validation is not PASS")
    if stop_validation.get("final_network_selected") is not False:
        raise ValueError("Stop Universe V2 unexpectedly selected a final network")

    nodes, edges, rules, frozen_anchors = load_frozen_graph_inputs(frozen_dir)
    existing = pd.read_csv(existing_stops_path, dtype=str)
    proposed = pd.read_csv(proposed_stops_path, dtype=str)
    source = build_source_anchor_records_v2(
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
    validation_path = output_dir / "reduced_path_matrix_v2_validation.json"

    _write_csv(routing_path, routing.to_dict("records"), list(routing.columns))
    membership_out = membership.copy()
    for col in ["lon", "lat", "snap_distance_m"]:
        membership_out[col] = membership_out[col].map(lambda value: f"{float(value):.9f}")
    membership_out["route_ready"] = membership_out["route_ready"].map(lambda value: str(bool(value)).lower())
    _write_csv(membership_path, membership_out.to_dict("records"), list(membership_out.columns))
    _write_csv(matrix_path, matrix.to_dict("records"), list(matrix.columns))

    source_counts = dict(sorted(Counter(source["source_kind"]).items()))
    snap_counts = dict(sorted(Counter(source["snap_status"]).items()))
    evidence_counts = dict(sorted(Counter(source["evidence_status"]).items()))
    scope_counts = dict(sorted(Counter(source["source_scope"]).items()))
    validation = {
        "status": "PASS_REDUCED_PATH_MATRIX_V2_BUILD",
        "contract": "PHASE2_REDUCED_STOP_PATH_MATRIX_V2",
        "epoch_id": EPOCH_ID,
        "hub_anchor_id": HUB_ID,
        "source_anchor_count": len(source),
        "source_anchor_counts": source_counts,
        "source_snap_status_counts": snap_counts,
        "source_evidence_status_counts": evidence_counts,
        "source_scope_counts": scope_counts,
        "route_ready_source_anchors": int(source["route_ready"].sum()),
        "collapsed_same_graph_node_source_anchors": int(
            (membership["collapse_reason"] == "COLLAPSED_SAME_FROZEN_GRAPH_NODE").sum()
        ),
        **path_info,
        "lineage": {
            "stop_universe_v2_persisted_head": STOP_UNIVERSE_V2_PERSISTED_HEAD,
            "stop_universe_v2_computational_head": STOP_UNIVERSE_V2_COMPUTATIONAL_HEAD,
            "stop_universe_v2_run_id": STOP_UNIVERSE_V2_RUN_ID,
            "stop_universe_v2_artifact_id": STOP_UNIVERSE_V2_ARTIFACT_ID,
            "stop_universe_v2_artifact_sha256": STOP_UNIVERSE_V2_ARTIFACT_SHA256,
            "stop_universe_validation": str(stop_universe_validation_path),
            "stop_universe_validation_sha256": sha256_path(stop_universe_validation_path),
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
            "context_gtfs_centroid_promoted_to_exact_fact_coordinate": False,
            "headway_or_timetable_selected": False,
            "budget_modified": False,
        },
        "epistemic_note": (
            "The V2 matrix makes validated Stop-Universe-V2 anchors routable on the complete frozen Gate-D epoch. "
            "It preserves the derived status of context-only GTFS cluster centroids and does not turn "
            "PROPOSED_STOP/FIELD_CHECK_PENDING into a verified physical stop."
        ),
    }
    validation_path.write_text(json.dumps(validation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return validation
