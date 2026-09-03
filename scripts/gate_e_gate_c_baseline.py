#!/usr/bin/env python3
"""Build a Gate E current-service baseline from formally validated Gate C artifacts.

This adapter deliberately does not annualize a single service date and does not
convert current D184/D185 timetable columns into a future service plan.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.service_math import ServiceMathError  # noqa: E402

BUS_ROUTES_REQUIRED = ("D184", "D185")


def _load_json(path: Path) -> dict:
    with path.open(encoding="utf-8-sig") as f:
        value = json.load(f)
    if not isinstance(value, dict):
        raise ServiceMathError(f"{path}: expected JSON object")
    return value


def build_baseline(bus: dict, rail: dict, *, gate_c_commit: str, bus_artifact: str, rail_artifact: str) -> list[dict[str, object]]:
    if not gate_c_commit.strip():
        raise ServiceMathError("Gate C PASS baseline requires a commit SHA")
    if str(bus.get("gate", "")).upper() != "C" or str(rail.get("gate", "")).upper() != "C":
        raise ServiceMathError("both baseline artifacts must declare gate C")
    bus_date = str(bus.get("service_date", "")).strip()
    rail_date = str(rail.get("service_date", "")).strip()
    if not bus_date or bus_date != rail_date:
        raise ServiceMathError(f"Gate C baseline service dates differ: bus={bus_date!r}, rail={rail_date!r}")

    routes = bus.get("routes")
    if not isinstance(routes, list):
        raise ServiceMathError("Gate C bus artifact missing routes list")
    by_route = {str(r.get("route_id", "")).strip(): r for r in routes if isinstance(r, dict)}
    missing = [route for route in BUS_ROUTES_REQUIRED if route not in by_route]
    if missing:
        raise ServiceMathError(f"Gate C bus artifact missing required routes: {missing}")

    station = rail.get("station")
    if not isinstance(station, dict) or not station.get("stop_id") or not station.get("stop_name"):
        raise ServiceMathError("Gate C rail artifact missing resolved station identity")
    route_ids = {str(x) for x in rail.get("route_ids_resolved_for_s8", [])}
    if "S8" not in route_ids:
        raise ServiceMathError("Gate C rail artifact does not resolve route S8")

    rows: list[dict[str, object]] = []
    bus_total = 0
    for route_id in BUS_ROUTES_REQUIRED:
        route = by_route[route_id]
        try:
            count = int(route["active_timetable_columns"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ServiceMathError(f"{route_id}: invalid active_timetable_columns") from exc
        if count < 0:
            raise ServiceMathError(f"{route_id}: active_timetable_columns cannot be negative")
        bus_total += count
        notes = route.get("notes_detected") if isinstance(route.get("notes_detected"), dict) else {}
        rows.append({
            "service_date": bus_date,
            "mode": "BUS",
            "service_id": route_id,
            "metric": "active_timetable_columns",
            "value": count,
            "unit": "SOURCE_GROUNDED_TIMETABLE_COLUMNS_ON_SERVICE_DATE",
            "epistemic_status": str(route.get("epistemic_status", "RECONSTRUCTED")).upper(),
            "source_class": str(bus.get("source_class", "")),
            "valid_from": str(route.get("valid_from", "")),
            "valid_to": str(route.get("valid_to", "")),
            "gate_c_status": "PASS",
            "gate_c_commit": gate_c_commit,
            "gate_c_artifact": bus_artifact,
            "context_warning": "BRIVIO_BRIDGE_CANTU_DEVIATION_ACTIVE_IN_SOURCE" if notes.get("brivio_bridge_cantu_deviation") else "",
            "annualization_status": "FORBIDDEN_FROM_SINGLE_DATE_BASELINE",
            "future_plan_status": "NOT_A_FUTURE_SERVICE_PLAN",
        })

    rows.append({
        "service_date": bus_date,
        "mode": "BUS",
        "service_id": "D184+D185",
        "metric": "active_timetable_columns_sum",
        "value": bus_total,
        "unit": "DERIVED_SUM_OF_SOURCE_GROUNDED_TIMETABLE_COLUMNS_ON_SERVICE_DATE",
        "epistemic_status": "DERIVED",
        "source_class": str(bus.get("source_class", "")),
        "valid_from": "",
        "valid_to": "",
        "gate_c_status": "PASS",
        "gate_c_commit": gate_c_commit,
        "gate_c_artifact": bus_artifact,
        "context_warning": "",
        "annualization_status": "FORBIDDEN_FROM_SINGLE_DATE_BASELINE",
        "future_plan_status": "NOT_A_FUTURE_SERVICE_PLAN",
    })

    try:
        s8_events = int(rail["active_s8_station_events_count"])
        s8_trips = int(rail["active_s8_trips_count"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ServiceMathError("Gate C rail artifact missing S8 event/trip counts") from exc
    if s8_events < 0 or s8_trips < 0 or s8_events != s8_trips:
        raise ServiceMathError("Gate C S8 station event/trip counts must be non-negative and equal")

    span = rail.get("feed_service_span") if isinstance(rail.get("feed_service_span"), dict) else {}
    rows.append({
        "service_date": rail_date,
        "mode": "RAIL",
        "service_id": f"S8@{station['stop_id']}",
        "metric": "active_station_events",
        "value": s8_events,
        "unit": "SCHEDULED_STATION_EVENTS_ON_SERVICE_DATE",
        "epistemic_status": "FACT",
        "source_class": str(rail.get("source_type", "")),
        "valid_from": str(span.get("start", "")),
        "valid_to": str(span.get("end", "")),
        "gate_c_status": "PASS",
        "gate_c_commit": gate_c_commit,
        "gate_c_artifact": rail_artifact,
        "context_warning": f"STATION={station['stop_name']}",
        "annualization_status": "FORBIDDEN_FROM_SINGLE_DATE_BASELINE",
        "future_plan_status": "CONNECTION_CONTEXT_ONLY_NOT_A_BUS_SERVICE_PLAN",
    })
    return rows


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        raise ServiceMathError("refusing to write empty Gate C baseline")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--bus-json", type=Path, required=True)
    p.add_argument("--rail-json", type=Path, required=True)
    p.add_argument("--gate-c-commit", required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    try:
        rows = build_baseline(
            _load_json(args.bus_json), _load_json(args.rail_json),
            gate_c_commit=args.gate_c_commit,
            bus_artifact=str(args.bus_json), rail_artifact=str(args.rail_json),
        )
        write_csv(args.output, rows)
        print(f"Gate C PASS current-service baseline rows: {len(rows)}")
        print("Annualization: FORBIDDEN_FROM_SINGLE_DATE_BASELINE")
        return 0
    except (OSError, json.JSONDecodeError, ServiceMathError, ValueError) as exc:
        print(f"GATE_E_GATE_C_BASELINE_FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
