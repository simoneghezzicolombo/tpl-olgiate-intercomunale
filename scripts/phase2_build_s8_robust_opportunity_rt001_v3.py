#!/usr/bin/env python3
"""Rejoin certified S8 opportunity evidence to repaired Stage-C RT-001 V3.

The scenario/timing S8 evidence is unchanged. This adapter reuses the already
validated lineage-pinned S8 join algorithm and changes only the accepted
Passenger Utility upstream contract and the output status/contract. No phase,
threshold, candidate, budget or service policy is selected.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
import sys

import scripts.phase2_build_s8_robust_opportunity_surface_v2 as base

NEW_PU_STATUS = "PASS_PHASE2_PASSENGER_UTILITY_FRONTIER_RT001_V3"
NEW_PU_CONTRACT = "PHASE2_NO_WEIGHT_PASSENGER_UTILITY_EXACT_EXISTENTIAL_BUDGET_V3"
OLD_PU_STATUS = "PASS_PHASE2_PASSENGER_UTILITY_FRONTIER_V2"
OLD_PU_CONTRACT = "PHASE2_NO_WEIGHT_PASSENGER_UTILITY_FRONTIER_V2"
STATUS = "PASS_PHASE2_S8_ROBUST_OPPORTUNITY_RT001_V3"
CONTRACT = "PHASE2_LINEAGE_PINNED_PRE_TIMETABLE_S8_OPPORTUNITY_RT001_V3"

_original_load_json = base.load_json
_seen_repaired_pu = False


def load_json_compat(path: Path) -> dict:
    global _seen_repaired_pu
    payload = _original_load_json(path)
    if payload.get("status") == NEW_PU_STATUS:
        if payload.get("contract") != NEW_PU_CONTRACT:
            raise ValueError("Unexpected repaired Passenger Utility contract")
        if payload.get("rt001_repair") is not True or payload.get("exact_budget_eligibility_repaired_before_stage_c") is not True:
            raise ValueError("Passenger Utility V3 does not prove RT-001 repair")
        if payload.get("annual_bus_km_is_selected_timetable_production") is not False:
            raise ValueError("Passenger Utility V3 annual_bus_km semantics regressed")
        payload = copy.deepcopy(payload)
        payload["status"] = OLD_PU_STATUS
        payload["contract"] = OLD_PU_CONTRACT
        _seen_repaired_pu = True
    return payload


base.load_json = load_json_compat
base.STATUS = STATUS
base.CONTRACT = CONTRACT


def _validation_path() -> Path:
    try:
        return Path(sys.argv[sys.argv.index("--validation") + 1])
    except (ValueError, IndexError) as exc:
        raise ValueError("Missing --validation") from exc


def main() -> int:
    rc = base.main()
    if not _seen_repaired_pu:
        raise RuntimeError("Repaired Passenger Utility V3 was not consumed")
    path = _validation_path()
    v = json.loads(path.read_text(encoding="utf-8"))
    v["status"] = STATUS
    v["contract"] = CONTRACT
    v["upstream_statuses"]["passenger_utility"] = NEW_PU_STATUS
    v["rt001_repair"] = True
    v["passenger_utility_upstream_contract"] = NEW_PU_CONTRACT
    v["candidate_count_is_dynamic_from_repaired_stage_c"] = True
    v["limitations"] = [
        "This remains pre-timetable S8 phase-opportunity evidence, not final reliability.",
        "The scenario/timing S8 evidence is unchanged; only the repaired Stage-C plan membership is rejoined.",
        "A route having some complete-match phase does not prove a joint cross-route phase vector is feasible.",
        "Exact phase selection, explicit trips, exact budget production and vehicle blocks remain rebuilt Stage D tasks.",
    ]
    path.write_text(json.dumps(v, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
