"""Spatial-only D184/D185 comparison on Nodo8's pinned RT028 substrate.

No comparison with the legacy V4 percentages or current trip-level guarantees.
The confirmed proposal must reproduce before a new baseline may be published.
"""
from pathlib import Path
import argparse
import csv
import hashlib
import json
import math
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
import numpy as np
import pandas as pd
from phase2_rt029_v4_substrate import validate_walk_matrix
from phase2_final_stop_pedestrian_accessibility_substrate_v3 import parse_osm_pedestrian_graph, EARTH_RADIUS_M
from scripts.phase2_audit_rt031_conditional_new_stop_access_v3 import scaled_core_weights, weighted_ratio
from scripts.phase2_audit_rt031_unique_line_walk_access_v3 import EXPECTED, pedestrian_time

WALK = ROOT / "cache/rt028-certified-34039162932"
MATRIX = WALK / "output/rt028_population_unit_stop_walk_matrix_v3.csv"
OSM = WALK / "input/rt028_osm_pedestrian_snapshot_v3.osm"
CLUSTERS = ROOT / "outputs/phase2/current_service_access_baseline_v4/current_service_physical_stop_clusters_v4.csv"
CURRENT = ROOT / "outputs/phase2/current_service_access_baseline_v4/current_service_access_baseline_v4_validation.json"
PROPOSAL = ROOT / "assets/nodo8-proposal.json"
ASSET = ROOT / "assets/nodo8-coverage-comparison.json"
POPULATION = WALK / "input/rt016_border_neutral_population_units_v3.csv"
LIMITS = (5, 8, 10)
PINNED_SOURCES = {
    CLUSTERS: "b9690e2814d93c62f26b104cd5713cb097ac64898b8d0c53bfbf64afff0404c9",
    CURRENT: "4308b5c5dcce7f58d598c891442f877b60aee09f9eac62fcf56b29ede1208306",
    POPULATION: "edba328d0214bec3a17357d2f21aba316b7ce4596b8ef47dad0c0ac92e45cd54",
}

def digest(path):
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()

