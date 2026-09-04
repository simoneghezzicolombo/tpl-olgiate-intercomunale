#!/usr/bin/env python3
"""Lineage-key compatibility adapter for the corrected Stage-D integration.

The certified Passenger Utility V2 validation names its primary output hash
``frontier_output_sha256``.  The integration builder internally expects the
generic alias ``output_sha256``.  This runner adds that alias in memory only;
it does not alter upstream evidence or relax hash equality.
"""
from __future__ import annotations

import copy

import scripts.phase2_run_exact_timetable_integration_fix_v2 as target

_original_read_json = target.read_json


def _read_json_with_frontier_alias(path):
    payload = _original_read_json(path)
    if payload.get("status") == "PASS_PHASE2_PASSENGER_UTILITY_FRONTIER_V2":
        lineage = payload.get("lineage", {})
        canonical = lineage.get("frontier_output_sha256")
        if not canonical:
            raise ValueError("Passenger Utility V2 lacks frontier_output_sha256")
        payload = copy.deepcopy(payload)
        payload.setdefault("lineage", {})["output_sha256"] = canonical
    return payload


target.read_json = _read_json_with_frontier_alias

if __name__ == "__main__":
    raise SystemExit(target.main())
