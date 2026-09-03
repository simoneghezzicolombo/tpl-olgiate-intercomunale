#!/usr/bin/env python3
"""Build the Phase 2 topology-neutral S8 interchange evidence bundle."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.phase2_s8_interchange import (  # noqa: E402
    S8ModelError,
    annotate_work_demand_addressability,
    build_active_s8_events,
    characterize_timetable,
    station_sfr_context,
    summarize_addressable_workers,
)


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        raise S8ModelError(f"refusing to write empty output {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def direction_rows(summary: dict[str, object]) -> list[dict[str, object]]:
    directions = summary["directions"]
    rows: list[dict[str, object]] = []
    for direction, values in sorted(directions.items()):
        row = {"direction": direction, **values}
        if isinstance(row.get("departure_minute_offsets"), list):
            row["departure_minute_offsets"] = "|".join(
                str(x) for x in row["departure_minute_offsets"]
            )
        rows.append(row)
    return rows


def build_contract(
    gate_c_payload: dict,
    rail_events: list[dict[str, object]],
    demand_summary: dict[str, object],
    sfr: dict[str, object],
    gate_c_commit: str,
    verified_transfer_path: Path | None,
) -> dict[str, object]:
    return {
        "model": "PHASE2_S8_INTERCHANGE_OPPORTUNITY_V1",
        "topology_dependency": "NONE",
        "station": {"stop_id": "S01514", "name": "Olgiate-Calco-Brivio"},
        "service_date": gate_c_payload["service_date"],
        "gate_c_commit": gate_c_commit,
        "official_gtfs_sha256": gate_c_payload["download_sha256"],
        "active_s8_events": len(rail_events),
        "rail_direction_method": "STOP_SEQUENCE_DOWNSTREAM_ENDPOINT_ANCHOR_NOT_TRAIN_NUMBER_HEURISTIC",
        "bus_to_rail_anchor": "BUS_ARRIVAL_AT_HUB_VS_S8_DEPARTURE",
        "rail_to_bus_anchor": "S8_ARRIVAL_VS_BUS_DEPARTURE_AT_HUB",
        "transfer_quality": {
            "type": "CONTINUOUS",
            "formula": "LOGISTIC_CATCH_FACTOR_X_EXPONENTIAL_PREFERRED_WAIT_DECAY",
            "hard_quality_threshold": None,
            "parameter_status": "ASSUMPTION_SENSITIVITY",
            "physical_miss_definition": "NEGATIVE_SLACK_AFTER_TRANSFER_WALK",
        },
        "delay_robustness": {
            "method": "DETERMINISTIC_WEIGHTED_BUS_RAIL_DELAY_CASES",
            "random_sampling": False,
            "outputs": [
                "expected_quality",
                "worst_case_quality",
                "hard_miss_probability",
                "expected_slack_after_walk_min",
            ],
        },
        "optimizer_bus_event_contract": {
            "required_fields": ["scenario_id", "event_type", "event_time"],
            "event_types": ["BUS_ARRIVAL", "BUS_DEPARTURE"],
            "forbidden_requirement": "NO_ROUTE_TOPOLOGY_FIELD_REQUIRED",
            "compatible_topologies": [
                "loop",
                "radial",
                "figure8",
                "interlining",
                "trunk_branches",
                "short_turn",
                "hybrid",
            ],
        },
        "work_demand": {
            **demand_summary,
            "scope": "ISTAT_2021_WORK_COMMUTING_ONLY",
            "S8_DIRECT_is_modal_share": False,
            "transfer_destinations_require_explicit_verified_evidence": True,
            "verified_transfer_map_supplied": verified_transfer_path is not None,
        },
        "sfr_context": {
            **sfr,
            "use_in_model": "CONTEXT_ONLY_NOT_OD_AND_NOT_MODAL_SHARE",
        },
        "epistemic_contract": {
            "active_rail_service": "DERIVED_FROM_LIVE_OFFICIAL_GTFS_GATE_C",
            "rail_stop_sequence_direction": "DERIVED_FROM_MATCHING_OFFICIAL_GTFS",
            "work_OD": "ISTAT_2021_WORK_COMMUTING",
            "transfer_profile": "ASSUMPTION_SENSITIVITY",
            "delay_cases": "ASSUMPTION_SENSITIVITY",
            "SFR": "DERIVED_CONTEXT_ONLY",
        },
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--gate-c-live-json", type=Path, required=True)
    p.add_argument("--gtfs-zip", type=Path, required=True)
    p.add_argument("--gate-c-commit", required=True)
    p.add_argument("--demand", type=Path, required=True)
    p.add_argument("--s8-municipalities", type=Path, required=True)
    p.add_argument("--sfr", type=Path, required=True)
    p.add_argument("--verified-transfers", type=Path)
    p.add_argument("--output-dir", type=Path, required=True)
    args = p.parse_args()

    try:
        rail_events, gate_c_payload = build_active_s8_events(
            args.gate_c_live_json, args.gtfs_zip
        )
        timetable = characterize_timetable(rail_events)
        demand_rows = annotate_work_demand_addressability(
            args.demand, args.s8_municipalities, args.verified_transfers
        )
        demand_summary = summarize_addressable_workers(demand_rows)
        sfr = station_sfr_context(args.sfr)
        contract = build_contract(
            gate_c_payload,
            rail_events,
            demand_summary,
            sfr,
            args.gate_c_commit,
            args.verified_transfers,
        )

        out = args.output_dir
        out.mkdir(parents=True, exist_ok=True)
        write_csv(out / "s8_events.csv", rail_events)
        write_csv(out / "s8_direction_summary.csv", direction_rows(timetable))
        write_csv(out / "s8_work_demand_addressability.csv", demand_rows)
        (out / "s8_timetable_characterization.json").write_text(
            json.dumps(timetable, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        (out / "s8_station_context.json").write_text(
            json.dumps(sfr, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        (out / "s8_interchange_contract.json").write_text(
            json.dumps(contract, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )

        print(f"Phase 2 S8 events: {len(rail_events)}")
        print(
            "Directions: "
            + ", ".join(
                f"{d}={timetable['directions'][d]['event_count']}"
                for d in sorted(timetable["directions"])
            )
        )
        print(f"Direct S8-addressable work destinations: {demand_summary['direct_s8_workers']} workers")
        print(f"Verified-transfer work destinations: {demand_summary['verified_transfer_workers']} workers")
        print(f"Latest SFR Olgiate-Calco-Brivio: {sfr['latest_saliti24h']:.0f} boardings/day context")
        return 0
    except (OSError, S8ModelError, ValueError, zipfile.BadZipFile) as exc:  # type: ignore[name-defined]
        print(f"PHASE2_S8_FAIL: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    import zipfile
    raise SystemExit(main())
