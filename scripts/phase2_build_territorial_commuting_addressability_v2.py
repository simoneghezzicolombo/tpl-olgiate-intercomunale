#!/usr/bin/env python3
"""Build municipal-OD territorial commuting structural addressability for Phase 2."""
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

from src.phase2_territorial_commuting_addressability_v2 import (
    CONTRACT,
    STATUS,
    RouteGeometry,
    WorkOD,
    summarise_addressability,
)


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def loadj(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def tf(value: bool) -> str:
    return "true" if value else "false"


def parse_json_list(value: str, field: str, *, unique: bool = True) -> list[str]:
    parsed = json.loads(value)
    if (
        not isinstance(parsed, list)
        or any(not isinstance(item, str) or not item for item in parsed)
    ):
        raise ValueError(f"Invalid {field}")
    if unique and len(parsed) != len(set(parsed)):
        raise ValueError(f"Duplicate IDs in {field}")
    return parsed


def gz_writer(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = path.open("wb")
    gz = gzip.GzipFile(
        filename="",
        mode="wb",
        fileobj=raw,
        compresslevel=9,
        mtime=0,
    )
    text = io.TextIOWrapper(gz, encoding="utf-8", newline="")
    return raw, text


def load_anchors(path: Path) -> dict[str, frozenset[str]]:
    anchors: dict[str, frozenset[str]] = {}
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"anchor_id", "enabled", "municipalities"}
        if not required <= set(reader.fieldnames or []):
            raise ValueError("Anchor universe schema invalid")
        for row in reader:
            if row["enabled"].strip().lower() != "true":
                continue
            anchor_id = row["anchor_id"].strip()
            municipalities = frozenset(
                value.strip()
                for value in row["municipalities"].split("|")
                if value.strip()
            )
            if not anchor_id or not municipalities:
                raise ValueError(
                    f"Enabled anchor lacks municipality lineage: {anchor_id}"
                )
            if anchor_id in anchors:
                raise ValueError(f"Duplicate anchor {anchor_id}")
            anchors[anchor_id] = municipalities
    return anchors


def load_routes(
    path: Path,
    anchors: dict[str, frozenset[str]],
) -> dict[str, RouteGeometry]:
    routes: dict[str, RouteGeometry] = {}
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {
            "route_id",
            "anchors_json",
            "public_service_starts_at_hub",
            "vehicle_closure_added",
        }
        if not required <= set(reader.fieldnames or []):
            raise ValueError("Route universe schema invalid")
        for row in reader:
            if row["public_service_starts_at_hub"] != "true":
                raise ValueError("Route does not start as public service at hub")

            # Public anchor sequences may legitimately revisit an anchor, e.g. a
            # closed loop whose first and last public anchor are both the hub.
            # Scenario route-ID lists remain uniqueness-constrained downstream.
            anchor_ids = tuple(
                parse_json_list(row["anchors_json"], "anchors_json", unique=False)
            )
            if any(anchor_id not in anchors for anchor_id in anchor_ids):
                raise ValueError(
                    "Route references anchor without municipality lineage: "
                    f"{row['route_id']}"
                )
            route = RouteGeometry(row["route_id"], anchor_ids)
            route.validate()
            if route.route_id in routes:
                raise ValueError(f"Duplicate route {route.route_id}")
            routes[route.route_id] = route
    return routes


def load_od(
    path: Path,
    validation: dict,
    footprint: set[str],
    output: Path,
) -> tuple[list[WorkOD], dict]:
    core = set(map(str, validation["core_codes"]))
    rows: list[WorkOD] = []
    seen: set[tuple[str, str]] = set()
    category_mass = {
        key: 0.0 for key in ("SELF", "OTHER_CORE", "S8_DIRECT", "OTHER_EXTERNAL")
    }
    universe: list[dict[str, object]] = []

    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {
            "procom_res",
            "origin_name",
            "procom_lav",
            "destination_name",
            "workers",
            "category",
            "rail_semantics",
        }
        if not required <= set(reader.fieldnames or []):
            raise ValueError("OD source schema invalid")
        for source in reader:
            if source["procom_res"] not in core:
                raise ValueError("OD origin outside certified five-municipality core")
            if (
                source["rail_semantics"]
                != "INFRASTRUCTURE_ADDRESSABILITY_NOT_MODAL_SHARE"
            ):
                raise ValueError("OD rail semantics changed")

            key = (source["procom_res"], source["procom_lav"])
            if key in seen:
                raise ValueError(f"Duplicate municipal OD {key}")
            seen.add(key)

            od = WorkOD(
                source["procom_res"],
                source["origin_name"],
                source["procom_lav"],
                source["destination_name"],
                float(source["workers"]),
                source["category"],
            )
            od.validate()
            rows.append(od)
            category_mass[od.category] += od.workers

            destination_in_footprint = od.destination_name in footprint
            scorable = od.category != "SELF" and destination_in_footprint
            universe.append(
                {
                    "origin_code": od.origin_code,
                    "origin_municipality": od.origin_name,
                    "destination_code": od.destination_code,
                    "destination_municipality": od.destination_name,
                    "workers": f"{od.workers:.9f}",
                    "category": od.category,
                    "destination_in_structural_search_footprint": tf(
                        destination_in_footprint
                    ),
                    "territorial_structural_addressability_scorable": tf(scorable),
                    "self_od_resolution_status": (
                        "SELF_MUNICIPAL_OD_UNRESOLVED"
                        if od.category == "SELF"
                        else "NOT_SELF"
                    ),
                    "worker_semantics": (
                        "MUNICIPAL_WORK_OD_WEIGHT_NOT_BUS_RIDERSHIP_NOT_ROUTE_DEMAND"
                    ),
                }
            )

    expected = {
        "SELF": validation["self_workers"],
        "OTHER_CORE": validation["other_core_workers"],
        "S8_DIRECT": validation["s8_direct_workers"],
        "OTHER_EXTERNAL": validation["other_external_workers"],
    }
    for category, value in expected.items():
        if abs(category_mass[category] - float(value)) > 1e-9:
            raise ValueError(
                f"OD category mass mismatch {category}: "
                f"{category_mass[category]} != {value}"
            )
    if abs(sum(od.workers for od in rows) - float(validation["resident_workers"])) > 1e-9:
        raise ValueError("OD total does not match certified resident workers")

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(universe[0]),
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(universe)

    scoped = [
        od
        for od in rows
        if od.category != "SELF" and od.destination_name in footprint
    ]
    meta = {
        "od_relation_count": len(rows),
        "resident_worker_od_mass": sum(od.workers for od in rows),
        "self_worker_od_mass": sum(
            od.workers for od in rows if od.category == "SELF"
        ),
        "intermunicipal_worker_od_mass": sum(
            od.workers for od in rows if od.category != "SELF"
        ),
        "footprint_intermunicipal_od_relation_count": len(scoped),
        "footprint_intermunicipal_worker_od_mass": sum(
            od.workers for od in scoped
        ),
        "footprint_destination_municipalities": sorted(
            {od.destination_name for od in scoped}
        ),
        "structural_footprint_municipalities": sorted(footprint),
    }
    return scoped, meta


FIELDS = [
    "scenario_id",
    "topology_family",
    "public_structurally_addressable_od_relation_count",
    "public_structurally_addressable_worker_od_mass_upper_bound",
    "public_structurally_addressable_relation_share_of_footprint",
    "public_structurally_addressable_worker_mass_share_of_footprint",
    "public_plus_extensions_structurally_addressable_od_relation_count",
    "public_plus_extensions_structurally_addressable_worker_od_mass_upper_bound",
    "public_plus_extensions_structurally_addressable_relation_share_of_footprint",
    "public_plus_extensions_structurally_addressable_worker_mass_share_of_footprint",
    "public_other_core_worker_od_mass_upper_bound",
    "public_s8_direct_worker_od_mass_upper_bound",
    "public_other_external_worker_od_mass_upper_bound",
    "public_plus_extensions_other_core_worker_od_mass_upper_bound",
    "public_plus_extensions_s8_direct_worker_od_mass_upper_bound",
    "public_plus_extensions_other_external_worker_od_mass_upper_bound",
    "worker_assignment_to_routes",
    "modal_share_inferred",
    "submunicipal_worker_allocation",
    "walking_access_combined",
    "timetable_feasibility_evaluated",
    "territorial_metric_is_observed_bus_ridership",
    "topology_ranked",
    "service_policy_selected",
]


def main() -> int:
    parser = argparse.ArgumentParser()
    for name in (
        "od",
        "od_validation",
        "anchors",
        "matrix_validation",
        "routes",
        "s8_validation",
        "scenario_mapping",
    ):
        parser.add_argument(
            "--" + name.replace("_", "-"),
            dest=name,
            type=Path,
            required=True,
        )
    parser.add_argument("--od-universe-output", type=Path, required=True)
    parser.add_argument("--scenario-output", type=Path, required=True)
    parser.add_argument("--validation", type=Path, required=True)
    args = parser.parse_args()

    od_validation = loadj(args.od_validation)
    matrix_validation = loadj(args.matrix_validation)
    s8_validation = loadj(args.s8_validation)

    if (
        od_validation.get("source_scope") != "ISTAT_2021_WORK_COMMUTING_ONLY"
        or int(od_validation.get("resident_workers", -1)) != 8754
    ):
        raise ValueError("OD validation contract/scope unexpected")
    if (
        matrix_validation.get("status") != "PASS_REDUCED_PATH_MATRIX_V2_BUILD"
        or matrix_validation.get("lineage", {}).get(
            "routing_anchor_universe_sha256"
        )
        != sha(args.anchors)
    ):
        raise ValueError("Routing-anchor lineage mismatch")
    if (
        s8_validation.get("status") != "PASS_S8_PHASE_OPPORTUNITY_V2_BUILD"
        or s8_validation.get("lineage", {}).get("route_universe_sha256")
        != sha(args.routes)
        or s8_validation.get("lineage", {}).get(
            "scenario_route_mapping_sha256"
        )
        != sha(args.scenario_mapping)
    ):
        raise ValueError("Route/scenario lineage mismatch")

    anchors = load_anchors(args.anchors)
    footprint = {
        municipality
        for municipalities in anchors.values()
        for municipality in municipalities
    }
    routes = load_routes(args.routes, anchors)
    if len(routes) != int(s8_validation["unique_route_count"]):
        raise ValueError("Route count mismatch")

    scoped, meta = load_od(
        args.od,
        od_validation,
        footprint,
        args.od_universe_output,
    )
    denominator_relations = len(scoped)
    denominator_mass = sum(od.workers for od in scoped)

    raw, text = gz_writer(args.scenario_output)
    scenario_count = 0
    improved = 0
    max_public = 0.0
    max_plus_extensions = 0.0
    try:
        writer = csv.DictWriter(text, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        with gzip.open(
            args.scenario_mapping,
            "rt",
            encoding="utf-8-sig",
            newline="",
        ) as handle:
            reader = csv.DictReader(handle)
            required_mapping = {
                "scenario_id",
                "topology_family",
                "public_route_ids_json",
                "extension_route_ids_json",
            }
            if not required_mapping <= set(reader.fieldnames or []):
                raise ValueError("Scenario mapping schema invalid")

            for row in reader:
                public_ids = parse_json_list(
                    row["public_route_ids_json"],
                    "public_route_ids_json",
                )
                extension_ids = parse_json_list(
                    row["extension_route_ids_json"],
                    "extension_route_ids_json",
                )
                try:
                    public_routes = [routes[route_id] for route_id in public_ids]
                    extension_routes = [routes[route_id] for route_id in extension_ids]
                except KeyError as exc:
                    raise ValueError(
                        f"Scenario references unknown route {exc.args[0]}"
                    ) from exc

                public = summarise_addressability(scoped, public_routes, anchors)
                public_plus_extensions = summarise_addressability(
                    scoped,
                    public_routes + extension_routes,
                    anchors,
                )
                public_mass = float(
                    public["structurally_addressable_worker_od_mass_upper_bound"]
                )
                plus_mass = float(
                    public_plus_extensions[
                        "structurally_addressable_worker_od_mass_upper_bound"
                    ]
                )
                if plus_mass + 1e-9 < public_mass:
                    raise AssertionError(
                        "Adding optional extensions reduced structural addressability"
                    )
                if plus_mass > public_mass + 1e-9:
                    improved += 1
                max_public = max(max_public, public_mass)
                max_plus_extensions = max(max_plus_extensions, plus_mass)

                output_row: dict[str, object] = {
                    "scenario_id": row["scenario_id"],
                    "topology_family": row["topology_family"],
                    "public_structurally_addressable_od_relation_count": public[
                        "structurally_addressable_od_relation_count"
                    ],
                    "public_structurally_addressable_worker_od_mass_upper_bound": (
                        f"{public_mass:.9f}"
                    ),
                    "public_structurally_addressable_relation_share_of_footprint": (
                        f"{int(public['structurally_addressable_od_relation_count']) / denominator_relations if denominator_relations else 0:.9f}"
                    ),
                    "public_structurally_addressable_worker_mass_share_of_footprint": (
                        f"{public_mass / denominator_mass if denominator_mass else 0:.9f}"
                    ),
                    "public_plus_extensions_structurally_addressable_od_relation_count": (
                        public_plus_extensions[
                            "structurally_addressable_od_relation_count"
                        ]
                    ),
                    "public_plus_extensions_structurally_addressable_worker_od_mass_upper_bound": (
                        f"{plus_mass:.9f}"
                    ),
                    "public_plus_extensions_structurally_addressable_relation_share_of_footprint": (
                        f"{int(public_plus_extensions['structurally_addressable_od_relation_count']) / denominator_relations if denominator_relations else 0:.9f}"
                    ),
                    "public_plus_extensions_structurally_addressable_worker_mass_share_of_footprint": (
                        f"{plus_mass / denominator_mass if denominator_mass else 0:.9f}"
                    ),
                }
                for prefix, summary in (
                    ("public", public),
                    ("public_plus_extensions", public_plus_extensions),
                ):
                    for category in ("other_core", "s8_direct", "other_external"):
                        output_row[
                            f"{prefix}_{category}_worker_od_mass_upper_bound"
                        ] = f"{float(summary[f'{category}_addressable_worker_od_mass_upper_bound']):.9f}"
                output_row.update(
                    {
                        "worker_assignment_to_routes": "false",
                        "modal_share_inferred": "false",
                        "submunicipal_worker_allocation": "false",
                        "walking_access_combined": "false",
                        "timetable_feasibility_evaluated": "false",
                        "territorial_metric_is_observed_bus_ridership": "false",
                        "topology_ranked": "false",
                        "service_policy_selected": "false",
                    }
                )
                writer.writerow(output_row)
                scenario_count += 1
    finally:
        text.close()
        raw.close()

    if scenario_count != int(s8_validation["scenario_count"]):
        raise ValueError("Scenario count mismatch")

    report = {
        "status": STATUS,
        "contract": CONTRACT,
        "source_scope": "ISTAT_2021_WORK_COMMUTING_ONLY",
        "source_resolution": "MUNICIPAL_OD",
        "scenario_count": scenario_count,
        **meta,
        "scoped_worker_semantics": (
            "STRUCTURALLY_ADDRESSABLE_MUNICIPAL_OD_MASS_UPPER_BOUND_NOT_SERVED_PASSENGERS"
        ),
        "self_od_structural_scoring": (
            "EXCLUDED_UNRESOLVED_AT_MUNICIPAL_OD_RESOLUTION"
        ),
        "scenarios_where_optional_extensions_increase_addressable_worker_mass": improved,
        "max_public_structurally_addressable_worker_od_mass_upper_bound": max_public,
        "max_public_plus_extensions_structurally_addressable_worker_od_mass_upper_bound": (
            max_plus_extensions
        ),
        "worker_assignment_to_routes": False,
        "modal_share_inferred": False,
        "submunicipal_worker_allocation": False,
        "walking_access_combined": False,
        "timetable_feasibility_evaluated": False,
        "territorial_metric_is_observed_bus_ridership": False,
        "s8_feeder_metric_combined_into_territorial_metric": False,
        "topology_ranked": False,
        "service_policy_selected": False,
        "lineage": {
            "od": str(args.od),
            "od_sha256": sha(args.od),
            "od_validation_sha256": sha(args.od_validation),
            "anchors_sha256": sha(args.anchors),
            "matrix_validation_sha256": sha(args.matrix_validation),
            "routes_sha256": sha(args.routes),
            "s8_validation_sha256": sha(args.s8_validation),
            "scenario_mapping_sha256": sha(args.scenario_mapping),
            "od_universe_output_sha256": sha(args.od_universe_output),
            "scenario_output_sha256": sha(args.scenario_output),
        },
        "epistemic_note": (
            "Worker weights remain municipal workplace-commuting OD weights. "
            "Scenario values are upper-bound structural addressability masses: "
            "a municipality-level OD is counted only when a directed passenger-service "
            "path exists between at least one anchor in each municipality. This does "
            "not establish that the worker lives or works within walking distance of "
            "those anchors, uses bus, or has a feasible timetable. SELF OD is retained "
            "in the inventory but excluded from structural scoring."
        ),
    }
    args.validation.parent.mkdir(parents=True, exist_ok=True)
    args.validation.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                key: report[key]
                for key in (
                    "scenario_count",
                    "resident_worker_od_mass",
                    "footprint_intermunicipal_worker_od_mass",
                    "scenarios_where_optional_extensions_increase_addressable_worker_mass",
                    "max_public_structurally_addressable_worker_od_mass_upper_bound",
                    "max_public_plus_extensions_structurally_addressable_worker_od_mass_upper_bound",
                )
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
