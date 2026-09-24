#!/usr/bin/env python3
"""Freeze the empirical Passenger GJT V2 work-demand universe.

This stage does not calculate GJT. It materialises only municipal OD rows that
are already certified as S8 feeder-objective eligible, and freezes the explicit
behavioural sensitivity grid. Spatial allocation is deliberately deferred.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import json
from pathlib import Path


def sha256_path(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def truthy(value: object) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes"}


def load_sensitivity_cases(path: Path) -> tuple[dict, list[dict[str, float | str]]]:
    payload = load_json(path)
    if payload.get("contract") != "PHASE2_PASSENGER_GJT_SENSITIVITY_V2":
        raise ValueError("Unexpected Passenger GJT sensitivity contract")
    if payload.get("status") != "ASSUMPTION_SENSITIVITY_NOT_EMPIRICAL_INTERVAL":
        raise ValueError("Passenger GJT sensitivity status is not explicit ASSUMPTION sensitivity")
    grid = payload.get("parameter_grid") or {}
    keys = (
        "bus_ivt_weight",
        "walk_weight",
        "wait_weight",
        "transfer_penalty_min",
        "missed_connection_cost_multiplier",
    )
    values = []
    for key in keys:
        row = grid.get(key)
        if not isinstance(row, list) or not row:
            raise ValueError(f"Missing GJT sensitivity values for {key}")
        vals = tuple(float(v) for v in row)
        if any(v < 0 for v in vals):
            raise ValueError(f"Invalid GJT sensitivity values for {key}")
        if key in {"bus_ivt_weight", "walk_weight", "wait_weight"} and any(v <= 0 for v in vals):
            raise ValueError(f"Invalid positive GJT weights for {key}")
        values.append(vals)
    cases = []
    for index, combo in enumerate(itertools.product(*values)):
        case = dict(zip(keys, combo))
        case["sensitivity_id"] = f"GJT2_{index:03d}"
        cases.append(case)
    if len(cases) != int(payload.get("expected_full_factorial_case_count", -1)):
        raise ValueError("GJT sensitivity factorial cardinality mismatch")
    return payload, cases


def materialise_universe(addressability_path: Path, od_validation_path: Path) -> tuple[list[dict[str, str]], dict]:
    od_validation = load_json(od_validation_path)
    if od_validation.get("source_scope") != "ISTAT_2021_WORK_COMMUTING_ONLY":
        raise ValueError("Unexpected OD source scope")
    expected_weight = float(od_validation.get("s8_direct_workers", -1))
    core_codes = {str(v) for v in od_validation.get("core_codes", [])}
    if expected_weight <= 0 or len(core_codes) != 5:
        raise ValueError("OD validation lacks certified five-municipality S8 direct demand")

    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    with addressability_path.open(encoding="utf-8-sig", newline="") as handle:
        for source in csv.DictReader(handle):
            if not truthy(source.get("feeder_objective_eligible")):
                continue
            category = str(source.get("category", "")).strip()
            rail_addressability = str(source.get("rail_addressability", "")).strip()
            if category != "S8_DIRECT":
                raise ValueError("Feeder-eligible row is not categorised S8_DIRECT")
            if rail_addressability != "DIRECT_S8_GTFS_VERIFIED":
                raise ValueError("Feeder-eligible row lacks verified direct S8 addressability")
            semantics = str(source.get("rail_semantics", "")).strip()
            if semantics != "INFRASTRUCTURE_ADDRESSABILITY_NOT_MODAL_SHARE":
                raise ValueError("Unexpected S8_DIRECT rail semantics")
            origin_code = str(source.get("procom_res", "")).strip()
            destination_code = str(source.get("procom_lav", "")).strip()
            if origin_code not in core_codes:
                raise ValueError(f"Feeder row origin outside certified core: {origin_code}")
            try:
                weight = float(source["workers"])
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError("Invalid workers value in feeder row") from exc
            if weight <= 0:
                raise ValueError("Feeder demand weight must be positive")
            key = f"{origin_code}>{destination_code}"
            if key in seen:
                raise ValueError(f"Duplicate empirical journey key {key}")
            seen.add(key)
            rows.append({
                "journey_key": key,
                "origin_code": origin_code,
                "origin_municipality": str(source.get("origin_name", "")).strip(),
                "destination_code": destination_code,
                "destination_municipality": str(source.get("destination_name", "")).strip(),
                "demand_weight": f"{weight:.9f}",
                "layer": "ISTAT_2021_WORK_S8_DIRECT",
                "source_resolution": "MUNICIPAL_OD",
                "category": category,
                "rail_addressability": rail_addressability,
                "rail_semantics": semantics,
                "spatial_allocation_status": "MUNICIPAL_OD_ONLY_NO_SPATIAL_ALLOCATION",
                "full_gjt_ready": "false",
                "evidence_status": "DERIVED_FROM_ISTAT_2021_WORK_OD_AND_VERIFIED_S8_MUNICIPAL_ADDRESSABILITY",
            })
    rows.sort(key=lambda r: (r["origin_code"], r["destination_code"]))
    actual_weight = sum(float(row["demand_weight"]) for row in rows)
    if abs(actual_weight - expected_weight) > 1e-9:
        raise ValueError(f"S8 direct demand weight mismatch: {actual_weight} != {expected_weight}")
    if not rows:
        raise ValueError("No feeder-objective-eligible journeys materialised")
    return rows, od_validation


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--addressability", type=Path, required=True)
    p.add_argument("--od-validation", type=Path, required=True)
    p.add_argument("--sensitivity", type=Path, required=True)
    p.add_argument("--journey-output", type=Path, required=True)
    p.add_argument("--sensitivity-output", type=Path, required=True)
    p.add_argument("--validation", type=Path, required=True)
    args = p.parse_args()

    rows, od_validation = materialise_universe(args.addressability, args.od_validation)
    sensitivity_payload, sensitivity_cases = load_sensitivity_cases(args.sensitivity)

    args.journey_output.parent.mkdir(parents=True, exist_ok=True)
    with args.journey_output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    with args.sensitivity_output.open("w", encoding="utf-8", newline="") as handle:
        fields = ["sensitivity_id", "bus_ivt_weight", "walk_weight", "wait_weight", "transfer_penalty_min", "missed_connection_cost_multiplier"]
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in sensitivity_cases:
            writer.writerow({key: row[key] for key in fields})

    validation = {
        "status": "PASS_PASSENGER_JOURNEY_UNIVERSE_V2_BUILD",
        "contract": "PHASE2_PASSENGER_JOURNEY_UNIVERSE_V2",
        "source_scope": od_validation["source_scope"],
        "source_resolution": "MUNICIPAL_OD",
        "journey_count": len(rows),
        "origin_municipality_count": len({r["origin_code"] for r in rows}),
        "destination_municipality_count": len({r["destination_code"] for r in rows}),
        "demand_weight_sum": sum(float(r["demand_weight"]) for r in rows),
        "expected_demand_weight_sum": float(od_validation["s8_direct_workers"]),
        "sensitivity_case_count": len(sensitivity_cases),
        "full_gjt_ready": False,
        "spatial_allocation_performed": False,
        "population_proportional_worker_allocation_performed": False,
        "nearest_stop_imputation_performed": False,
        "S8_DIRECT_is_modal_share": False,
        "fine_walking_access_combined_with_empirical_OD": False,
        "downstream_requirement": "EXPLICIT_SPATIAL_ALLOCATION_LINEAGE_BEFORE_FULL_PASSENGER_GJT",
        "lineage": {
            "addressability_sha256": sha256_path(args.addressability),
            "od_validation_sha256": sha256_path(args.od_validation),
            "sensitivity_config_sha256": sha256_path(args.sensitivity),
            "journey_output_sha256": sha256_path(args.journey_output),
            "sensitivity_output_sha256": sha256_path(args.sensitivity_output),
        },
        "sensitivity_contract": sensitivity_payload["contract"],
    }
    args.validation.write_text(json.dumps(validation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
