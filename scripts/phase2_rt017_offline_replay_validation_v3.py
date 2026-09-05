#!/usr/bin/env python3
"""Offline deterministic replay validation for RT-017 territorial evidence V3.

The live territorial acquisition is performed once against a fixed historical OSM
epoch.  This validator consumes that immutable run artifact and independently
replays the deterministic parts that RT-017 actually claims: adjacent-envelope
stability, smallest converged-level selection and all-pairs routing on the frozen
graph.  It deliberately performs zero network requests, so remote Overpass rate
limits cannot be confused with computational non-determinism.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from scripts import phase2_rt017_adaptive_border_neutral_routing_envelope_v3 as rt017
from src.phase2_adaptive_routing_envelope_v3 import (
    choose_smallest_converged_level,
    compare_pair_results,
)

STATUS = "PASS_RT017_OFFLINE_DETERMINISTIC_REPLAY_V3"
SOURCE_RUN_ID = 33974438701
SOURCE_ARTIFACT_ID = 9972107416
SOURCE_ARTIFACT_DIGEST = "sha256:29a0ffe77bbe16126ff10c85e16278db1f16eaa40c06b8c796cef143f44d5493"
SOURCE_EVIDENCE_HEAD = "dc3866fe19f40d6370a7f2b935e4c3addf916550"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def normal_bool(value: object) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes"}


def assert_pair_frames_equal(expected: pd.DataFrame, actual: pd.DataFrame) -> None:
    key = "pair_id"
    if expected[key].duplicated().any() or actual[key].duplicated().any():
        raise AssertionError("duplicate pair_id in offline replay comparison")
    a = expected.sort_values(key, kind="mergesort").reset_index(drop=True)
    b = actual.sort_values(key, kind="mergesort").reset_index(drop=True)
    if list(a[key].astype(str)) != list(b[key].astype(str)):
        raise AssertionError("offline replay pair universe differs")

    string_cols = [
        "pair_id",
        "source_routing_terminal_id",
        "target_routing_terminal_id",
        "source_graph_node_id",
        "target_graph_node_id",
        "path_edge_ids",
        "path_node_ids",
        "path_geometry_sha256",
    ]
    for col in string_cols:
        av = a[col].fillna("").astype(str).tolist()
        bv = b[col].fillna("").astype(str).tolist()
        if av != bv:
            raise AssertionError(f"offline replay mismatch in {col}")

    for col in ["route_found", "boundary_sensitive"]:
        av = [normal_bool(v) for v in a[col]]
        bv = [normal_bool(v) for v in b[col]]
        if av != bv:
            raise AssertionError(f"offline replay mismatch in {col}")

    for col in [
        "running_minutes_model",
        "distance_m",
        "boundary_clearance_m",
    ]:
        av = pd.to_numeric(a[col], errors="coerce").to_numpy(dtype=float)
        bv = pd.to_numeric(b[col], errors="coerce").to_numpy(dtype=float)
        if not np.allclose(av, bv, rtol=0.0, atol=1e-9, equal_nan=True):
            delta = np.nanmax(np.abs(av - bv))
            raise AssertionError(f"offline replay numeric mismatch in {col}: {delta}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    source = args.input_dir

    required = [
        "rt017_validation.json",
        "frozen_routing_envelope_metadata_v3.json",
        "envelope_expansion_audit_v3.csv",
        "pair_stabilization_transitions_v3.csv",
        "osm_acquisition_audit_v3.csv",
        "complete_directed_probe_pair_manifest_v3.csv",
        "frozen_pair_results_v3.csv",
        "frozen_graph_nodes.csv.gz",
        "frozen_graph_edges.csv.gz",
        "frozen_turn_rules.csv.gz",
        "frozen_osm_snapshot.json.gz",
    ]
    missing = [name for name in required if not (source / name).exists()]
    if missing:
        raise FileNotFoundError(f"RT-017 source artifact missing files: {missing}")

    metadata = json.loads((source / "frozen_routing_envelope_metadata_v3.json").read_text())
    validation = json.loads((source / "rt017_validation.json").read_text())
    if metadata != validation:
        raise AssertionError("RT-017 validation and frozen metadata differ")
    if metadata.get("status") != "PASS_RT017_ADAPTIVE_BORDER_NEUTRAL_ROAD_ENVELOPE_V3":
        raise AssertionError("source territorial run is not PASS")
    if metadata.get("complete_directed_probe_pairs") != 36 * 35:
        raise AssertionError("source directed probe universe is not 36*35")
    if metadata.get("all_pairs_routable_at_frozen_level") is not True:
        raise AssertionError("source frozen level does not route all probe pairs")
    if int(metadata.get("boundary_sensitive_pairs_at_frozen_level", -1)) != 0:
        raise AssertionError("source frozen level contains boundary-sensitive paths")

    # Verify that the frozen canonical OSM bytes match the digest certified by the
    # live territorial run before any offline computation is trusted.
    with gzip.open(source / "frozen_osm_snapshot.json.gz", "rb") as handle:
        frozen_osm_bytes = handle.read()
    frozen_osm_digest = sha256_bytes(frozen_osm_bytes)
    expected_osm_digest = metadata["digests"]["frozen_osm_canonical_sha256"]
    if frozen_osm_digest != expected_osm_digest:
        raise AssertionError("frozen canonical OSM digest mismatch")

    levels = pd.read_csv(source / "envelope_expansion_audit_v3.csv")
    persisted_transitions = pd.read_csv(source / "pair_stabilization_transitions_v3.csv")
    acquisitions = pd.read_csv(source / "osm_acquisition_audit_v3.csv")
    if len(levels) < 3 or len(persisted_transitions) < 2:
        raise AssertionError("source evidence lacks two confirming expansions")
    if levels["level"].astype(int).tolist()[:3] != [0, 1, 2]:
        raise AssertionError("unexpected RT-017 expansion level sequence")
    if not acquisitions["raw_osm_sha256"].astype(str).equals(levels["raw_osm_sha256"].astype(str)):
        raise AssertionError("acquisition and level raw-OSM digests differ")

    # Recompute adjacent-envelope stability from the persisted complete pair
    # outputs, rather than trusting the persisted transition table.
    recomputed_transitions: list[dict] = []
    pair_frames: dict[int, pd.DataFrame] = {}
    snap_frames: dict[int, pd.DataFrame] = {}
    for level in levels["level"].astype(int):
        pair_path = source / f"pair_results_level_{level:02d}.csv"
        snap_path = source / f"probe_snaps_level_{level:02d}.csv"
        if not pair_path.exists() or not snap_path.exists():
            raise FileNotFoundError(f"missing level evidence for {level}")
        pair_frames[level] = pd.read_csv(pair_path)
        snap_frames[level] = pd.read_csv(snap_path)

    for previous, current in zip(levels["level"].astype(int)[:-1], levels["level"].astype(int)[1:]):
        transition = compare_pair_results(pair_frames[previous], pair_frames[current])
        previous_snaps = snap_frames[previous].set_index("routing_terminal_id")["graph_node_id"].astype(str)
        current_snaps = snap_frames[current].set_index("routing_terminal_id")["graph_node_id"].astype(str)
        snap_stable = previous_snaps.equals(current_snaps)
        transition.update({
            "from_level": int(previous),
            "to_level": int(current),
            "snap_node_identity_stable": bool(snap_stable),
        })
        transition["stable"] = bool(transition["stable"] and snap_stable)
        recomputed_transitions.append(transition)

    persisted = {
        (int(r.from_level), int(r.to_level)): r
        for r in persisted_transitions.itertuples(index=False)
    }
    for row in recomputed_transitions:
        key = (row["from_level"], row["to_level"])
        if key not in persisted:
            raise AssertionError(f"persisted transition missing {key}")
        expected = persisted[key]
        for field in [
            "stable",
            "pair_universe_equal",
            "changed_pair_count",
            "newly_routable_count",
            "lost_route_count",
            "material_improvement_count",
            "snap_node_identity_stable",
        ]:
            got = row[field]
            want = getattr(expected, field)
            if isinstance(got, bool):
                want = normal_bool(want)
            elif isinstance(got, int):
                want = int(want)
            if got != want:
                raise AssertionError(f"transition {key} field {field}: {got} != {want}")

    level_records = levels.to_dict("records")
    for row in level_records:
        row["all_pairs_routable"] = normal_bool(row["all_pairs_routable"])
        row["boundary_sensitive_pair_count"] = int(row["boundary_sensitive_pair_count"])
    decision = choose_smallest_converged_level(level_records, recomputed_transitions)
    if not decision.converged:
        raise AssertionError(f"offline convergence replay failed: {decision.reason}")
    if int(decision.frozen_level) != int(metadata["frozen_level"]):
        raise AssertionError("offline replay selected a different frozen level")

    # Independently reroute all complete directed probe pairs over the persisted
    # frozen graph.  This is the computational determinism check that the failed
    # second live run was intended to provide, without another remote acquisition.
    frozen_level = int(metadata["frozen_level"])
    nodes = pd.read_csv(source / "frozen_graph_nodes.csv.gz")
    edges = pd.read_csv(source / "frozen_graph_edges.csv.gz")
    rules = pd.read_csv(source / "frozen_turn_rules.csv.gz")
    manifest = pd.read_csv(source / "complete_directed_probe_pair_manifest_v3.csv")
    probes = snap_frames[frozen_level]
    bounds = tuple(float(v) for v in metadata["frozen_metric_bounds"])
    replay_pairs = rt017.route_all_pairs(manifest, probes, nodes, edges, rules, bounds)
    expected_pairs = pd.read_csv(source / "frozen_pair_results_v3.csv")
    assert_pair_frames_equal(expected_pairs, replay_pairs)

    output = {
        "status": STATUS,
        "source_run_id": SOURCE_RUN_ID,
        "source_artifact_id": SOURCE_ARTIFACT_ID,
        "source_artifact_digest": SOURCE_ARTIFACT_DIGEST,
        "source_evidence_head": SOURCE_EVIDENCE_HEAD,
        "source_territorial_status": metadata["status"],
        "frozen_level_recomputed": int(decision.frozen_level),
        "frozen_margin_m": float(metadata["frozen_margin_m"]),
        "complete_directed_probe_pairs_replayed": int(len(replay_pairs)),
        "replayed_pair_results_identical": True,
        "successive_transitions_recomputed": len(recomputed_transitions),
        "all_recomputed_transitions_stable": all(bool(v["stable"]) for v in recomputed_transitions[:2]),
        "frozen_osm_canonical_sha256_verified": frozen_osm_digest,
        "network_requests_performed": 0,
        "determinism_semantics": "IMMUTABLE_ACQUISITION_EVIDENCE_PLUS_OFFLINE_FULL_FROZEN_GRAPH_ROUTING_REPLAY",
        "claims_not_authorized": metadata.get("claims_not_authorized", []),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, sort_keys=True, separators=(",", ":")) + "\n")
    print(json.dumps(output, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
