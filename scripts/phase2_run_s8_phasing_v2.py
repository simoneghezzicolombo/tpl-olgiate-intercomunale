#!/usr/bin/env python3
"""Materialise Phase 2 S8 clockface phasing without selecting a network."""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.phase2_s8_phasing import (
    PhasingProfile,
    choose_robust_phase_grid,
    rail_clockface_offsets,
    route_cycle_runtime,
)


def sha256_path(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def require_hash(path: Path, expected: str, label: str) -> None:
    actual = sha256_path(path)
    if actual != expected:
        raise ValueError(f"{label} SHA256 mismatch: {actual} != {expected}")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def load_runtime_lookup(path: Path) -> dict[tuple[str, str], float]:
    rows = load_csv(path)
    lookup: dict[tuple[str, str], float] = {}
    for row in rows:
        key = (row["origin"].strip(), row["destination"].strip())
        if key in lookup:
            raise ValueError(f"Duplicate matrix pair {key}")
        lookup[key] = float(row["runtime_min"])
    if not lookup:
        raise ValueError("Reduced path matrix is empty")
    return lookup


def load_profiles(path: Path) -> tuple[dict, list[PhasingProfile]]:
    payload = load_json(path)
    if payload.get("contract") != "PHASE2_S8_PHASING_SENSITIVITY_V2":
        raise ValueError("Unexpected S8 phasing sensitivity contract")
    if payload.get("status") != "ASSUMPTION_SENSITIVITY_NOT_EMPIRICAL_INTERVAL":
        raise ValueError("S8 phasing parameters are not explicitly assumptions")
    rows = payload.get("transfer_profiles")
    if not isinstance(rows, list) or len(rows) < 2:
        raise ValueError("S8 phase search requires multiple sensitivity profiles")
    profiles = []
    ids = set()
    for row in rows:
        if "ASSUMPTION" not in str(row.get("status", "")):
            raise ValueError("Every transfer profile must be an explicit assumption")
        profile = PhasingProfile(
            profile_id=str(row["profile_id"]),
            transfer_walk_min=float(row["transfer_walk_min"]),
            preferred_wait_min=float(row["preferred_wait_min"]),
            miss_transition_scale_min=float(row["miss_transition_scale_min"]),
            wait_decay_min=float(row["wait_decay_min"]),
        )
        profile.as_transfer_profile()
        if profile.profile_id in ids:
            raise ValueError(f"Duplicate profile_id {profile.profile_id}")
        ids.add(profile.profile_id)
        profiles.append(profile)
    return payload, profiles


def deterministic_gzip_text_writer(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = path.open("wb")
    gz = gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0)
    text = io.TextIOWrapper(gz, encoding="utf-8", newline="")
    return raw, gz, text


def write_phase_rows(
    *,
    catalog_path: Path,
    runtime_lookup: dict[tuple[str, str], float],
    rail_events: list[dict[str, str]],
    profiles: list[PhasingProfile],
    headways: list[int],
    shares: list[float],
    output_path: Path,
) -> tuple[int, dict[str, int], dict[str, dict[str, int]], int]:
    family_counts: dict[str, int] = {}
    phase_counts: dict[str, dict[str, int]] = {}
    signature_cache: dict[
        tuple[tuple[float, ...], float | None, tuple[float, ...]],
        dict[tuple[int, float], dict[str, object]],
    ] = {}
    fieldnames = [
        "scenario_id",
        "topology_family",
        "uniform_headway_min",
        "extension_share",
        "phase_offset_min",
        "extension_rotation_index",
        "extension_pattern_period_departures",
        "public_route_count",
        "robust_min_transfer_quality",
        "robust_unweighted_mean_transfer_quality",
        "worst_profile_bus_to_rail_lecco",
        "worst_profile_bus_to_rail_milano",
        "worst_profile_rail_to_bus_lecco",
        "worst_profile_rail_to_bus_milano",
        "profile_cell_quality_json",
        "phase_status",
        "clockface_semantics",
        "passenger_weighted",
        "exact_timetable_constructed",
    ]

    raw, _gz, text = deterministic_gzip_text_writer(output_path)
    row_count = 0
    try:
        writer = csv.DictWriter(text, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        with catalog_path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                scenario_id = row["scenario_id"].strip()
                family = row["topology_family"].strip()
                routes = json.loads(row["routes_json"])
                extensions = json.loads(row["optional_extensions_json"])
                if not scenario_id or not routes:
                    raise ValueError("Catalog contains empty scenario/routes")
                runtimes = tuple(sorted(
                    round(route_cycle_runtime(route, runtime_lookup), 9)
                    for route in routes
                ))
                extension_runtime = None
                scenario_shares = (0.0,)
                if family == "scheduled_extensions":
                    if len(routes) != 1 or len(extensions) != 1:
                        raise ValueError(
                            f"{scenario_id}: scheduled extension requires one base and one extension route"
                        )
                    extension_runtime = round(
                        route_cycle_runtime(extensions[0], runtime_lookup), 9
                    )
                    scenario_shares = tuple(shares)
                elif extensions:
                    raise ValueError(f"{scenario_id}: unexpected optional extensions outside family")

                cache_key = (runtimes, extension_runtime, tuple(scenario_shares))
                grid = signature_cache.get(cache_key)
                if grid is None:
                    grid = choose_robust_phase_grid(
                        headways_min=headways,
                        public_route_runtimes_min=runtimes,
                        extension_shares=scenario_shares,
                        extension_runtime_min=extension_runtime,
                        rail_events=rail_events,
                        profiles=profiles,
                    )
                    signature_cache[cache_key] = grid

                family_counts[family] = family_counts.get(family, 0) + 1
                for (headway, share), result in sorted(grid.items()):
                    phase_key = f"h{headway}_ext{share:.2f}"
                    phase_text = str(int(result["phase_offset_min"]))
                    phase_counts.setdefault(phase_key, {})
                    phase_counts[phase_key][phase_text] = (
                        phase_counts[phase_key].get(phase_text, 0) + 1
                    )
                    writer.writerow({
                        "scenario_id": scenario_id,
                        "topology_family": family,
                        "uniform_headway_min": headway,
                        "extension_share": f"{share:.2f}",
                        "phase_offset_min": int(result["phase_offset_min"]),
                        "extension_rotation_index": int(result["extension_rotation_index"]),
                        "extension_pattern_period_departures": int(
                            result["extension_pattern_period_departures"]
                        ),
                        "public_route_count": len(runtimes),
                        "robust_min_transfer_quality": f"{float(result['robust_min_transfer_quality']):.12f}",
                        "robust_unweighted_mean_transfer_quality": (
                            f"{float(result['robust_unweighted_mean_transfer_quality']):.12f}"
                        ),
                        "worst_profile_bus_to_rail_lecco": (
                            f"{float(result['worst_profile_bus_to_rail_lecco']):.12f}"
                        ),
                        "worst_profile_bus_to_rail_milano": (
                            f"{float(result['worst_profile_bus_to_rail_milano']):.12f}"
                        ),
                        "worst_profile_rail_to_bus_lecco": (
                            f"{float(result['worst_profile_rail_to_bus_lecco']):.12f}"
                        ),
                        "worst_profile_rail_to_bus_milano": (
                            f"{float(result['worst_profile_rail_to_bus_milano']):.12f}"
                        ),
                        "profile_cell_quality_json": json.dumps(
                            result["profile_cell_quality"],
                            ensure_ascii=False,
                            sort_keys=True,
                            separators=(",", ":"),
                        ),
                        "phase_status": "MODEL_OUTPUT_FROM_EXPLICIT_ASSUMPTION_SENSITIVITY",
                        "clockface_semantics": (
                            "REPEATING_HALF_HOUR_S8_PHASE_NOT_EXACT_FIRST_LAST_TRIP_TIMETABLE"
                        ),
                        "passenger_weighted": "false",
                        "exact_timetable_constructed": "false",
                    })
                    row_count += 1
    finally:
        text.flush()
        text.close()
        raw.close()
    return row_count, dict(sorted(family_counts.items())), phase_counts, len(signature_cache)


def write_policy_map(policy_path: Path, output_path: Path) -> int:
    rows = load_csv(policy_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "policy_index",
        "policy_id",
        "uniform_headway_min",
        "span_id",
        "span_start_min",
        "span_end_min",
        "calendar_id",
        "annual_service_days",
        "recovery_min",
        "extension_share",
        "phase_template_key",
        "phase_requires_scenario_runtime",
        "span_boundary_quality_evaluated",
        "policy_selected",
    ]
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            share = float(row["extension_share"])
            writer.writerow({
                **{field: row[field] for field in fields[:10]},
                "phase_template_key": (
                    f"h{int(row['uniform_headway_min'])}_ext{share:.2f}"
                ),
                "phase_requires_scenario_runtime": "true",
                "span_boundary_quality_evaluated": "false",
                "policy_selected": "false",
            })
    return len(rows)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--catalog", type=Path, required=True)
    p.add_argument("--catalog-validation", type=Path, required=True)
    p.add_argument("--matrix", type=Path, required=True)
    p.add_argument("--matrix-validation", type=Path, required=True)
    p.add_argument("--service-validation", type=Path, required=True)
    p.add_argument("--policy-grid", type=Path, required=True)
    p.add_argument("--policy-feasibility", type=Path, required=True)
    p.add_argument("--s8-events", type=Path, required=True)
    p.add_argument("--s8-contract", type=Path, required=True)
    p.add_argument("--s8-characterization", type=Path, required=True)
    p.add_argument("--sensitivity", type=Path, required=True)
    p.add_argument("--phase-output", type=Path, required=True)
    p.add_argument("--policy-map-output", type=Path, required=True)
    p.add_argument("--validation", type=Path, required=True)
    args = p.parse_args()

    catalog_val = load_json(args.catalog_validation)
    matrix_val = load_json(args.matrix_validation)
    service_val = load_json(args.service_validation)
    s8_contract = load_json(args.s8_contract)
    characterization = load_json(args.s8_characterization)

    if catalog_val.get("status") != "PASS_STRUCTURAL_CATALOG_V2_BUILD":
        raise ValueError("Structural Catalog V2 upstream is not PASS")
    if matrix_val.get("status") != "PASS_REDUCED_PATH_MATRIX_V2_BUILD":
        raise ValueError("Reduced Path Matrix V2 upstream is not PASS")
    if service_val.get("status") != "PASS_SERVICE_POLICY_SEARCH_V2_BUILD":
        raise ValueError("Service Policy Search V2 upstream is not PASS")
    if service_val.get("scenario_count") != 100000:
        raise ValueError("Unexpected upstream scenario count")
    if service_val.get("s8_phase_selected") is not False:
        raise ValueError("Upstream service search already claims an S8 phase")

    require_hash(
        args.catalog,
        catalog_val["lineage"]["scenario_catalog_sha256"],
        "Structural Catalog V2",
    )
    require_hash(
        args.matrix,
        matrix_val["lineage"]["reduced_path_matrix_sha256"],
        "Reduced Path Matrix V2",
    )
    for path, key, label in (
        (args.policy_grid, "policy_grid_sha256", "Service policy grid"),
        (args.policy_feasibility, "feasibility_output_sha256", "Service feasibility"),
        (args.s8_contract, "s8_contract_sha256", "S8 contract"),
        (args.s8_characterization, "s8_characterization_sha256", "S8 characterization"),
    ):
        require_hash(path, service_val["lineage"][key], label)

    if s8_contract.get("active_s8_events") != 74:
        raise ValueError("S8 contract does not contain the certified 74 active events")
    if s8_contract.get("service_date") != "2026-09-03":
        raise ValueError("Unexpected S8 factual reference date")
    for direction in ("MILANO", "LECCO"):
        if characterization["directions"][direction]["headway_median_min"] != 30.0:
            raise ValueError("S8 Phase V2 requires certified 30-minute median headway")
        if characterization["directions"][direction]["headway_min_min"] != 30.0:
            raise ValueError("S8 Phase V2 requires exact 30-minute minimum headway")
        if characterization["directions"][direction]["headway_max_min"] != 30.0:
            raise ValueError("S8 Phase V2 requires exact 30-minute maximum headway")

    sensitivity_payload, profiles = load_profiles(args.sensitivity)
    rail_events = load_csv(args.s8_events)
    if len(rail_events) != 74 or {row["epistemic_status"] for row in rail_events} != {
        "DERIVED_FROM_LIVE_OFFICIAL_GTFS"
    }:
        raise ValueError("S8 event table is not the certified 74-event derived set")
    offsets = rail_clockface_offsets(rail_events)

    headways = sorted(int(v) for v in service_val["design_space"]["headways_min"])
    shares = sorted(float(v) for v in service_val["design_space"]["scheduled_extension_shares"])
    runtime_lookup = load_runtime_lookup(args.matrix)

    phase_rows, family_counts, phase_counts, signature_count = write_phase_rows(
        catalog_path=args.catalog,
        runtime_lookup=runtime_lookup,
        rail_events=rail_events,
        profiles=profiles,
        headways=headways,
        shares=shares,
        output_path=args.phase_output,
    )
    policy_rows = write_policy_map(args.policy_grid, args.policy_map_output)

    scheduled_count = family_counts.get("scheduled_extensions", 0)
    expected_rows = (
        (100000 - scheduled_count) * len(headways)
        + scheduled_count * len(headways) * len(shares)
    )
    if phase_rows != expected_rows:
        raise AssertionError(f"Unexpected phase row count {phase_rows} != {expected_rows}")
    if policy_rows != service_val["policy_count"]:
        raise AssertionError("Policy phase map does not preserve full policy universe")

    payload = {
        "status": "PASS_S8_PHASING_V2_BUILD",
        "contract": "PHASE2_S8_CLOCKFACE_PHASE_SEARCH_V2",
        "evidence_label": "MODEL_OUTPUT_FROM_ASSUMPTION_SENSITIVITY_NOT_FINAL_TIMETABLE",
        "service_date": s8_contract["service_date"],
        "scenario_count": 100000,
        "family_counts": family_counts,
        "phase_result_rows": phase_rows,
        "unique_runtime_signature_count": signature_count,
        "policy_map_rows": policy_rows,
        "headways_min": headways,
        "scheduled_extension_shares": shares,
        "transfer_profile_count": len(profiles),
        "transfer_profile_ids": [profile.profile_id for profile in profiles],
        "rail_clockface_offsets": {
            f"{connection_type}|{direction}": list(values)
            for (connection_type, direction), values in sorted(offsets.items())
        },
        "phase_objective": sensitivity_payload["phase_objective"],
        "shared_clockface_phase": sensitivity_payload["shared_clockface_phase"],
        "scheduled_extension_pattern": sensitivity_payload["scheduled_extensions"],
        "phase_distribution": phase_counts,
        "clockface_period_min": 30,
        "clockface_period_is_factually_supported_on_reference_day": True,
        "first_last_trip_boundary_quality_evaluated": False,
        "delay_robustness_evaluated": False,
        "passenger_weighted": False,
        "passenger_utility_calculated": False,
        "topology_ranked": False,
        "service_policy_selected": False,
        "stop_set_selected": False,
        "exact_timetable_constructed": False,
        "exact_vehicle_blocks_constructed": False,
        "lineage": {
            "catalog_validation": str(args.catalog_validation),
            "catalog_validation_sha256": sha256_path(args.catalog_validation),
            "catalog": str(args.catalog),
            "catalog_sha256": sha256_path(args.catalog),
            "matrix_validation": str(args.matrix_validation),
            "matrix_validation_sha256": sha256_path(args.matrix_validation),
            "matrix": str(args.matrix),
            "matrix_sha256": sha256_path(args.matrix),
            "service_validation": str(args.service_validation),
            "service_validation_sha256": sha256_path(args.service_validation),
            "policy_grid": str(args.policy_grid),
            "policy_grid_sha256": sha256_path(args.policy_grid),
            "policy_feasibility": str(args.policy_feasibility),
            "policy_feasibility_sha256": sha256_path(args.policy_feasibility),
            "s8_events": str(args.s8_events),
            "s8_events_sha256": sha256_path(args.s8_events),
            "s8_contract": str(args.s8_contract),
            "s8_contract_sha256": sha256_path(args.s8_contract),
            "s8_characterization": str(args.s8_characterization),
            "s8_characterization_sha256": sha256_path(args.s8_characterization),
            "sensitivity": str(args.sensitivity),
            "sensitivity_sha256": sha256_path(args.sensitivity),
            "phase_output": str(args.phase_output),
            "phase_output_sha256": sha256_path(args.phase_output),
            "policy_map_output": str(args.policy_map_output),
            "policy_map_output_sha256": sha256_path(args.policy_map_output),
        },
        "epistemic_note": (
            "S8 Phase V2 derives one robust-balanced repeating hub phase for each "
            "scenario/headway/extension-share template. It uses the factual half-hourly "
            "2026-09-03 S8 pulse and multiple explicit transfer-parameter assumptions. "
            "It is not passenger-weighted, does not evaluate first/last trip boundaries "
            "or delays, and does not select a topology or service policy."
        ),
    }
    args.validation.parent.mkdir(parents=True, exist_ok=True)
    args.validation.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "phase_result_rows": phase_rows,
        "unique_runtime_signatures": signature_count,
        "policy_map_rows": policy_rows,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
