from __future__ import annotations

import hashlib
import heapq
import json
import math
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree
from shapely.geometry import LineString, Point, Polygon
from shapely.strtree import STRtree

EARTH_RADIUS_M = 6_371_008.8
DEFAULT_WALK_SPEED_KMH = 4.8
DEFAULT_MAX_CONNECTOR_M = 90.0
EXPECTED_STOP_COUNT = 36
EXPECTED_CONVENTIONAL_COUNT = 35
EXPECTED_SPECIAL_COUNT = 1
SPECIAL_STOP_ID = "SPECIAL::CASA_DI_COMUNITA_OLGIATE"
FORBIDDEN_CANDIDATE_TOKENS = (
    "candidate", "backbone", "structure_id", "rank", "score",
    "primary", "runner_up", "winner", "pareto",
)

PROHIBITED_HIGHWAYS = {
    "motorway", "motorway_link", "trunk", "trunk_link",
    "construction", "proposed", "raceway",
}
BLOCKING_ACCESS = {"no", "private"}
FOOT_OVERRIDE_ALLOW = {"yes", "designated", "permissive", "destination"}
BLOCKING_BARRIERS = {
    "wall", "fence", "retaining_wall", "hedge", "ditch",
    "jersey_barrier", "chain", "block", "turnstile",
}


class RT028ContractError(ValueError):
    pass


@dataclass(frozen=True)
class SnapResult:
    status: str
    node_id: str | None
    connector_distance_m: float | None
    reason: str | None


@dataclass
class PedestrianGraph:
    node_ids: tuple[str, ...]
    latitudes: np.ndarray
    longitudes: np.ndarray
    adjacency: dict[str, list[tuple[str, float]]]
    reverse_adjacency: dict[str, list[tuple[str, float]]]
    blocked_node_ids: frozenset[str]
    obstacle_geometries: tuple[object, ...]
    osm_sha256: str
    graph_digest: str

    def __post_init__(self) -> None:
        if len(self.node_ids) == 0:
            raise RT028ContractError("pedestrian graph has no routable nodes")
        lat0 = math.radians(float(np.mean(self.latitudes)))
        self._xy = np.column_stack(
            (
                EARTH_RADIUS_M * np.radians(self.longitudes) * math.cos(lat0),
                EARTH_RADIUS_M * np.radians(self.latitudes),
            )
        )
        self._lat0 = lat0
        self._tree = cKDTree(self._xy)
        self._obstacle_tree = STRtree(list(self.obstacle_geometries)) if self.obstacle_geometries else None

    def _xy_for(self, lat: float, lon: float) -> np.ndarray:
        return np.array([
            EARTH_RADIUS_M * math.radians(float(lon)) * math.cos(self._lat0),
            EARTH_RADIUS_M * math.radians(float(lat)),
        ])

    def snap(self, lat: float, lon: float, *, max_connector_m: float = DEFAULT_MAX_CONNECTOR_M, k: int = 16) -> SnapResult:
        if not math.isfinite(float(lat)) or not math.isfinite(float(lon)):
            return SnapResult("UNREACHABLE", None, None, "INVALID_COORDINATE")
        kk = min(max(1, int(k)), len(self.node_ids))
        distances, indices = self._tree.query(self._xy_for(lat, lon), k=kk)
        distances = np.atleast_1d(distances)
        indices = np.atleast_1d(indices)
        any_within = False
        blocked_by_barrier = False
        for dist, idx in sorted(zip(distances.tolist(), indices.tolist()), key=lambda x: (x[0], self.node_ids[int(x[1])])):
            if float(dist) > float(max_connector_m):
                continue
            any_within = True
            node_id = self.node_ids[int(idx)]
            if node_id in self.blocked_node_ids:
                blocked_by_barrier = True
                continue
            target_lat = float(self.latitudes[int(idx)])
            target_lon = float(self.longitudes[int(idx)])
            connector = LineString([(float(lon), float(lat)), (target_lon, target_lat)])
            if self._obstacle_tree is not None and connector.length > 0:
                obstacle_indices = self._obstacle_tree.query(connector)
                unsafe = False
                for obstacle_idx in np.atleast_1d(obstacle_indices).tolist():
                    obstacle = self.obstacle_geometries[int(obstacle_idx)]
                    if connector.crosses(obstacle) or connector.within(obstacle):
                        unsafe = True
                        break
                    inter = connector.intersection(obstacle)
                    if not inter.is_empty:
                        endpoint = Point(target_lon, target_lat)
                        if not inter.equals(endpoint) and not (
                            hasattr(inter, "geoms")
                            and all(g.equals(endpoint) for g in inter.geoms)
                        ):
                            unsafe = True
                            break
                if unsafe:
                    blocked_by_barrier = True
                    continue
            return SnapResult("REACHABLE", node_id, float(dist), None)
        if blocked_by_barrier:
            return SnapResult("UNREACHABLE", None, None, "CONNECTOR_BLOCKED_BY_BARRIER")
        if any_within:
            return SnapResult("UNREACHABLE", None, None, "NO_ROUTABLE_NODE")
        return SnapResult("UNREACHABLE", None, None, "NO_ACCESSIBLE_NODE_WITHIN_MAX_CONNECTOR")


