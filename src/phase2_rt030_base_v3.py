from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
from pyproj import Transformer

CONTRACT = "RT030_PASSENGER_STOP_REALIZATION_LAYER_V3"
EXPECTED_GRAPH_EPOCH = "RT017::2026-09-05T13:45:50Z::466f562f95805cb1"
SPECIAL_STOP_ID = "SPECIAL::CASA_DI_COMUNITA_OLGIATE"
PHYSICAL_SEGMENT_TIE_EPS_M = 1e-6
ROUTE_PROXIMITY_BUFFER_M = 0.0
RT023_ARTIFACT_RUN_HEAD_SHA = "0d9a82caa1d1d624e0f6945e709f3548785fb8dc"
RT023_FINAL_HEAD_SHA = "2e8baf13ea4171164bc8c4b18d4b31bee4c3003d"
RT023_FINAL_REALIZATION_CATALOG_SHA256 = "24d806b3b30cf75c91cf531746bada443bf3d5bedf3878e9587778cad7c9d36a"
RT023_PROVENANCE_COLUMNS = (
    "rt021_elementary_corridor_evidence_sha256",
    "rt018_stop_attachment_layer_sha256",
    "rt018_stop_occurrence_corpus_sha256",
)


class RT030ContractError(ValueError):
    pass


@dataclass(frozen=True)
class RT030Result:
    patterns: pd.DataFrame
    occurrences: pd.DataFrame
    stop_segment_attachments: pd.DataFrame
    diagnostics: pd.DataFrame
    audit: dict


def _required(df: pd.DataFrame, cols: Iterable[str], label: str) -> None:
    missing = sorted(set(cols) - set(df.columns))
    if missing:
        raise RT030ContractError(f"{label} missing columns: {missing}")


def _as_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y"}:
        return True
    if text in {"0", "false", "no", "n"}:
        return False
    raise RT030ContractError(f"Not boolean-like: {value!r}")


def _split(value: object) -> list[str]:
    text = str(value).strip()
    return [] if not text else [x for x in text.split(";") if x]


def _physical_segment_key(u: str, v: str) -> str:
    a, b = sorted((str(u), str(v)))
    return f"{a}|{b}"


def _physical_segment_id(u: str, v: str) -> str:
    raw = _physical_segment_key(u, v).encode("utf-8")
    return "RT030_SEG_" + hashlib.sha256(raw).hexdigest()[:20].upper()


def _canonical_csv_bytes(df: pd.DataFrame, sort_cols: list[str]) -> bytes:
    ordered = df.sort_values(sort_cols, kind="mergesort").reset_index(drop=True)
    return ordered.to_csv(index=False, lineterminator="\n", float_format="%.9f").encode("utf-8")


def _sha_df(df: pd.DataFrame, sort_cols: list[str]) -> str:
    return hashlib.sha256(_canonical_csv_bytes(df, sort_cols)).hexdigest()


def _rt023_catalog_sha(df: pd.DataFrame) -> str:
    stable = df.sort_values(
        ["structural_link_id", "direction", "alternative_ordinal", "corridor_id"],
        kind="mergesort",
    ).reset_index(drop=True)
    return hashlib.sha256(
        stable.to_csv(index=False, lineterminator="\n").encode("utf-8")
    ).hexdigest()


def reconcile_rt023_run_catalog_to_final(
    run_catalog: pd.DataFrame,
    *,
    elementary_corridors_sha256: str,
    stop_attachments_sha256: str,
    corridor_stop_occurrences_sha256: str,
) -> tuple[pd.DataFrame, dict]:
    """Reproduce the final RT-023 catalog from the certified run artifact.

    Run 34034770563 executed at 0d9a82c... and produced the 17-column
    realization catalog. Final commit 2e8baf... added only three frozen
    provenance columns. Reconstructing those columns must reproduce the exact
    final canonical hash declared by RT-023.
    """
    required = {
        "realization_id", "structural_link_id", "direction",
        "alternative_ordinal", "corridor_id"
    }
    missing = sorted(required - set(run_catalog.columns))
    if missing:
        raise RT030ContractError(f"RT-023 run catalog missing columns: {missing}")
    if len(run_catalog) != 288:
        raise RT030ContractError(
            f"RT-023 run artifact must contain 288 realizations, got {len(run_catalog)}"
        )
    existing = set(RT023_PROVENANCE_COLUMNS) & set(run_catalog.columns)
    if existing and existing != set(RT023_PROVENANCE_COLUMNS):
        raise RT030ContractError(
            f"RT-023 catalog has partial final provenance columns: {sorted(existing)}"
        )
    out = run_catalog.copy()
    values = {
        "rt021_elementary_corridor_evidence_sha256": elementary_corridors_sha256,
        "rt018_stop_attachment_layer_sha256": stop_attachments_sha256,
        "rt018_stop_occurrence_corpus_sha256": corridor_stop_occurrences_sha256,
    }
    for col, value in values.items():
        if col in out.columns:
            if set(out[col].astype(str)) != {str(value)}:
                raise RT030ContractError(f"RT-023 final provenance drift in {col}")
        else:
            out[col] = str(value)
    computed = _rt023_catalog_sha(out)
    if computed != RT023_FINAL_REALIZATION_CATALOG_SHA256:
        raise RT030ContractError(
            "RT-023 0d9a82c -> 2e8baf reconciliation hash mismatch: "
            f"{computed} != {RT023_FINAL_REALIZATION_CATALOG_SHA256}"
        )
    proof = {
        "run_id": 34034770563,
        "artifact_id": 9989805162,
        "artifact_head_sha": RT023_ARTIFACT_RUN_HEAD_SHA,
        "final_certification_head_sha": RT023_FINAL_HEAD_SHA,
        "transformation": "ADD_THREE_FROZEN_PROVENANCE_COLUMNS_ONLY",
        "added_columns": list(RT023_PROVENANCE_COLUMNS),
        "expected_final_realization_catalog_sha256": RT023_FINAL_REALIZATION_CATALOG_SHA256,
        "computed_final_realization_catalog_sha256": computed,
        "hash_reconciliation_proven": True,
    }
    return out, proof


