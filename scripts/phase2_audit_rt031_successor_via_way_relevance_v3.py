#!/usr/bin/env python3
"""Historical replay of successor-envelope via-way restrictions for RT-031.

Bounded claim only: whether the via-way restrictions observed in RT-017 successor
envelopes can affect any composition made exclusively from the 288 certified
RT-023 atomic carriers. No claim is made for future carrier generation outside
that frozen atomic universe.
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


def tiles4(bbox):
    south, west, north, east = bbox
    mid_lat = (south + north) / 2.0
    mid_lon = (west + east) / 2.0
    return [
        (south, west, mid_lat, mid_lon),
        (south, mid_lon, mid_lat, east),
        (mid_lat, west, north, mid_lon),
        (mid_lat, mid_lon, north, east),
    ]


def query_tile(tile):
    south, west, north, east = tile
    query = f'''[out:json][timeout:180][date:"{TIMESTAMP}"];
relation["type"="restriction"]({south:.8f},{west:.8f},{north:.8f},{east:.8f});
out meta;'''
    payload = urllib.parse.urlencode({"data": query}).encode()
    errors = []
    for endpoint in ENDPOINTS:
        for attempt in range(2):
            try:
                request = urllib.request.Request(endpoint, data=payload, headers={"User-Agent": USER_AGENT})
                with urllib.request.urlopen(request, timeout=210) as response:
                    result = json.loads(response.read().decode("utf-8"))
                if not isinstance(result.get("elements"), list):
                    raise ValueError("historical Overpass response missing elements")
                return result, endpoint
            except Exception as exc:
                errors.append(f"{endpoint}#{attempt + 1}:{type(exc).__name__}:{exc}")
                time.sleep(1.0)
    raise RuntimeError("historical restriction replay failed: " + " | ".join(errors))


def acquire_relations(bbox):
    merged = {}
    endpoints = []
    for tile in tiles4(bbox):
        payload, endpoint = query_tile(tile)
        endpoints.append(endpoint)
        for element in payload.get("elements", []):
            if element.get("type") != "relation":
                continue
            rid = str(element.get("id", ""))
            if not rid:
                raise ValueError("restriction relation missing id")
            old = merged.get(rid)
            if old is not None and canonical(old) != canonical(element):
                raise AssertionError("conflicting historical relation versions")
            merged[rid] = element
    return [merged[k] for k in sorted(merged, key=int)], endpoints


def run(root: Path, out: Path):
    tables, hashes = {}, {}
    for key, (relative, expected) in EXPECTED.items():
        path = root / relative
        observed = sha(path)
        if observed != expected:
            raise ValueError(f"{key} SHA mismatch")
        hashes[key] = observed
        if key == "validation":
            tables[key] = json.loads(path.read_text(encoding="utf-8"))
        else:
            tables[key] = read_csv(path)

    validation = tables["validation"]
    if validation.get("status") != "PASS_RT017_ADAPTIVE_BORDER_NEUTRAL_ROAD_ENVELOPE_V3":
        raise ValueError("RT-017 not PASS")
    if validation.get("osm_snapshot_timestamp") != TIMESTAMP:
        raise ValueError("RT-017 timestamp mismatch")
    frozen = int(validation["frozen_level"])
    successors = sorted((r for r in tables["levels"] if int(r["level"]) > frozen), key=lambda r: int(r["level"]))
    if len(successors) < 2:
        raise AssertionError("RT-017 successor evidence missing")

    edge_way = {str(r["edge_id"]): str(r["osm_way_id"]) for r in tables["edges"]}
    corridors = {str(r["corridor_id"]): r for r in tables["corridors"]}
    patterns = tables["patterns"]
    if len(patterns) != 288:
        raise AssertionError("RT-030 realization universe changed")
    carrier_edges = set()
    carrier_ways = set()
    for pattern in patterns:
        corridor = corridors[str(pattern["corridor_id"])]
        for eid in str(corridor["path_edge_ids"]).split(";"):
            if eid not in edge_way:
                raise ValueError("RT-023 carrier edge missing from frozen RT-017")
            carrier_edges.add(eid)
            carrier_ways.add(edge_way[eid])
    if len(carrier_edges) != 5205 or len(carrier_ways) != 394:
        raise AssertionError(f"RT-023 carrier universe changed: {len(carrier_edges)}/{len(carrier_ways)}")

    level_outputs = []
    relation_by_id = {}
    relation_sets = []
    for row in successors:
        bbox = tuple(float(row[k]) for k in ("wgs_south", "wgs_west", "wgs_north", "wgs_east"))
        elements, endpoints = acquire_relations(bbox)
        via_rows = extract_bus_applicable_via_way_relations(elements)
        expected_count = int(row["via_way_restrictions_not_approximated"])
        if len(via_rows) != expected_count:
            raise AssertionError(f"successor level {row['level']} via-way replay count {len(via_rows)} != {expected_count}")
        relation_sets.append(tuple(r["relation_id"] for r in via_rows))
        for rel in via_rows:
            old = relation_by_id.get(rel["relation_id"])
            if old is not None and old != rel:
                raise AssertionError("successor levels disagree on via-way relation payload")
            relation_by_id[rel["relation_id"]] = rel
        level_outputs.append({
            "level": int(row["level"]),
            "bbox": bbox,
            "expected_via_way_count": expected_count,
            "observed_via_way_relation_ids": [r["relation_id"] for r in via_rows],
            "overpass_endpoints_used": endpoints,
            "restriction_relation_subset_sha256": hashlib.sha256(canonical(elements)).hexdigest(),
        })

    relations = [relation_by_id[k] for k in sorted(relation_by_id, key=int)]
    relevance = audit_rt023_carrier_relevance(relations, carrier_ways)
    stable_relation_set = len(set(relation_sets)) == 1
    irrelevant = relevance["all_successor_via_way_irrelevant_to_rt023_composed_domain"]
    status = ("PASS_RT031_SUCCESSOR_VIA_WAY_IRRELEVANT_TO_RT023_COMPOSED_DOMAIN"
              if stable_relation_set and irrelevant else
              "OPEN_RT031_SUCCESSOR_VIA_WAY_RELEVANCE")

    audit = {
        "status": status,
        "claim_scope": "ONLY_COMPOSITIONS_OF_THE_288_CERTIFIED_RT023_ATOMIC_CARRIERS",
        "input_hashes": hashes,
        "osm_snapshot_timestamp": TIMESTAMP,
        "frozen_level": frozen,
        "successor_levels_replayed": [r["level"] for r in level_outputs],
        "successor_level_evidence": level_outputs,
        "successor_relation_set_stable": stable_relation_set,
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
