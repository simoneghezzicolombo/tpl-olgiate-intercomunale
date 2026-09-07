#!/usr/bin/env python3
"""Pinned real RT-031 boundary-location correspondence audit."""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
from pathlib import Path

from src.phase2_rt031_boundary_correspondence_v3 import build_boundary_catalog, CERTIFIED

EXPECTED = {
    "edges": ("rt017/frozen_graph_edges.csv.gz", "466f562f95805cb194cc079c3829d5abcd54a431653cce5364538869909dff19"),
    "corridors": ("rt022/elementary_corridors_for_reciprocity.csv", "7798f41b238dc818c76f4a440b4fc16203f4bb1e710f40394816399b39adf76c"),
    "patterns": ("rt030/rt030_realization_passenger_stop_patterns.csv", "44fd5d95717ea99d8bee205fa1949c978b44074af4134420ac59bc8a0769684e"),
    "occurrences": ("rt030/rt030_realization_stop_occurrences.csv", "124494b69713a7fe1792d241415d3437d2e87414752eb74603e5ec6aaf8bda37"),
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(path: Path):
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def canonical(value) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def run(root: Path, out: Path):
    tables, hashes = {}, {}
    for key, (relative, expected) in EXPECTED.items():
        path = root / relative
        observed = sha(path)
        if observed != expected:
            raise ValueError(f"{key} SHA mismatch")
        hashes[key] = observed
        tables[key] = read_csv(path)

    rows = build_boundary_catalog(
        tables["patterns"], tables["occurrences"], tables["corridors"], tables["edges"])
    rows = sorted(rows, key=lambda r: (r["left_realization_id"], r["right_realization_id"]))
    if len(rows) != 2881:
        raise AssertionError(f"boundary pair count changed: {len(rows)}")
    if len({r["boundary_correspondence_id"] for r in rows}) != len(rows):
        raise AssertionError("boundary correspondence IDs not unique")
    certified = [r for r in rows if r["boundary_location_status"] == CERTIFIED]
    if len(certified) != len(rows):
        raise AssertionError("real corpus has unresolved boundary location")
    if any(r["automatic_occurrence_merge_authorized"] or r["same_service_event_certified"] for r in rows):
        raise AssertionError("boundary location evidence promoted into service-event merge")
    if any(r["vehicle_continuity"] is not None or r["passenger_continuity"] is not None for r in rows):
        raise AssertionError("continuity invented from location correspondence")

    out.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0])
    csv_path = out / "rt031_atomic_boundary_location_correspondence.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    audit = {
        "status": "PASS_RT031_REAL_BOUNDARY_LOCATION_CORRESPONDENCE_NOT_SERVICE_EVENT_MERGE",
        "input_hashes": hashes,
        "realization_count": len(tables["patterns"]),
        "occurrence_count": len(tables["occurrences"]),
        "carrier_contiguous_atomic_boundary_pairs": len(rows),
        "certified_same_boundary_location_pairs": len(certified),
        "unknown_boundary_location_pairs": len(rows) - len(certified),
        "automatic_occurrence_merge_authorized_pairs": 0,
        "same_service_event_certified_pairs": 0,
        "vehicle_continuity_inferred": False,
        "passenger_continuity_inferred": False,
        "pickup_dropoff_inferred": False,
        "through_service_inferred": False,
        "network_selected": False,
        "territorial_search_performed": False,
        "production_rt031_pass": False,
        "catalog_sha256": sha(csv_path),
        "interpretation": "CERTIFIES_SHARED_CARRIER_BOUNDARY_LOCATION_ONLY; SERVICE_EVENT_IDENTITY_AND_CONTINUITY_REMAIN_UNASSIGNED",
    }
    (out / "rt031_boundary_correspondence_audit.json").write_bytes(canonical(audit))
    return audit


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.inputs, args.out), indent=2, ensure_ascii=False))
