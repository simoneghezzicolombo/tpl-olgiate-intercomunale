#!/usr/bin/env python3
"""Resolve OSM restriction relations to routable Gate D turn constraints.

Input is the raw Overpass JSON acquired by gate_d_real_road_audit.py. Output keeps
source relation/way/node identifiers and the real via-node coordinates. Restrictions
with a bus/psv/public_service_vehicle exception are retained but marked not
applicable to buses. Via-way restrictions are not silently approximated.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

BUS_EXCEPTIONS = {"bus", "psv", "public_service_vehicle"}


def split_except(value: str | None) -> set[str]:
    text = str(value or "").lower().replace(",", ";")
    return {part.strip() for part in text.split(";") if part.strip()}


def resolve_restrictions(payload: dict) -> tuple[pd.DataFrame, dict]:
    elements = payload.get("elements", [])
    nodes = {
        int(e["id"]): (float(e["lon"]), float(e["lat"]))
        for e in elements
        if e.get("type") == "node" and "lon" in e and "lat" in e
    }
    rows = []
    via_way_count = 0
    missing_via_node_count = 0
    conditional_only_count = 0
    for rel in elements:
        tags = rel.get("tags", {})
        if rel.get("type") != "relation" or tags.get("type") != "restriction":
            continue
        members = rel.get("members", [])
        by_role = {m.get("role"): m for m in members if m.get("role") in {"from", "via", "to"}}
        from_m, via_m, to_m = by_role.get("from", {}), by_role.get("via", {}), by_role.get("to", {})
        restriction = tags.get("restriction", "")
        conditional = tags.get("restriction:conditional", "")
        if not restriction and conditional:
            conditional_only_count += 1
        except_modes = split_except(tags.get("except"))
        bus_exempt = bool(except_modes & BUS_EXCEPTIONS)
        via_type = via_m.get("type")
        via_ref = via_m.get("ref")
        via_lon = via_lat = None
        routable_via_node = False
        if via_type == "node" and via_ref in nodes:
            via_lon, via_lat = nodes[via_ref]
            routable_via_node = True
        elif via_type == "way":
            via_way_count += 1
        else:
            missing_via_node_count += 1
        applies_to_bus = bool(restriction) and not bus_exempt and routable_via_node
        rows.append({
            "relation_id": int(rel["id"]),
            "restriction": restriction,
            "restriction_conditional": conditional,
            "except": tags.get("except", ""),
            "from_ref": from_m.get("ref"),
            "via_type": via_type,
            "via_ref": via_ref,
            "via_lon": via_lon,
            "via_lat": via_lat,
            "to_ref": to_m.get("ref"),
            "applies_to_bus": applies_to_bus,
            "bus_exempt": bus_exempt,
            "routable_via_node": routable_via_node,
            "epistemic_status": "FACT_OSM_OBSERVATION",
        })
    df = pd.DataFrame(rows)
    summary = {
        "relations_total": int(len(df)),
        "bus_applicable_node_restrictions": int(df["applies_to_bus"].sum()) if len(df) else 0,
        "bus_exempt_restrictions": int(df["bus_exempt"].sum()) if len(df) else 0,
        "via_way_restrictions_not_approximated": int(via_way_count),
        "missing_via_node_coordinates": int(missing_via_node_count),
        "conditional_only_restrictions_not_enforced": int(conditional_only_count),
        "epistemic_status": "DERIVED_FROM_FACT_OSM_RELATIONS",
    }
    return df, summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--raw-osm",
        default="data/audit_gate_d/raw/osm_gate_d_context.json",
    )
    parser.add_argument(
        "--out",
        default="data/audit_gate_d/osm_turn_restrictions_routable.csv",
    )
    parser.add_argument(
        "--summary",
        default="data/audit_gate_d/osm_turn_restrictions_summary.json",
    )
    args = parser.parse_args()
    payload = json.loads(Path(args.raw_osm).read_text(encoding="utf-8"))
    df, summary = resolve_restrictions(payload)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    Path(args.summary).write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    if df.empty:
        raise AssertionError("No OSM restriction relations found in Gate D context")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
