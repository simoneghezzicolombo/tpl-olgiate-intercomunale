from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path
from typing import Iterable

import pandas as pd

from src.phase2_complete_directed_pairs_v3 import (
    audit_pair_execution_completeness,
    build_complete_directed_pair_manifest,
)
from src.phase2_final_stop_materialization_v3 import (
    attach_stop_places_to_graph,
    validate_final_stop_places,
)
from src.phase2_restriction_aware_ksp import (
    build_restriction_aware_state_context,
    k_shortest_loopless_paths,
)

CONTRACT = "RT021_FROZEN_TERRITORIAL_CORRIDOR_CORPUS_V3"
EXPECTED_STOP_COUNT = 36
EXPECTED_CONVENTIONAL_COUNT = 35
EXPECTED_SPECIAL_COUNT = 1
EXPECTED_DIRECTED_PAIRS = EXPECTED_CONVENTIONAL_COUNT * (EXPECTED_CONVENTIONAL_COUNT - 1)
KSP_K = 3
KSP_MAX_RAW_STATE_PATHS = 20_000

STOP_PATH = Path(
    "outputs/phase2/network_design_method_audit_v3/master_stop_inventory_gpt_v3/"
    "existing_stop_places_operational_gpt_v5.csv"
)

PAIR_COLUMNS = [
    "pair_id",
    "source_routing_terminal_id",
    "target_routing_terminal_id",
    "reverse_pair_id",
    "scope",
]
CORRIDOR_COLUMNS = [
    "corridor_id",
    "pair_id",
    "source_routing_terminal_id",
    "target_routing_terminal_id",
    "source_stop_place_id",
    "target_stop_place_id",
    "source_graph_node_id",
    "target_graph_node_id",
    "corridor_rank_by_running_time",
    "running_minutes_model",
    "distance_m",
    "edge_count",
    "physical_node_count",
    "path_edge_ids",
    "path_node_ids",
    "path_geometry_sha256",
    "provenance",
    "is_exact_rt017_certified_shortest",
    "certified_shortest_physical_loopless",
    "physical_loopless",
    "tie_band_complete",
    "graph_epoch_id",
    "decision_role",
]
PAIR_STATUS_COLUMNS = [
    "pair_id",
    "source_routing_terminal_id",
    "target_routing_terminal_id",
    "source_stop_place_id",
    "target_stop_place_id",
    "source_graph_node_id",
    "target_graph_node_id",
    "status",
    "corridor_count",
    "certified_shortest_present",
    "certified_shortest_physical_loopless",
    "certified_state_path_representable",
    "certified_edge_sequence_matches_rt017",
    "certified_runtime_delta_vs_rt017_min",
    "certified_distance_delta_vs_rt017_m",
    "raw_state_paths_examined",
    "state_generator_exhausted",
    "tie_band_complete",
    "graph_epoch_id",
]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def canonical_json_bytes(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        .encode("utf-8")
        + b"\n"
    )


def canonical_csv_bytes(
    frame: pd.DataFrame,
    *,
    sort_by: Iterable[str],
    columns: list[str] | None = None,
) -> bytes:
    out = frame.copy()
    if columns is not None:
        missing = sorted(set(columns) - set(out.columns))
        if missing:
            raise ValueError(f"canonical CSV missing columns: {missing}")
        out = out[columns]
    out = out.sort_values(list(sort_by), kind="mergesort").reset_index(drop=True)
    return out.to_csv(index=False, lineterminator="\n").encode("utf-8")


def write_csv(
    path: Path,
    frame: pd.DataFrame,
    *,
    sort_by: Iterable[str],
    columns: list[str] | None = None,
) -> str:
    payload = canonical_csv_bytes(frame, sort_by=sort_by, columns=columns)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return sha256_bytes(payload)


def write_deterministic_gzip(path: Path, payload: bytes) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as zipped:
            zipped.write(payload)
    return sha256_file(path)


def graph_epoch_id(metadata: dict) -> str:
    timestamp = str(metadata["osm_snapshot_timestamp"])
    graph_digest = str(metadata["digests"]["frozen_graph_edges_gz_sha256"])
    return f"RT017::{timestamp}::{graph_digest[:16]}"


