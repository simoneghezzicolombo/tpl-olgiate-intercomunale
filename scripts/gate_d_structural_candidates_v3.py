#!/usr/bin/env python3
"""Gate D structural candidate audit, dependency-closed version.

Gate B and Gate C are formally PASS. This wrapper extends the v2 structural
routing audit with an explicitly ASSUMPTION-labelled Calco Superiore sensitivity
and removes the obsolete Gate C provisional status from the generated summary.

The Calco Superiore design anchor is resolved from the real OSM named road
``Via Calco Superiore``. No coordinate, distance, runtime or recommendation is
hard-coded. Official Comune di Calco evidence is retained as corroboration that
Calco Superiore is a public-road locality and that shuttle/navetta access to the
upper hamlets has existed, but that evidence does not prove suitability for every
full-size bus class.
"""
from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gate_d_structural_candidates_v2 as v2

base = v2.base

GATE_B_VALIDATED_COMMIT = "55d726564e13acca55ce563cc911263ac513acb0"
GATE_C_FINAL_COMMIT = "dcc3e75ae3b4f4ea5170f48e85345b83620c5536"
CALCO_SUPERIORE_SOURCE = (
    "https://comune.calco.lc.it/wp-content/uploads/2025/04/"
    "Regolamento-per-lapplicazione-del-canone-patrimoniale-di-concessione-"
    "autorizzazione-o-esposizione-pubblicitaria-CANONE-UNICO-del-27.03.2023.pdf"
)
CALCO_NAVETTA_EVIDENCE = (
    "https://www.merateonline.it/notizie/70813/"
    "calco-il-25-e-26-si-raggiungono-le-ville-in-navetta-aprono-le-porte-per-la-giornata-fai"
)

base.ANCHOR_SPECS["CALCO_SUPERIORE"] = {
    "type": "osm_named_road",
    "name": "Via Calco Superiore",
}

_EXTRA_CANDIDATES = [
    {
        "candidate_id": "EAST_CALCO_SUPERIORE_SENSITIVITY_CW",
        "family": "EAST_CALCO_SUPERIORE_SENSITIVITY",
        "direction": "CW",
        "anchors": [
            "FS", "CALCO", "CALCO_SUPERIORE", "BEVERATE", "BRIVIO", "ARLATE", "FS"
        ],
    },
    {
        "candidate_id": "EAST_CALCO_SUPERIORE_SENSITIVITY_CCW",
        "family": "EAST_CALCO_SUPERIORE_SENSITIVITY",
        "direction": "CCW",
        "anchors": [
            "FS", "ARLATE", "BRIVIO", "BEVERATE", "CALCO_SUPERIORE", "CALCO", "FS"
        ],
    },
]
_existing_ids = {candidate["candidate_id"] for candidate in base.CANDIDATES}
for candidate in _EXTRA_CANDIDATES:
    if candidate["candidate_id"] not in _existing_ids:
        base.CANDIDATES.append(candidate)

_original_resolve_anchors = v2.resolve_anchors


def resolve_anchors(feeds: list[dict], roads) -> pd.DataFrame:
    result = _original_resolve_anchors(feeds, roads).copy()
    mask = result["anchor_id"] == "CALCO_SUPERIORE"
    if int(mask.sum()) != 1:
        raise AssertionError("Expected exactly one Calco Superiore design anchor")
    result.loc[mask, "corroborating_source_authority"] = "Comune di Calco"
    result.loc[mask, "corroborating_source_url"] = CALCO_SUPERIORE_SOURCE
    result.loc[mask, "operational_evidence_url"] = CALCO_NAVETTA_EVIDENCE
    result.loc[mask, "operational_evidence_status"] = (
        "SUPPORTING_EVIDENCE_ONLY_NOT_FULL_SIZE_BUS_PROOF"
    )
    return result


base.resolve_anchors = resolve_anchors
_original_build_summary = base.build_summary


def build_summary(metrics, bridge_detail, turn_summary, acquisition) -> dict:
    summary = _original_build_summary(metrics, bridge_detail, turn_summary, acquisition)
    lookup = metrics.set_index("candidate_id")
    cw = lookup.loc["EAST_CALCO_SUPERIORE_SENSITIVITY_CW"]
    ccw = lookup.loc["EAST_CALCO_SUPERIORE_SENSITIVITY_CCW"]
    summary.update(
        {
            "verdict": "READY_FOR_GATE_D_REVIEW",
            "gate_b_status": "PASS",
            "gate_b_validated_commit": GATE_B_VALIDATED_COMMIT,
            "gate_c_status": "PASS",
            "gate_c_final_commit": GATE_C_FINAL_COMMIT,
            "gate_c_dependency": "RESOLVED",
            "calco_superiore_status": "TESTED_SENSITIVITY_ASSUMPTION_OSM_ANCHOR",
            "calco_superiore_cw_km": float(cw["route_km"]),
            "calco_superiore_ccw_km": float(ccw["route_km"]),
            "calco_superiore_cw_pure_running_minutes_model": float(
                cw["pure_running_minutes"]
            ),
            "calco_superiore_ccw_pure_running_minutes_model": float(
                ccw["pure_running_minutes"]
            ),
        }
    )
    remaining = [
        item
        for item in summary.get("remaining_physical_checks", [])
        if not item.startswith("Calco Superiore")
    ]
    remaining.append(
        "Calco Superiore: confirm vehicle-class swept path/meeting clearance before operational design; public navetta evidence supports motorized shuttle access but is not proof for every full-size bus class"
    )
    summary["remaining_physical_checks"] = remaining
    return summary


base.build_summary = build_summary


def main() -> int:
    return v2.main()


if __name__ == "__main__":
    raise SystemExit(main())
