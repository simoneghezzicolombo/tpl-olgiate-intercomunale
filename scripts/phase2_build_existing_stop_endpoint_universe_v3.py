#!/usr/bin/env python3
"""Build the Phase-2 V3 existing-stop endpoint evidence universe.

This is an exhaustive evidence inventory, not endpoint selection.  It admits
only already-existing official physical stop clusters that are route-ready on
the frozen Gate-D bus graph and whose coordinates lie inside exactly one of the
five policy municipalities.

Important epistemic rules:
- municipality membership is recomputed from frozen official polygons rather
  than trusted from the GTFS administrative label;
- official/reference-period GTFS remains the primary evidence that a physical
  stop exists;
- frozen OSM is a cross-check.  An OSM conflict raises a review flag but does
  not erase or automatically disqualify an official GTFS stop;
- population catchments are attached as evidence dimensions only.  They do not
  rank or prune stops in this builder;
- no proposed stop, corridor, topology, headway or winner is created.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path

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
THRESHOLDS = (5, 8, 10, 12)

DEFAULT_ROUTING = ROOT / "outputs/phase2/reduced_path_matrix_v2/routing_anchor_membership.csv"
DEFAULT_EXISTING = ROOT / "outputs/phase2/stop_universe_v2/existing_official_stops.csv"
DEFAULT_CATCHMENT = ROOT / "outputs/phase2/stop_universe_v2/existing_stop_catchment_summary.csv"
DEFAULT_MATCHES = ROOT / "outputs/phase2/network_design_method_audit_v3/existing_stop_gtfs_osm_matches_v3.csv"
DEFAULT_MUNICIPALITIES = ROOT / "data/phase2/analysis_envelope/source/municipalities_context.geojson.gz"
DEFAULT_OUT = ROOT / "outputs/phase2/network_design_method_audit_v3/existing_stop_endpoint_universe_v3"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def truthy(value: object) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes"}


def municipality_code_column(frame: gpd.GeoDataFrame) -> str:
    for column in ("procom", "PRO_COM_T", "PRO_COM", "PRO_COMUNE", "municipality_code"):
        if column in frame.columns:
            return column
    raise ValueError(f"Cannot identify municipality code column: {list(frame.columns)}")


def load_municipalities(path: Path) -> gpd.GeoDataFrame:
    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            payload = json.load(handle)
        frame = gpd.GeoDataFrame.from_features(payload["features"], crs="EPSG:4326")
    else:
        frame = gpd.read_file(path)
        if frame.crs is None:
            frame = frame.set_crs(4326)
        frame = frame.to_crs(4326)

    source_code = municipality_code_column(frame)
    out = frame.copy()
    out["core_code"] = (
        out[source_code]
        .astype(str)
        .str.replace(".0", "", regex=False)
        .str.zfill(6)
    )
    out = out[out["core_code"].isin(CORE)].copy()
    if set(out["core_code"]) != set(CORE):
        raise ValueError(
            "Frozen municipality evidence does not contain all five policy municipalities: "
            f"{sorted(set(out['core_code']))}"
        )
    out["core_name"] = out["core_code"].map(CORE)
    return out[["core_code", "core_name", "geometry"]].sort_values(
        "core_code", kind="mergesort"
    ).reset_index(drop=True)


def assign_municipality(
    lon: float,
    lat: float,
    municipalities: gpd.GeoDataFrame,
) -> tuple[str, str, str]:
    point = Point(float(lon), float(lat))
    hits: list[tuple[str, str]] = []
    for _, row in municipalities.iterrows():
        if row.geometry.covers(point):
            hits.append((str(row["core_code"]), str(row["core_name"])))
    if len(hits) == 1:
        return hits[0][0], hits[0][1], "UNIQUE_OFFICIAL_POLYGON_COVERS_POINT"
    if not hits:
        return "", "", "OUTSIDE_FIVE_POLICY_MUNICIPALITIES"
    return (
        "|".join(code for code, _ in hits),
        "|".join(name for _, name in hits),
        "AMBIGUOUS_MULTIPLE_OFFICIAL_POLYGONS",
    )


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
        raise ValueError(f"Existing-stop evidence missing columns: {sorted(missing)}")

    rows: list[dict] = []
    for cluster_id, group in existing.groupby("physical_cluster_id", sort=True):
        routes: set[str] = set()
        for value in group["official_routes_reference_gtfs"].fillna("").astype(str):
            routes.update(part for part in value.split("|") if part)
        rows.append(
            {
                "physical_cluster_id": str(cluster_id),
                "gtfs_stop_ids": "|".join(sorted(set(group["stop_id"].astype(str)))),
                "gtfs_stop_names": "|".join(sorted(set(group["stop_name"].astype(str)))),
                "reference_routes": "|".join(sorted(routes)),
                "source_scopes": "|".join(
                    sorted(v for v in set(group["source_scope"].astype(str)) if v)
                ),
                "source_epistemic_statuses": "|".join(
                    sorted(v for v in set(group["epistemic_status"].astype(str)) if v)
                ),
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
        raise ValueError(f"Existing-stop catchment evidence missing columns: {sorted(missing)}")

    frame = catchment.copy()
    frame["threshold_min"] = pd.to_numeric(frame["threshold_min"], errors="raise").astype(int)
    if frame.duplicated(["physical_cluster_id", "threshold_min"]).any():
        raise ValueError("Catchment evidence is not unique by physical cluster and threshold")

    rows: list[dict] = []
    for cluster_id, group in frame.groupby("physical_cluster_id", sort=True):
        by_threshold = {int(row.threshold_min): row for row in group.itertuples(index=False)}
        row: dict[str, object] = {
            "physical_cluster_id": str(cluster_id),
            "catchment_epistemic_status": "|".join(
                sorted(set(group["epistemic_status"].astype(str)))
            ),
        }
        for threshold in THRESHOLDS:
            item = by_threshold.get(threshold)
            if item is None:
                row[f"population_reachable_{threshold}min"] = pd.NA
                row[f"population_unit_count_{threshold}min"] = pd.NA
            else:
                row[f"population_reachable_{threshold}min"] = float(
                    item.population_reachable_building_model
                )
                row[f"population_unit_count_{threshold}min"] = int(item.population_unit_count)
        rows.append(row)
    return pd.DataFrame(rows)


def aggregate_osm_crosscheck(matches: pd.DataFrame) -> pd.DataFrame:
    required = {"matched_physical_cluster_id", "match_status", "osm_id"}
    missing = required - set(matches.columns)
    if missing:
        raise ValueError(f"GTFS-OSM match evidence missing columns: {sorted(missing)}")

    matched = matches[matches["matched_physical_cluster_id"].astype(str).str.len() > 0].copy()
    rows: list[dict] = []
    for cluster_id, group in matched.groupby("matched_physical_cluster_id", sort=True):
        statuses = group["match_status"].astype(str)
        rows.append(
            {
                "physical_cluster_id": str(cluster_id),
                "osm_confirmed_element_count": int(statuses.str.startswith("CONFIRMED").sum()),
                "osm_review_element_count": int(statuses.str.contains("REVIEW", regex=False).sum()),
                "osm_conflict_element_count": int(statuses.str.startswith("CONFLICT").sum()),
                "osm_crosscheck_statuses": "|".join(sorted(set(statuses))),
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--routing", type=Path, default=DEFAULT_ROUTING)
    parser.add_argument("--existing", type=Path, default=DEFAULT_EXISTING)
    parser.add_argument("--catchment", type=Path, default=DEFAULT_CATCHMENT)
    parser.add_argument("--matches", type=Path, default=DEFAULT_MATCHES)
    parser.add_argument("--municipalities", type=Path, default=DEFAULT_MUNICIPALITIES)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    inputs = [args.routing, args.existing, args.catchment, args.matches, args.municipalities]
    for path in inputs:
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
    route_ready["physical_cluster_id"] = route_ready["source_anchor_id"].str.replace(
        "existing:", "", regex=False
    )
    if route_ready.empty:
        raise ValueError("No route-ready existing physical stop clusters")
    if route_ready["physical_cluster_id"].duplicated().any():
        raise ValueError("Route-ready membership duplicates a physical cluster")

    municipalities = load_municipalities(args.municipalities)
    assignments = [
        assign_municipality(float(row.lon), float(row.lat), municipalities)
        for row in route_ready.itertuples(index=False)
    ]
    route_ready["spatial_municipality_code"] = [item[0] for item in assignments]
    route_ready["spatial_municipality"] = [item[1] for item in assignments]
    route_ready["municipality_assignment_status"] = [item[2] for item in assignments]

    existing = aggregate_existing(pd.read_csv(args.existing, dtype=str).fillna(""))
    catchments = pivot_catchments(pd.read_csv(args.catchment, dtype=str).fillna(""))
    osm = aggregate_osm_crosscheck(pd.read_csv(args.matches, dtype=str).fillna(""))

    merged = route_ready.merge(existing, on="physical_cluster_id", how="left", validate="one_to_one")
    merged = merged.merge(catchments, on="physical_cluster_id", how="left", validate="one_to_one")
    merged = merged.merge(osm, on="physical_cluster_id", how="left", validate="one_to_one")

    if merged["gtfs_stop_ids"].isna().any():
        raise ValueError("A route-ready physical stop has no official GTFS evidence")
    if merged["population_reachable_10min"].isna().any():
        missing_clusters = merged.loc[
            merged["population_reachable_10min"].isna(), "physical_cluster_id"
        ].tolist()
        raise ValueError(f"Route-ready existing clusters missing catchment evidence: {missing_clusters}")

    for column in (
        "osm_confirmed_element_count",
        "osm_review_element_count",
        "osm_conflict_element_count",
    ):
        merged[column] = pd.to_numeric(merged[column].fillna(0), errors="raise").astype(int)
    merged["osm_crosscheck_statuses"] = merged["osm_crosscheck_statuses"].fillna(
        "NO_MATCHED_OSM_ELEMENT_IN_FROZEN_EXTRACT"
    )

    merged["municipality_label_agrees_with_spatial_assignment"] = [
        str(row.municipality).strip().casefold()
        == str(row.spatial_municipality).strip().casefold()
        for row in merged.itertuples(index=False)
    ]

    in_core = merged[
        merged["municipality_assignment_status"].eq("UNIQUE_OFFICIAL_POLYGON_COVERS_POINT")
    ].copy()
    excluded = merged[
        ~merged["municipality_assignment_status"].eq("UNIQUE_OFFICIAL_POLYGON_COVERS_POINT")
    ].copy()
    if in_core.empty:
        raise ValueError("Spatial verification excluded every existing stop")

    # Official GTFS remains primary.  OSM conflict is a review flag, not a veto.
    in_core["cross_source_review_required"] = in_core["osm_conflict_element_count"].gt(0)
    in_core["generation_eligible_existing_stop"] = True
    in_core["generation_hold_reason"] = ""
    in_core["endpoint_id"] = "existing:" + in_core["physical_cluster_id"].astype(str)
    in_core["endpoint_universe_role"] = "EXHAUSTIVE_EXISTING_ROUTE_READY_CORE_STOP_NOT_SELECTED"

    output_rows: list[dict] = []
    for row in in_core.itertuples(index=False):
        item = {
            "endpoint_id": row.endpoint_id,
            "physical_cluster_id": row.physical_cluster_id,
            "source_record_id": row.source_record_id,
            "human_label": row.source_name,
            "lon": f"{float(row.lon):.9f}",
            "lat": f"{float(row.lat):.9f}",
            "graph_node_id": row.graph_node_id,
            "bus_graph_snap_distance_m": f"{float(row.snap_distance_m):.9f}",
            "bus_graph_snap_status": row.snap_status,
            "inherited_gtfs_municipality": row.municipality,
            "spatial_municipality_code": row.spatial_municipality_code,
            "spatial_municipality": row.spatial_municipality,
            "municipality_assignment_status": row.municipality_assignment_status,
            "municipality_label_agrees_with_spatial_assignment": str(
                bool(row.municipality_label_agrees_with_spatial_assignment)
            ).lower(),
            "gtfs_stop_ids": row.gtfs_stop_ids,
            "gtfs_stop_names": row.gtfs_stop_names,
            "reference_routes": row.reference_routes,
            "source_scopes": row.source_scopes,
            "source_epistemic_statuses": row.source_epistemic_statuses,
            "gtfs_record_count": int(row.gtfs_record_count),
            "osm_confirmed_element_count": int(row.osm_confirmed_element_count),
            "osm_review_element_count": int(row.osm_review_element_count),
            "osm_conflict_element_count": int(row.osm_conflict_element_count),
            "osm_crosscheck_statuses": row.osm_crosscheck_statuses,
            "cross_source_review_required": str(bool(row.cross_source_review_required)).lower(),
            "catchment_epistemic_status": row.catchment_epistemic_status,
            "generation_eligible_existing_stop": "true",
            "generation_hold_reason": "",
            "proposed_stop": "false",
            "endpoint_universe_role": row.endpoint_universe_role,
            "epoch_id": row.epoch_id,
        }
        for threshold in THRESHOLDS:
            item[f"population_reachable_{threshold}min"] = (
                f"{float(getattr(row, f'population_reachable_{threshold}min')):.9f}"
            )
            item[f"population_unit_count_{threshold}min"] = int(
                getattr(row, f"population_unit_count_{threshold}min")
            )
        output_rows.append(item)

    endpoints = pd.DataFrame(output_rows).sort_values(
        ["spatial_municipality_code", "physical_cluster_id"], kind="mergesort"
    ).reset_index(drop=True)

    exclusions = pd.DataFrame(
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

    mismatches = endpoints[
        endpoints["municipality_label_agrees_with_spatial_assignment"].eq("false")
    ][
        [
            "endpoint_id",
            "physical_cluster_id",
            "human_label",
            "inherited_gtfs_municipality",
            "spatial_municipality_code",
            "spatial_municipality",
        ]
    ].copy()
    mismatches["audit_status"] = "GTFS_LABEL_SPATIAL_POLYGON_DISAGREEMENT"

    endpoint_path = args.out / "existing_stop_endpoint_universe_v3.csv"
    exclusion_path = args.out / "existing_stop_endpoint_exclusions_v3.csv"
    mismatch_path = args.out / "existing_stop_municipality_mismatches_v3.csv"
    validation_path = args.out / "existing_stop_endpoint_universe_v3_validation.json"
    endpoints.to_csv(endpoint_path, index=False)
    exclusions.to_csv(exclusion_path, index=False)
    mismatches.to_csv(mismatch_path, index=False)

    per_municipality = {
        code: {
            "municipality": CORE[code],
            "endpoint_count": int((endpoints["spatial_municipality_code"] == code).sum()),
            "generation_eligible_count": int(
                (
                    (endpoints["spatial_municipality_code"] == code)
                    & endpoints["generation_eligible_existing_stop"].eq("true")
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
            "municipality_membership_semantics": "POINT_COVERED_BY_FROZEN_OFFICIAL_MUNICIPAL_POLYGON",
        },
        "inputs": {
            "routing_anchor_membership": str(args.routing.relative_to(ROOT)),
            "routing_anchor_membership_sha256": sha256(args.routing),
            "existing_official_stops": str(args.existing.relative_to(ROOT)),
            "existing_official_stops_sha256": sha256(args.existing),
            "existing_stop_catchment_summary": str(args.catchment.relative_to(ROOT)),
            "existing_stop_catchment_summary_sha256": sha256(args.catchment),
            "gtfs_osm_matches": str(args.matches.relative_to(ROOT)),
            "gtfs_osm_matches_sha256": sha256(args.matches),
            "municipalities": str(args.municipalities.relative_to(ROOT)),
            "municipalities_sha256": sha256(args.municipalities),
        },
        "counts": {
            "route_ready_existing_clusters_before_spatial_scope": int(len(route_ready)),
            "core_existing_endpoint_clusters": int(len(endpoints)),
            "generation_eligible_existing_endpoint_clusters": int(len(endpoints)),
            "cross_source_review_required_clusters": int(
                endpoints["cross_source_review_required"].eq("true").sum()
            ),
            "outside_or_ambiguous_core_exclusions": int(len(exclusions)),
            "gtfs_municipality_label_spatial_mismatches_inside_core": int(len(mismatches)),
        },
        "per_municipality": per_municipality,
        "evidence_semantics": {
            "official_gtfs_is_primary_physical_stop_evidence": True,
            "osm_match_required_for_existing_stop": False,
            "osm_conflict_is_review_flag_not_automatic_veto": True,
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
            "exclusions": str(exclusion_path.relative_to(ROOT)),
            "exclusions_sha256": sha256(exclusion_path),
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
