#!/usr/bin/env python3
"""Compatibility and contract adapter for corrected Stage-D integration.

This adapter normalises two certified upstream field names in memory only and
injects the contract-correct S8 cell constructor that excludes BUS_TO_RAIL
public returns outside the declared start-inclusive/end-exclusive span.
No upstream evidence is modified and no equality check is relaxed.
"""
from __future__ import annotations

import copy

import scripts.phase2_run_exact_timetable_integration_fix_v2 as target
from src.phase2_exact_timetable_contract_v2 import precompute_route_phase_cells_contract

_original_read_json = target.read_json


def _read_json_with_certified_aliases(path):
    payload = _original_read_json(path)
    if payload.get("status") == "PASS_PHASE2_PASSENGER_UTILITY_FRONTIER_V2":
        lineage = payload.get("lineage", {})
        canonical = lineage.get("frontier_output_sha256")
        if not canonical:
            raise ValueError("Passenger Utility V2 lacks frontier_output_sha256")
        payload = copy.deepcopy(payload)
        payload.setdefault("lineage", {})["output_sha256"] = canonical
    if payload.get("status") == "PASS_PHASE2_STAGE_D_INPUT_MANIFEST_V2":
        canonical = payload.get("passenger_plan_context_count_represented")
        if canonical is None:
            raise ValueError("Stage-D manifest lacks passenger_plan_context_count_represented")
        payload = copy.deepcopy(payload)
        payload["stage_c_plan_context_count"] = canonical
    return payload


target.read_json = _read_json_with_certified_aliases
target.precompute_route_phase_cells = precompute_route_phase_cells_contract

if __name__ == "__main__":
    raise SystemExit(target.main())
