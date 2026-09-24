#!/usr/bin/env python3
"""Run Access Equity V2 with a fail-closed pedestrian-only station hub bridge.

The operational routing anchor ``rail:S01514`` remains unchanged. For resident
walking access only, it inherits the already-certified catchment of the official
bus stop cluster ``EX_039`` containing ``L00407`` (Olgiate Molgora stazione f.s.).
No route geometry, runtime, bus-km, OD evidence, S8 evidence or service policy is
modified by this wrapper.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import scripts.phase2_run_access_equity_v2 as base

RAIL_ANCHOR_ID = "rail:S01514"
OFFICIAL_STOP_ID = "L00407"
PHYSICAL_CLUSTER_ID = "EX_039"
BRIDGE_SOURCE_KIND = "EXISTING_PHYSICAL_STOP_CLUSTER"

_ORIGINAL_LOAD_ANCHOR_SOURCE_MEMBERS = base.load_anchor_source_members
_ORIGINAL_EXPLICIT_STOP_ANCHORS = base.explicit_stop_anchors


def _normalise_name(value: str) -> str:
    return " ".join(str(value).strip().lower().replace(".", " ").split())


def verify_official_station_stop(path: Path) -> dict[str, str]:
    """Fail closed unless frozen Stop Universe V2 identifies L00407 as EX_039."""
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = [row for row in csv.DictReader(handle) if str(row.get("stop_id", "")).strip() == OFFICIAL_STOP_ID]
    if len(rows) != 1:
        raise ValueError(f"Expected exactly one {OFFICIAL_STOP_ID} row, got {len(rows)}")
    row = rows[0]
    cluster = str(row.get("physical_cluster_id", "")).strip()
    if cluster != PHYSICAL_CLUSTER_ID:
        raise ValueError(f"{OFFICIAL_STOP_ID} belongs to {cluster!r}, expected {PHYSICAL_CLUSTER_ID!r}")
    name = _normalise_name(row.get("stop_name", ""))
    if "olgiate molgora" not in name or "stazione" not in name or "f s" not in name:
        raise ValueError(f"Unexpected station stop name for {OFFICIAL_STOP_ID}: {row.get('stop_name')!r}")
    routes = {token.strip() for token in str(row.get("official_routes_reference_gtfs", "")).split("|") if token.strip()}
    if not {"D184", "D185"}.issubset(routes):
        raise ValueError(f"{OFFICIAL_STOP_ID} does not retain D184+D185 reference evidence: {sorted(routes)}")
    if str(row.get("stop_type", "")).strip() != "EXISTING_OFFICIAL_STOP":
        raise ValueError(f"{OFFICIAL_STOP_ID} is not typed as EXISTING_OFFICIAL_STOP")
    return row


def bridged_load_anchor_source_members(path: Path):
    members, kinds = _ORIGINAL_LOAD_ANCHOR_SOURCE_MEMBERS(path)
    if kinds.get(RAIL_ANCHOR_ID) != "HUB_RAIL":
        raise ValueError(f"{RAIL_ANCHOR_ID} is not a HUB_RAIL routing anchor")
    if members.get(RAIL_ANCHOR_ID) != ():
        raise ValueError(f"Core runner semantics for {RAIL_ANCHOR_ID} changed; bridge refuses to stack")
    station_anchor = f"existing:{PHYSICAL_CLUSTER_ID}"
    if kinds.get(station_anchor) != "EXISTING_PHYSICAL_STOP_CLUSTER":
        raise ValueError(f"Missing certified station bus-cluster anchor {station_anchor}")
    members = dict(members)
    members[RAIL_ANCHOR_ID] = ((BRIDGE_SOURCE_KIND, PHYSICAL_CLUSTER_ID),)
    return members, kinds


def bridged_explicit_stop_anchors(routes: list[list[str]], *, anchor_kinds: dict[str, str]) -> frozenset[str]:
    """Preserve core behavior, adding only the verified station rail anchor for access."""
    anchors = set(_ORIGINAL_EXPLICIT_STOP_ANCHORS(routes, anchor_kinds=anchor_kinds))
    if any(RAIL_ANCHOR_ID in route for route in routes):
        if anchor_kinds.get(RAIL_ANCHOR_ID) != "HUB_RAIL":
            raise ValueError(f"Scenario contains {RAIL_ANCHOR_ID} without HUB_RAIL type")
        anchors.add(RAIL_ANCHOR_ID)
    return frozenset(anchors)


def _extract_wrapper_args(argv: list[str]):
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--bridge-stop-evidence", type=Path, required=True)
    known, remaining = parser.parse_known_args(argv[1:])
    return known, [argv[0], *remaining]


def _extract_validation_output(argv: list[str]) -> Path:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--validation-output", type=Path, required=True)
    known, _ = parser.parse_known_args(argv[1:])
    return known.validation_output


def annotate_validation(path: Path, *, station_row: dict[str, str], evidence_path: Path) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("status") != "PASS_ACCESS_EQUITY_V2_BUILD":
        raise ValueError("Core Access Equity V2 did not PASS before bridge annotation")
    payload["hub_access_bridge"] = {
        "status": "VERIFIED_APPLIED",
        "scope": "PEDESTRIAN_ACCESS_ONLY",
        "rail_anchor_id": RAIL_ANCHOR_ID,
        "official_bus_stop_id": OFFICIAL_STOP_ID,
        "physical_cluster_id": PHYSICAL_CLUSTER_ID,
        "official_stop_name": str(station_row["stop_name"]),
        "official_routes_reference_gtfs": str(station_row["official_routes_reference_gtfs"]),
        "station_stop_evidence_path": str(evidence_path),
        "operational_network_changed": False,
        "route_geometry_changed": False,
        "runtime_changed": False,
        "bus_km_changed": False,
        "od_evidence_changed": False,
        "s8_evidence_changed": False,
        "service_policy_changed": False,
    }
    payload["limitations"] = list(payload.get("limitations", [])) + [
        "The rail routing anchor inherits only the certified pedestrian catchment of official station bus-stop cluster EX_039; this bridge is not an operational route merge and does not rewrite historical current-service stop identity."
    ]
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    wrapper_args, base_argv = _extract_wrapper_args(sys.argv)
    if not wrapper_args.bridge_stop_evidence.is_file():
        raise FileNotFoundError(wrapper_args.bridge_stop_evidence)
    station_row = verify_official_station_stop(wrapper_args.bridge_stop_evidence)
    validation_output = _extract_validation_output(base_argv)

    base.load_anchor_source_members = bridged_load_anchor_source_members
    base.explicit_stop_anchors = bridged_explicit_stop_anchors
    sys.argv = base_argv
    base.main()
    annotate_validation(validation_output, station_row=station_row, evidence_path=wrapper_args.bridge_stop_evidence)


if __name__ == "__main__":
    main()
