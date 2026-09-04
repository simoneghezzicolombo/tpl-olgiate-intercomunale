#!/usr/bin/env python3
"""Bind the persisted independent Stage-D V3 cross-audit into Stage-E V3 lineage."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

TARGET_STATUS = "PASS_PHASE2_FINAL_OPERATIONAL_ROBUSTNESS_RT001_V3"
AUDIT_STATUS = "PASS_PHASE2_STAGE_D_V3_CROSS_IMPLEMENTATION_EQUIVALENCE"
AUDIT_CONTRACT = "PHASE2_STAGE_D_RT001_V3_INDEPENDENT_SEMANTIC_EQUIVALENCE_AUDIT"
CODEX_EVIDENCE_COMMIT = "d41bb678382d018929c1c6b46542f12549f20d4f"


def sha256_path(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--stage-e-validation", type=Path, required=True)
    p.add_argument("--cross-audit-validation", type=Path, required=True)
    args = p.parse_args()
    if not args.stage_e_validation.is_file() or not args.cross_audit_validation.is_file():
        raise FileNotFoundError("Stage-E validation or Stage-D cross-audit evidence missing")
    target = json.loads(args.stage_e_validation.read_text(encoding="utf-8"))
    audit = json.loads(args.cross_audit_validation.read_text(encoding="utf-8"))
    if target.get("status") != TARGET_STATUS:
        raise ValueError("Stage-E RT001 V3 validation is not PASS")
    if audit.get("status") != AUDIT_STATUS or audit.get("contract") != AUDIT_CONTRACT:
        raise ValueError("Stage-D independent cross-audit is not certified PASS")
    if audit.get("equivalent") is not True:
        raise ValueError("Stage-D implementations are not semantically equivalent")
    exact_zero_fields = (
        "contexts_missing_in_a_count",
        "contexts_missing_in_b_count",
        "differing_context_count",
        "differing_selected_phase_context_count",
        "semantic_timetables_only_a_count",
        "semantic_timetables_only_b_count",
        "differing_semantic_timetable_count",
        "differing_semantic_trip_set_count",
    )
    for key in exact_zero_fields:
        if int(audit.get(key, -1)) != 0:
            raise ValueError(f"Stage-D cross-audit mismatch remains: {key}")
    if int(audit.get("context_count_a", -1)) != 16495 or int(audit.get("context_count_b", -1)) != 16495:
        raise ValueError("Stage-D cross-audit context universe changed")
    if int(audit.get("semantic_timetable_count_a", -1)) != 6000 or int(audit.get("semantic_timetable_count_b", -1)) != 6000:
        raise ValueError("Stage-D cross-audit timetable universe changed")
    if int(audit.get("trip_count_a", -1)) != 285748 or int(audit.get("trip_count_b", -1)) != 285748:
        raise ValueError("Stage-D cross-audit trip universe changed")
    provenance = audit.get("provenance", {})
    if provenance.get("codex_persisted_evidence_commit") != CODEX_EVIDENCE_COMMIT:
        raise ValueError("Stage-E canonical Stage-D commit is not the cross-audited Codex evidence commit")
    recoveries = list(audit.get("common_block_assignment_recoveries_compared", []))
    mismatches = {str(k): int(v) for k, v in audit.get("block_partition_mismatch_count_by_recovery", {}).items()}
    for recovery in recoveries:
        if mismatches.get(str(recovery), -1) != 0:
            raise ValueError(f"block partition mismatch remains for recovery {recovery}")
    lineage = dict(target.get("lineage", {}))
    lineage["stage_d_cross_implementation_audit_sha256"] = sha256_path(args.cross_audit_validation)
    target["lineage"] = lineage
    target.update({
        "stage_d_cross_implementation_equivalence_certified": True,
        "stage_d_cross_implementation_audit_status": AUDIT_STATUS,
        "stage_d_cross_implementation_audit_contract": AUDIT_CONTRACT,
        "stage_d_cross_implementation_canonical_commit": CODEX_EVIDENCE_COMMIT,
        "stage_d_cross_implementation_context_count": 16495,
        "stage_d_cross_implementation_semantic_timetable_count": 6000,
        "stage_d_cross_implementation_trip_count": 285748,
        "stage_d_cross_implementation_differing_context_count": 0,
        "stage_d_cross_implementation_differing_selected_phase_context_count": 0,
        "stage_d_cross_implementation_differing_semantic_timetable_count": 0,
        "stage_d_cross_implementation_differing_semantic_trip_set_count": 0,
        "stage_d_cross_implementation_common_block_partitions_compared": recoveries,
        "stage_d_cross_implementation_block_partition_mismatch_count_by_recovery": mismatches,
        "stage_d_cross_implementation_recovery5_10_block_partition_direct_comparison_available": False,
        "stage_d_cross_implementation_recovery5_10_fleet_counts_compared_at_context_timetable_level": True,
    })
    limitations = list(target.get("limitations", []))
    limitation = (
        "Independent Stage-D cross-audit directly compared canonical vehicle-block partitions only for recovery 15, because the second implementation materialised per-trip assignments only for recovery 15. Recovery 5/10 fleet counts were compared at context/timetable level; Stage E consumes the canonical Codex per-trip assignments for all 5/10/15 recoveries."
    )
    if limitation not in limitations:
        limitations.append(limitation)
    target["limitations"] = limitations
    args.stage_e_validation.write_text(json.dumps(target, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": target["status"],
        "cross_audit_status": AUDIT_STATUS,
        "cross_audit_sha256": lineage["stage_d_cross_implementation_audit_sha256"],
        "context_count": 16495,
        "semantic_timetable_count": 6000,
        "trip_count": 285748,
        "common_block_partitions_compared": recoveries,
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
