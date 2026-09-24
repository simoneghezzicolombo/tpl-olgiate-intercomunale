#!/usr/bin/env python3
"""Build the Phase-2 V2 candidate-stop universe from validated building population.

This runner preserves the audited V1 stop-discovery and pruning contract while replacing
WorldPop grid cells with the validated dasymetric building-section-piece population layer.
It also uses the validated analysis envelope for candidate discovery and augments the
reference-period existing-stop universe with official Gate-D GTFS stop-cluster centroids
inside that envelope. No topology, service plan, ranking or final stop choice is produced.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import geopandas as gpd
import networkx as nx
import numpy as np
import pandas as pd
from pyproj import Transformer

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.phase2_stop_cluster import walk_distances_to_stop_records
from src.phase2_stop_core import (
    DISCOVERY_SAMPLE_M,
    DISCOVERY_SEED_RADIUS_M,
    GATE_B_COMMIT,
    GATE_D_COMPUTATIONAL_COMMIT,
    PRUNE_CANDIDATE_RADIUS_M,
    PRUNE_CATCHMENT_JACCARD,
    PRUNE_EXISTING_STOP_M,
    THRESHOLDS,
    UTM,
    WALK_CONNECTOR_KMH,
    cell_membership,
    cluster_existing_stops,
    load_walk_graph,
    multi_source_nearest_stop_distance,
    read_gtfs_zip,
    sha256,
    stop_route_lookup,
    walk_distances_to_stop_node,
)
from src.phase2_stop_metrics_v2 import build_candidate_metrics, geometric_overlap_prune
from src.phase2_stop_sources import (
    attach_point_to_walk_graph,
    existing_walk_time_for_anchors,
    extract_osm_anchors,
    extract_osm_point_settlements,
    nearest_seed_samples,
    sample_bus_eligible_roads,
    spatial_thin,
)

BUILDING_POPULATION_HEAD = "29203ad64c3e32e6164ef6997933eb5c5ff2d5b1"
BUILDING_POPULATION_ARTIFACT_ID = 9910900017
BUILDING_POPULATION_ARTIFACT_SHA256 = "4f5f0123ced2b763c2a063258ad724c43ac7f57ede707db3fa76e6a8977688b1"
ANALYSIS_ENVELOPE_COMPUTATIONAL_COMMIT = "8a4608a60ecb367535814d965822e7502ae31eb9"
CORE_CODES = {"097010", "097012", "097058", "097074", "097092"}


def _truthy(series: pd.Series) -> pd.Series:
    return series.astype(str).str.lower().isin({"true", "1"})


def _load_building_population_units(building_dir: Path, inverse: Transformer) -> tuple[pd.DataFrame, dict]:
    validation = json.loads((building_dir / "building_population_validation.json").read_text(encoding="utf-8"))
    if validation.get("status") != "PASS_BUILDING_POPULATION_BUILD":
        raise ValueError("Building-population artifact is not PASS_BUILDING_POPULATION_BUILD")
    if validation.get("final_network_selected") is not False or validation.get("final_stop_ranking_produced") is not False:
        raise ValueError("Building-population artifact violates downstream-neutral contract")

    frame = pd.read_csv(
        building_dir / "building_population_accessibility.csv",
        dtype={"building_id": str, "section_id": str, "municipality_code": str},
    )
    required = {
        "building_id", "section_id", "municipality_code",
        "piece_x_utm32", "piece_y_utm32", "building_piece_population_model",
        "nearest_graph_node_id", "connector_walk_min", "connector_within_limit",
        "covered_5min", "covered_8min", "covered_10min", "covered_12min",
        "resident_estimate_epistemic_status", "accessibility_epistemic_status",
    }
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"Building accessibility missing columns: {sorted(missing)}")

    frame["municipality_code"] = frame["municipality_code"].astype(str).str.zfill(6)
    if set(frame["municipality_code"]) != CORE_CODES:
        raise ValueError(f"Unexpected building-population core municipalities: {sorted(set(frame['municipality_code']))}")
    if frame["building_piece_population_model"].isna().any():
        raise ValueError("Building population contains null model population")
    if (pd.to_numeric(frame["building_piece_population_model"], errors="raise") < 0).any():
        raise ValueError("Building population contains negative population")

    frame["population_unit_id"] = frame["building_id"].astype(str) + "::SEC=" + frame["section_id"].astype(str)
    if frame["population_unit_id"].duplicated().any():
        raise ValueError("Building-section population-unit identity is not unique")

    lon, lat = inverse.transform(
        frame["piece_x_utm32"].to_numpy(float),
        frame["piece_y_utm32"].to_numpy(float),
    )
    units = pd.DataFrame(
        {
            "population_unit_id": frame["population_unit_id"],
            "cell_id": frame["population_unit_id"],
            "building_id": frame["building_id"],
            "section_id": frame["section_id"],
            "PRO_COM_T": frame["municipality_code"],
            "lon": lon,
            "lat": lat,
            "x_utm32": frame["piece_x_utm32"].astype(float),
            "y_utm32": frame["piece_y_utm32"].astype(float),
            "pop_calibrated_2025": frame["building_piece_population_model"].astype(float),
            "nearest_graph_node_id": frame["nearest_graph_node_id"].astype(int),
            "connector_walk_min": frame["connector_walk_min"].astype(float),
            "connector_within_limit": _truthy(frame["connector_within_limit"]),
            "covered_5min": _truthy(frame["covered_5min"]),
            "covered_8min": _truthy(frame["covered_8min"]),
            "covered_10min": _truthy(frame["covered_10min"]),
            "covered_12min": _truthy(frame["covered_12min"]),
            "population_unit_type": "BUILDING_SECTION_INTERSECTION",
            "population_model_status": frame["resident_estimate_epistemic_status"],
            "accessibility_source_status": frame["accessibility_epistemic_status"],
        }
    )

    reconciliation = pd.read_csv(
        building_dir / "building_population_municipal_reconciliation.csv",
        dtype={"municipality_code": str},
    )
    reconciliation["municipality_code"] = reconciliation["municipality_code"].astype(str).str.zfill(6)
    core_reconciliation = reconciliation[reconciliation["municipality_code"].isin(CORE_CODES)].copy()
    if set(core_reconciliation["municipality_code"]) != CORE_CODES:
        raise ValueError("Building-population reconciliation is missing one or more core municipalities")
    if not _truthy(core_reconciliation["reconciliation_pass"]).all():
        raise ValueError("Building-population municipal reconciliation failed")

    located = float(units["pop_calibrated_2025"].sum())
    total_posas = float(core_reconciliation["population_2025_posas_fact"].sum())
    residual = float(core_reconciliation["section_residual_population"].sum())
    if abs((located + residual) - total_posas) > 1e-6:
        raise ValueError(
            f"Core building population accounting mismatch: located={located}, residual={residual}, total={total_posas}"
        )
    metadata = {
        "population_total_posas_2025": total_posas,
        "population_located_building_pieces": located,
        "population_residual_unlocated": residual,
        "building_validation_core_coverage_pct_total_posas": validation["core_v2_coverage_pct_total_posas"],
    }
    return units, metadata


def _selected_analysis_boundary(path: Path, out: Path) -> Path:
    envelope = gpd.read_file(path)
    if "feature_role" not in envelope.columns:
        raise ValueError("Analysis envelope is missing feature_role")
    selected = envelope[envelope["feature_role"].astype(str).eq("ANALYSIS_ENVELOPE")].copy()
    if len(selected) != 1:
        raise ValueError(f"Expected exactly one ANALYSIS_ENVELOPE feature, found {len(selected)}")
    if selected.crs is None:
        selected = selected.set_crs(4326)
    boundary_path = out / "_analysis_envelope_selected.geojson"
    selected.to_file(boundary_path, driver="GeoJSON")
    return boundary_path


def _load_existing_stops(
    gate_b_dir: Path,
    gate_d_dir: Path,
    context_anchors_path: Path,
    walk_tree,
    ids,
    transformer,
) -> tuple[pd.DataFrame, dict[str, set[str]], int]:
    core = pd.read_csv(
        gate_b_dir / "gtfs_core_stops.csv",
        dtype={"stop_id": str, "PRO_COM_T": str},
    )
    if "PRO_COM_T" in core.columns:
        core["PRO_COM_T"] = core["PRO_COM_T"].astype(str).str.zfill(6)

    feeds = []
    for fname, label in [
        ("arriva_addabus_2025_2026.zip", "ARRIVA_ADDABUS"),
        ("lineelecco_2025_2026.zip", "LINEELECCO"),
    ]:
        feeds.append(read_gtfs_zip(gate_d_dir / "raw" / fname, label))
    route_lookup = stop_route_lookup(feeds)
    core["official_routes_reference_gtfs"] = core["stop_id"].map(
        lambda value: "|".join(sorted(route_lookup.get(str(value), set())))
    )
    core["source_scope"] = "GATE_B_CORE_GTFS_RECORD"
    core["stop_type"] = "EXISTING_OFFICIAL_STOP"
    core["epistemic_status"] = "FACT_OFFICIAL_GTFS_REFERENCE_PERIOD_NOT_CURRENT_SERVICE"

    context = pd.read_csv(context_anchors_path, dtype=str)
    context = context[
        context["anchor_class"].eq("GATE_D_VALIDATED_ANCHOR")
        & context["source_detail"].eq("OFFICIAL_GTFS_STOP_CLUSTER_CENTROID")
    ].copy()
    context_count = int(len(context))
    if not context.empty:
        context_points = pd.DataFrame(
            {
                "stop_id": context["source_record_id"].astype(str),
                "stop_name": context["source_name"].astype(str),
                "stop_lon": pd.to_numeric(context["lon"], errors="raise"),
                "stop_lat": pd.to_numeric(context["lat"], errors="raise"),
                "official_routes_reference_gtfs": context["routes_serving"].fillna("").astype(str),
                "PRO_COM_T": context["procom"].fillna("").astype(str).str.zfill(6),
                "source_scope": "ANALYSIS_ENVELOPE_GATE_D_GTFS_CLUSTER_CENTROID",
                "stop_type": "EXISTING_OFFICIAL_STOP",
                "epistemic_status": "FACT_OFFICIAL_GTFS_REFERENCE_PERIOD_CLUSTER_CENTROID",
            }
        )
        attached = attach_point_to_walk_graph(
            context_points.rename(columns={"stop_lon": "lon", "stop_lat": "lat"}).copy(),
            walk_tree,
            ids,
            transformer,
        )
        context_points["graph_node_id"] = attached["walk_graph_node_id"].astype(int)
        context_points["snap_distance_m"] = attached["walk_graph_connector_m"].astype(float)
        context_points["snap_ok"] = attached["walk_graph_snap_ok"].astype(bool)
        for column in core.columns:
            if column not in context_points.columns:
                context_points[column] = np.nan
        for column in context_points.columns:
            if column not in core.columns:
                core[column] = np.nan
        combined = pd.concat([core[context_points.columns], context_points], ignore_index=True)
    else:
        combined = core.copy()

    combined = cluster_existing_stops(combined)
    cluster_routes: dict[str, set[str]] = {}
    for cluster_id, group in combined.groupby("physical_cluster_id", sort=True):
        routes: set[str] = set()
        for text in group["official_routes_reference_gtfs"].fillna("").astype(str):
            routes.update(filter(None, text.split("|")))
        cluster_routes[str(cluster_id)] = routes
    return combined, cluster_routes, context_count


def _recompute_existing_coverage(units: pd.DataFrame, directed: nx.DiGraph, stops: pd.DataFrame) -> pd.DataFrame:
    reversed_graph = directed.reverse(copy=True)
    super_source = min(reversed_graph.nodes) - 1
    while super_source in reversed_graph:
        super_source -= 1
    reversed_graph.add_node(super_source)
    speed_m_per_min = WALK_CONNECTOR_KMH * 1000.0 / 60.0
    best_by_node: dict[int, float] = {}
    snapped = stops.loc[_truthy(stops["snap_ok"])].copy()
    for row in snapped.itertuples(index=False):
        node = int(row.graph_node_id)
        connector = float(row.snap_distance_m) / speed_m_per_min
        best_by_node[node] = min(best_by_node.get(node, float("inf")), connector)
    for node, connector in best_by_node.items():
        reversed_graph.add_edge(super_source, node, walk_min=connector)
    network = nx.single_source_dijkstra_path_length(reversed_graph, super_source, weight="walk_min")
    out = units.copy()
    net = out["nearest_graph_node_id"].map(network)
    out["walk_min_to_nearest_existing_stop_v2"] = (
        pd.to_numeric(net, errors="coerce") + out["connector_walk_min"].astype(float)
    )
    for threshold in THRESHOLDS:
        out[f"covered_{threshold}min"] = (
            out["connector_within_limit"].astype(bool)
            & out["walk_min_to_nearest_existing_stop_v2"].notna()
            & out["walk_min_to_nearest_existing_stop_v2"].le(threshold)
        )
    return out


def _municipality_columns(boundaries: gpd.GeoDataFrame) -> tuple[str, str | None]:
    code = next((c for c in ("procom", "PRO_COM_T", "PRO_COM", "PRO_COMUNE") if c in boundaries.columns), None)
    name = next((c for c in ("municipality_name", "COMUNE", "COMUNE_A", "DEN_COM") if c in boundaries.columns), None)
    if code is None:
        raise ValueError(f"Cannot identify municipality code column: {list(boundaries.columns)}")
    return code, name


def _assign_municipalities(points: pd.DataFrame, municipalities_path: Path) -> pd.DataFrame:
    result = points.copy()
    if result.empty:
        result["PRO_COM_T"] = []
        result["COMUNE"] = []
        result["analysis_role"] = []
        return result
    municipalities = gpd.read_file(municipalities_path).to_crs(4326)
    code_col, name_col = _municipality_columns(municipalities)
    keep_columns = [code_col] + ([name_col] if name_col else [])
    if "analysis_role" in municipalities.columns:
        keep_columns.append("analysis_role")
    keep_columns.append("geometry")
    geo = gpd.GeoDataFrame(
        result.copy(),
        geometry=gpd.points_from_xy(result["lon"], result["lat"]),
        crs=4326,
    )
    joined = gpd.sjoin(geo, municipalities[keep_columns], how="left", predicate="within")
    if joined.index.duplicated().any():
        joined = joined[~joined.index.duplicated(keep="first")]
    codes = joined[code_col].reindex(result.index)
    result["PRO_COM_T"] = codes.map(
        lambda value: str(value).zfill(6) if pd.notna(value) and str(value).strip() else ""
    )
    result["COMUNE"] = joined[name_col].reindex(result.index).fillna("").astype(str) if name_col else ""
    result["analysis_role"] = (
        joined["analysis_role"].reindex(result.index).fillna("OUTSIDE_CONTEXT_GEOMETRY").astype(str)
        if "analysis_role" in joined.columns else "UNSPECIFIED"
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gate-b-dir", required=True)
    parser.add_argument("--gate-d-dir", required=True)
    parser.add_argument("--building-dir", required=True)
    parser.add_argument("--analysis-envelope", required=True)
    parser.add_argument("--municipalities-context", required=True)
    parser.add_argument("--context-stops-anchors", required=True)
    parser.add_argument("--osm-pois", required=True)
    parser.add_argument("--osm-points", required=True)
    parser.add_argument("--od-summary", required=True)
    parser.add_argument("--output-dir", default="outputs/phase2/stop_universe_v2")
    args = parser.parse_args()

    gate_b_dir = Path(args.gate_b_dir)
    gate_d_dir = Path(args.gate_d_dir)
    building_dir = Path(args.building_dir)
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)

    transformer = Transformer.from_crs(4326, UTM, always_xy=True)
    inverse = Transformer.from_crs(UTM, 4326, always_xy=True)
    directed, undirected, _, ids, walk_tree = load_walk_graph(gate_b_dir)
    units, population_meta = _load_building_population_units(building_dir, inverse)

    selected_boundary = _selected_analysis_boundary(Path(args.analysis_envelope), out)
    stops, cluster_routes, context_stop_clusters_input = _load_existing_stops(
        gate_b_dir, gate_d_dir, Path(args.context_stops_anchors), walk_tree, ids, transformer
    )
    nearest_stop_dist, nearest_stop_source = multi_source_nearest_stop_distance(undirected, stops)
    units = _recompute_existing_coverage(units, directed, stops)

    municipality_inventory = pd.read_csv(
        ROOT / "outputs/phase2/analysis_envelope/municipalities_intersected.csv",
        dtype={"procom": str},
    )
    name_map = dict(zip(municipality_inventory["procom"].str.zfill(6), municipality_inventory["municipality_name"]))
    units["COMUNE"] = units["PRO_COM_T"].map(name_map).fillna("")

    catch_summary = []
    catch_rows = []
    for cluster_id, group in stops.groupby("physical_cluster_id", sort=True):
        snapped = group.loc[_truthy(group["snap_ok"])].copy()
        if snapped.empty:
            continue
        distances = walk_distances_to_stop_records(directed, snapped, cutoff=max(THRESHOLDS))
        for threshold in THRESHOLDS:
            mask, _ = cell_membership(units, distances, threshold)
            catch_summary.append(
                {
                    "physical_cluster_id": cluster_id,
                    "threshold_min": threshold,
                    "population_reachable_building_model": float(units.loc[mask, "pop_calibrated_2025"].sum()),
                    "population_total_posas_2025": population_meta["population_total_posas_2025"],
                    "population_located_building_pieces": population_meta["population_located_building_pieces"],
                    "population_residual_unlocated": population_meta["population_residual_unlocated"],
                    "population_unit_count": int(mask.sum()),
                    "gtfs_records_used_as_sources": int(len(snapped)),
                    "epistemic_status": "MODEL_OUTPUT_V2_BUILDING_POPULATION_GATE_B_WALK_GRAPH_MULTI_SOURCE_PHYSICAL_CLUSTER",
                }
            )
        mask, total = cell_membership(units, distances, 12)
        for index in units.index[mask]:
            catch_rows.append(
                {
                    "physical_cluster_id": cluster_id,
                    "population_unit_id": units.at[index, "population_unit_id"],
                    "walk_min_to_stop": float(total.at[index]),
                    "building_piece_population_model": float(units.at[index, "pop_calibrated_2025"]),
                }
            )
    pd.DataFrame(catch_summary).to_csv(out / "existing_stop_catchment_summary.csv", index=False)
    pd.DataFrame(catch_rows).to_csv(out / "existing_stop_catchment_units_12min.csv", index=False)

    gap = units[
        [
            "population_unit_id", "building_id", "section_id", "lat", "lon", "x_utm32", "y_utm32",
            "PRO_COM_T", "COMUNE", "pop_calibrated_2025", "walk_min_to_nearest_existing_stop_v2",
            "covered_5min", "covered_8min", "covered_10min", "covered_12min",
        ]
    ].copy()
    gap = gap.rename(columns={"pop_calibrated_2025": "building_piece_population_model"})
    for threshold in THRESHOLDS:
        gap[f"gap_{threshold}min"] = ~gap[f"covered_{threshold}min"].astype(bool)
    gap["epistemic_status"] = "MODEL_OUTPUT_V2_BUILDING_POPULATION_GATE_B_WALK_GRAPH"
    gap.to_csv(out / "accessibility_gap_building_pieces.csv", index=False)
    gpd.GeoDataFrame(gap, geometry=gpd.points_from_xy(gap["lon"], gap["lat"]), crs=4326).to_file(
        out / "accessibility_gap_building_pieces.geojson", driver="GeoJSON"
    )

    boundary_utm = gpd.read_file(selected_boundary).to_crs(UTM)
    destination_anchors = extract_osm_anchors(Path(args.osm_pois), boundary_utm, transformer)
    settlement_anchors = extract_osm_point_settlements(Path(args.osm_points), boundary_utm, transformer)
    anchors = pd.concat([destination_anchors, settlement_anchors], ignore_index=True).drop_duplicates("anchor_id")
    anchors = attach_point_to_walk_graph(anchors, walk_tree, ids, transformer)
    anchors["current_walk_min"] = existing_walk_time_for_anchors(anchors, directed, stops)
    anchors["current_gap_10min"] = anchors["current_walk_min"].gt(10) | anchors["current_walk_min"].isna()
    anchors.to_csv(out / "settlement_destination_anchors.csv", index=False)
    if not anchors.empty:
        gpd.GeoDataFrame(anchors, geometry=gpd.points_from_xy(anchors["lon"], anchors["lat"]), crs=4326).to_file(
            out / "settlement_destination_anchors.geojson", driver="GeoJSON"
        )

    samples, _ = sample_bus_eligible_roads(gate_d_dir / "osm_gate_d_structural.geojson", selected_boundary)
    sample_lon, sample_lat = inverse.transform(samples["x_utm32"].to_numpy(float), samples["y_utm32"].to_numpy(float))
    samples["lon"] = sample_lon
    samples["lat"] = sample_lat
    sample_attached = attach_point_to_walk_graph(
        pd.DataFrame(samples.drop(columns="geometry")), walk_tree, ids, transformer
    )
    samples = samples.loc[sample_attached["walk_graph_snap_ok"].to_numpy()].copy().reset_index(drop=True)

    gap8 = units.loc[~units["covered_8min"].astype(bool)].copy()
    seed_xy = list(gap8[["x_utm32", "y_utm32"]].to_numpy(float))
    seed_labels = [f"BUILDING_GAP8:{uid}" for uid in gap8["population_unit_id"].astype(str)]
    for anchor in anchors.itertuples(index=False):
        if np.isfinite(anchor.current_walk_min) and float(anchor.current_walk_min) <= 8:
            continue
        seed_xy.append(np.array([anchor.x_utm32, anchor.y_utm32], dtype=float))
        seed_labels.append(f"{anchor.anchor_type}_GAP8:{anchor.anchor_id}")
    if not seed_xy:
        raise ValueError("No uncovered building or anchor seeds available for V2 stop discovery")

    raw = nearest_seed_samples(samples, np.asarray(seed_xy, dtype=float), seed_labels)
    raw_unthinned_count = int(len(raw))
    raw = spatial_thin(raw, 140.0)
    metrics = build_candidate_metrics(
        raw, units, anchors, directed, ids, walk_tree, transformer,
        nearest_stop_dist, nearest_stop_source, cluster_routes,
    )
    metrics["pruned_near_existing_stop"] = metrics["nearest_official_stop_walk_network_m"].lt(PRUNE_EXISTING_STOP_M)
    has_gain = (
        metrics["population_additional_8min"].gt(1e-9)
        | metrics["population_additional_10min"].gt(1e-9)
        | metrics["settlement_additional_10min_count"].gt(0)
        | metrics["destination_additional_10min_count"].gt(0)
    )
    metrics["pruned_no_access_gain"] = ~has_gain
    pre = metrics.loc[~metrics["pruned_near_existing_stop"] & ~metrics["pruned_no_access_gain"]].copy().reset_index(drop=True)

    pre_sets = {}
    for index, row in pre.iterrows():
        distances = walk_distances_to_stop_node(
            directed, int(row.walk_graph_node_id), float(row.walk_graph_connector_min), 12
        )
        mask, _ = cell_membership(units, distances, 10)
        pre_sets[index] = set(units.loc[mask, "population_unit_id"].astype(str))
    final, prune_audit = geometric_overlap_prune(pre, pre_sets)
    final = final.sort_values(["y_utm32", "x_utm32", "osm_way_id"]).reset_index(drop=True)
    final["candidate_id"] = [f"P2V2S_{i:04d}" for i in range(1, len(final) + 1)]
    final["stop_type"] = "PROPOSED_STOP"
    final["physical_status"] = "FIELD_CHECK_PENDING"
    final["epistemic_status"] = "PROPOSED_STOP/FIELD_CHECK_PENDING"
    final["road_eligibility_status"] = "DERIVED_GATE_D_BUS_ELIGIBLE"
    final["candidate_status"] = "HYPOTHESIS_NOT_RECOMMENDATION"
    final["population_spatial_model"] = "DASYMETRIC_BUILDING_SECTION_INTERSECTION_V2"
    final["discovery_area_contract"] = "ANALYSIS_ENVELOPE_PLUS_INHERITED_150M_SITING_BUFFER"
    final["potential_interchange_with_reference_gtfs"] = (
        final["nearest_official_stop_walk_network_m"].le(300.0) & final["nearby_official_route_count"].gt(0)
    )
    final["interchange_evidence_status"] = "DERIVED_FROM_REFERENCE_PERIOD_GTFS_PROXIMITY_NOT_CURRENT_SERVICE_GUARANTEE"
    final["discovery_sample_spacing_m_assumption"] = DISCOVERY_SAMPLE_M
    final["candidate_pruning_radius_m_assumption"] = PRUNE_CANDIDATE_RADIUS_M
    final["source_gate_b_commit"] = GATE_B_COMMIT
    final["source_gate_d_commit"] = GATE_D_COMPUTATIONAL_COMMIT
    final["source_building_population_head"] = BUILDING_POPULATION_HEAD
    final["source_analysis_envelope_commit"] = ANALYSIS_ENVELOPE_COMPUTATIONAL_COMMIT
    final = _assign_municipalities(final, Path(args.municipalities_context))

    od = pd.read_csv(args.od_summary, dtype={"procom": str})
    od["procom"] = od["procom"].astype(str).str.zfill(6)
    odmap = od.set_index("procom")
    final["municipal_2021_resident_work_commuters_context"] = final["PRO_COM_T"].map(odmap["resident_commuters"])
    final["municipal_2021_outbound_workers_context"] = final["PRO_COM_T"].map(odmap["outbound_workers"])
    final["od_2021_context_status"] = "FACT_ISTAT_2021_WORK_COMMUTING_MUNICIPAL_ONLY_NOT_STOP_DEMAND"
    final.to_csv(out / "proposed_stop_candidates.csv", index=False)
    gpd.GeoDataFrame(final.copy(), geometry=gpd.points_from_xy(final["lon"], final["lat"]), crs=4326).to_file(
        out / "proposed_stop_candidates.geojson", driver="GeoJSON"
    )

    stops.to_csv(out / "existing_official_stops.csv", index=False)
    gpd.GeoDataFrame(stops.copy(), geometry=gpd.points_from_xy(stops["stop_lon"], stops["stop_lat"]), crs=4326).to_file(
        out / "existing_official_stops.geojson", driver="GeoJSON"
    )

    interchange_rows = []
    for cluster_id, group in stops.groupby("physical_cluster_id", sort=True):
        routes = cluster_routes.get(str(cluster_id), set())
        interchange_rows.append(
            {
                "physical_cluster_id": cluster_id,
                "stop_ids": "|".join(sorted(set(group["stop_id"].astype(str)))),
                "stop_names": "|".join(sorted(set(group["stop_name"].astype(str)))),
                "official_routes_reference_gtfs": "|".join(sorted(routes)),
                "route_count": len(routes),
                "interchange_candidate": len(routes) >= 2,
                "source_scopes": "|".join(sorted(set(group["source_scope"].astype(str)))),
                "epistemic_status": "DERIVED_FROM_OFFICIAL_GTFS_REFERENCE_PERIOD",
            }
        )
    pd.DataFrame(interchange_rows).to_csv(out / "interchange_opportunities.csv", index=False)
    prune_audit.to_csv(out / "candidate_pruning_audit.csv", index=False)

    candidate_units = []
    for row in final.itertuples(index=False):
        distances = walk_distances_to_stop_node(
            directed, int(row.walk_graph_node_id), float(row.walk_graph_connector_min), 10
        )
        mask, total = cell_membership(units, distances, 10)
        for index in units.index[mask]:
            candidate_units.append(
                {
                    "candidate_id": row.candidate_id,
                    "population_unit_id": units.at[index, "population_unit_id"],
                    "walk_min_to_candidate": float(total.at[index]),
                    "building_piece_population_model": float(units.at[index, "pop_calibrated_2025"]),
                    "already_covered_10min": bool(units.at[index, "covered_10min"]),
                    "municipality_code": units.at[index, "PRO_COM_T"],
                }
            )
    pd.DataFrame(candidate_units).to_csv(out / "proposed_stop_candidate_catchment_units_10min.csv", index=False)

    total_posas = population_meta["population_total_posas_2025"]
    located = population_meta["population_located_building_pieces"]
    baseline_total = {}
    baseline_located = {}
    for threshold in THRESHOLDS:
        covered_pop = float(units.loc[units[f"covered_{threshold}min"], "pop_calibrated_2025"].sum())
        baseline_total[str(threshold)] = covered_pop / total_posas * 100.0
        baseline_located[str(threshold)] = covered_pop / located * 100.0

    validation = {
        "status": "PASS_STOP_UNIVERSE_V2_BUILD",
        "scope": "CANDIDATE_STOP_UNIVERSE_V2_NOT_FINAL_NETWORK",
        "population_unit_type": "BUILDING_SECTION_INTERSECTION",
        "population_model_status": "MODEL_OUTPUT_DASYMETRIC_BUILDING_POPULATION",
        "gate_b_commit": GATE_B_COMMIT,
        "gate_d_computational_commit": GATE_D_COMPUTATIONAL_COMMIT,
        "building_population_head": BUILDING_POPULATION_HEAD,
        "building_population_artifact_id": BUILDING_POPULATION_ARTIFACT_ID,
        "building_population_artifact_sha256": BUILDING_POPULATION_ARTIFACT_SHA256,
        "analysis_envelope_computational_commit": ANALYSIS_ENVELOPE_COMPUTATIONAL_COMMIT,
        "analysis_envelope_rule": "METRIC_GUARD_ONLY",
        "candidate_discovery_area": "ANALYSIS_ENVELOPE_PLUS_INHERITED_150M_SITING_BUFFER",
        "core_population_total_posas_2025": total_posas,
        "core_population_located_building_pieces": located,
        "core_population_residual_unlocated": population_meta["population_residual_unlocated"],
        "population_units": int(len(units)),
        "baseline_coverage_pct_total_posas": baseline_total,
        "baseline_coverage_pct_located_building_population": baseline_located,
        "building_artifact_baseline_coverage_pct_total_posas": population_meta["building_validation_core_coverage_pct_total_posas"],
        "existing_official_stop_records": int(len(stops)),
        "existing_physical_stop_clusters": int(stops["physical_cluster_id"].nunique()),
        "existing_snapped_stop_records": int(_truthy(stops["snap_ok"]).sum()),
        "analysis_envelope_context_gtfs_cluster_centroids_input": context_stop_clusters_input,
        "osm_settlement_anchors": int((anchors["anchor_type"] == "SETTLEMENT").sum()) if not anchors.empty else 0,
        "osm_destination_anchors": int((anchors["anchor_type"] == "DESTINATION").sum()) if not anchors.empty else 0,
        "bus_eligible_discovery_samples_with_gate_b_walk_access": int(len(samples)),
        "uncovered_building_piece_seeds_8min": int(len(gap8)),
        "raw_seeded_candidates_before_geometry_thin": raw_unthinned_count,
        "raw_seeded_candidates": int(len(raw)),
        "pre_geometric_pruning_candidates": int(len(pre)),
        "final_proposed_candidates": int(len(final)),
        "principal_optimizer_catchment_threshold_min": 10,
        "thresholds_reported_min": list(THRESHOLDS),
        "existing_physical_cluster_catchment_method": "MULTI_SOURCE_ALL_SNAPPED_OFFICIAL_GTFS_RECORDS_OR_CLUSTER_CENTROIDS",
        "pruning_unitset_alignment": "STABLE_PRE_SORT_POPULATION_UNIT_KEYS",
        "new_stop_epistemic_status": "PROPOSED_STOP/FIELD_CHECK_PENDING",
        "residual_population_forced_to_buildings": False,
        "legacy_worldpop_cells_used_for_v2_candidate_population": False,
        "legacy_processed_population_used": False,
        "legacy_hardcoded_poi_dataset_used": False,
        "live_overpass_used": False,
        "final_network_selected": False,
        "final_stop_ranking_produced": False,
        "ranking_produced": False,
        "headway_modified": False,
        "timetable_modified": False,
        "budget_modified": False,
        "assumptions": {
            "discovery_sample_m": DISCOVERY_SAMPLE_M,
            "seed_radius_m": DISCOVERY_SEED_RADIUS_M,
            "near_existing_prune_m": PRUNE_EXISTING_STOP_M,
            "candidate_prune_radius_m": PRUNE_CANDIDATE_RADIUS_M,
            "catchment_jaccard_prune": PRUNE_CATCHMENT_JACCARD,
        },
        "limitations": [
            "Building resident counts are model outputs, not observed residents by address.",
            "Core POSAS residual population remains explicitly unlocated and cannot be attributed to candidate catchments.",
            "Reference-period GTFS stop and route evidence is not a guarantee of exact current service after 2026-06-08.",
            "OSM settlement/destination anchors are observations, not an exhaustive registry.",
            "No proposed stop is physically certified; every proposed point remains FIELD_CHECK_PENDING.",
            "ISTAT 2021 work OD remains municipal context and is not downscaled to stop demand.",
        ],
    }
    (out / "stop_universe_v2_validation.json").write_text(
        json.dumps(validation, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    generated = sorted(
        path for path in out.iterdir()
        if path.is_file() and not path.name.startswith("_") and path.name != "stop_universe_v2_checksums.sha256"
    )
    (out / "stop_universe_v2_checksums.sha256").write_text(
        "".join(f"{sha256(path)}  {path.name}\n" for path in generated), encoding="utf-8"
    )
    print(json.dumps(validation, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