def build_data():
    for path, expected in PINNED_SOURCES.items():
        if digest(path) != expected:
            raise ValueError("Pinned comparison source drift: " + str(path))
    if hashlib.sha256(MATRIX.read_bytes()).hexdigest() != EXPECTED["matrix"] or hashlib.sha256(OSM.read_bytes()).hexdigest() != EXPECTED["pedestrian_osm"]:
        raise ValueError("Pinned RT028 substrate drift")
    proposal = json.loads(PROPOSAL.read_text(encoding="utf-8"))
    current = json.loads(CURRENT.read_text(encoding="utf-8"))
    if current["contract"] != "PHASE2_CURRENT_SERVICE_STRUCTURAL_PHYSICAL_STOP_BASELINE_V4" or not current["gtfs_source_official"]:
        raise ValueError("Official structural stop provenance missing")
    columns = ["population_unit_id", "population_weight_2025", "population_scope",
               "population_municipality_code", "population_municipality_name",
               "stop_place_id", "stop_service_class", "walk_time_min", "reachability_status",
               "population_snap_node_id", "population_connector_distance_m"]
    raw = pd.read_csv(MATRIX, usecols=columns, dtype={key: str for key in
        ("population_unit_id", "population_weight_2025", "population_municipality_code", "stop_place_id", "population_snap_node_id")})
    raw["population_municipality_code"] = raw["population_municipality_code"].map(lambda value: str(int(value)))
    snaps = raw[["population_unit_id", "population_weight_2025", "population_snap_node_id", "population_connector_distance_m"]].drop_duplicates()
    if snaps["population_unit_id"].duplicated().any():
        raise ValueError("Ambiguous population metadata")
    substrate = validate_walk_matrix(raw)
    units = substrate.population_meta["population_unit_id"].astype(str).tolist()
    snap_map = snaps.set_index("population_unit_id")[["population_snap_node_id", "population_connector_distance_m"]].to_dict("index")
    core, weights = scaled_core_weights(substrate, snaps.set_index("population_unit_id")["population_weight_2025"].to_dict())
    codes = substrate.population_meta["population_municipality_code"].astype(str).to_numpy()
    graph = parse_osm_pedestrian_graph(OSM)
    if graph.graph_digest != "aaad8a16e4c3715161cce6f686acccbf29e4e9def57424e8ad02594c9a69f1f4":
        raise ValueError("Pedestrian graph drift")
    population = pd.read_csv(POPULATION, dtype={"unit_id": str}).set_index("unit_id").loc[units]
    core_lat = population["lat"].to_numpy()[core]
    core_lon = population["lon"].to_numpy()[core]
    # A deliberately weak geometric bound, verified against every frozen graph
    # edge. Coordinate variation in latitude, or half the variation in longitude,
    # cannot cost more than that edge or a connector in this local projection.
    xy = {key: (lat, lon) for key, lat, lon in zip(graph.node_ids, graph.latitudes, graph.longitudes)}
    def axis_bound(lat1, lon1, lat2, lon2):
        return EARTH_RADIUS_M * np.maximum(np.abs(np.radians(lat1 - lat2)), 0.5 * np.abs(np.radians(lon1 - lon2)))
    if np.max(np.abs(graph.latitudes)) >= 59 or abs(math.cos(graph._lat0)) < 0.5:
        raise ValueError("Coordinate lower-bound domain exceeded")
    for start, edges in graph.adjacency.items():
        for end, length in edges:
            if length + 1e-6 < axis_bound(*xy[start], *xy[end]):
                raise ValueError("Geometric bound not supported by a frozen edge")
    excluded_distant_points = []
    vectors = {}
    def point_time(lon, lat):
        key = (lon, lat)
        if key not in vectors:
            vectors[key] = pedestrian_time(graph, snap_map, units, lat, lon)[0]
        return vectors[key]
    proposed_time = np.full(len(units), math.inf)
    for site in proposal["sites"]:
        key = site["site_id"]
        if key in substrate.stop_index:
            vector = substrate.walk_time_matrix[:, substrate.stop_index[key]]
        else:
            if not site["proposed_new_site"]:
                raise ValueError("Existing proposal site missing in pinned matrix: " + key)
            vector = point_time(*site["coordinates_lon_lat"])
        proposed_time = np.minimum(proposed_time, vector)
    domains = {"TOTAL": core, **{m["code"]: core & (codes == m["code"]) for m in proposal["municipalities"]}}
    def percentages(times):
        return {code: {str(limit): 100 * float(weighted_ratio(times <= limit, weights, eligible))
                for limit in LIMITS} for code, eligible in domains.items()}
    reproduced = percentages(proposed_time)
    for code, values in reproduced.items():
        for limit, value in values.items():
            if abs(value - proposal["coverage"][code][limit]) > 1e-7:
                raise ValueError(f"Confirmed proposal coverage did not reproduce: {code}/{limit}: {value} != {proposal['coverage'][code][limit]}")
    baseline_time = np.full(len(units), math.inf)
    official_ids = set()
    with CLUSTERS.open(encoding="utf-8", newline="") as stream:
        clusters = list(csv.DictReader(stream))
    if len(clusters) != 44:
        raise ValueError("Official stop cluster universe drift")
    for row in clusters:
        ids = row["member_stop_ids"].split(";")
        coordinates = row["member_coordinates"].split(";")
        if len(ids) != len(coordinates):
            raise ValueError("Ambiguous official stop coordinates")
        for identity, coordinate in zip(ids, coordinates):
            lat, lon = map(float, coordinate.split(","))
            official_ids.add(identity)
            snap = graph.snap(lat, lon)
            if snap.status != "REACHABLE":
                bound = float(np.min(axis_bound(lat, lon, core_lat, core_lon)))
                if bound <= max(LIMITS) * 80:
                    raise ValueError("Unresolved official stop could affect core coverage: " + identity)
                excluded_distant_points.append({"stop_id": identity, "coordinates_lon_lat": [lon, lat],
                    "snap_reason": snap.reason, "minimum_core_distance_lower_bound_m": bound,
                    "cannot_affect_thresholds_min": list(LIMITS)})
                continue
            baseline_time = np.minimum(baseline_time, point_time(lon, lat))
    baseline = percentages(baseline_time)
    return {
        "contract": "nodo8_same_substrate_spatial_coverage_comparison_v1",
        "semantics": "Potential walk to official structural D184/D185 stop coordinates versus confirmed Nodo8 sites, same frozen RT028 graph, population, weights, connectors and thresholds. Not ridership, frequency, useful-direction access, stop-level current activation or a certified service improvement.",
        "baseline_label": "D184 / D185 · fermate del riferimento ufficiale",
        "baseline_trip_level_current_activation_certified": False,
        "temporary_bridge_disruption_included": False,
        "proposal_coverage_reproduced": True,
        "thresholds_min": list(LIMITS),
        "official_physical_cluster_count": len(clusters),
        "official_stop_identity_count": len(official_ids),
        "distant_unattached_points": excluded_distant_points,
        "all_unattached_points_proven_outside_core_thresholds": True,
        "sources": {key: {"path": path.relative_to(ROOT).as_posix(), "sha256": digest(path),
                    "sha256_semantics": "SOURCE_BYTES_WITH_CRLF_NORMALISED_TO_LF"} for key, path in
                    {"proposal": PROPOSAL, "walk_matrix": MATRIX, "pedestrian_osm": OSM, "population_coordinates": POPULATION, "official_clusters": CLUSTERS, "official_validation": CURRENT}.items()},
        "population_weight_total_not_headcount": sum(float(value) for value, use in zip(snaps.set_index("population_unit_id").loc[units, "population_weight_2025"], core) if use),
        "additional_resident_count_inferred": False,
        "baseline_percent": baseline,
        "proposal_percent": reproduced,
        "delta_percentage_points": {code: {limit: reproduced[code][limit] - baseline[code][limit] for limit in baseline[code]} for code in domains},
    }

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    payload = json.dumps(build_data(), ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n"
    if args.check:
        if ASSET.read_text(encoding="utf-8") != payload:
            raise SystemExit("Coverage comparison is stale")
    else:
        ASSET.write_text(payload, encoding="utf-8", newline="\n")
    print("Same-substrate spatial comparison validated")
