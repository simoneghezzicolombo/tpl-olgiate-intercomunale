#!/usr/bin/env python3
"""Materialise the audited S8 passenger-support mask for Passenger GJT V2."""
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

from src.phase2_s8_passenger_support_mask_v2 import (
    SUPPORT_CONTRACT,
    SUPPORT_EVIDENCE,
    SUPPORT_STATUS,
    build_route_support_rows,
    build_scenario_support_rows,
    summarise_support,
)


ROUTE_FIELDS = [
    "route_id",
    "runtime_archetype_id",
    "roles",
    "public_runtime_min",
    "cycle_runtime_min",
    "rail_to_bus_passenger_supported",
    "bus_to_rail_passenger_supported",
    "roundtrip_passenger_supported",
    "passenger_support_class",
    "support_evidence_status",
    "passenger_demand_assigned_to_route",
    "passenger_utility_calculated",
]
SCENARIO_FIELDS = [
    "scenario_id",
    "topology_family",
    "public_route_count",
    "public_roundtrip_supported_route_count",
    "public_rail_to_bus_only_route_count",
    "extension_route_count",
    "extension_roundtrip_supported_route_count",
    "extension_rail_to_bus_only_route_count",
    "passenger_demand_assigned_to_routes",
    "scenario_passenger_utility_calculated",
    "topology_ranked",
]


def sha256_path(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def load_gzip_csv(path: Path) -> list[dict[str, str]]:
    with gzip.open(path, "rt", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _serialise(value: object) -> object:
    if value is True:
        return "true"
    if value is False:
        return "false"
    return value


def write_csv(path: Path, fields: list[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _serialise(row[key]) for key in fields})


def write_deterministic_gzip_csv(
    path: Path,
    fields: list[str],
    rows: list[dict[str, object]],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, compresslevel=9, mtime=0) as gz:
            with io.TextIOWrapper(gz, encoding="utf-8", newline="") as text:
                writer = csv.DictWriter(text, fieldnames=fields, lineterminator="\n")
                writer.writeheader()
                for row in rows:
                    writer.writerow({key: _serialise(row[key]) for key in fields})


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--s8-validation", type=Path, required=True)
    parser.add_argument("--routes", type=Path, required=True)
    parser.add_argument("--scenario-mapping", type=Path, required=True)
    parser.add_argument("--route-output", type=Path, required=True)
    parser.add_argument("--scenario-output", type=Path, required=True)
    parser.add_argument("--validation", type=Path, required=True)
    args = parser.parse_args()

    validation = load_json(args.s8_validation)
    route_input = load_csv(args.routes)
    scenario_input = load_gzip_csv(args.scenario_mapping)

    route_rows, supports = build_route_support_rows(validation, route_input)
    scenario_rows = build_scenario_support_rows(scenario_input, supports)
    summary = summarise_support(route_rows, scenario_rows)

    if summary["route_count"] != int(validation["unique_route_count"]):
        raise ValueError("Passenger-support route count differs from audited S8 route count")
    if summary["roundtrip_passenger_supported_route_count"] != int(
        validation["bus_to_rail_passenger_supported_route_count"]
    ):
        raise ValueError("Passenger-support roundtrip count differs from audited S8 BUS_TO_RAIL count")
    if summary["rail_to_bus_only_route_count"] != int(validation["vehicle_closure_route_count"]):
        raise ValueError("Passenger-support open-route count differs from audited S8 closure count")
    if summary["scenario_count"] != int(validation["scenario_count"]):
        raise ValueError("Passenger-support scenario count differs from audited S8 scenario count")

    write_csv(args.route_output, ROUTE_FIELDS, route_rows)
    write_deterministic_gzip_csv(args.scenario_output, SCENARIO_FIELDS, scenario_rows)

    report = {
        "status": SUPPORT_STATUS,
        "contract": SUPPORT_CONTRACT,
        "evidence_status": SUPPORT_EVIDENCE,
        **summary,
        "passenger_demand_assigned_to_routes": False,
        "passenger_utility_calculated": False,
        "full_gjt_calculated": False,
        "topology_ranked": False,
        "service_policy_selected": False,
        "source_resolution_for_empirical_work_demand": "MUNICIPAL_OD",
        "s8_addressability_is_modal_share": False,
        "epistemic_note": (
            "This artifact propagates audited S8 public-service geometry into route and scenario "
            "passenger-support flags/counts only. It does not allocate the 1,882 municipal-OD workers "
            "to routes, infer sub-municipal origins, calculate Passenger GJT, or rank topologies. "
            "Open public routes retain RAIL_TO_BUS support from the hub but do not gain BUS_TO_RAIL "
            "support from a vehicle-only return closure."
        ),
        "lineage": {
            "s8_validation": str(args.s8_validation),
            "s8_validation_sha256": sha256_path(args.s8_validation),
            "s8_route_universe": str(args.routes),
            "s8_route_universe_sha256": sha256_path(args.routes),
            "s8_scenario_route_mapping": str(args.scenario_mapping),
            "s8_scenario_route_mapping_sha256": sha256_path(args.scenario_mapping),
            "route_support_output": str(args.route_output),
            "route_support_output_sha256": sha256_path(args.route_output),
            "scenario_support_output": str(args.scenario_output),
            "scenario_support_output_sha256": sha256_path(args.scenario_output),
            "upstream_s8_contract": validation["contract"],
            "upstream_s8_status": validation["status"],
        },
    }
    args.validation.parent.mkdir(parents=True, exist_ok=True)
    args.validation.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in (
        "status",
        "route_count",
        "roundtrip_passenger_supported_route_count",
        "rail_to_bus_only_route_count",
        "scenario_count",
    )}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
