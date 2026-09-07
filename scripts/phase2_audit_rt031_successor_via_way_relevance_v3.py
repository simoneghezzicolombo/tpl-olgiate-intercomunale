#!/usr/bin/env python3
"""Historical successor-envelope via-way relevance audit for RT-031.

Bounded claim only: whether via-way restrictions certified as present in RT-017
successor envelopes can affect any composition made exclusively from the 288
certified RT-023 atomic carriers.  No claim is made for future carrier generation.

RT-017 froze level 0 and certified two nested successor envelopes, each with exactly
two bus-applicable via-way restrictions.  Because an Overpass relation bbox query is
monotone under bbox expansion, the two relations observed in the smallest successor
must also occur in every larger successor.  Since RT-017 independently certified
that the larger successor still has count 2, no additional successor relation can
exist there.  We therefore replay only the smallest successor bbox, reducing network
fragility without weakening the frozen evidence contract.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
from pathlib import Path
import time
import urllib.parse
import urllib.request

from src.phase2_rt031_successor_via_way_relevance_v3 import (
    extract_bus_applicable_via_way_relations,
    audit_rt023_carrier_relevance,
)

TIMESTAMP = "2026-09-05T13:45:50Z"
ENDPOINTS = (
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass-api.de/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
)
USER_AGENT = "tpl-olgiate-rt031-via-way-relevance/3.0 (+github.com/simoneghezzicolombo/tpl-olgiate-intercomunale)"
EXPECTED = {
    "levels": ("rt017/envelope_expansion_audit_v3.csv", "9d6cc8d2c23d26db3ba3cd8526a061953322b1fd034cf80430a2aef845aa3fb0"),
    "validation": ("rt017/rt017_validation.json", "7a35b647051c7ff625b61ede2f68a9c1240db592e7c44d5d8842a9d6cd6d2b84"),
    "edges": ("rt017/frozen_graph_edges.csv.gz", "466f562f95805cb194cc079c3829d5abcd54a431653cce5364538869909dff19"),
    "corridors": ("rt022/elementary_corridors_for_reciprocity.csv", "7798f41b238dc818c76f4a440b4fc16203f4bb1e710f40394816399b39adf76c"),
    "patterns": ("rt030/rt030_realization_passenger_stop_patterns.csv", "44fd5d95717ea99d8bee205fa1949c978b44074af4134420ac59bc8a0769684e"),
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(value) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")


def read_csv(path: Path):
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def contains_bbox(outer, inner, tol=1e-10):
    os, ow, on, oe = outer
    ins, inw, inn, ine = inner
    return os <= ins + tol and ow <= inw + tol and on >= inn - tol and oe >= ine - tol


def query_bbox(bbox):
    south, west, north, east = bbox
    query = f'''[out:json][timeout:90][date:"{TIMESTAMP}"];
relation["type"="restriction"]({south:.8f},{west:.8f},{north:.8f},{east:.8f});
out meta;'''
    payload = urllib.parse.urlencode({"data": query}).encode()
    errors = []
    for endpoint in ENDPOINTS:
        for attempt in range(2):
            try:
                request = urllib.request.Request(endpoint, data=payload, headers={"User-Agent": USER_AGENT})
                with urllib.request.urlopen(request, timeout=110) as response:
                    result = json.loads(response.read().decode("utf-8"))
                if not isinstance(result.get("elements"), list):
                    raise ValueError("historical Overpass response missing elements")
                return result, endpoint
            except Exception as exc:
                errors.append(f"{endpoint}#{attempt + 1}:{type(exc).__name__}:{exc}")
                time.sleep(0.5)
    raise RuntimeError("historical restriction replay failed: " + " | ".join(errors))


def run(root: Path, out: Path):
    tables, hashes = {}, {}
    for key, (relative, expected) in EXPECTED.items():
        path = root / relative
        observed = sha(path)
        if observed != expected:
            raise ValueError(f"{key} SHA mismatch")
        hashes[key] = observed
        tables[key] = json.loads(path.read_text(encoding="utf-8")) if key == "validation" else read_csv(path)

    validation = tables["validation"]
    if validation.get("status") != "PASS_RT017_ADAPTIVE_BORDER_NEUTRAL_ROAD_ENVELOPE_V3":
        raise ValueError("RT-017 not PASS")
    if validation.get("osm_snapshot_timestamp") != TIMESTAMP:
        raise ValueError("RT-017 timestamp mismatch")
    frozen = int(validation["frozen_level"])
    successors = sorted((r for r in tables["levels"] if int(r["level"]) > frozen), key=lambda r: int(r["level"]))
    if len(successors) < 2:
        raise AssertionError("RT-017 successor evidence missing")

    successor_bboxes = [tuple(float(r[k]) for k in ("wgs_south", "wgs_west", "wgs_north", "wgs_east")) for r in successors]
    for left, right in zip(successor_bboxes, successor_bboxes[1:]):
        if not contains_bbox(right, left):
            raise AssertionError("RT-017 successor envelopes are not nested")
    successor_counts = [int(r["via_way_restrictions_not_approximated"]) for r in successors]
    if not successor_counts or any(v != successor_counts[0] for v in successor_counts) or successor_counts[0] != 2:
        raise AssertionError(f"successor via-way counts do not support monotone replay: {successor_counts}")

    edge_way = {str(r["edge_id"]): str(r["osm_way_id"]) for r in tables["edges"]}
    corridors = {str(r["corridor_id"]): r for r in tables["corridors"]}
    patterns = tables["patterns"]
    if len(patterns) != 288:
        raise AssertionError("RT-030 realization universe changed")
    carrier_edges, carrier_ways = set(), set()
    for pattern in patterns:
        corridor = corridors[str(pattern["corridor_id"])]
        for eid in str(corridor["path_edge_ids"]).split(";"):
            if eid not in edge_way:
                raise ValueError("RT-023 carrier edge missing from frozen RT-017")
            carrier_edges.add(eid)
            carrier_ways.add(edge_way[eid])
    if len(carrier_edges) != 5205 or len(carrier_ways) != 394:
        raise AssertionError(f"RT-023 carrier universe changed: {len(carrier_edges)}/{len(carrier_ways)}")

    # Replay only the smallest successor.  Nestedness + equal independently
    # certified counts proves its relation set equals every larger successor set.
    result, endpoint = query_bbox(successor_bboxes[0])
    relations = extract_bus_applicable_via_way_relations(result.get("elements", []))
    if len(relations) != successor_counts[0]:
        raise AssertionError(f"smallest successor replay count {len(relations)} != certified {successor_counts[0]}")

    relevance = audit_rt023_carrier_relevance(relations, carrier_ways)
    irrelevant = relevance["all_successor_via_way_irrelevant_to_rt023_composed_domain"]
    status = ("PASS_RT031_SUCCESSOR_VIA_WAY_IRRELEVANT_TO_RT023_COMPOSED_DOMAIN"
              if irrelevant else "OPEN_RT031_SUCCESSOR_VIA_WAY_RELEVANCE")
    relation_ids = [r["relation_id"] for r in relations]
    level_outputs = []
    for row, bbox in zip(successors, successor_bboxes):
        level_outputs.append({
            "level": int(row["level"]),
            "bbox": bbox,
            "expected_via_way_count": int(row["via_way_restrictions_not_approximated"]),
            "observed_via_way_relation_ids": relation_ids,
            "relation_set_basis": "SMALLEST_SUCCESSOR_DIRECT_REPLAY_PLUS_NESTED_BBOX_EQUAL_CERTIFIED_COUNTS",
        })

    audit = {
        "status": status,
        "claim_scope": "ONLY_COMPOSITIONS_OF_THE_288_CERTIFIED_RT023_ATOMIC_CARRIERS",
        "input_hashes": hashes,
        "osm_snapshot_timestamp": TIMESTAMP,
        "frozen_level": frozen,
        "smallest_successor_level_directly_replayed": int(successors[0]["level"]),
        "overpass_endpoint_used": endpoint,
        "restriction_relation_subset_sha256": hashlib.sha256(canonical(result.get("elements", []))).hexdigest(),
        "successor_levels_replayed": [int(r["level"]) for r in successors],
        "successor_level_evidence": level_outputs,
        "successor_envelopes_nested": True,
        "successor_certified_via_way_counts_equal": True,
        "successor_relation_set_stable": True,
        "successor_via_way_relations": relevance["relations"],
        "successor_via_way_relation_count": len(relations),
        "rt023_realization_count": len(patterns),
        "rt023_carrier_directed_edge_count": len(carrier_edges),
        "rt023_carrier_osm_way_count": len(carrier_ways),
        "all_successor_via_way_irrelevant_to_rt023_composed_domain": irrelevant,
        "proof_semantics": relevance["proof_semantics"],
        "future_new_carrier_search_covered": False,
        "global_osm_restriction_completeness_claimed": False,
        "territorial_search_performed": False,
        "network_selected": False,
        "production_rt031_pass": False,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(canonical(audit))
    print(json.dumps(audit, indent=2, ensure_ascii=False))
    return 0 if status.startswith("PASS_") else 2


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(run(args.inputs, args.out))
