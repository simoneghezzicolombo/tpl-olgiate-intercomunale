#!/usr/bin/env python3
"""Bind the certified historical engineering-stress source into Stage-E V3 lineage."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

SOURCE_STATUS = "PASS_PHASE2_STAGE_D_EXACT_TIMETABLE_V2"
SOURCE_CONTRACT = "PHASE2_EXHAUSTIVE_EXACT_TIMETABLE_S8_AND_VEHICLE_BLOCKS_V2"
SOURCE_GRID = [0, 5, 10, 15]
SOURCE_SEMANTICS = "ENGINEERING_STRESS_ONLY_NOT_EMPIRICAL_DELAY_PROBABILITY_AND_NOT_PHASE_OBJECTIVE"
TARGET_STATUS = "PASS_PHASE2_FINAL_OPERATIONAL_ROBUSTNESS_RT001_V3"


def sha256_path(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--validation", type=Path, required=True)
    p.add_argument("--source-validation", type=Path, required=True)
    args = p.parse_args()
    if not args.validation.is_file() or not args.source_validation.is_file():
        raise FileNotFoundError("validation/source-validation input missing")
    target = json.loads(args.validation.read_text(encoding="utf-8"))
    source = json.loads(args.source_validation.read_text(encoding="utf-8"))
    if target.get("status") != TARGET_STATUS:
        raise ValueError("Stage-E RT001 V3 validation is not PASS")
    if source.get("status") != SOURCE_STATUS or source.get("contract") != SOURCE_CONTRACT:
        raise ValueError("historical bus runtime stress source is not the certified Stage-D V2 contract")
    if source.get("runtime_stress_minutes_reported_not_selected") != SOURCE_GRID:
        raise ValueError("historical bus runtime stress grid changed")
    if source.get("runtime_stress_semantics") != SOURCE_SEMANTICS:
        raise ValueError("historical bus runtime stress semantics changed")
    if target.get("bus_runtime_delay_minutes") != SOURCE_GRID:
        raise ValueError("Stage-E V3 bus runtime grid does not match certified source")
    if target.get("bus_runtime_delay_source") != "CARRIED_FORWARD_FROM_CERTIFIED_STAGE_D_V2_ENGINEERING_SENSITIVITY_GRID_NOT_EMPIRICAL_PROBABILITY":
        raise ValueError("Stage-E V3 bus runtime source declaration changed")
    lineage = dict(target.get("lineage", {}))
    lineage["bus_runtime_delay_source_validation_sha256"] = sha256_path(args.source_validation)
    target["lineage"] = lineage
    target["bus_runtime_delay_source_status"] = SOURCE_STATUS
    target["bus_runtime_delay_source_contract"] = SOURCE_CONTRACT
    target["bus_runtime_delay_source_semantics_verified"] = SOURCE_SEMANTICS
    target["bus_runtime_delay_source_grid_verified"] = SOURCE_GRID
    target["bus_runtime_delay_source_is_empirical_probability"] = False
    args.validation.write_text(json.dumps(target, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": target["status"],
        "source_status": SOURCE_STATUS,
        "source_contract": SOURCE_CONTRACT,
        "source_sha256": lineage["bus_runtime_delay_source_validation_sha256"],
        "runtime_stress_grid": SOURCE_GRID,
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
