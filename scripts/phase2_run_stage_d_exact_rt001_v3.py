#!/usr/bin/env python3
"""Run exact Stage D on the RT-001 budget-lossless V3 manifest.

The computational implementation is the independently audited V2 exhaustive
kernel/caller lineage.  This thin adapter binds it to the repaired upstream
contracts, injects the certified in-span passenger-return semantics, and gives
the new evidence a distinct contract and identifier namespace.
"""
from __future__ import annotations

import scripts.phase2_run_exact_timetable_integration_fix_v2 as target
from src.phase2_exact_timetable_contract_v2 import precompute_route_phase_cells_contract

target.STATUS = "PASS_PHASE2_STAGE_D_EXACT_TIMETABLE_RT001_V3"
target.CONTRACT = "PHASE2_BUDGET_LOSSLESS_EXHAUSTIVE_EXACT_CLOCKFACE_TIMETABLE_RT001_V3"
target.TIMETABLE_ID_PREFIX = "D4RT001V3_"
target.precompute_route_phase_cells = precompute_route_phase_cells_contract


if __name__ == "__main__":
    raise SystemExit(target.main())