def adapt_rt017_nodes_for_rt018(nodes: pd.DataFrame, epoch_id: str) -> pd.DataFrame:
    required = {"node_id", "x", "y"}
    missing = sorted(required - set(nodes.columns))
    if missing:
        raise ValueError(f"RT-017 node table missing columns: {missing}")
    out = pd.DataFrame(
        {
            "node_id": nodes["node_id"].astype(str),
            "x_m_epsg32632": pd.to_numeric(nodes["x"], errors="raise"),
            "y_m_epsg32632": pd.to_numeric(nodes["y"], errors="raise"),
            "epoch_id": str(epoch_id),
        }
    )
    if out["node_id"].duplicated().any():
        raise ValueError("RT-017 node_id values are not unique")
    return out.sort_values("node_id", kind="mergesort").reset_index(drop=True)


def conventional_anchor_universe(attachments: pd.DataFrame) -> pd.DataFrame:
    frame = attachments.copy()
    conventional = frame[frame["service_class"].astype(str).eq("CONVENTIONAL_TPL")].copy()
    special = frame[frame["service_class"].astype(str).eq("SPECIAL_SERVICE")].copy()
    if len(frame) != EXPECTED_STOP_COUNT:
        raise AssertionError(f"attachment count changed: {len(frame)}")
    if len(conventional) != EXPECTED_CONVENTIONAL_COUNT:
        raise AssertionError(f"conventional stop count changed: {len(conventional)}")
    if len(special) != EXPECTED_SPECIAL_COUNT:
        raise AssertionError(f"special-service stop count changed: {len(special)}")
    if not conventional["route_ready"].astype(bool).all():
        blocked = conventional.loc[
            ~conventional["route_ready"].astype(bool),
            ["stop_place_id", "stop_name", "attachment_distance_m", "attachment_status"],
        ]
        raise AssertionError(
            "conventional RT-018 attachments exceed automatic threshold: "
            + blocked.to_dict("records").__repr__()
        )
    if conventional["graph_node_id"].astype(str).duplicated().any():
        collisions = conventional[
            conventional["graph_node_id"].astype(str).duplicated(keep=False)
        ][["stop_place_id", "stop_name", "graph_node_id", "attachment_distance_m"]]
        raise AssertionError(
            "distinct conventional stop places collide on one RT-017 graph node: "
            + collisions.to_dict("records").__repr__()
        )
    conventional["routing_terminal_id"] = (
        "STOP_PLACE::" + conventional["stop_place_id"].astype(str)
    )
    if conventional["routing_terminal_id"].duplicated().any():
        raise AssertionError("routing terminal identity is not unique")
    return conventional.sort_values("routing_terminal_id", kind="mergesort").reset_index(drop=True)


def build_rt021_pair_manifest(anchors: pd.DataFrame) -> pd.DataFrame:
    result = build_complete_directed_pair_manifest(
        anchors[["routing_terminal_id"]],
        max_directed_pairs=5000,
    )
    if not result["complete"]:
        raise AssertionError(result)
    manifest = result["manifest"].copy()
    if len(manifest) != EXPECTED_DIRECTED_PAIRS:
        raise AssertionError(f"directed pair count changed: {len(manifest)}")
    if int(result["unordered_pair_count"]) != 595:
        raise AssertionError(f"unordered pair count changed: {result['unordered_pair_count']}")
    return manifest[PAIR_COLUMNS].sort_values(
        ["source_routing_terminal_id", "target_routing_terminal_id"],
        kind="mergesort",
    ).reset_index(drop=True)


def _stop_id(terminal_id: str) -> str:
    prefix = "STOP_PLACE::"
    value = str(terminal_id)
    if not value.startswith(prefix) or len(value) <= len(prefix):
        raise ValueError(f"invalid RT-021 technical anchor id: {terminal_id}")
    return value[len(prefix):]


def _rt017_probe_stop_id(terminal_id: str) -> str:
    prefix = "STOP_PROBE::"
    value = str(terminal_id)
    if not value.startswith(prefix) or len(value) <= len(prefix):
        raise ValueError(f"invalid RT-017 probe id: {terminal_id}")
    return value[len(prefix):]


