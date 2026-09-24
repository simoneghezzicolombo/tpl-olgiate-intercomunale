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
    canonical_dataframe_sha256,
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

    population_layer_digest = canonical_dataframe_sha256(pop, ["unit_id"])
    final_stop_layer_digest = canonical_dataframe_sha256(stops, ["stop_place_id"])
    lineage = {
        "rt016_commit": RT016_COMMIT,
        "rt016_artifact_id": RT016_ARTIFACT_ID,
        "rt016_artifact_digest": RT016_ARTIFACT_DIGEST,
        "population_layer_canonical_sha256": population_layer_digest,
        "final_stop_commit": FINAL_STOP_COMMIT,
        "final_stop_layer_canonical_sha256": final_stop_layer_digest,
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
    matrix["population_layer_canonical_sha256"] = population_layer_digest
    matrix["final_stop_layer_canonical_sha256"] = final_stop_layer_digest
    audit["matrix_sha256"] = canonical_dataframe_sha256(
        matrix, ["population_unit_id", "stop_place_id"]
    )
    audit["osm_snapshot_metadata"] = {
        "bbox_south_west_north_east": meta["bbox_south_west_north_east"],
        "overpass_endpoint_used": meta["overpass_endpoint_used"],
        "snapshot_timestamp": meta["snapshot_timestamp"],
        "query_sha256": meta["query_sha256"],
    }
    audit["cross_engine_walk_check"] = {
        "status": "NOT_RUN_TECHNICAL_BLOCKER",
        "reason": (
            "RT-012 certifies r5py 1.1.7 only on its pinned upstream Helsinki sample fixture. "
            "RT-028 territorial evidence is a pinned Overpass OSM XML snapshot, while r5py requires an OSM PBF input. "
            "The repository has no frozen validated territorial XML-to-PBF conversion lineage. Introducing a new conversion path here "
            "would make the independent engine use a different, newly introduced graph-preparation lineage. The optional cross-check is "
            "therefore not run; no second-engine value is fabricated or averaged into the primary result."
        ),
        "rt012_runtime_certified": True,
        "rt012_certification_scope": "PINNED_UPSTREAM_HELSINKI_SAMPLE_FIXTURE_NOT_TERRITORIAL_DATA",
        "territorial_xml_to_pbf_lineage_certified": False,
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
        "population_layer_canonical_sha256": population_layer_digest,
        "final_stop_layer_canonical_sha256": final_stop_layer_digest,
    }
    out = Path(args.output_dir)
    (out / "rt028_pedestrian_graph_summary_v3.json").write_text(
        json.dumps(graph_summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(audit, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