def _validate_stop_contract(stops: pd.DataFrame, expected_graph_epoch: str) -> pd.DataFrame:
    _required(stops, [
        "stop_place_id", "lat", "lon", "service_class", "graph_node_id",
        "attachment_distance_m", "route_ready", "automatic_materialization_eligible",
        "graph_epoch_id", "attachment_semantics"
    ], "stop attachments")
    x = stops.copy()
    x["stop_place_id"] = x["stop_place_id"].astype(str)
    if len(x) != 36 or x["stop_place_id"].duplicated().any():
        raise RT030ContractError("Production frozen stop layer must contain exactly 36 unique stop places")
    classes = x["service_class"].astype(str)
    if int((classes == "CONVENTIONAL_TPL").sum()) != 35 or int((classes == "SPECIAL_SERVICE").sum()) != 1:
        raise RT030ContractError("Frozen stop universe must be exactly 35 CONVENTIONAL_TPL + 1 SPECIAL_SERVICE")
    special = x.loc[classes == "SPECIAL_SERVICE", "stop_place_id"].tolist()
    if special != [SPECIAL_STOP_ID]:
        raise RT030ContractError(f"Unexpected SPECIAL_SERVICE identity: {special}")
    epochs = set(x["graph_epoch_id"].astype(str))
    if epochs != {expected_graph_epoch}:
        raise RT030ContractError(f"Stop graph epoch mismatch: {sorted(epochs)}")
    conv = x[classes == "CONVENTIONAL_TPL"]
    if not all(_as_bool(v) for v in conv["route_ready"]):
        raise RT030ContractError("All frozen conventional stops must remain route-ready")
    if not all(_as_bool(v) for v in conv["automatic_materialization_eligible"]):
        raise RT030ContractError("All 35 frozen conventional stops must remain auto-materialization eligible")
    if any(_as_bool(v) for v in x.loc[classes == "SPECIAL_SERVICE", "automatic_materialization_eligible"]):
        raise RT030ContractError("SPECIAL_SERVICE must remain excluded")
    return x.sort_values("stop_place_id", kind="mergesort").reset_index(drop=True)


