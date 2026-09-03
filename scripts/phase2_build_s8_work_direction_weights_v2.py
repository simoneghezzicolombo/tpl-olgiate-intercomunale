#!/usr/bin/env python3
"""Attach official S8 directions to the empirical work-demand journey universe."""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import zipfile

from src.phase2_s8_destination_direction_v2 import (
    direct_stop_direction_map,
    municipality_direction_map,
    opposite_direction,
)


def sha256_path(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def load_zip_csv(path: Path, member: str) -> list[dict[str, str]]:
    with zipfile.ZipFile(path) as zf:
        try:
            raw = zf.read(member)
        except KeyError as exc:
            raise ValueError(f"Official GTFS missing {member}") from exc
    return list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))))


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--journeys", type=Path, required=True)
    p.add_argument("--s8-events", type=Path, required=True)
    p.add_argument("--station-municipalities", type=Path, required=True)
    p.add_argument("--s8-contract", type=Path, required=True)
    p.add_argument("--gtfs-zip", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--summary", type=Path, required=True)
    p.add_argument("--validation", type=Path, required=True)
    args = p.parse_args()

    contract = json.loads(args.s8_contract.read_text(encoding="utf-8"))
    expected_sha = str(contract.get("official_gtfs_sha256", "")).lower()
    actual_sha = sha256_path(args.gtfs_zip)
    if not expected_sha or actual_sha != expected_sha:
        raise ValueError(f"Official Trenord GTFS SHA mismatch: {actual_sha} != {expected_sha}")
    if contract.get("rail_direction_method") != "STOP_SEQUENCE_DOWNSTREAM_ENDPOINT_ANCHOR_NOT_TRAIN_NUMBER_HEURISTIC":
        raise ValueError("Unexpected upstream S8 direction method")
    if contract.get("work_demand", {}).get("S8_DIRECT_is_modal_share") is not False:
        raise ValueError("S8 direct demand semantics are not explicitly non-modal-share")

    journeys = load_csv(args.journeys)
    active_events = load_csv(args.s8_events)
    station_rows = load_csv(args.station_municipalities)
    stop_times = load_zip_csv(args.gtfs_zip, "stop_times.txt")

    stop_map = direct_stop_direction_map(active_events, stop_times)
    muni_map = municipality_direction_map(station_rows, stop_map)

    output_rows: list[dict[str, str]] = []
    for row in journeys:
        if row.get("layer") != "ISTAT_2021_WORK_S8_DIRECT":
            raise ValueError("Unexpected empirical journey layer")
        if row.get("full_gjt_ready") != "false":
            raise ValueError("Direction mapping must not imply full GJT readiness")
        destination_code = str(row.get("destination_code", "")).strip()
        try:
            outbound = muni_map[destination_code]
        except KeyError as exc:
            raise ValueError(f"No official direct S8 direction for destination {destination_code}") from exc
        output_rows.append({
            **row,
            "outbound_bus_to_rail_direction": outbound,
            "return_rail_to_bus_direction": opposite_direction(outbound),
            "rail_direction_evidence": "DERIVED_FROM_MATCHING_OFFICIAL_GTFS_STOP_SEQUENCE",
            "round_trip_semantics": "ONE_OUTBOUND_AND_ONE_RETURN_DIRECTION_PAIR_NO_DAILY_FREQUENCY_CLAIM",
        })

    if not output_rows:
        raise ValueError("No empirical S8 work journeys found")
    output_rows.sort(key=lambda r: (r["origin_code"], r["destination_code"]))
    demand_sum = sum(float(r["demand_weight"]) for r in output_rows)
    expected_demand = float(contract.get("work_demand", {}).get("direct_s8_workers", -1))
    if abs(demand_sum - expected_demand) > 1e-9:
        raise ValueError(f"Direction-weight demand sum mismatch: {demand_sum} != {expected_demand}")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    fields = list(output_rows[0].keys())
    with args.output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(output_rows)

    summary_rows = []
    for leg, field in (
        ("OUTBOUND_BUS_TO_RAIL", "outbound_bus_to_rail_direction"),
        ("RETURN_RAIL_TO_BUS", "return_rail_to_bus_direction"),
    ):
        for direction in ("LECCO", "MILANO"):
            subset = [r for r in output_rows if r[field] == direction]
            summary_rows.append({
                "leg": leg,
                "direction": direction,
                "journey_count": len(subset),
                "demand_weight": f"{sum(float(r['demand_weight']) for r in subset):.9f}",
                "demand_semantics": "ISTAT_2021_WORKER_COUNT_ADDRESSABLE_TO_DIRECT_S8_NOT_MODAL_SHARE",
            })
    with args.summary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(summary_rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(summary_rows)

    validation = {
        "status": "PASS_S8_WORK_DIRECTION_WEIGHTS_V2_BUILD",
        "contract": "PHASE2_S8_WORK_DIRECTION_WEIGHTS_V2",
        "journey_count": len(output_rows),
        "destination_municipality_count": len({r["destination_code"] for r in output_rows}),
        "demand_weight_sum": demand_sum,
        "expected_demand_weight_sum": expected_demand,
        "official_gtfs_sha256": actual_sha,
        "direction_method": "ACTIVE_S8_GTFS_STOP_SEQUENCE_DOWNSTREAM_OF_OLGIATE_CALCO_BRIVIO",
        "outbound_direction_demand": {
            d: sum(float(r["demand_weight"]) for r in output_rows if r["outbound_bus_to_rail_direction"] == d)
            for d in ("LECCO", "MILANO")
        },
        "return_direction_demand": {
            d: sum(float(r["demand_weight"]) for r in output_rows if r["return_rail_to_bus_direction"] == d)
            for d in ("LECCO", "MILANO")
        },
        "S8_DIRECT_is_modal_share": False,
        "full_gjt_ready": False,
        "spatial_allocation_performed": False,
        "lineage": {
            "journeys_sha256": sha256_path(args.journeys),
            "s8_events_sha256": sha256_path(args.s8_events),
            "station_municipalities_sha256": sha256_path(args.station_municipalities),
            "s8_contract_sha256": sha256_path(args.s8_contract),
            "gtfs_sha256": actual_sha,
            "output_sha256": sha256_path(args.output),
            "summary_sha256": sha256_path(args.summary),
        },
    }
    args.validation.write_text(json.dumps(validation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
