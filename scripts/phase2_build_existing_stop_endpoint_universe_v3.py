#!/usr/bin/env python3
"""Build a spatially verified existing-stop endpoint evidence universe for Phase 2 V3.

RT-006 contract
---------------
This builder does *not* choose route endpoints, corridors, passenger stop
patterns, topologies, headways or winners.  It creates an exhaustive inventory
of already-existing, bus-graph-route-ready physical stop clusters whose actual
coordinates fall inside one of the five policy municipalities.

The source GTFS municipality label is preserved only as evidence.  Geographic
membership is reassigned from the frozen official municipal polygons because
reference GTFS records can carry administrative labels that disagree with the
stop coordinate.  Such disagreement is reported, never silently repaired in
upstream data.

Existing official stops remain the primary physical evidence.  Frozen OSM
conflation is a cross-check: lack of an OSM match does not invalidate an
official GTFS stop, while an explicit GTFS<->OSM identity/distance conflict is
held for review and not admitted to automatic corridor generation.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path
from typing import Iterable

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

ROOT = Path(__file__).resolve().parents[1]
CORE = {
    "097010": "Brivio",
    "097012": "Calco",
    "097058": "Olgiate Molgora",
    "097074": "Santa Maria Hoè",
    "097092": "La Valletta Brianza",
}
DEFAULT_ROUTING = ROOT / "outputs/phase2/reduced_path_matrix_v2/routing_anchor_membership.csv"
DEFAULT_EXISTING = ROOT / "outputs/phase2/stop_universe_v2/existing_official_stops.csv"
DEFAULT_CATCHMENT = ROOT / "outputs/phase2/stop_universe_v2/existing_stop_catchment_summary.csv"
DEFAULT_CONFLATION = ROOT / "outputs/phase2/network_design_method_audit_v3/existing_stop_master_clusters_audit_v3.csv"
DEFAULT_MUNICIPALITIES = ROOT / "data/phase2/analysis_envelope/source/municipalities_context.geojson.gz"
DEFAULT_OUT = ROOT / "outputs/phase2/network_design_method_audit_v3/existing_stop_endpoint_universe_v3"
THRESHOLDS = (5, 8, 10, 12)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def truthy(value: object) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes"}


def _code_col(frame: gpd.GeoDataFrame) -> str:
    for col in ("procom", "PRO_COM_T", "PRO_COM", "PRO_COMUNE", "municipality_code"):
        if col in frame.columns:
            return col
    raise ValueError(f"Cannot identify municipality code column: {list(frame.columns)}")


def _name_col(frame: gpd.GeoDataFrame) -> str | None:
    for col in ("municipality_name", "COMUNE", "COMUNE_A", "DEN_COM", "comune"):
        if col in frame.columns:
            return col
    return None


def load_municipalities(path: Path) -> gpd.GeoDataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            payload = json.load(handle)
        frame = gpd.GeoDataFrame.from_features(payload["features"], crs="EPSG:4326")
    else:
        frame = gpd.read_file(path)
        if frame.crs is None:
            frame = frame.set_crs(4326)
        frame = frame.to_crs(4326)
    code_col = _code_col(frame)
    name_col = _name_col(frame)
    frame = frame.copy()
    frame["_core_code"] = frame[code_col].astype(str).str.replace(".0", "", regex=False).str.zfill(6)
    frame = frame[frame["_core_code"].isin(CORE)].copy()
    if set(frame["_core_code"]) != set(CORE):
        raise ValueError(
            f"Frozen municipality source does not contain exactly all five core municipalities: "
            f"{sorted(set(frame['_core_code']))}"
        )
    frame["_core_name"] = frame["_core_code"].map(CORE)
    if name_col:
        frame["_source_name"] = frame[name_col].astype(str)
    else:
        frame["_source_name"] = frame["_core_name"]
    return frame[["_core_code", "_core_name", "_source_name", "geometry"]].sort_values(
        "_core_code", kind="mergesort"
    ).reset_index(drop=True)


def spatial_assignment(lon: float, lat: float, municipalities: gpd.GeoDataFrame) -> tuple[str, str, str]:
    point = Point(float(lon), float(lat))
    hits: list[tuple[str, str]] = []
    for row in municipalities.itertuples(index=False):
        if row.geometry.covers(point):
            hits.append((str(row._core_code), str(row._core_name)))
    if len(hits) == 1:
        return hits[0][0], hits[0][1], "UNIQUE_OFFICIAL_POLYGON_COVERS_POINT"
    if not hits:
        return "", "", "OUTSIDE_FIVE_POLICY_MUNICIPALITIES"
    return "|".join(code for code, _ in hits), "|".join(name for _, name in hits), "AMBIGUOUS_MULTIPLE_POLYGONS"


def aggregate_existing(existing: pd.DataFrame) -> pd.DataFrame:
    required = {
        "physical_cluster_id",
        "stop_id",
        "stop_name",
        "official_routes_reference_gtfs",
        "source_scope",
        "epistemic_status",
    }
    missing = required - set(existing.columns)
    if missing:
        raise ValueError(f"Existing official stop input missing columns: {sorted(missing)}")
    rows = []
    for cluster_id, group in existing.groupby("physical_cluster_id", sort=True):
        routes: set[str] = set()
        scopes: set[str] = set()
        statuses: set[str] = set()
        for value in group["official_routes_reference_gtfs"].fillna("").astype(str):
            routes.update(part for part in value.split("|") if part)
        scopes.update(v for v in group["source_scope"].fillna("").astype(str) if v)
        statuses.update(v for v in group["epistemic_status"].fillna("").astype(str) if v)
        rows.append(
            {
                "physical_cluster_id": str(cluster_id),
                "gtfs_stop_ids": "|".join(sorted(set(group["stop_id"].astype(str)))),
                "gtfs_stop_names": "|".join(sorted(set(group["stop_name"].astype(str)))),
                "reference_routes": "|".join(sorted(routes)),
                "source_scopes": "|".join(sorted(scopes)),
                "source_epistemic_statuses": "|".join(sorted(statuses)),
                "gtfs_record_count": int(len(group)),
            }
        )
    return pd.DataFrame(rows)


def pivot_catchments(catchment: pd.DataFrame) -> pd.DataFrame:
    required = {
        "physical_cluster_id",
        "threshold_min",
        "population_reachable_building_model",
        "population_unit_count",
        "epistemic_status",
    }
    missing = required - set(catchment.columns)
    if missing:
        raise ValueError(f"Existing stop catchment input missing columns: {sorted(missing)}")
    frame = catchment.copy()
    frame["threshold_min"] = pd.to_numeric(frame["threshold_min"], errors="raise").astype(int)
    if not set(THRESHOLDS).issubset(set(frame["threshold_min"])):
        raise ValueError("Existing stop catchment evidence is missing one or more 5/8/10/12 minute thresholds")
    duplicate = frame.duplicated(["physical_cluster_id", "threshold_min"])
    if duplicate.any():
        raise ValueError("Existing stop catchment summary is not unique by cluster and threshold")
    rows = []
    for cluster_id, group in frame.groupby("physical_cluster_id", sort=True):
        by_t = {int(row.threshold_min): row for row in group.itertuples(index=False)}
        row = {
            "physical_cluster_id": str(cluster_id),
            "catchment_epistemic_status": "|".join(sorted(set(group["epistemic_status"].astype(str)))),
        }
        for threshold in THRESHOLDS:
            item = by_t.get(threshold)
            row[f"population_reachable_{threshold}min"] = (
                float(item.population_reachable_building_model) if item is not None else float("nan")
            )
            row[f"population_unit_count_{threshold}min"] = (
                int(item.population_unit_count) if item is not None else pd.NA
            )
        rows.append(row)
    return pd.DataFrame(rows)


def load_conflation(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    frame = pd.read_csv(path, dtype=str).fillna("")
    required = {
        "physical_cluster_id",
        "osm_confirmed_element_count",
        "osm_review_element_count",
        "cross_source_status",
    }
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"Conflation audit missing columns: {sorted(missing)}")
    if frame["physical_cluster_id"].duplicated().any():
        raise ValueError("Conflation cluster audit is not unique by physical_cluster_id")
    return frame[list(required)].copy()


def stable_columns() -> list[str]:
    return [
        "endpoint_id",
        "physical_cluster_id",
        "source_record_id",
        "human_label",
        "lon",
        "lat",
        "graph_node_id",
        "bus_graph_snap_distance_m",
        "bus_graph_snap_status",
        "inherited_gtfs_municipality",
        "spatial_municipality_code",
        "spatial_municipality",
        "municipality_assignment_status",
        "municipality_label_agrees_with_spatial_assignment",
        "gtfs_stop_ids",
        "gtfs_stop_names",
        "reference_routes",
        "source_scopes",
        "source_epistemic_statuses",
        "gtfs_record_count",
        "cross_source_status",
        "osm_confirmed_element_count",
        "osm_review_element_count",
        "population_reachable_5min",
        "population_reachable_8min",
        "population_reachable_10min",
        "population_reachable_12min",
        "population_unit_count_5min",
        "population_unit_count_8min",
        "population_unit_count_10min",
        "population_unit_count_12min",
        "catchment_epistemic_status",
        "generation_eligible_existing_stop",
        "generation_hold_reason",
        "proposed_stop",
        "endpoint_universe_role",
        "epoch_id",
    ]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--routing", type=Path, default=DEFAULT_ROUTING)
    ap.add_argument("--existing", type=Path, default=DEFAULT_EXISTING)
    ap.add_argument("--catchment", type=Path, default=DEFAULT_CATCHMENT)
    ap.add_argument("--conflation", type=Path, default=DEFAULT_CONFLATION)
    ap.add_argument("--municipalities", type=Path, default=DEFAULT_MUNICIPALITIES)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args()

    for path in (args.routing, args.existing, args.catchment, args.conflation, args.municipalities):
        if not path.exists():
            raise FileNotFoundError(path)
    args.out.mkdir(parents=True, exist_ok=True)

    routing = pd.read_csv(args.routing, dtype=str).fillna("")
    required_routing = {
        "source_anchor_id",
        "source_kind",
        "source_record_id",
        "source_name",
        "municipality",
        "lon",
        "lat",
        "graph_node_id",
        "snap_distance_m",
        "snap_status",
        "route_ready",
        "epoch_id",
    }
    missing = required_routing - set(routing.columns)
    if missing:
        raise ValueError(f"Routing membership missing columns: {sorted(missing)}")
    route_ready = routing[
        routing["source_kind"].eq("EXISTING_PHYSICAL_STOP_CLUSTER")
        & routing["route_ready"].map(truthy)
        & routing["snap_status"].eq("ROUTE_READY_LE_75M")
    ].copy()
    if route_ready.empty:
        raise ValueError("No route-ready existing physical stop clusters found")
    route_ready["physical_cluster_id"] = route_ready["source_anchor_id"].str.replace(
        "existing:", "", regex=False
    )
    if route_ready["physical_cluster_id"].duplicated().any():
        raise ValueError("Routing membership contains duplicate existing physical_cluster_id rows")

    municipalities = load_municipalities(args.municipalities)
    assignments = [
        spatial_assignment(float(row.lon), float(row.lat), municipalities)
        for row in route_ready.itertuples(index=False)
    ]
    route_ready["spatial_municipality_code"] = [item[0] for item in assignments]
    route_ready["spatial_municipality"] = [item[1] for item in assignments]
    route_ready["municipality_assignment_status"] = [item[2] for item in assignments]

    existing = aggregate_existing(pd.read_csv(args.existing, dtype=str).fillna(""))
    catchment = pivot_catchments(pd.read_csv(args.catchment, dtype=str).fillna(""))
    conflation = load_conflation(args.conflation)
    merged = route_ready.merge(existing, on="physical_cluster_id", how="left", validate="one_to_one")
    merged = merged.merge(catchment, on="physical_cluster_id", how="left", validate="one_to_one")
    merged = merged.merge(conflation, on="physical_cluster_id", how="left", validate="one_to_one")
    if merged["gtfs_stop_ids"].isna().any():
        missing_clusters = merged.loc[merged["gtfs_stop_ids"].isna(), "physical_cluster_id"].tolist()
        raise ValueError(f"Route-ready physical clusters missing official GTFS evidence: {missing_clusters}")
    if merged["population_reachable_10min"].isna().any():
        missing_clusters = merged.loc[
            merged["population_reachable_10min"].isna(), "physical_cluster_id"
        ].tolist()
        raise ValueError(f"Route-ready physical clusters missing catchment evidence: {missing_clusters}")

    merged["cross_source_status"] = merged["cross_source_status"].fillna("GTFS_ONLY_NO_CONFLATION_ROW")
    merged["osm_confirmed_element_count"] = pd.to_numeric(
        merged["osm_confirmed_element_count"].fillna("0"), errors="raise"
    ).astype(int)
    merged["osm_review_element_count"] = pd.to_numeric(
        merged["osm_review_element_count"].fillna("0"), errors="raise"
    ).astype(int)

    def agree(row) -> bool:
        inherited = str(row.municipality).strip().casefold()
        spatial = str(row.spatial_municipality).strip().casefold()
        return bool(inherited and spatial and inherited == spatial)

    merged["municipality_label_agrees_with_spatial_assignment"] = [
        agree(row) for row in merged.itertuples(index=False)
    ]

    in_core = merged[merged["municipality_assignment_status"].eq("UNIQUE_OFFICIAL_POLYGON_COVERS_POINT")].copy()
    excluded = merged[~merged["municipality_assignment_status"].eq("UNIQUE_OFFICIAL_POLYGON_COVERS_POINT")].copy()
    if in_core.empty:
        raise ValueError("Spatial municipality verification excluded all existing stops")

    conflict_mask = in_core["cross_source_status"].astype(str).str.contains("CONFLICT", case=False, regex=False)
    in_core["generation_eligible_existing_stop"] = ~conflict_mask
    in_core["generation_hold_reason"] = conflict_mask.map(
        lambda value: "GTFS_OSM_IDENTITY_DISTANCE_CONFLICT_REVIEW" if bool(value) else ""
    )
    in_core["endpoint_id"] = "existing:" + in_core["physical_cluster_id"].astype(str)
    in_core["proposed_stop"] = False
    in_core["endpoint_universe_role"] = "EXHAUSTIVE_EXISTING_ROUTE_READY_CORE_STOP_NOT_SELECTED"

    out = pd.DataFrame(
        {
            "endpoint_id": in_core["endpoint_id"],
            "physical_cluster_id": in_core["physical_cluster_id"],
            "source_record_id": in_core["source_record_id"],
            "human_label": in_core["source_name"],
            "lon": pd.to_numeric(in_core["lon"], errors="raise").map(lambda v: f"{v:.9f}"),
            "lat": pd.to_numeric(in_core["lat"], errors="raise").map(lambda v: f"{v:.9f}"),
            "graph_node_id": in_core["graph_node_id"],
            "bus_graph_snap_distance_m": pd.to_numeric(in_core["snap_distance_m"], errors="raise").map(lambda v: f"{v:.9f}"),
            "bus_graph_snap_status": in_core["snap_status"],
            "inherited_gtfs_municipality": in_core["municipality"],
            "spatial_municipality_code": in_core["spatial_municipality_code"],
            "spatial_municipality": in_core["spatial_municipality"],
            "municipality_assignment_status": in_core["municipality_assignment_status"],
            "municipality_label_agrees_with_spatial_assignment": in_core[
                "municipality_label_agrees_with_spatial_assignment"
            ].map(lambda v: str(bool(v)).lower()),
            "gtfs_stop_ids": in_core["gtfs_stop_ids"],
            "gtfs_stop_names": in_core["gtfs_stop_names"],
            "reference_routes": in_core["reference_routes"],
            "source_scopes": in_core["source_scopes"],
            "source_epistemic_statuses": in_core["source_epistemic_statuses"],
            "gtfs_record_count": in_core["gtfs_record_count"].astype(int),
            "cross_source_status": in_core["cross_source_status"],
            "osm_confirmed_element_count": in_core["osm_confirmed_element_count"].astype(int),
            "osm_review_element_count": in_core["osm_review_element_count"].astype(int),
            **{
                f"population_reachable_{t}min": pd.to_numeric(
                    in_core[f"population_reachable_{t}min"], errors="raise"
                ).map(lambda v: f"{v:.9f}")
                for t in THRESHOLDS
            },
            **{
                f"population_unit_count_{t}min": pd.to_numeric(
                    in_core[f"population_unit_count_{t}min"], errors="raise"
                ).astype(int)
                for t in THRESHOLDS
            },
            "catchment_epistemic_status": in_core["catchment_epistemic_status"],
            "generation_eligible_existing_stop": in_core["generation_eligible_existing_stop"].map(
                lambda v: str(bool(v)).lower()
            ),
            "generation_hold_reason": in_core["generation_hold_reason"],
            "proposed_stop": "false",
            "endpoint_universe_role": in_core["endpoint_universe_role"],
            "epoch_id": in_core["epoch_id"],
        }
    )[stable_columns()].sort_values(
        ["spatial_municipality_code", "physical_cluster_id"], kind="mergesort"
    ).reset_index(drop=True)

    excluded_out = pd.DataFrame(
        {
            "physical_cluster_id": excluded["physical_cluster_id"],
            "source_record_id": excluded["source_record_id"],
            "human_label": excluded["source_name"],
            "lon": excluded["lon"],
            "lat": excluded["lat"],
            "inherited_gtfs_municipality": excluded["municipality"],
            "municipality_assignment_status": excluded["municipality_assignment_status"],
            "reason": "NOT_PHYSICALLY_INSIDE_EXACTLY_ONE_OF_FIVE_POLICY_MUNICIPALITIES",
            "decision_role": "EXCLUDED_FROM_CORE_ENDPOINT_UNIVERSE_NOT_DELETED_FROM_SOURCE_EVIDENCE",
        }
    ).sort_values("physical_cluster_id", kind="mergesort").reset_index(drop=True)

    mismatches = out[
        out["municipality_label_agrees_with_spatial_assignment"].eq("false")
    ].copy()
    mismatch_out = mismatches[
        [
            "endpoint_id",
            "physical_cluster_id",
            "human_label",
            "inherited_gtfs_municipality",
            "spatial_municipality_code",
            "spatial_municipality",
        ]
    ].copy()
    mismatch_out["audit_status"] = "GTFS_LABEL_SPATIAL_POLYGON_DISAGREEMENT"

    endpoint_path = args.out / "existing_stop_endpoint_universe_v3.csv"
    excluded_path = args.out / "existing_stop_endpoint_exclusions_v3.csv"
    mismatch_path = args.out / "existing_stop_municipality_mismatches_v3.csv"
    validation_path = args.out / "existing_stop_endpoint_universe_v3_validation.json"
    out.to_csv(endpoint_path, index=False)
    excluded_out.to_csv(excluded_path, index=False)
    mismatch_out.to_csv(mismatch_path, index=False)

    per_municipality = {
        code: {
            "municipality": CORE[code],
            "endpoint_count": int((out["spatial_municipality_code"] == code).sum()),
            "generation_eligible_count": int(
                (
                    (out["spatial_municipality_code"] == code)
                    & out["generation_eligible_existing_stop"].eq("true")
                ).sum()
            ),
        }
        for code in sorted(CORE)
    }
    status = "PASS_EXISTING_STOP_ENDPOINT_UNIVERSE_V3"
    if any(value["generation_eligible_count"] == 0 for value in per_municipality.values()):
        status = "FAIL_EXISTING_STOP_ENDPOINT_UNIVERSE_V3"

    validation = {
        "status": status,
        "contract": "EXHAUSTIVE_EXISTING_STOP_ENDPOINT_EVIDENCE_NOT_ENDPOINT_SELECTION",
        "policy_scope": {
            "municipalities": CORE,
            "municipality_membership_source": str(args.municipalities.relative_to(ROOT)),
            "municipality_membership_semantics": "POINT_COVERED_BY_FROZEN_OFFICIAL_MUNICIPAL_POLYGON",
        },
        "inputs": {
            "routing_anchor_membership": str(args.routing.relative_to(ROOT)),
            "routing_anchor_membership_sha256": sha256(args.routing),
            "existing_official_stops": str(args.existing.relative_to(ROOT)),
            "existing_official_stops_sha256": sha256(args.existing),
            "existing_stop_catchment_summary": str(args.catchment.relative_to(ROOT)),
            "existing_stop_catchment_summary_sha256": sha256(args.catchment),
            "gtfs_osm_conflation_cluster_audit": str(args.conflation.relative_to(ROOT)),
            "gtfs_osm_conflation_cluster_audit_sha256": sha256(args.conflation),
            "municipalities_sha256": sha256(args.municipalities),
        },
        "counts": {
            "route_ready_existing_clusters_before_spatial_scope": int(len(route_ready)),
            "core_existing_endpoint_clusters": int(len(out)),
            "generation_eligible_existing_endpoint_clusters": int(
                out["generation_eligible_existing_stop"].eq("true").sum()
            ),
            "held_for_cross_source_conflict_review": int(
                out["generation_eligible_existing_stop"].eq("false").sum()
            ),
            "outside_or_ambiguous_core_exclusions": int(len(excluded_out)),
            "gtfs_municipality_label_spatial_mismatches_inside_core": int(len(mismatch_out)),
        },
        "per_municipality": per_municipality,
        "evidence_semantics": {
            "existing_gtfs_is_primary_physical_stop_evidence": True,
            "osm_match_required_for_existing_stop": False,
            "explicit_gtfs_osm_identity_distance_conflict_requires_review": True,
            "population_catchments_are_selection_scores": False,
            "catchment_thresholds_minutes": list(THRESHOLDS),
        },
        "guards": {
            "proposed_stops_present": False,
            "endpoint_selected": False,
            "corridor_selected": False,
            "passenger_stop_pattern_selected": False,
            "manual_settlement_waypoints_used": False,
            "population_ranking_used_to_exclude_existing_stops": False,
            "winner_selected": False,
        },
        "outputs": {
            "endpoint_universe": str(endpoint_path.relative_to(ROOT)),
            "endpoint_universe_sha256": sha256(endpoint_path),
            "exclusions": str(excluded_path.relative_to(ROOT)),
            "exclusions_sha256": sha256(excluded_path),
            "municipality_mismatches": str(mismatch_path.relative_to(ROOT)),
            "municipality_mismatches_sha256": sha256(mismatch_path),
        },
    }
    validation_path.write_text(
        json.dumps(validation, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if status.startswith("FAIL"):
        raise SystemExit(status)
    print(json.dumps(validation, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
