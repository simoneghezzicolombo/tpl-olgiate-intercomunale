#!/usr/bin/env python3
"""Validate and normalize a Gate D v2 handoff into the Gate E D-side contract.

The key guardrail is assumption propagation: a route-km measurement derived
from an assumed route definition remains assumption-dependent for Gate E.
"""
from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.service_math import ALLOWED, FORBIDDEN, ServiceMathError  # noqa: E402

CONTRACT = "GATE_D_TO_E_V2"
REQUIRED = (
    "contract_version", "scenario_id", "service_day_group", "band_id", "direction", "analysis_mode",
    "upstream_gate_d_status", "gate_d_artifact", "gate_d_commit", "candidate_geometry_id",
    "route_definition_status", "route_definition_basis", "route_km", "route_km_status", "route_km_method",
    "pure_running_min", "pure_running_status", "running_time_calibration_status", "uncertain_road_km",
    "road_uncertainty_status",
)
OUT = (
    "scenario_id", "service_day_group", "band_id", "direction", "upstream_gate_d_status",
    "gate_d_artifact", "gate_d_commit", "route_km", "route_km_status", "pure_running_min",
    "pure_running_status",
)
CALIBRATION = {"CALIBRATED", "VALIDATED_AGAINST_SCHEDULE", "UNCALIBRATED", "NOT_APPLICABLE"}
ROAD_UNCERTAINTY = {"RESOLVED", "QUANTIFIED", "UNKNOWN"}


def _status(value: str, field: str) -> str:
    status = value.strip().upper()
    if status in FORBIDDEN:
        raise ServiceMathError(f"{field}: {status} cannot feed Gate E")
    if status not in ALLOWED:
        raise ServiceMathError(
            f"{field}: {status!r} is outside the project epistemic taxonomy; use a standard status such as DERIVED "
            "and put method detail in a separate field"
        )
    return status


def normalize_rows(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    if not rows:
        raise ServiceMathError("Gate D handoff contains no rows")
    seen: set[tuple[str, str, str, str]] = set()
    out: list[dict[str, object]] = []
    for row in rows:
        if row["contract_version"].strip().upper() != CONTRACT:
            raise ServiceMathError(f"contract_version must be {CONTRACT}")
        direction = row["direction"].strip().upper()
        if direction not in {"CW", "CCW"}:
            raise ServiceMathError("direction must be CW or CCW")
        mode = row["analysis_mode"].strip().upper()
        if mode not in {"PRODUCTION", "SENSITIVITY"}:
            raise ServiceMathError("analysis_mode must be PRODUCTION or SENSITIVITY")
        key = (row["scenario_id"].strip(), row["service_day_group"].strip(), row["band_id"].strip(), direction)
        if not all(key[:3]):
            raise ServiceMathError("scenario_id, service_day_group and band_id are required")
        if key in seen:
            raise ServiceMathError(f"duplicate Gate D handoff key {key}")
        seen.add(key)

        gate_status = row["upstream_gate_d_status"].strip().upper()
        artifact, commit = row["gate_d_artifact"].strip(), row["gate_d_commit"].strip()
        if gate_status == "PASS" and (not artifact or not commit):
            raise ServiceMathError("Gate D PASS requires artifact and commit lineage")
        if not row["candidate_geometry_id"].strip() or not row["route_definition_basis"].strip():
            raise ServiceMathError("candidate_geometry_id and route_definition_basis are required")

        route_definition_status = _status(row["route_definition_status"], "route_definition_status")
        route_km_status = _status(row["route_km_status"], "route_km_status")
        running_status = _status(row["pure_running_status"], "pure_running_status")
        if route_definition_status == "ASSUMPTION" and mode != "SENSITIVITY":
            raise ServiceMathError("assumed route definition is allowed only in SENSITIVITY")
        if route_km_status == "ASSUMPTION" and mode != "SENSITIVITY":
            raise ServiceMathError("assumed route_km is allowed only in SENSITIVITY")
        if running_status == "ASSUMPTION" and mode != "SENSITIVITY":
            raise ServiceMathError("assumed pure_running_min is allowed only in SENSITIVITY")

        try:
            route_km = float(row["route_km"])
            running = float(row["pure_running_min"])
            uncertain = float(row["uncertain_road_km"])
        except ValueError as exc:
            raise ServiceMathError("route_km, pure_running_min and uncertain_road_km must be numeric") from exc
        if not math.isfinite(route_km) or route_km <= 0 or not math.isfinite(running) or running <= 0:
            raise ServiceMathError("route_km and pure_running_min must be finite and > 0")
        if not math.isfinite(uncertain) or uncertain < 0 or uncertain > route_km + 1e-9:
            raise ServiceMathError("uncertain_road_km must be within [0, route_km]")
        if not row["route_km_method"].strip():
            raise ServiceMathError("route_km_method is required")
        calibration = row["running_time_calibration_status"].strip().upper()
        if calibration not in CALIBRATION:
            raise ServiceMathError(f"invalid running_time_calibration_status {calibration!r}")
        uncertainty_status = row["road_uncertainty_status"].strip().upper()
        if uncertainty_status not in ROAD_UNCERTAINTY:
            raise ServiceMathError(f"invalid road_uncertainty_status {uncertainty_status!r}")
        if mode == "PRODUCTION" and gate_status == "PASS" and running_status == "MODEL OUTPUT" and calibration == "UNCALIBRATED":
            raise ServiceMathError("Gate D PASS MODEL OUTPUT running time cannot feed production while UNCALIBRATED")

        # Conservative propagation: a precisely measured distance over an assumed
        # candidate definition is still assumption-dependent downstream.
        downstream_route_status = "ASSUMPTION" if route_definition_status == "ASSUMPTION" else route_km_status
        out.append({
            "scenario_id": key[0], "service_day_group": key[1], "band_id": key[2], "direction": direction,
            "upstream_gate_d_status": gate_status, "gate_d_artifact": artifact, "gate_d_commit": commit,
            "route_km": route_km, "route_km_status": downstream_route_status,
            "pure_running_min": running, "pure_running_status": running_status,
        })
    return out


def read(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        missing = set(REQUIRED) - set(reader.fieldnames or [])
        if missing:
            raise ServiceMathError(f"Gate D v2 handoff missing columns: {sorted(missing)}")
        return [{k: row[k].strip() for k in REQUIRED} for row in reader]


def write(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUT)
        writer.writeheader(); writer.writerows(rows)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    try:
        rows = normalize_rows(read(args.input))
        write(args.output, rows)
        print(f"Normalized Gate D rows: {len(rows)}")
        return 0
    except (OSError, ServiceMathError, ValueError) as exc:
        print(f"GATE_E_GATE_D_NORMALIZE_FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
