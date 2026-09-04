#!/usr/bin/env python3
"""Build a dynamic lossless Stage-D manifest from repaired Stage-C RT-001 V3.

This adapter reuses the certified V2 packaging logic but removes the historical
16,883-row cardinality assumption. Every budget-qualified repaired Stage-C row
is preserved; daily timing inputs are deduplicated only by scenario+headway+span.
"""
from __future__ import annotations

from collections import defaultdict
import copy
import json
from pathlib import Path
import sys

import scripts.phase2_build_stage_d_input_manifest_v2 as base

PU_STATUS="PASS_PHASE2_PASSENGER_UTILITY_FRONTIER_RT001_V3"
PU_CONTRACT="PHASE2_NO_WEIGHT_PASSENGER_UTILITY_EXACT_EXISTENTIAL_BUDGET_V3"
S8_STATUS="PASS_PHASE2_S8_ROBUST_OPPORTUNITY_RT001_V3"
S8_CONTRACT="PHASE2_LINEAGE_PINNED_PRE_TIMETABLE_S8_OPPORTUNITY_RT001_V3"
CONT_STATUS="PASS_PHASE2_CURRENT_SERVICE_CONTINUITY_RT001_V3"
CONT_CONTRACT="PHASE2_CERTIFIED_LOCALIZABLE_CURRENT_SERVICE_CONTINUITY_LOWER_BOUND_RT001_V3"
STATUS="PASS_PHASE2_STAGE_D_INPUT_MANIFEST_RT001_V3"
CONTRACT="PHASE2_LOSSLESS_DAILY_TIMING_INPUT_MANIFEST_RT001_V3"

_original_read_json=base.read_json
_seen={"pu":False,"s8":False,"cont":False}


def read_json_compat(path: Path)->dict:
    payload=_original_read_json(path)
    status=payload.get("status")
    if status==PU_STATUS:
        if payload.get("contract")!=PU_CONTRACT or payload.get("rt001_repair") is not True:
            raise ValueError("Invalid repaired Passenger Utility upstream")
        payload=copy.deepcopy(payload)
        payload["status"]="PASS_PHASE2_PASSENGER_UTILITY_FRONTIER_V2"
        payload["contract"]="PHASE2_NO_WEIGHT_PASSENGER_UTILITY_FRONTIER_V2"
        _seen["pu"]=True
    elif status==S8_STATUS:
        if payload.get("contract")!=S8_CONTRACT or payload.get("rt001_repair") is not True:
            raise ValueError("Invalid repaired S8 opportunity upstream")
        payload=copy.deepcopy(payload)
        payload["status"]="PASS_PHASE2_S8_ROBUST_OPPORTUNITY_SURFACE_V2"
        payload["contract"]="PHASE2_LINEAGE_PINNED_PRE_TIMETABLE_S8_OPPORTUNITY_V2"
        _seen["s8"]=True
    elif status==CONT_STATUS:
        if payload.get("contract")!=CONT_CONTRACT or payload.get("rt001_repair") is not True:
            raise ValueError("Invalid repaired continuity upstream")
        payload=copy.deepcopy(payload)
        payload["status"]="PASS_PHASE2_CURRENT_SERVICE_CONTINUITY_LOWER_BOUND_V2"
        payload["contract"]="PHASE2_CERTIFIED_LOCALIZABLE_CURRENT_SERVICE_CONTINUITY_LOWER_BOUND_V2"
        _seen["cont"]=True
    return payload

base.read_json=read_json_compat
base.STATUS=STATUS
base.CONTRACT=CONTRACT


def load_passenger_groups_dynamic(path: Path):
    groups=defaultdict(list)
    context_ids=set()
    for row in base.read_gzip_csv(path):
        context_id=base.plan_context_id(row)
        if context_id in context_ids:
            raise ValueError(f"Duplicate repaired Stage-C plan context {context_id}")
        context_ids.add(context_id)
        enriched=dict(row); enriched["_plan_context_id"]=context_id
        key=(str(row["scenario_id"]),int(row["uniform_headway_min"]),str(row["span_id"]))
        groups[key].append(enriched)
    if not context_ids:
        raise ValueError("Repaired Stage-C frontier is empty")
    return groups,context_ids

base.load_passenger_groups=load_passenger_groups_dynamic


def _validation_path()->Path:
    try:return Path(sys.argv[sys.argv.index("--validation")+1])
    except (ValueError,IndexError) as exc: raise ValueError("Missing --validation") from exc


def main()->int:
    rc=base.main()
    if not all(_seen.values()):
        raise RuntimeError(f"Not all repaired upstreams consumed: {_seen}")
    path=_validation_path(); v=json.loads(path.read_text(encoding="utf-8"))
    v["status"]=STATUS; v["contract"]=CONTRACT
    v["rt001_repair"]=True
    v["input_passenger_utility_status"]=PU_STATUS
    v["input_s8_opportunity_status"]=S8_STATUS
    v["input_continuity_status"]=CONT_STATUS
    v["historical_stage_d_input_count_assumed"]=False
    v["historical_stage_c_plan_count_assumed"]=False
    v["candidate_count_dynamic_from_repaired_stage_c"]=True
    v["exact_budget_eligibility_repaired_upstream"]=True
    path.write_text(json.dumps(v,indent=2,ensure_ascii=False,sort_keys=True)+"\n",encoding="utf-8")
    return rc

if __name__=="__main__": raise SystemExit(main())