def _validate_graph(nodes: pd.DataFrame, edges: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    _required(nodes, ["node_id", "x", "y"], "graph nodes")
    _required(edges, ["edge_id", "u_node_id", "v_node_id", "osm_way_id"], "graph edges")
    n = nodes.copy(); e = edges.copy()
    n["node_id"] = n["node_id"].astype(str)
    e["edge_id"] = e["edge_id"].astype(str)
    e["u_node_id"] = e["u_node_id"].astype(str); e["v_node_id"] = e["v_node_id"].astype(str)
    if n["node_id"].duplicated().any() or e["edge_id"].duplicated().any():
        raise RT030ContractError("Graph node_id/edge_id must be unique")
    known = set(n["node_id"])
    if not set(e["u_node_id"]).issubset(known) or not set(e["v_node_id"]).issubset(known):
        raise RT030ContractError("Graph edge references unknown node")
    return n, e


def build_global_stop_segment_attachments(
    stop_attachments: pd.DataFrame,
    graph_nodes: pd.DataFrame,
    graph_edges: pd.DataFrame,
    *,
    expected_graph_epoch: str = EXPECTED_GRAPH_EPOCH,
    production_contract: bool = True,
) -> pd.DataFrame:
    """Attach each stop to its globally nearest frozen physical graph segment.

    This is deliberately route-independent. No candidate path is an input, and no
    distance-to-route buffer exists. The certified RT-018 node attachment remains
    primary evidence; this segment attachment is supplemental road-carrier evidence.
    """
    stops = _validate_stop_contract(stop_attachments, expected_graph_epoch) if production_contract else stop_attachments.copy()
    nodes, edges = _validate_graph(graph_nodes, graph_edges)

    node_xy = nodes.set_index("node_id")[["x", "y"]].astype(float)
    seg = edges.copy()
    seg["segment_key"] = [
        _physical_segment_key(u, v) for u, v in zip(seg["u_node_id"], seg["v_node_id"])
    ]
    seg["canonical_u_node_id"] = [min(str(u), str(v)) for u, v in zip(seg["u_node_id"], seg["v_node_id"])]
    seg["canonical_v_node_id"] = [max(str(u), str(v)) for u, v in zip(seg["u_node_id"], seg["v_node_id"])]
    grp = seg.groupby("segment_key", sort=True)
    ambiguous_multiway = grp["osm_way_id"].nunique()
    bad = ambiguous_multiway[ambiguous_multiway > 1]
    if not bad.empty:
        raise RT030ContractError(f"Physical segment maps to multiple OSM ways: {bad.index.tolist()[:5]}")
    if "highway" in seg.columns:
        highway_drift = grp["highway"].nunique(dropna=False)
        bad_highway = highway_drift[highway_drift > 1]
        if not bad_highway.empty:
            raise RT030ContractError(
                f"Physical segment has direction-dependent highway class: {bad_highway.index.tolist()[:5]}"
            )
    phys = seg.sort_values(["segment_key", "edge_id"], kind="mergesort").groupby(
        "segment_key", sort=True, as_index=False
    ).first()
    phys["u_node_id"] = phys["canonical_u_node_id"].astype(str)
    phys["v_node_id"] = phys["canonical_v_node_id"].astype(str)
    phys["physical_segment_id"] = [
        _physical_segment_id(u, v) for u, v in zip(phys["u_node_id"], phys["v_node_id"])
    ]
    phys["x1"] = phys["u_node_id"].map(node_xy["x"])
    phys["y1"] = phys["u_node_id"].map(node_xy["y"])
    phys["x2"] = phys["v_node_id"].map(node_xy["x"])
    phys["y2"] = phys["v_node_id"].map(node_xy["y"])

    x1 = phys["x1"].to_numpy(float); y1 = phys["y1"].to_numpy(float)
    dx = phys["x2"].to_numpy(float) - x1; dy = phys["y2"].to_numpy(float) - y1
    l2 = dx * dx + dy * dy
    if np.any(l2 <= 0):
        raise RT030ContractError("Zero-length physical graph segment")

    transformer = Transformer.from_crs(4326, 32632, always_xy=True)
    rows = []
    for r in stops.sort_values("stop_place_id", kind="mergesort").to_dict("records"):
        px, py = transformer.transform(float(r["lon"]), float(r["lat"]))
        t = ((px - x1) * dx + (py - y1) * dy) / l2
        tc = np.clip(t, 0.0, 1.0)
        qx = x1 + tc * dx; qy = y1 + tc * dy
        dist = np.hypot(px - qx, py - qy)
        best = float(np.min(dist))
        tied = np.flatnonzero(np.abs(dist - best) <= PHYSICAL_SEGMENT_TIE_EPS_M)
        unique = len(tied) == 1
        idx = int(tied[0]) if unique else int(tied[np.argmin(phys.iloc[tied]["physical_segment_id"].astype(str).to_numpy())])
        p = phys.iloc[idx]
        eligible = (
            str(r.get("service_class", "")) == "CONVENTIONAL_TPL"
            and _as_bool(r.get("route_ready", False))
            and _as_bool(r.get("automatic_materialization_eligible", False))
            and unique
        )
        rows.append({
            "stop_place_id": str(r["stop_place_id"]),
            "service_class": str(r.get("service_class", "")),
            "graph_epoch_id": str(r.get("graph_epoch_id", expected_graph_epoch)),
            "certified_attachment_node_id": str(r.get("graph_node_id", "")),
            "certified_attachment_node_distance_m": float(r.get("attachment_distance_m", np.nan)),
            "physical_segment_id": str(p["physical_segment_id"]),
            "physical_segment_u_node_id": str(p["u_node_id"]),
            "physical_segment_v_node_id": str(p["v_node_id"]),
            "physical_segment_osm_way_id": str(p["osm_way_id"]),
            "physical_segment_highway": str(p.get("highway", "")),
            "attachment_edge_distance_m": best,
            "attachment_projection_fraction_canonical_uv": float(tc[idx]),
            "nearest_physical_segment_unique": bool(unique),
            "nearest_physical_segment_tie_count": int(len(tied)),
            "supplemental_segment_materialization_eligible": bool(eligible),
            "segment_attachment_semantics": "FROZEN_GLOBAL_NEAREST_BUS_GRAPH_PHYSICAL_SEGMENT_ROUTE_INDEPENDENT",
            "route_proximity_buffer_m": ROUTE_PROXIMITY_BUFFER_M,
        })
    out = pd.DataFrame(rows).sort_values("stop_place_id", kind="mergesort").reset_index(drop=True)
    return out
