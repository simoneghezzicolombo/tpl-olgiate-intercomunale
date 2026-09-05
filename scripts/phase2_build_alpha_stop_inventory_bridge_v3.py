#!/usr/bin/env python3
"""Build the normalized stop-evidence bridge consumed by Alpha network search."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

from src.phase2_alpha_stop_inventory import STUDY_MUNICIPALITIES, build_alpha_stop_inventory

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FOUNDATION = ROOT / "outputs/phase2/stop_pattern_redesign_v3/passenger_stop_foundation_v3.csv"
DEFAULT_ROUTING = ROOT / "outputs/phase2/reduced_path_matrix_v2/routing_anchor_membership.csv"
DEFAULT_OUT = ROOT / "outputs/phase2/network_design_method_audit_v3/alpha_stop_inventory_bridge_v3"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--foundation", type=Path, default=DEFAULT_FOUNDATION)
    parser.add_argument("--routing-membership", type=Path, default=DEFAULT_ROUTING)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    foundation = pd.read_csv(args.foundation, dtype=str, keep_default_na=False)
    routing = pd.read_csv(args.routing_membership, dtype=str, keep_default_na=False)
    inventory = build_alpha_stop_inventory(foundation, routing)
    args.out.mkdir(parents=True, exist_ok=True)

    csv_path = args.out / "alpha_stop_inventory_bridge_v3.csv"
    inventory.to_csv(csv_path, index=False, lineterminator="\n")

    eligible = inventory.loc[inventory["alpha_design_eligible"]].copy()
    proposed_eligible = eligible.loc[~eligible["existing_official"]]
    municipalities = sorted(set(eligible["municipality"].astype(str)))
    expected = sorted(STUDY_MUNICIPALITIES)
    reference_reuse = eligible.loc[
        eligible["infrastructure_reuse_scope"].eq("REFERENCE_PERIOD_OFFICIAL_STOP_REUSE_CANDIDATE")
    ]

    checks = {
        "eligible_rows_exist": len(eligible) > 0,
        "all_five_policy_municipalities_have_eligible_existing_infrastructure": municipalities == expected,
        "no_non_existing_stop_is_alpha_eligible": proposed_eligible.empty,
        "all_alpha_eligible_rows_are_route_ready": bool(eligible["route_ready"].all()) if len(eligible) else False,
        "all_alpha_eligible_rows_have_human_identity": bool(eligible["human_identity_ready"].all()) if len(eligible) else False,
        "all_alpha_eligible_rows_have_graph_node": bool(eligible["graph_node_id"].astype(str).str.len().gt(0).all()) if len(eligible) else False,
        "reference_period_official_infrastructure_is_not_blanket_excluded": len(reference_reuse) > 0,
    }
    status = "PASS_ALPHA_STOP_INVENTORY_BRIDGE_V3" if all(checks.values()) else "FAIL_ALPHA_STOP_INVENTORY_BRIDGE_V3"
    validation = {
        "status": status,
        "contract": "EVIDENCE_ADAPTER_EXISTING_OFFICIAL_ROUTE_READY_HUMAN_IDENTIFIED_FIVE_MUNICIPALITIES_NOT_STOP_SELECTION",
        "inputs": {
            "foundation": str(args.foundation.relative_to(ROOT)),
            "foundation_sha256": sha256(args.foundation),
            "routing_membership": str(args.routing_membership.relative_to(ROOT)),
            "routing_membership_sha256": sha256(args.routing_membership),
        },
        "counts": {
            "foundation_rows": int(len(inventory)),
            "alpha_design_eligible_existing_stops": int(len(eligible)),
            "eligible_current_d184_d185": int(eligible["current_d184_d185"].sum()) if len(eligible) else 0,
            "eligible_reference_period_other_or_noncurrent": int(len(reference_reuse)),
            "eligible_by_municipality": {
                municipality: int((eligible["municipality"] == municipality).sum())
                for municipality in STUDY_MUNICIPALITIES
            },
        },
        "checks": checks,
        "guards": {
            "candidate_network_generated": False,
            "passenger_stop_pattern_selected": False,
            "proposed_stop_promoted": False,
            "named_service_area_forced": False,
            "winner_selected": False,
        },
        "interpretation": (
            "Eligibility is epistemic/design-universe admissibility only. It does not select a stop, "
            "corridor, topology, timetable or winner. Official reference-period infrastructure may be "
            "reused; proposed FIELD_CHECK_PENDING hypotheses remain outside the first canonical Alpha run."
        ),
        "output_sha256": sha256(csv_path),
    }
    validation_path = args.out / "alpha_stop_inventory_bridge_v3_validation.json"
    validation_path.write_text(json.dumps(validation, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(validation, indent=2, sort_keys=True))
    if status.startswith("FAIL"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
