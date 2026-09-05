"""Final 36-stop operational materialization bridge for Phase 2 V3.

This module consumes the user-approved operational stop-place layer where one
row means one physical stop place and direction/roadside/operator micro-identities
are intentionally collapsed. It does not discover, conflate or propose stops.

Graph attachment is a reproducible technical binding step. It may be rerun on a
new frozen road graph (notably the future RT-017 graph) without changing stop
identity. Corridor materialization inserts only stop places whose bound graph
node is actually encountered by the ordered corridor path.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from math import isfinite
from typing import Iterable, Sequence

import pandas as pd
from pyproj import Transformer
from scipy.spatial import cKDTree

CORE_MUNICIPALITY_COUNTS = {
    "Brivio": 10,
    "Calco": 9,
    "La Valletta Brianza": 4,
    "Olgiate Molgora": 6,
    "Santa Maria Hoè": 7,
}
EXPECTED_STOP_PLACE_COUNT = 36
AUTO_ATTACHMENT_MAX_M = 75.0
REVIEW_ATTACHMENT_MAX_M = 250.0
DEFAULT_AUTOMATIC_SERVICE_CLASSES = ("CONVENTIONAL_TPL",)

STOP_REQUIRED_COLUMNS = {
    "operational_stop_no",
    "stop_place_id",
    "stop_name",
    "municipality",
    "lat",
    "lon",
    "source_families",
    "source_native_ids",
    "known_routes",
    "existence_confidence",
    "service_class",
    "notes",
}
NODE_REQUIRED_COLUMNS = {
    "node_id",
    "x_m_epsg32632",
    "y_m_epsg32632",
    "epoch_id",
}


def _require_columns(frame: pd.DataFrame, required: Iterable[str], label: str) -> None:
    missing = sorted(set(required) - set(frame.columns))
    if missing:
        raise ValueError(f"{label} missing columns: {missing}")


def _as_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def validate_final_stop_places(stop_places: pd.DataFrame) -> pd.DataFrame:
    """Validate and canonically order the frozen 36-stop operational layer."""
    _require_columns(stop_places, STOP_REQUIRED_COLUMNS, "final stop-place inventory")
    frame = stop_places.copy()

    if len(frame) != EXPECTED_STOP_PLACE_COUNT:
        raise ValueError(
            f"Final operational stop inventory must contain exactly {EXPECTED_STOP_PLACE_COUNT} rows; "
            f"got {len(frame)}"
        )

    for column in ("stop_place_id", "stop_name", "municipality", "service_class"):
        frame[column] = frame[column].astype(str).str.strip()
        if frame[column].eq("").any():
            raise ValueError(f"Blank {column} in final stop-place inventory")

    if frame["stop_place_id"].duplicated().any():
        duplicates = sorted(frame.loc[frame["stop_place_id"].duplicated(False), "stop_place_id"].unique())
        raise ValueError(f"stop_place_id must be unique: {duplicates}")

    frame["operational_stop_no"] = pd.to_numeric(frame["operational_stop_no"], errors="raise").astype(int)
    expected_numbers = set(range(1, EXPECTED_STOP_PLACE_COUNT + 1))
    if set(frame["operational_stop_no"]) != expected_numbers:
        raise ValueError("operational_stop_no must be exactly 1..36")

    frame["lat"] = pd.to_numeric(frame["lat"], errors="raise")
    frame["lon"] = pd.to_numeric(frame["lon"], errors="raise")
    if not frame["lat"].map(lambda value: isfinite(float(value)) and -90 <= float(value) <= 90).all():
        raise ValueError("Invalid latitude in final stop-place inventory")
    if not frame["lon"].map(lambda value: isfinite(float(value)) and -180 <= float(value) <= 180).all():
        raise ValueError("Invalid longitude in final stop-place inventory")

    observed_counts = Counter(frame["municipality"].astype(str))
    if dict(sorted(observed_counts.items())) != dict(sorted(CORE_MUNICIPALITY_COUNTS.items())):
        raise ValueError(
            "Final stop municipality counts changed: "
            f"observed={dict(sorted(observed_counts.items()))}, expected={CORE_MUNICIPALITY_COUNTS}"
        )

    # Stable ID, not source ordering, is canonical for downstream identity.
    return frame.sort_values("stop_place_id", kind="mergesort").reset_index(drop=True)


def _validate_graph_nodes(graph_nodes: pd.DataFrame) -> tuple[pd.DataFrame, str]:
    _require_columns(graph_nodes, NODE_REQUIRED_COLUMNS, "graph nodes")
    nodes = graph_nodes.copy()
    nodes["node_id"] = nodes["node_id"].astype(str)
    if nodes["node_id"].duplicated().any():
        raise ValueError("graph node_id must be unique")
    nodes["x_m_epsg32632"] = pd.to_numeric(nodes["x_m_epsg32632"], errors="raise")
    nodes["y_m_epsg32632"] = pd.to_numeric(nodes["y_m_epsg32632"], errors="raise")
    if not nodes["x_m_epsg32632"].map(lambda value: isfinite(float(value))).all():
        raise ValueError("Non-finite graph node x coordinate")
    if not nodes["y_m_epsg32632"].map(lambda value: isfinite(float(value))).all():
        raise ValueError("Non-finite graph node y coordinate")
    epochs = sorted(set(nodes["epoch_id"].astype(str)))
    if len(epochs) != 1 or not epochs[0]:
        raise ValueError(f"Graph nodes must expose exactly one non-empty epoch_id; got {epochs}")
    return nodes, epochs[0]


def attach_stop_places_to_graph(
    stop_places: pd.DataFrame,
    graph_nodes: pd.DataFrame,
    *,
    auto_max_m: float = AUTO_ATTACHMENT_MAX_M,
    review_max_m: float = REVIEW_ATTACHMENT_MAX_M,
    automatic_service_classes: Sequence[str] = DEFAULT_AUTOMATIC_SERVICE_CLASSES,
) -> pd.DataFrame:
    """Bind every frozen stop place to its nearest supplied bus-graph node.

    Attachment does not alter identity and never drops a stop. Distances above
    the automatic threshold remain explicit review/unresolved rows. The 75 m
    and 250 m tiers inherit the existing frozen-graph technical snap contract;
    they are not passenger-access or service-design thresholds.
    """
    if auto_max_m < 0 or review_max_m < auto_max_m:
        raise ValueError("Attachment thresholds must satisfy 0 <= auto <= review")
    stops = validate_final_stop_places(stop_places)
    nodes, graph_epoch_id = _validate_graph_nodes(graph_nodes)
    if nodes.empty:
        raise ValueError("Cannot attach stop places to an empty graph")

    allowed_classes = tuple(sorted({str(value) for value in automatic_service_classes}))
    transformer = Transformer.from_crs(4326, 32632, always_xy=True)
    stop_x, stop_y = transformer.transform(stops["lon"].tolist(), stops["lat"].tolist())
    node_xy = nodes[["x_m_epsg32632", "y_m_epsg32632"]].astype(float).to_numpy()
    tree = cKDTree(node_xy)
    distances, positions = tree.query(list(zip(stop_x, stop_y)), k=1)
    nearest_nodes = nodes.iloc[positions]["node_id"].astype(str).tolist()

    rows: list[dict[str, object]] = []
    for position, (_, stop) in enumerate(stops.iterrows()):
        distance_m = float(distances[position])
        if distance_m <= auto_max_m:
            attachment_status = "ROUTE_READY_LE_75M"
        elif distance_m <= review_max_m:
            attachment_status = "REVIEW_75_250M"
        else:
            attachment_status = "OUTSIDE_250M"
        route_ready = distance_m <= auto_max_m
        service_class_allowed = str(stop["service_class"]) in allowed_classes
        automatic = route_ready and service_class_allowed
        exclusion_reasons: list[str] = []
        if not route_ready:
            exclusion_reasons.append(attachment_status)
        if not service_class_allowed:
            exclusion_reasons.append(f"SERVICE_CLASS_{stop['service_class']}_NOT_AUTOMATIC")
        rows.append(
            {
                "stop_place_id": str(stop["stop_place_id"]),
                "operational_stop_no": int(stop["operational_stop_no"]),
                "stop_name": str(stop["stop_name"]),
                "municipality": str(stop["municipality"]),
                "lat": float(stop["lat"]),
                "lon": float(stop["lon"]),
                "service_class": str(stop["service_class"]),
                "source_families": str(stop["source_families"]),
                "source_native_ids": str(stop["source_native_ids"]),
                "known_routes": str(stop["known_routes"]),
                "existence_confidence": str(stop["existence_confidence"]),
                "graph_node_id": nearest_nodes[position],
                "attachment_distance_m": distance_m,
                "attachment_status": attachment_status,
                "route_ready": route_ready,
                "service_class_automatic": service_class_allowed,
                "automatic_materialization_eligible": automatic,
                "automatic_exclusion_reason": "ELIGIBLE" if automatic else ";".join(exclusion_reasons),
                "graph_epoch_id": graph_epoch_id,
                "attachment_semantics": "NEAREST_BUS_GRAPH_NODE_TECHNICAL_BINDING_IDENTITY_UNCHANGED",
            }
        )

    result = pd.DataFrame(rows).sort_values("stop_place_id", kind="mergesort").reset_index(drop=True)
    if len(result) != EXPECTED_STOP_PLACE_COUNT or result["stop_place_id"].duplicated().any():
        raise AssertionError("Attachment changed the frozen stop-place identity cardinality")
    return result


def materialize_stop_occurrences(
    corridor_id: str,
    path_node_ids: Sequence[str],
    attachments: pd.DataFrame,
    *,
    allowed_service_classes: Sequence[str] = DEFAULT_AUTOMATIC_SERVICE_CLASSES,
    require_route_ready: bool = True,
) -> pd.DataFrame:
    """Insert attached stop occurrences in exact directed path-node order.

    Repeated visits to a graph node intentionally create repeated occurrences of
    the same stop place, which is required for loops and out-and-back patterns.
    There is no global stop-place deduplication. Multiple distinct stop places
    bound to the same path node are emitted deterministically by stable ID.
    """
    if not str(corridor_id).strip():
        raise ValueError("corridor_id must be non-empty")
    path = [str(node) for node in path_node_ids]
    if not path:
        raise ValueError("path_node_ids must not be empty")
    required = {
        "stop_place_id",
        "stop_name",
        "municipality",
        "lat",
        "lon",
        "service_class",
        "graph_node_id",
        "route_ready",
        "attachment_status",
        "graph_epoch_id",
    }
    _require_columns(attachments, required, "stop attachments")
    if attachments["stop_place_id"].astype(str).duplicated().any():
        raise ValueError("attachments must contain one row per stop_place_id")

    allowed = {str(value) for value in allowed_service_classes}
    by_node: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in attachments.to_dict("records"):
        if require_route_ready and not _as_bool(row.get("route_ready")):
            continue
        if str(row.get("service_class", "")) not in allowed:
            continue
        by_node[str(row["graph_node_id"])].append(row)
    for node in by_node:
        by_node[node].sort(key=lambda row: str(row["stop_place_id"]))

    occurrence_by_stop: Counter[str] = Counter()
    output: list[dict[str, object]] = []
    stop_sequence = 0
    for path_position, node in enumerate(path):
        for row in by_node.get(node, []):
            stop_sequence += 1
            stop_place_id = str(row["stop_place_id"])
            occurrence_by_stop[stop_place_id] += 1
            output.append(
                {
                    "corridor_id": str(corridor_id),
                    "stop_sequence": stop_sequence,
                    "path_node_position": path_position,
                    "stop_place_id": stop_place_id,
                    "stop_occurrence_index": occurrence_by_stop[stop_place_id],
                    "stop_name": str(row["stop_name"]),
                    "municipality": str(row["municipality"]),
                    "lat": float(row["lat"]),
                    "lon": float(row["lon"]),
                    "service_class": str(row["service_class"]),
                    "graph_node_id": node,
                    "attachment_status": str(row["attachment_status"]),
                    "graph_epoch_id": str(row["graph_epoch_id"]),
                    "materialization_semantics": "EXISTING_FROZEN_STOP_PLACE_ON_EXACT_ORDERED_CORRIDOR_PATH_NODE",
                }
            )
    columns = [
        "corridor_id",
        "stop_sequence",
        "path_node_position",
        "stop_place_id",
        "stop_occurrence_index",
        "stop_name",
        "municipality",
        "lat",
        "lon",
        "service_class",
        "graph_node_id",
        "attachment_status",
        "graph_epoch_id",
        "materialization_semantics",
    ]
    return pd.DataFrame(output, columns=columns)


def summarise_stop_occurrences(occurrences: pd.DataFrame) -> dict[str, object]:
    """Return non-weighted diagnostics for an already materialized corridor."""
    if occurrences.empty:
        return {
            "stop_occurrences": 0,
            "unique_stop_places": 0,
            "municipalities_with_stop": [],
            "all_five_core_municipalities_have_stop": False,
        }
    _require_columns(
        occurrences,
        {"stop_place_id", "municipality", "stop_sequence"},
        "stop occurrences",
    )
    municipalities = sorted(set(occurrences["municipality"].astype(str)))
    return {
        "stop_occurrences": int(len(occurrences)),
        "unique_stop_places": int(occurrences["stop_place_id"].astype(str).nunique()),
        "municipalities_with_stop": municipalities,
        "all_five_core_municipalities_have_stop": set(CORE_MUNICIPALITY_COUNTS).issubset(municipalities),
    }
