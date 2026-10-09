"""Independent active-network walking vectors on the frozen RT028/RT016 model.

The core map points join population coordinates by the exact RT016 unit ID.
Nodo8 inventory-site times retain their pinned RT028 pair values; proposed
sites and dated D184/D185 stop calls attach to the same pedestrian graph.
This asset is potential spatial access, not observed demand or current service.
"""
from pathlib import Path
import argparse
import hashlib
import heapq
import json
import math
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

import numpy as np
import pandas as pd
from phase2_final_stop_pedestrian_accessibility_substrate_v3 import parse_osm_pedestrian_graph
from phase2_rt029_v4_substrate import validate_walk_matrix
from scripts.build_nodo8_coverage_comparison import MATRIX, OSM, POPULATION, PROPOSAL, LIMITS, digest, PINNED_SOURCES
from scripts.phase2_audit_rt031_conditional_new_stop_access_v3 import scaled_core_weights, weighted_ratio
from scripts.phase2_audit_rt031_unique_line_walk_access_v3 import EXPECTED, pedestrian_time

CURRENT = ROOT / "assets/nodo8-current-simulation.json"
OSM_META = OSM.with_name("rt028_osm_pedestrian_snapshot_metadata_v3.json")
OUT = ROOT / "assets/nodo8-active-walk.json"
GRAPH_DIGEST = "aaad8a16e4c3715161cce6f686acccbf29e4e9def57424e8ad02594c9a69f1f4"
NETWORKS = ("NODO8", "D184", "D185")
COLUMNS = ("population_unit_id", "longitude", "latitude", "municipality_code", "population_weight_2025", *NETWORKS)


def source(path):
    return {"path": path.relative_to(ROOT).as_posix(), "sha256": digest(path),
            "sha256_semantics": "SOURCE_BYTES_WITH_CRLF_NORMALISED_TO_LF"}


def route_time(graph, snap_map, units, stops):
    """Weighted reverse multi-source Dijkstra equals min over all stop paths.

    A stop connector is the source cost and a population connector is added
    after shortest-path search. Distinct stop identities sharing a node retain
    their evidence; only the smallest connector is needed at that graph node.
    """
    distances = {}
    evidence = []
    for identity, coordinates in sorted(stops.items()):
        lon, lat = coordinates
        snap = graph.snap(lat, lon)
        evidence.append({"stop_id": identity, "coordinates_lon_lat": coordinates,
                         "snap_status": snap.status, "snap_reason": snap.reason,
                         "graph_node_id": snap.node_id, "connector_distance_m": snap.connector_distance_m})
        if snap.status == "REACHABLE" and snap.node_id:
            distances[snap.node_id] = min(distances.get(snap.node_id, math.inf), float(snap.connector_distance_m))
    queue = [(distance, node) for node, distance in distances.items()]
    heapq.heapify(queue)
    while queue:
        distance, node = heapq.heappop(queue)
        if distance != distances.get(node):
            continue
        for previous, length in graph.reverse_adjacency.get(node, []):
            candidate = distance + float(length)
            if candidate < distances.get(previous, math.inf):
                distances[previous] = candidate
                heapq.heappush(queue, (candidate, previous))
    values = np.asarray([
        (float(snap_map[unit]["population_connector_distance_m"])
         + distances.get(str(snap_map[unit]["population_snap_node_id"]), math.inf)) / 80
        for unit in units], dtype=float)
    return values, evidence