def _sha256_path(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(min(1.0, math.sqrt(a)))


def _allows_foot(tags: Mapping[str, str]) -> bool:
    highway = tags.get("highway")
    if not highway or highway in PROHIBITED_HIGHWAYS:
        return False
    foot = tags.get("foot", "").strip().lower()
    access = tags.get("access", "").strip().lower()
    if foot in BLOCKING_ACCESS:
        return False
    if access in BLOCKING_ACCESS and foot not in FOOT_OVERRIDE_ALLOW:
        return False
    return True


def _barrier_blocks(tags: Mapping[str, str]) -> bool:
    barrier = tags.get("barrier", "").strip().lower()
    if not barrier:
        return False
    foot = tags.get("foot", "").strip().lower()
    access = tags.get("access", "").strip().lower()
    if foot in FOOT_OVERRIDE_ALLOW:
        return False
    if foot in BLOCKING_ACCESS or access in BLOCKING_ACCESS:
        return True
    return barrier in BLOCKING_BARRIERS


def parse_osm_pedestrian_graph(path: str | Path) -> PedestrianGraph:
    path = Path(path)
    nodes: dict[str, tuple[float, float, dict[str, str]]] = {}
    ways: list[tuple[list[str], dict[str, str]]] = []
    for event, elem in ET.iterparse(path, events=("end",)):
        tag = elem.tag.split("}")[-1]
        if tag == "node":
            node_id = str(elem.attrib["id"])
            tags = {str(t.attrib["k"]): str(t.attrib["v"]) for t in elem.findall("tag")}
            nodes[node_id] = (float(elem.attrib["lat"]), float(elem.attrib["lon"]), tags)
            elem.clear()
        elif tag == "way":
            refs = [str(nd.attrib["ref"]) for nd in elem.findall("nd")]
            tags = {str(t.attrib["k"]): str(t.attrib["v"]) for t in elem.findall("tag")}
            if refs:
                ways.append((refs, tags))
            elem.clear()

    blocked = {nid for nid, (_, _, tags) in nodes.items() if _barrier_blocks(tags)}
    adjacency: dict[str, list[tuple[str, float]]] = {}
    reverse: dict[str, list[tuple[str, float]]] = {}
    obstacle_geometries: list[object] = []
    used_nodes: set[str] = set()

    def add_edge(u: str, v: str, length: float) -> None:
        adjacency.setdefault(u, []).append((v, length))
        reverse.setdefault(v, []).append((u, length))
        adjacency.setdefault(v, [])
        reverse.setdefault(u, [])

    for refs, tags in ways:
        valid_coords = [(nodes[r][1], nodes[r][0]) for r in refs if r in nodes]
        if len(valid_coords) >= 2:
            obstacle = (
                "barrier" in tags
                or "railway" in tags
                or "waterway" in tags
                or tags.get("natural") == "water"
                or "water" in tags
            )
            if obstacle:
                try:
                    if valid_coords[0] == valid_coords[-1] and len(valid_coords) >= 4 and (
                        tags.get("natural") == "water" or "water" in tags
                    ):
                        obstacle_geometries.append(Polygon(valid_coords))
                    else:
                        obstacle_geometries.append(LineString(valid_coords))
                except Exception:
                    pass
        if not _allows_foot(tags):
            continue
        oneway_foot = tags.get("oneway:foot", "").strip().lower()
        directed = oneway_foot in {"yes", "1", "true"}
        reverse_directed = oneway_foot in {"-1", "reverse"}
        for a, b in zip(refs, refs[1:]):
            if a not in nodes or b not in nodes or a in blocked or b in blocked:
                continue
            lat1, lon1, _ = nodes[a]
            lat2, lon2, _ = nodes[b]
            length = _haversine_m(lat1, lon1, lat2, lon2)
            if not math.isfinite(length) or length <= 0:
                continue
            used_nodes.update((a, b))
            if reverse_directed:
                add_edge(b, a, length)
            else:
                add_edge(a, b, length)
                if not directed:
                    add_edge(b, a, length)

    routable = sorted(n for n in used_nodes if adjacency.get(n) or reverse.get(n))
    if not routable:
        raise RT028ContractError("OSM snapshot contains no routable pedestrian edges")
    latitudes = np.array([nodes[n][0] for n in routable], dtype=float)
    longitudes = np.array([nodes[n][1] for n in routable], dtype=float)
    osm_sha = _sha256_path(path)

    edge_rows = []
    for u in sorted(adjacency):
        for v, length in sorted(adjacency[u], key=lambda x: (x[0], x[1])):
            edge_rows.append(f"{u}|{v}|{length:.6f}")
    graph_digest = hashlib.sha256(
        (osm_sha + "\n" + "\n".join(edge_rows)).encode("utf-8")
    ).hexdigest()

    routable_set = set(routable)
    adj2 = {
        u: sorted([(v, d) for v, d in adjacency.get(u, []) if v in routable_set], key=lambda x: (x[0], x[1]))
        for u in routable
    }
    rev2 = {
        u: sorted([(v, d) for v, d in reverse.get(u, []) if v in routable_set], key=lambda x: (x[0], x[1]))
        for u in routable
    }
    return PedestrianGraph(
        node_ids=tuple(routable),
        latitudes=latitudes,
        longitudes=longitudes,
        adjacency=adj2,
        reverse_adjacency=rev2,
        blocked_node_ids=frozenset(blocked),
        obstacle_geometries=tuple(obstacle_geometries),
        osm_sha256=osm_sha,
        graph_digest=graph_digest,
    )


def _validate_stops(stops: pd.DataFrame) -> pd.DataFrame:
    req = {"stop_place_id", "stop_name", "municipality", "lat", "lon", "service_class"}
    missing = req - set(stops.columns)
    if missing:
        raise RT028ContractError(f"stop inventory missing columns: {sorted(missing)}")
    if len(stops) != EXPECTED_STOP_COUNT:
        raise RT028ContractError(f"final stop inventory must contain exactly 36 rows, got {len(stops)}")
    if stops["stop_place_id"].astype(str).duplicated().any():
        raise RT028ContractError("duplicate stop_place_id")
    classes = stops["service_class"].astype(str)
    if int((classes == "CONVENTIONAL_TPL").sum()) != EXPECTED_CONVENTIONAL_COUNT:
        raise RT028ContractError("final stop inventory must contain exactly 35 CONVENTIONAL_TPL stops")
    special = stops.loc[classes == "SPECIAL_SERVICE", "stop_place_id"].astype(str).tolist()
    if special != [SPECIAL_STOP_ID]:
        raise RT028ContractError("final stop inventory must contain exactly the frozen Casa di Comunita SPECIAL_SERVICE stop")
    if len(special) != EXPECTED_SPECIAL_COUNT:
        raise RT028ContractError("final stop inventory must contain exactly one SPECIAL_SERVICE stop")
    for c in ("lat", "lon"):
        vals = pd.to_numeric(stops[c], errors="coerce")
        if vals.isna().any():
            raise RT028ContractError(f"invalid stop {c}")
    return stops.copy()


def _validate_population(pop: pd.DataFrame) -> pd.DataFrame:
    req = {
        "unit_id", "lat", "lon", "municipality_code", "municipality_name",
        "population_weight_2025", "population_scope",
    }
    missing = req - set(pop.columns)
    if missing:
        raise RT028ContractError(f"population universe missing columns: {sorted(missing)}")
    if pop.empty:
        raise RT028ContractError("population universe must not be empty")
    if pop["unit_id"].astype(str).duplicated().any():
        raise RT028ContractError("duplicate population unit_id")
    scopes = set(pop["population_scope"].astype(str))
    if not scopes.issubset({"core", "external"}) or "core" not in scopes:
        raise RT028ContractError(f"invalid population_scope values: {sorted(scopes)}")
    weights = pd.to_numeric(pop["population_weight_2025"], errors="coerce")
    if weights.isna().any() or (weights < 0).any():
        raise RT028ContractError("population weights must be finite and non-negative")
    return pop.copy()


def _assert_no_candidate_columns(frames: Iterable[pd.DataFrame]) -> None:
    for frame in frames:
        for col in frame.columns:
            low = str(col).lower()
            if any(token in low for token in FORBIDDEN_CANDIDATE_TOKENS):
                raise RT028ContractError(f"candidate/network-selection field forbidden in RT-028: {col}")


def _dijkstra_to_stop(reverse_adjacency: Mapping[str, list[tuple[str, float]]], stop_node: str) -> dict[str, float]:
    dist: dict[str, float] = {stop_node: 0.0}
    queue: list[tuple[float, str]] = [(0.0, stop_node)]
    while queue:
        current, u = heapq.heappop(queue)
        if current != dist.get(u):
            continue
        for v, weight in reverse_adjacency.get(u, []):
            nd = current + float(weight)
            if nd < dist.get(v, math.inf):
                dist[v] = nd
                heapq.heappush(queue, (nd, v))
    return dist


def _pair_id(unit_id: str, stop_id: str, graph_digest: str) -> str:
    digest = hashlib.sha256(f"{unit_id}|{stop_id}|{graph_digest}".encode("utf-8")).hexdigest()[:20]
    return f"RT028::{digest}"


def canonical_dataframe_sha256(df: pd.DataFrame, sort_cols: list[str]) -> str:
    stable = df.sort_values(sort_cols, kind="mergesort").reset_index(drop=True)
    return hashlib.sha256(stable.to_csv(index=False, lineterminator="\n").encode("utf-8")).hexdigest()


def build_atomic_walk_matrix(
    *,
    graph: PedestrianGraph,
    population_units: pd.DataFrame,
    stops: pd.DataFrame,
    walk_speed_kmh: float = DEFAULT_WALK_SPEED_KMH,
    max_connector_m: float = DEFAULT_MAX_CONNECTOR_M,
    lineage: Mapping[str, str] | None = None,
) -> tuple[pd.DataFrame, dict]:
    population_units = _validate_population(population_units)
    stops = _validate_stops(stops)
    _assert_no_candidate_columns((population_units, stops))
    if walk_speed_kmh <= 0 or not math.isfinite(float(walk_speed_kmh)):
        raise RT028ContractError("walk_speed_kmh must be positive")
    if max_connector_m <= 0:
        raise RT028ContractError("max_connector_m must be positive")

    pop_sorted = population_units.sort_values("unit_id", kind="mergesort").reset_index(drop=True)
    stop_sorted = stops.sort_values("stop_place_id", kind="mergesort").reset_index(drop=True)
    pop_snaps = {
        str(r.unit_id): graph.snap(float(r.lat), float(r.lon), max_connector_m=max_connector_m)
        for r in pop_sorted.itertuples(index=False)
    }
    stop_snaps = {
        str(r.stop_place_id): graph.snap(float(r.lat), float(r.lon), max_connector_m=max_connector_m)
        for r in stop_sorted.itertuples(index=False)
    }

    speed_mps = float(walk_speed_kmh) * 1000.0 / 3600.0
    stop_distances: dict[str, dict[str, float]] = {}
    for stop_id, snap in stop_snaps.items():
        if snap.status == "REACHABLE" and snap.node_id is not None:
            stop_distances[stop_id] = _dijkstra_to_stop(graph.reverse_adjacency, snap.node_id)

    lineage = dict(lineage or {})
    rows: list[dict] = []
    for p in pop_sorted.itertuples(index=False):
        unit_id = str(p.unit_id)
        ps = pop_snaps[unit_id]
        for s in stop_sorted.itertuples(index=False):
            stop_id = str(s.stop_place_id)
            ss = stop_snaps[stop_id]
            row = {
                "pair_id": _pair_id(unit_id, stop_id, graph.graph_digest),
                "population_unit_id": unit_id,
                "population_weight_2025": float(p.population_weight_2025),
                "population_scope": str(p.population_scope),
                "population_municipality_code": str(p.municipality_code),
                "population_municipality_name": str(p.municipality_name),
                "stop_place_id": stop_id,
                "stop_name": str(s.stop_name),
                "stop_municipality": str(s.municipality),
                "stop_service_class": str(s.service_class),
                "population_snap_node_id": ps.node_id or "",
                "stop_snap_node_id": ss.node_id or "",
                "population_connector_distance_m": ps.connector_distance_m,
                "stop_connector_distance_m": ss.connector_distance_m,
                "walk_distance_m": None,
                "walk_time_sec": None,
                "walk_time_min": None,
                "reachability_status": "UNREACHABLE",
                "unreachable_reason": None,
                "walk_speed_kmh": float(walk_speed_kmh),
                "max_connector_m": float(max_connector_m),
                "osm_snapshot_sha256": graph.osm_sha256,
                "pedestrian_graph_digest": graph.graph_digest,
                "rt016_commit": lineage.get("rt016_commit", ""),
                "rt016_artifact_id": lineage.get("rt016_artifact_id", ""),
                "rt016_artifact_digest": lineage.get("rt016_artifact_digest", ""),
                "final_stop_commit": lineage.get("final_stop_commit", ""),
                "osm_snapshot_timestamp": lineage.get("osm_snapshot_timestamp", ""),
                "osm_query_sha256": lineage.get("osm_query_sha256", ""),
            }
            if ps.status != "REACHABLE":
                row["unreachable_reason"] = f"POPULATION_{ps.reason}"
            elif ss.status != "REACHABLE":
                row["unreachable_reason"] = f"STOP_{ss.reason}"
            else:
                graph_dist = stop_distances.get(stop_id, {}).get(str(ps.node_id), math.inf)
                if not math.isfinite(graph_dist):
                    row["unreachable_reason"] = "GRAPH_DISCONNECTED"
                else:
                    total_distance = float(ps.connector_distance_m or 0.0) + float(graph_dist) + float(ss.connector_distance_m or 0.0)
                    total_sec = total_distance / speed_mps
                    row["walk_distance_m"] = total_distance
                    row["walk_time_sec"] = total_sec
                    row["walk_time_min"] = total_sec / 60.0
                    row["reachability_status"] = "REACHABLE"
                    row["unreachable_reason"] = ""
            rows.append(row)

    matrix = pd.DataFrame(rows)
    expected = len(pop_sorted) * EXPECTED_STOP_COUNT
    if len(matrix) != expected:
        raise RT028ContractError(f"matrix cardinality mismatch: expected {expected}, got {len(matrix)}")
    if matrix[["population_unit_id", "stop_place_id"]].duplicated().any():
        raise RT028ContractError("duplicate population-stop pair")
    if not matrix["reachability_status"].isin(["REACHABLE", "UNREACHABLE"]).all():
        raise RT028ContractError("every population-stop pair requires explicit reachability status")
    unreachable = matrix["reachability_status"] == "UNREACHABLE"
    if matrix.loc[unreachable, "unreachable_reason"].isna().any() or (matrix.loc[unreachable, "unreachable_reason"].astype(str) == "").any():
        raise RT028ContractError("every unreachable pair requires an explicit reason")
    _assert_no_candidate_columns((matrix,))

    matrix = matrix.sort_values(["population_unit_id", "stop_place_id"], kind="mergesort").reset_index(drop=True)
    audit = {
        "contract": "RT028_FINAL_STOP_BORDER_NEUTRAL_PEDESTRIAN_ACCESSIBILITY_SUBSTRATE_V3",
        "status": "PASS",
        "population_unit_count": int(len(pop_sorted)),
        "stop_count": EXPECTED_STOP_COUNT,
        "conventional_stop_count": EXPECTED_CONVENTIONAL_COUNT,
        "special_service_stop_count": EXPECTED_SPECIAL_COUNT,
        "pair_count": int(len(matrix)),
        "reachable_pair_count": int((matrix["reachability_status"] == "REACHABLE").sum()),
        "unreachable_pair_count": int((matrix["reachability_status"] == "UNREACHABLE").sum()),
        "walk_speed_kmh": float(walk_speed_kmh),
        "max_connector_m": float(max_connector_m),
        "osm_snapshot_sha256": graph.osm_sha256,
        "pedestrian_graph_digest": graph.graph_digest,
        "matrix_sha256": canonical_dataframe_sha256(matrix, ["population_unit_id", "stop_place_id"]),
        "lineage": lineage,
        "negative_assertions": {
            "uses_straight_line_as_routing_engine": False,
            "uses_detour_factor": False,
            "treats_municipal_border_as_barrier": False,
            "accepts_old_43_stop_universe": False,
            "uses_candidate_identity": False,
            "ranks_candidates": False,
            "selects_network": False,
            "computes_accessibility_thresholds": False,
            "averages_cross_engine_results": False,
        },
    }
    return matrix, audit


def write_outputs(matrix: pd.DataFrame, audit: Mapping, output_dir: str | Path) -> None:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    matrix.to_csv(out / "rt028_population_unit_stop_walk_matrix_v3.csv", index=False)
    (out / "rt028_pedestrian_accessibility_validation_v3.json").write_text(
        json.dumps(dict(audit), indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
