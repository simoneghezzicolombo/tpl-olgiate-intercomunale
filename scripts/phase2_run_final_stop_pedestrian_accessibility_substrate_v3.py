#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from phase2_final_stop_pedestrian_accessibility_substrate_v3 import (
    DEFAULT_MAX_CONNECTOR_M,
    DEFAULT_WALK_SPEED_KMH,
    build_atomic_walk_matrix,
    parse_osm_pedestrian_graph,
    write_outputs,
)

RT016_COMMIT = "3eaa227fc7a3cd3f82a9c3161ac4827bc32b862a"
RT016_ARTIFACT_ID = "9971024216"
RT016_ARTIFACT_DIGEST = "sha256:2937c60aec0280ae1837bc3f763103d5ac45acd2e3b93a949cc75235b1152fe9"
FINAL_STOP_COMMIT = "ea30fbd18421164abaf2125033292cbe827e024d"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--population", required=True)
    ap.add_argument("--stops", required=True)
    ap.add_argument("--osm", required=True)
    ap.add_argument("--osm-meta", required=True)
    ap.add_argument("--output-dir", required=True)
    ap.add_argument("--walk-speed-kmh", type=float, default=DEFAULT_WALK_SPEED_KMH)
    ap.add_argument("--max-connector-m", type=float, default=DEFAULT_MAX_CONNECTOR_M)
    args = ap.parse_args()

    pop = pd.read_csv(args.population, dtype={"municipality_code": str})
    stops = pd.read_csv(args.stops)
    meta = json.loads(Path(args.osm_meta).read_text(encoding="utf-8"))
    graph = parse_osm_pedestrian_graph(args.osm)
    if graph.osm_sha256 != meta["osm_snapshot_sha256"]:
        raise ValueError("OSM snapshot digest does not match acquisition metadata")

    lineage = {
        "rt016_commit": RT016_COMMIT,
        "rt016_artifact_id": RT016_ARTIFACT_ID,
        "rt016_artifact_digest": RT016_ARTIFACT_DIGEST,
        "final_stop_commit": FINAL_STOP_COMMIT,
        "osm_snapshot_timestamp": str(meta["snapshot_timestamp"]),
        "osm_query_sha256": str(meta["query_sha256"]),
    }
    matrix, audit = build_atomic_walk_matrix(
        graph=graph,
        population_units=pop,
        stops=stops,
        walk_speed_kmh=args.walk_speed_kmh,
        max_connector_m=args.max_connector_m,
        lineage=lineage,
    )
    audit["osm_snapshot_metadata"] = {
        "bbox_south_west_north_east": meta["bbox_south_west_north_east"],
        "overpass_endpoint_used": meta["overpass_endpoint_used"],
        "snapshot_timestamp": meta["snapshot_timestamp"],
        "query_sha256": meta["query_sha256"],
    }
    audit["cross_engine_walk_check"] = {
        "status": "NOT_RUN",
        "reason": "No frozen validated R5/r5py WALK runtime is present in the repository; optional cross-check deliberately not substituted with a second unvalidated engine.",
        "results_averaged_with_primary_engine": False,
    }
    write_outputs(matrix, audit, args.output_dir)

    graph_summary = {
        "routable_node_count": len(graph.node_ids),
        "directed_edge_count": sum(len(v) for v in graph.adjacency.values()),
        "blocked_barrier_node_count": len(graph.blocked_node_ids),
        "obstacle_geometry_count": len(graph.obstacle_geometries),
        "osm_snapshot_sha256": graph.osm_sha256,
        "pedestrian_graph_digest": graph.graph_digest,
    }
    out = Path(args.output_dir)
    (out / "rt028_pedestrian_graph_summary_v3.json").write_text(
        json.dumps(graph_summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(audit, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