def rt017_reference_lookup(reference_pairs: pd.DataFrame) -> dict[tuple[str, str], dict]:
    required = {
        "source_routing_terminal_id",
        "target_routing_terminal_id",
        "source_graph_node_id",
        "target_graph_node_id",
        "route_found",
        "path_edge_ids",
        "running_minutes_model",
        "distance_m",
    }
    missing = sorted(required - set(reference_pairs.columns))
    if missing:
        raise ValueError(f"RT-017 reference pair table missing columns: {missing}")
    lookup: dict[tuple[str, str], dict] = {}
    for row in reference_pairs.to_dict("records"):
        source = _rt017_probe_stop_id(row["source_routing_terminal_id"])
        target = _rt017_probe_stop_id(row["target_routing_terminal_id"])
        key = (source, target)
        if key in lookup:
            raise ValueError(f"duplicate RT-017 probe pair: {key}")
        lookup[key] = row
    return lookup


def corridor_id(pair_id: str, edge_ids: list[str]) -> str:
    payload = f"{pair_id}|{';'.join(map(str, edge_ids))}".encode("utf-8")
    return "RT021_CORRIDOR_" + hashlib.sha256(payload).hexdigest()[:20].upper()


def path_geometry_sha256(nodes: list[str], node_xy: dict[str, tuple[float, float]]) -> str:
    coords = []
    for node in nodes:
        if str(node) not in node_xy:
            raise ValueError(f"path references unknown graph node: {node}")
        x, y = node_xy[str(node)]
        coords.append([round(float(x), 2), round(float(y), 2)])
    return sha256_bytes(canonical_json_bytes(coords))