def build_data():
    if hashlib.sha256(MATRIX.read_bytes()).hexdigest() != EXPECTED["matrix"]:
        raise ValueError("Pinned RT028 walk matrix drift")
    if hashlib.sha256(OSM.read_bytes()).hexdigest() != EXPECTED["pedestrian_osm"]:
        raise ValueError("Pinned RT028 pedestrian snapshot drift")
    if digest(POPULATION) != PINNED_SOURCES[POPULATION]:
        raise ValueError("Pinned RT016 population source drift")
    proposal = json.loads(PROPOSAL.read_text(encoding="utf-8"))
    current = json.loads(CURRENT.read_text(encoding="utf-8"))
    if (current.get("contract") != "nodo8_existing_service_dated_simulation_v1"
            or current.get("service_date") != "2026-05-06"
            or current.get("route_counts") != {"D184": 15, "D185": 19}
            or len(current.get("trips", [])) != 34
            or current["source"]["sha256"] != "f890c393b909a40ae9500ab5acba71166cdfc5af3d42be92f55a92d92927553b"
            or any(current["semantics"][key] is not False for key in ("live", "latest_2026_27_timetable", "vehicle_identity_certified"))):
        raise ValueError("Dated D184/D185 source contract drift")
    columns = ["population_unit_id", "population_weight_2025", "population_scope",
               "population_municipality_code", "population_municipality_name",
               "stop_place_id", "stop_service_class", "walk_time_min", "reachability_status",
               "population_snap_node_id", "population_connector_distance_m"]
    raw = pd.read_csv(MATRIX, usecols=columns, dtype={key: str for key in
        ("population_unit_id", "population_weight_2025", "population_municipality_code", "stop_place_id", "population_snap_node_id")})
    raw["population_municipality_code"] = raw["population_municipality_code"].map(lambda value: str(int(value)))
    snaps = raw[["population_unit_id", "population_weight_2025", "population_snap_node_id", "population_connector_distance_m"]].drop_duplicates()
    if snaps["population_unit_id"].duplicated().any():
        raise ValueError("Ambiguous population unit snap or weight")
    substrate = validate_walk_matrix(raw)
    units = substrate.population_meta["population_unit_id"].astype(str).tolist()
    snap_map = snaps.set_index("population_unit_id")[["population_snap_node_id", "population_connector_distance_m"]].to_dict("index")
    weight_map = snaps.set_index("population_unit_id")["population_weight_2025"].to_dict()
    core, weights = scaled_core_weights(substrate, weight_map)
    codes = substrate.population_meta["population_municipality_code"].astype(str).to_numpy()
    population = pd.read_csv(POPULATION, dtype={"unit_id": str, "municipality_code": str, "population_weight_2025": str})
    if population["unit_id"].duplicated().any() or set(population["unit_id"]) != set(units):
        raise ValueError("RT016 coordinate source and RT028 population ID universe differ")
    population = population.set_index("unit_id").loc[units]
    for index, unit in enumerate(units):
        row = population.loc[unit]
        if (str(int(row["municipality_code"])) != codes[index]
                or row["population_scope"] != substrate.population_meta.iloc[index]["population_scope"]
                # Both pinned exports serialise the same weight with slightly
                # different final decimal digits. RT028 weights remain the
                # authoritative coverage denominator; require numeric agreement.
                or not math.isclose(float(row["population_weight_2025"]), float(weight_map[unit]), rel_tol=1e-14, abs_tol=1e-12)
                or not all(math.isfinite(float(row[axis])) for axis in ("lon", "lat"))):
            raise ValueError("RT016/RT028 exact-ID metadata mismatch: " + unit)
    if int(core.sum()) != 4283 or set(codes[core]) != {m["code"] for m in proposal["municipalities"]}:
        raise ValueError("Five-municipality core population universe drift")
    graph = parse_osm_pedestrian_graph(OSM)
    osm_meta = json.loads(OSM_META.read_text(encoding="utf-8"))
    if graph.graph_digest != GRAPH_DIGEST or osm_meta["snapshot_timestamp"] != "2026-09-06T12:00:00Z":
        raise ValueError("Frozen pedestrian graph identity or snapshot date drift")
    proposed_time = np.full(len(units), math.inf)
    certified_time = np.full(len(units), math.inf)
    nodo8_evidence = []
    for site in proposal["sites"]:
        identity = site["site_id"]
        if identity in substrate.stop_index:
            # Preserve the full numeric RT028 pair value; the existing coverage
            # helper uses float32 for its matrix. Verify both threshold masks.
            rows = raw[raw["stop_place_id"] == identity].set_index("population_unit_id").loc[units]
            vector = np.where(rows["reachability_status"] == "REACHABLE", pd.to_numeric(rows["walk_time_min"], errors="coerce"), math.inf)
            certified = substrate.walk_time_matrix[:, substrate.stop_index[identity]]
            nodo8_evidence.append({"site_id": identity, "method": "PINNED_RT028_PAIR_VALUES"})
        else:
            if not site["proposed_new_site"]:
                raise ValueError("Existing Nodo8 site absent from RT028 matrix: " + identity)
            lon, lat = site["coordinates_lon_lat"]
            vector, snap = pedestrian_time(graph, snap_map, units, lat, lon)
            certified = vector
            nodo8_evidence.append({"site_id": identity, "method": "SAME_RT028_GRAPH_NEW_SITE", "coordinates_lon_lat": [lon, lat], "snap": snap})
        proposed_time = np.minimum(proposed_time, vector)
        certified_time = np.minimum(certified_time, certified)
    domains = {"TOTAL": core, **{m["code"]: core & (codes == m["code"]) for m in proposal["municipalities"]}}
    def percentages(values):
        return {code: {str(limit): 100 * float(weighted_ratio(values <= limit, weights, eligible))
                       for limit in LIMITS} for code, eligible in domains.items()}
    reproduced = percentages(proposed_time)
    for limit in LIMITS:
        if not np.array_equal(proposed_time[core] <= limit, certified_time[core] <= limit):
            raise ValueError("Full-precision Nodo8 threshold mask differs from certified matrix")
    for code, values in reproduced.items():
        for limit, value in values.items():
            if abs(value - proposal["coverage"][code][limit]) > 1e-7:
                raise ValueError(f"Confirmed Nodo8 coverage does not reproduce: {code}/{limit}")
    vectors = {"NODO8": proposed_time}
    network_evidence = {"NODO8": {"site_count": len(proposal["sites"]), "sites": nodo8_evidence}}
    for route in NETWORKS[1:]:
        stops = {}
        trips = [trip for trip in current["trips"] if trip["route"] == route]
        if len(trips) != current["route_counts"][route]:
            raise ValueError("Dated route trip inventory drift")
        for trip in trips:
            for call in trip["calls"]:
                identity, coordinates = call["stop_id"], call["coordinates"]
                if identity in stops and stops[identity] != coordinates:
                    raise ValueError("Dated stop coordinates conflict: " + identity)
                if len(coordinates) != 2 or not all(math.isfinite(float(value)) for value in coordinates):
                    raise ValueError("Invalid dated stop coordinate")
                stops[identity] = coordinates
        vectors[route], evidence = route_time(graph, snap_map, units, stops)
        network_evidence[route] = {"dated_trip_count": len(trips), "stop_identity_count": len(stops),
                                   "attached_stop_count": sum(stop["snap_status"] == "REACHABLE" for stop in evidence), "stops": evidence}
    rows = []
    for index in np.flatnonzero(core):
        unit = units[index]
        row = population.loc[unit]
        rows.append([unit, float(row["lon"]), float(row["lat"]), codes[index], float(weight_map[unit]),
                     *[float(vectors[network][index]) if math.isfinite(float(vectors[network][index])) else None for network in NETWORKS]])
    return {
        "contract": "nodo8_active_network_population_walk_v1",
        "semantics": "Potential walking minutes from exact RT016 core population points to enabled Nodo8 and/or dated D184/D185 stop networks, on pinned RT028. Minimum over enabled vectors. Null means no modelled connection, including stops outside the frozen graph or blocked connectors. Not observed demand, GPS, frequency, direction, latest timetable or boarding authorisation.",
        "population_scope": "core", "population_unit_count": len(rows), "full_rt016_population_unit_count": len(units),
        "population_coordinate_join": "EXACT_RT016_UNIT_ID_TO_RT028_POPULATION_UNIT_ID",
        "walk_speed_m_per_min": 80, "max_connector_m": 90, "connectors_included": ["population", "stop"],
        "null_semantics": "UNREACHABLE_OR_UNATTACHED_IN_FROZEN_RT028_MODEL",
        "network_names": list(NETWORKS), "union_rule": "MINIMUM_OF_ENABLED_NETWORK_TIMES", "s8_contributes": False,
        "current_service_date": current["service_date"], "pedestrian_snapshot_timestamp": osm_meta["snapshot_timestamp"],
        "pedestrian_graph_digest": graph.graph_digest,
        "sources": {name: source(path) for name, path in {"population_coordinates": POPULATION, "walk_matrix": MATRIX,
                    "pedestrian_osm": OSM, "pedestrian_snapshot_metadata": OSM_META, "proposal": PROPOSAL, "dated_current_service": CURRENT}.items()},
        "dated_current_gtfs_source": current["source"],
        "limitations": {"access_is_observed_demand": False, "live_or_gps": False, "latest_2026_27_timetable": False,
                        "useful_direction_or_frequency_certified": False, "physical_boarding_authorised": False,
                        "external_population_included": False, "outside_frozen_graph_stops_rematerialized": False},
        "network_evidence": network_evidence,
        "thresholds_min": list(LIMITS), "proposal_coverage_reproduced": True, "nodo8_percent": reproduced,
        "network_percent": {network: percentages(values) for network, values in vectors.items()},
        "columns": list(COLUMNS), "rows": rows,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    data = build_data()
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n"
    if args.check:
        if OUT.read_text(encoding="utf-8") != payload:
            raise SystemExit("Active-network walk asset is stale")
    else:
        OUT.write_text(payload, encoding="utf-8", newline="\n")
    print(f"Active-network walk validated: {data['population_unit_count']} exact core IDs; Nodo8 5/8/10 coverage reproduced")
