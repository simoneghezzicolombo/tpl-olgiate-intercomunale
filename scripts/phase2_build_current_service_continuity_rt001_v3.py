#!/usr/bin/env python3
"""Rejoin certified scenario continuity evidence to repaired Stage-C RT-001 V3.

Scenario-level continuity is recomputed from the same certified localisable
current-service lower bound and frozen route universe. Only repaired Stage-C
membership changes. No unresolved current stop is inferred and continuity is
not used to eliminate or rank candidates here.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
import sys

import scripts.phase2_build_current_service_continuity_v2 as base

NEW_PU_STATUS = "PASS_PHASE2_PASSENGER_UTILITY_FRONTIER_RT001_V3"
NEW_PU_CONTRACT = "PHASE2_NO_WEIGHT_PASSENGER_UTILITY_EXACT_EXISTENTIAL_BUDGET_V3"
OLD_PU_STATUS = "PASS_PHASE2_PASSENGER_UTILITY_FRONTIER_V2"
OLD_PU_CONTRACT = "PHASE2_NO_WEIGHT_PASSENGER_UTILITY_FRONTIER_V2"
STATUS = "PASS_PHASE2_CURRENT_SERVICE_CONTINUITY_RT001_V3"
CONTRACT = "PHASE2_CERTIFIED_LOCALIZABLE_CURRENT_SERVICE_CONTINUITY_LOWER_BOUND_RT001_V3"

_original_read_json = base.read_json
_seen_repaired_pu = False


def read_json_compat(path: Path) -> dict:
    global _seen_repaired_pu
    payload = _original_read_json(path)
    if payload.get("status") == NEW_PU_STATUS:
        if payload.get("contract") != NEW_PU_CONTRACT:
            raise ValueError("Unexpected repaired Passenger Utility contract")
        if payload.get("rt001_repair") is not True:
            raise ValueError("Passenger Utility upstream is not RT-001 repaired")
        payload = copy.deepcopy(payload)
        payload["status"] = OLD_PU_STATUS
        payload["contract"] = OLD_PU_CONTRACT
        payload["passenger_utility_frontier_row_count_all_budgets"] = int(payload["passenger_utility_frontier_row_count_all_budgets"])
        _seen_repaired_pu = True
    return payload


base.read_json = read_json_compat
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
    v["rt001_repair"] = True
    v["passenger_utility_upstream_status"] = NEW_PU_STATUS
    v["passenger_utility_upstream_contract"] = NEW_PU_CONTRACT
    v["baseline_role"] = "CERTIFIED_LOCALIZABLE_LOWER_BOUND_ONLY"
    v["continuity_is_true_current_service_nonregression_proof"] = False
    v["epistemic_note"] += " Repaired Stage-C membership changes only which plans receive this same scenario-level lower-bound evidence."
    path.write_text(json.dumps(v, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