def route_corpus(
    manifest: pd.DataFrame,
    anchors: pd.DataFrame,
    edges: pd.DataFrame,
    rules: pd.DataFrame,
    graph_nodes: pd.DataFrame,
    reference_pairs: pd.DataFrame,
    *,
    epoch_id: str,
    k: int = KSP_K,
    max_raw_state_paths: int = KSP_MAX_RAW_STATE_PATHS,
) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    if k < 2:
        raise ValueError("RT-021 alternative corridor corpus requires k >= 2")
    terminal_to_stop = dict(
        zip(anchors["routing_terminal_id"].astype(str), anchors["stop_place_id"].astype(str))
    )
    terminal_to_node = dict(
        zip(anchors["routing_terminal_id"].astype(str), anchors["graph_node_id"].astype(str))
    )
    node_xy = {
        str(row.node_id): (float(row.x), float(row.y))
        for row in graph_nodes[["node_id", "x", "y"]].itertuples(index=False)
    }
    reference = rt017_reference_lookup(reference_pairs)
    context = build_restriction_aware_state_context(edges, rules)

    corridor_rows: list[dict] = []
    pair_rows: list[dict] = []
    for pair in manifest.itertuples(index=False):
        pair_id = str(pair.pair_id)
        source_terminal = str(pair.source_routing_terminal_id)
        target_terminal = str(pair.target_routing_terminal_id)
        source_stop = terminal_to_stop[source_terminal]
        target_stop = terminal_to_stop[target_terminal]
        source_node = terminal_to_node[source_terminal]
        target_node = terminal_to_node[target_terminal]
        if source_node == target_node:
            raise AssertionError(
                f"distinct conventional anchors share RT-017 graph node: "
                f"{source_stop}->{target_stop} at {source_node}"
            )

        ref = reference.get((source_stop, target_stop))
        if ref is None:
            raise AssertionError(f"missing RT-017 reference probe pair: {source_stop}->{target_stop}")
        if str(ref["route_found"]).strip().lower() not in {"true", "1"}:
            raise AssertionError(
                f"RT-017 certified graph said conventional pair was unreachable: "
                f"{source_stop}->{target_stop}"
            )
        if str(ref["source_graph_node_id"]) != source_node or str(ref["target_graph_node_id"]) != target_node:
            raise AssertionError(
                "RT-018 reattachment drifted from RT-017 certified probe attachment: "
                f"{source_stop}->{target_stop}"
            )

        result = k_shortest_loopless_paths(
            context,
            source_node,
            target_node,
            k=k,
            max_raw_state_paths=max_raw_state_paths,
        )
        if not result["certified_shortest_present"]:
            raise AssertionError(f"KSP lost RT-017 certified reachability for {source_stop}->{target_stop}")
        if not result["certified_state_path_representable"]:
            raise AssertionError(
                f"certified path is not state-representable for {source_stop}->{target_stop}"
            )
        if not result["tie_band_complete"]:
            raise AssertionError(
                f"deterministic KSP tie band incomplete for {source_stop}->{target_stop}"
            )
        certified = result["certified_path"]
        if certified is None:
            raise AssertionError("certified_shortest_present without certified_path")
        reference_edges = [part for part in str(ref["path_edge_ids"]).split(";") if part]
        certified_edges = [str(value) for value in certified["edge_ids"]]
        edge_exact = certified_edges == reference_edges
        runtime_delta = float(certified["running_minutes_model"]) - float(ref["running_minutes_model"])
        distance_delta = float(certified["distance_m"]) - float(ref["distance_m"])
        if not edge_exact or abs(runtime_delta) > 1e-9 or abs(distance_delta) > 1e-6:
            raise AssertionError(
                "KSP certified shortest differs from frozen RT-017 pair evidence: "
                f"{source_stop}->{target_stop}, edge_exact={edge_exact}, "
                f"runtime_delta={runtime_delta}, distance_delta={distance_delta}"
            )

        paths = list(result["paths"])
        if not paths:
            raise AssertionError(
                f"no physically loopless corridor admitted for certified reachable pair "
                f"{source_stop}->{target_stop}"
            )
        seen_edge_sequences: set[tuple[str, ...]] = set()
        for path in paths:
            edge_ids = [str(value) for value in path["edge_ids"]]
            physical_nodes = [str(value) for value in path["physical_nodes"]]
            key = tuple(edge_ids)
            if key in seen_edge_sequences:
                raise AssertionError(f"duplicate corridor edge sequence within pair {pair_id}")
            seen_edge_sequences.add(key)
            if not bool(path["physical_loopless"]):
                raise AssertionError(f"physical loop survived KSP corridor filter for {pair_id}")
            is_certified = edge_ids == certified_edges
            corridor_rows.append(
                {
                    "corridor_id": corridor_id(pair_id, edge_ids),
                    "pair_id": pair_id,
                    "source_routing_terminal_id": source_terminal,
                    "target_routing_terminal_id": target_terminal,
                    "source_stop_place_id": source_stop,
                    "target_stop_place_id": target_stop,
                    "source_graph_node_id": source_node,
                    "target_graph_node_id": target_node,
                    "corridor_rank_by_running_time": int(path["rank"]),
                    "running_minutes_model": f"{float(path['running_minutes_model']):.9f}",
                    "distance_m": f"{float(path['distance_m']):.6f}",
                    "edge_count": len(edge_ids),
                    "physical_node_count": len(physical_nodes),
                    "path_edge_ids": ";".join(edge_ids),
                    "path_node_ids": ";".join(physical_nodes),
                    "path_geometry_sha256": path_geometry_sha256(physical_nodes, node_xy),
                    "provenance": str(path["provenance"]),
                    "is_exact_rt017_certified_shortest": str(is_certified).lower(),
                    "certified_shortest_physical_loopless": str(
                        bool(result["certified_shortest_physical_loopless"])
                    ).lower(),
                    "physical_loopless": "true",
                    "tie_band_complete": "true",
                    "graph_epoch_id": str(epoch_id),
                    "decision_role": "TECHNICAL_CORRIDOR_POOL_NOT_NETWORK_OR_TERMINAL_SELECTION",
                }
            )

        pair_rows.append(
            {
                "pair_id": pair_id,
                "source_routing_terminal_id": source_terminal,
                "target_routing_terminal_id": target_terminal,
                "source_stop_place_id": source_stop,
                "target_stop_place_id": target_stop,
                "source_graph_node_id": source_node,
                "target_graph_node_id": target_node,
                "status": "PASS_ROUTED_LOOPLESS_CORRIDOR_POOL",
                "corridor_count": len(paths),
                "certified_shortest_present": True,
                "certified_shortest_physical_loopless": bool(
                    result["certified_shortest_physical_loopless"]
                ),
                "certified_state_path_representable": True,
                "certified_edge_sequence_matches_rt017": edge_exact,
                "certified_runtime_delta_vs_rt017_min": f"{runtime_delta:.12f}",
                "certified_distance_delta_vs_rt017_m": f"{distance_delta:.9f}",
                "raw_state_paths_examined": int(result["raw_state_paths_examined"]),
                "state_generator_exhausted": bool(result["state_generator_exhausted"]),
                "tie_band_complete": True,
                "graph_epoch_id": str(epoch_id),
            }
        )

    corridors = pd.DataFrame(corridor_rows, columns=CORRIDOR_COLUMNS)
    pair_status = pd.DataFrame(pair_rows, columns=PAIR_STATUS_COLUMNS)
    execution = audit_pair_execution_completeness(manifest, pair_status)
    if not execution["complete"]:
        raise AssertionError(execution)
    if len(pair_status) != EXPECTED_DIRECTED_PAIRS:
        raise AssertionError(f"pair status count changed: {len(pair_status)}")
    if pair_status["corridor_count"].astype(int).lt(1).any():
        raise AssertionError("at least one directed pair has no admitted corridor")
    if corridors.empty or corridors["corridor_id"].duplicated().any():
        raise AssertionError("corridor corpus is empty or corridor_id is not unique")
    return corridors, pair_status, {"state_graph": context.stats, "pair_execution": execution}


