#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

from src.phase2_edge7_safe_link_reduction_v3 import (
    PASS_STATUS,
    StructuralLink,
    build_edge7_safe_link_reduction,
)

CORE_GROUPS = (
    "Brivio",
    "Calco",
    "La Valletta Brianza",
    "Olgiate Molgora",
    "Santa Maria Hoè",
)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_links(path: Path) -> list[StructuralLink]:
    with path.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    links = [
        StructuralLink(
            str(row["structural_link_id"]).strip(),
            str(row["terminal_a"]).strip(),
            str(row["terminal_b"]).strip(),
        )
        for row in rows
        if str(row.get("eligible_for_bidirectional_undirected_structure", "")).strip().lower() == "true"
    ]
    if len(rows) != 110 or len(links) != 110:
        raise AssertionError(f"expected exactly 110 reciprocal structural links, got rows={len(rows)} eligible={len(links)}")
    return links


def read_policy_mapping(stop_inventory: Path, terminals: set[str]) -> dict[str, tuple[str, ...]]:
    with stop_inventory.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    by_id: dict[str, dict[str, str]] = {}
    for row in rows:
        stop_id = str(row.get("stop_place_id", "")).strip()
        if stop_id in by_id:
            raise AssertionError(f"duplicate stop_place_id in inventory: {stop_id}")
        by_id[stop_id] = row
    if len(rows) != 36:
        raise AssertionError(f"expected canonical 36-stop inventory, got {len(rows)}")
    missing = sorted(terminals - set(by_id))
    if missing:
        raise AssertionError(f"structural terminals absent from stop inventory: {missing}")
    if len(terminals) != 35:
        raise AssertionError(f"expected exactly 35 structural terminals, got {len(terminals)}")

    mapping: dict[str, tuple[str, ...]] = {}
    for terminal in sorted(terminals):
        municipality = str(by_id[terminal].get("municipality", "")).strip()
        if municipality not in CORE_GROUPS:
            raise AssertionError(f"terminal has invalid/non-core policy group: {terminal} -> {municipality}")
        mapping[terminal] = (municipality,)
    present = {value[0] for value in mapping.values()}
    if present != set(CORE_GROUPS):
        raise AssertionError(f"policy groups mismatch: {sorted(present)}")
    return mapping


def write_outputs(result: dict[str, object], out_dir: Path, links_path: Path, inventory_path: Path) -> dict[str, object]:
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / "edge7_safe_link_feasibility.csv"
    audit_path = out_dir / "rt027_edge7_safe_link_reduction_audit.json"

    records = list(result["records"])
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow([
            "structural_link_id",
            "terminal_a",
            "terminal_b",
            "minimum_policy_covering_edges_including_link",
            "retained_for_edge7_safe_superset",
            "safely_excludable_from_edge7",
        ])
        for record in records:
            writer.writerow([
                record.link_id,
                record.u,
                record.v,
                "" if record.minimum_policy_covering_edges_including_link is None else record.minimum_policy_covering_edges_including_link,
                str(record.retained_for_edge7_safe_superset),
                str(record.safely_excludable_from_edge7),
            ])

    minima = Counter(
        "UNREACHABLE" if r.minimum_policy_covering_edges_including_link is None else str(r.minimum_policy_covering_edges_including_link)
        for r in records
    )
    audit = {
        "status": PASS_STATUS,
        "complete": bool(result["complete"]),
        "contract": result["contract"],
        "target_edge_count": result["target_edge_count"],
        "required_policy_groups": list(result["required_policy_groups"]),
        "counts": result["counts"],
        "minimum_edge_distribution": dict(sorted(minima.items(), key=lambda item: item[0])),
        "proof_semantics": result["proof_semantics"],
        "interpretation_boundary": result["interpretation_boundary"],
        "guards": result["guards"],
        "source_reciprocal_structural_links_sha256": sha256_file(links_path),
        "source_stop_inventory_sha256": sha256_file(inventory_path),
        "edge7_safe_link_feasibility_sha256": sha256_file(csv_path),
    }
    audit_path.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    audit["audit_sha256"] = sha256_file(audit_path)
    return audit


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--links", required=True, type=Path)
    parser.add_argument("--stop-inventory", required=True, type=Path)
    parser.add_argument("--out-dir", type=Path, default=Path("outputs/phase2/rt027_edge7_safe_link_reduction_v3"))
    args = parser.parse_args()

    links = read_links(args.links)
    terminals = {endpoint for link in links for endpoint in (link.u, link.v)}
    mapping = read_policy_mapping(args.stop_inventory, terminals)
    result = build_edge7_safe_link_reduction(
        links,
        required_policy_groups=CORE_GROUPS,
        terminal_policy_groups=mapping,
        target_edge_count=7,
    )
    audit = write_outputs(result, args.out_dir, args.links, args.stop_inventory)
    print(json.dumps(audit, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