def build_rt021(
    *,
    rt017_dir: Path,
    stops_path: Path,
    output_dir: Path,
    k: int = KSP_K,
    max_raw_state_paths: int = KSP_MAX_RAW_STATE_PATHS,
) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    metadata_path = rt017_dir / "frozen_routing_envelope_metadata_v3.json"
    nodes_path = rt017_dir / "frozen_graph_nodes.csv.gz"
    edges_path = rt017_dir / "frozen_graph_edges.csv.gz"
    rules_path = rt017_dir / "frozen_turn_rules.csv.gz"
    reference_pairs_path = rt017_dir / "frozen_pair_results_v3.csv"
    for path in [metadata_path, nodes_path, edges_path, rules_path, reference_pairs_path, stops_path]:
        if not path.exists():
            raise FileNotFoundError(path)

    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    if metadata.get("status") != "PASS_RT017_ADAPTIVE_BORDER_NEUTRAL_ROAD_ENVELOPE_V3":
        raise AssertionError("RT-021 requires certified PASS RT-017 metadata")
    expected_digests = metadata["digests"]
    actual_graph_digests = {
        "frozen_graph_nodes_gz_sha256": sha256_file(nodes_path),
        "frozen_graph_edges_gz_sha256": sha256_file(edges_path),
        "frozen_turn_rules_gz_sha256": sha256_file(rules_path),
        "frozen_pair_results_sha256": sha256_file(reference_pairs_path),
    }
    for key, actual in actual_graph_digests.items():
        expected = str(expected_digests[key])
        if actual != expected:
            raise AssertionError(f"RT-017 frozen input digest mismatch {key}: {actual} != {expected}")
    stop_sha = sha256_file(stops_path)
    if stop_sha != str(metadata["frozen_stop_sha256"]):
        raise AssertionError("frozen 36-stop dependency changed")

    stops = validate_final_stop_places(pd.read_csv(stops_path))
    nodes = pd.read_csv(nodes_path, compression="gzip")
    edges = pd.read_csv(edges_path, compression="gzip", dtype=str)
    rules = pd.read_csv(rules_path, compression="gzip", dtype=str).fillna("")
    reference_pairs = pd.read_csv(reference_pairs_path, dtype=str).fillna("")
    epoch = graph_epoch_id(metadata)
    rt018_nodes = adapt_rt017_nodes_for_rt018(nodes, epoch)
    attachments = attach_stop_places_to_graph(stops, rt018_nodes)
    anchors = conventional_anchor_universe(attachments)
    manifest = build_rt021_pair_manifest(anchors)

    corridors, pair_status, routing_audit = route_corpus(
        manifest,
        anchors,
        edges,
        rules,
        nodes,
        reference_pairs,
        epoch_id=epoch,
        k=k,
        max_raw_state_paths=max_raw_state_paths,
    )

    attachments_out = attachments.copy()
    attachments_out["route_ready"] = attachments_out["route_ready"].map(
        lambda value: str(bool(value)).lower()
    )
    attachments_out["service_class_automatic"] = attachments_out[
        "service_class_automatic"
    ].map(lambda value: str(bool(value)).lower())
    attachments_out["automatic_materialization_eligible"] = attachments_out[
        "automatic_materialization_eligible"
    ].map(lambda value: str(bool(value)).lower())
    attachment_sha = write_csv(
        output_dir / "rt021_stop_attachments_v3.csv",
        attachments_out,
        sort_by=["stop_place_id"],
    )
    manifest_sha = write_csv(
        output_dir / "rt021_complete_directed_pair_manifest_v3.csv",
        manifest,
        sort_by=["source_routing_terminal_id", "target_routing_terminal_id"],
        columns=PAIR_COLUMNS,
    )
    pair_status_sha = write_csv(
        output_dir / "rt021_pair_execution_status_v3.csv",
        pair_status,
        sort_by=["source_routing_terminal_id", "target_routing_terminal_id"],
        columns=PAIR_STATUS_COLUMNS,
    )
    corpus_bytes = canonical_csv_bytes(
        corridors,
        sort_by=["pair_id", "corridor_rank_by_running_time", "corridor_id"],
        columns=CORRIDOR_COLUMNS,
    )
    corpus_uncompressed_sha = sha256_bytes(corpus_bytes)
    corpus_gzip_sha = write_deterministic_gzip(
        output_dir / "rt021_corridor_corpus_v3.csv.gz",
        corpus_bytes,
    )

    conventional_attachment_max = float(
        pd.to_numeric(
            attachments.loc[
                attachments["service_class"].astype(str).eq("CONVENTIONAL_TPL"),
                "attachment_distance_m",
            ],
            errors="raise",
        ).max()
    )
    corridor_counts = pair_status["corridor_count"].astype(int)
    runtime_values = pd.to_numeric(corridors["running_minutes_model"], errors="raise")
    distance_values = pd.to_numeric(corridors["distance_m"], errors="raise")
    validation = {
        "status": "PASS_RT021_FROZEN_TERRITORIAL_CORRIDOR_CORPUS_V3",
        "contract": CONTRACT,
        "issue": 55,
        "graph_epoch_id": epoch,
        "rt017": {
            "status": metadata["status"],
            "osm_snapshot_timestamp": metadata["osm_snapshot_timestamp"],
            "frozen_level": metadata["frozen_level"],
            "frozen_margin_m": metadata["frozen_margin_m"],
            "input_digests": actual_graph_digests,
        },
        "stop_layer": {
            "frozen_stop_sha256": stop_sha,
            "stop_place_count": len(attachments),
            "conventional_tpl_count": int(
                attachments["service_class"].astype(str).eq("CONVENTIONAL_TPL").sum()
            ),
            "special_service_count": int(
                attachments["service_class"].astype(str).eq("SPECIAL_SERVICE").sum()
            ),
            "conventional_max_attachment_distance_m": conventional_attachment_max,
            "all_conventional_route_ready_le_75m": bool(
                attachments.loc[
                    attachments["service_class"].astype(str).eq("CONVENTIONAL_TPL"),
                    "route_ready",
                ].astype(bool).all()
            ),
            "special_service_excluded_from_pair_universe": True,
            "attachment_identity_sha256": attachment_sha,
        },
        "pair_universe": {
            "technical_anchor_semantics": (
                "35_CONVENTIONAL_STOP_PLACES_AS_PAIR_QUERY_ANCHORS_NOT_SERVICE_TERMINI"
            ),
            "directed_pair_count": len(manifest),
            "unordered_pair_count": len(manifest) // 2,
            "complete_execution_count": len(pair_status),
            "pair_manifest_sha256": manifest_sha,
            "pair_execution_status_sha256": pair_status_sha,
        },
        "corridor_corpus": {
            "generator": "RESTRICTION_AWARE_EDGE_STATE_YEN_KSP_V3",
            "k_exploration_depth": int(k),
            "k_semantics": (
                "AUDITED_TECHNICAL_EXPLORATION_DEPTH_NOT_SERVICE_RANK_OR_COMPLETENESS_CLAIM"
            ),
            "max_raw_state_paths_per_pair": int(max_raw_state_paths),
            "corridor_count": len(corridors),
            "pairs_with_1_corridor": int((corridor_counts == 1).sum()),
            "pairs_with_2_corridors": int((corridor_counts == 2).sum()),
            "pairs_with_3_corridors": int((corridor_counts == 3).sum()),
            "min_corridors_per_pair": int(corridor_counts.min()),
            "max_corridors_per_pair": int(corridor_counts.max()),
            "runtime_min_min": float(runtime_values.min()),
            "runtime_min_median": float(runtime_values.median()),
            "runtime_min_max": float(runtime_values.max()),
            "distance_m_min": float(distance_values.min()),
            "distance_m_median": float(distance_values.median()),
            "distance_m_max": float(distance_values.max()),
            "corridor_corpus_uncompressed_sha256": corpus_uncompressed_sha,
            "corridor_corpus_gzip_sha256": corpus_gzip_sha,
            "all_paths_physical_loopless": bool(
                corridors["physical_loopless"].astype(str).eq("true").all()
            ),
            "all_pair_tie_bands_complete": bool(
                pair_status["tie_band_complete"].astype(bool).all()
            ),
            "all_certified_shortest_sequences_match_rt017": bool(
                pair_status["certified_edge_sequence_matches_rt017"].astype(bool).all()
            ),
            "external_municipality_traversal": (
                "NOT_DERIVED_RT021_GRAPH_HAS_NO_MUNICIPALITY_LABEL_AND_NO_BOUNDARY_FILTER_IS_ALLOWED"
            ),
        },
        "state_graph": routing_audit["state_graph"],
        "checks": {
            "exactly_36_stop_places": len(attachments) == 36,
            "exactly_35_conventional_plus_1_special": (
                int(attachments["service_class"].astype(str).eq("CONVENTIONAL_TPL").sum()) == 35
                and int(attachments["service_class"].astype(str).eq("SPECIAL_SERVICE").sum()) == 1
            ),
            "all_35_conventional_route_ready_le_75m": conventional_attachment_max <= 75.0,
            "exactly_1190_directed_pairs": len(manifest) == EXPECTED_DIRECTED_PAIRS,
            "pair_execution_complete_no_omission": bool(
                routing_audit["pair_execution"]["complete"]
            ),
            "all_pairs_have_at_least_one_corridor": bool(corridor_counts.ge(1).all()),
            "all_ksp_tie_bands_complete": bool(
                pair_status["tie_band_complete"].astype(bool).all()
            ),
            "all_certified_paths_match_rt017": bool(
                pair_status["certified_edge_sequence_matches_rt017"].astype(bool).all()
            ),
            "all_corridors_physical_loopless": bool(
                corridors["physical_loopless"].astype(str).eq("true").all()
            ),
            "municipal_boundaries_not_used_as_routing_rules": (
                metadata.get("municipal_boundaries_used_as_routing_rules") is False
            ),
            "stop_discovery_not_performed": metadata.get("stop_discovery_performed") is False,
        },
        "claims_not_authorized": [
            "NETWORK_RECOMMENDATION",
            "TOPOLOGY_WINNER",
            "SERVICE_TERMINUS_SELECTION",
            "PRIMARY",
            "RUNNER_UP",
            "FIGURE_EIGHT_PRESCRIPTION",
            "NEW_STOP_HYPOTHESIS",
        ],
    }
    if not all(validation["checks"].values()):
        validation["status"] = "FAIL_RT021_VALIDATION_CHECK"
        (output_dir / "rt021_validation_v3.json").write_bytes(canonical_json_bytes(validation))
        raise AssertionError(validation["checks"])
    (output_dir / "rt021_validation_v3.json").write_bytes(canonical_json_bytes(validation))
    return validation


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rt017-dir", type=Path, required=True)
    parser.add_argument("--stops", type=Path, default=STOP_PATH)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--k", type=int, default=KSP_K)
    parser.add_argument("--max-raw-state-paths", type=int, default=KSP_MAX_RAW_STATE_PATHS)
    args = parser.parse_args()
    validation = build_rt021(
        rt017_dir=args.rt017_dir,
        stops_path=args.stops,
        output_dir=args.output_dir,
        k=args.k,
        max_raw_state_paths=args.max_raw_state_paths,
    )
    print(json.dumps(validation, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
