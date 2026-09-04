#!/usr/bin/env python3
"""Build scenario-level Territorial Commuting Addressability V2.

The output is a structural municipal OD worker-mass upper bound.  It is not a
ridership forecast and does not assign workers to routes or infer mode choice.
"""
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
    EVALUATED_CATEGORIES,
    EXCLUDED_CATEGORIES,
    ODRelation,
    canonical_place,
    evaluate_scenario,
)

CORE_NAMES = frozenset({
    canonical_place("Brivio"),
    canonical_place("Calco"),
    canonical_place("La Valletta Brianza"),
    canonical_place("Olgiate Molgora"),
    canonical_place("Santa Maria Hoè"),
})

OUTPUT_FIELDS = [
    "scenario_id", "topology_family", "public_route_count",
    "evaluated_od_relation_count", "evaluated_od_worker_mass",
    "evaluated_other_core_relation_count", "evaluated_other_core_worker_mass",
    "evaluated_other_external_relation_count", "evaluated_other_external_worker_mass",
    "structurally_addressable_od_relation_count", "structurally_addressable_od_worker_mass_upper_bound",
    "structurally_addressable_od_worker_mass_share",
    "structurally_addressable_other_core_relation_count", "structurally_addressable_other_core_worker_mass_upper_bound",
    "structurally_addressable_other_external_relation_count", "structurally_addressable_other_external_worker_mass_upper_bound",
    "self_workers_excluded", "s8_direct_workers_excluded",
    "passenger_assignment_inferred", "mode_choice_inferred", "ridership_forecast",
]


def sha256_path(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv(path: Path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        yield from csv.DictReader(handle)


def read_gzip_csv(path: Path):
    with gzip.open(path, "rt", encoding="utf-8-sig", newline="") as handle:
        yield from csv.DictReader(handle)


def parse_json_ids(value: str, *, scenario_id: str, field: str) -> list[str]:
    raw = json.loads(value)
    if not isinstance(raw, list) or any(not isinstance(v, str) or not v for v in raw):
        raise ValueError(f"{scenario_id}: invalid {field}")
    if len(raw) != len(set(raw)):
        raise ValueError(f"{scenario_id}: duplicate route ID in {field}")
    return raw


def load_anchor_municipalities(path: Path) -> dict[str, frozenset[str]]:
    out: dict[str, frozenset[str]] = {}
    for row in read_csv(path):
        anchor = str(row.get("anchor_id", "")).strip()
        if not anchor or anchor in out:
            raise ValueError("routing-anchor universe has blank or duplicate anchor_id")
        raw = str(row.get("municipalities", "")).strip()
        municipalities = frozenset(
            canonical_place(v) for v in raw.split("|") if canonical_place(v)
        )
        if not municipalities:
            raise ValueError(f"{anchor}: no explicit municipality lineage")
        out[anchor] = municipalities
    if len(out) != 198:
        raise ValueError(f"Expected 198 routing anchors, got {len(out)}")
    represented = set().union(*out.values())
    missing_core = CORE_NAMES - represented
    if missing_core:
        raise ValueError(f"Core municipalities missing from routing anchors: {sorted(missing_core)}")
    return out


def load_od_relations(path: Path, validation: dict, represented: set[str]):
    all_rows: list[ODRelation] = []
    seen_pairs: set[tuple[str, str]] = set()
    category_workers: dict[str, int] = {}
    for row in read_csv(path):
        origin_name = str(row["origin_name"]).strip()
        destination_name = str(row["destination_name"]).strip()
        origin_key = canonical_place(origin_name)
        destination_key = canonical_place(destination_name)
        category = str(row["category"]).strip()
        workers = int(row["workers"])
        if workers <= 0:
            raise ValueError("OD relation has non-positive worker count")
        if origin_key not in CORE_NAMES:
            raise ValueError(f"Unexpected OD origin outside core: {origin_name}")
        pair = (str(row["origin_code"]), str(row["destination_code"]))
        if pair in seen_pairs:
            raise ValueError(f"Duplicate OD code pair: {pair}")
        seen_pairs.add(pair)
        if category not in EVALUATED_CATEGORIES | EXCLUDED_CATEGORIES:
            raise ValueError(f"Unexpected OD category {category}")
        category_workers[category] = category_workers.get(category, 0) + workers
        all_rows.append(ODRelation(origin_name, destination_name, origin_key, destination_key, workers, category))

    expected = {
        "SELF": int(validation["self_workers"]),
        "OTHER_CORE": int(validation["other_core_workers"]),
        "S8_DIRECT": int(validation["s8_direct_workers"]),
        "OTHER_EXTERNAL": int(validation["other_external_workers"]),
    }
    if category_workers != expected:
        raise ValueError(f"OD category totals differ from certified validation: {category_workers} != {expected}")
    if sum(category_workers.values()) != int(validation["resident_workers"]):
        raise ValueError("OD resident-worker total differs from validation")

    evaluated = tuple(
        rel for rel in all_rows
        if rel.category in EVALUATED_CATEGORIES and rel.destination_key in represented
    )
    unrepresented = tuple(
        rel for rel in all_rows
        if rel.category in EVALUATED_CATEGORIES and rel.destination_key not in represented
    )
    if not evaluated:
        raise ValueError("No territorial OD relation is represented in the routing-anchor universe")
    return evaluated, unrepresented, expected


def load_routes(path: Path, known_anchors: set[str]) -> dict[str, tuple[str, ...]]:
    routes: dict[str, tuple[str, ...]] = {}
    for row in read_csv(path):
        route_id = str(row.get("scenario_route_id", "")).strip()
        if not route_id or route_id in routes:
            raise ValueError("unique-route universe has blank or duplicate scenario_route_id")
        anchors = tuple(v for v in str(row.get("public_anchor_ids", "")).split("|") if v)
        if not anchors:
            raise ValueError(f"{route_id}: no public anchors")
        unknown = set(anchors) - known_anchors
        if unknown:
            raise ValueError(f"{route_id}: unknown public anchors {sorted(unknown)[:5]}")
        routes[route_id] = anchors
    if len(routes) != 50115:
        raise ValueError(f"Expected 50,115 unique routes, got {len(routes)}")
    return routes


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--od", type=Path, required=True)
    p.add_argument("--od-validation", type=Path, required=True)
    p.add_argument("--routing-anchors", type=Path, required=True)
    p.add_argument("--route-universe", type=Path, required=True)
    p.add_argument("--scenario-route-mapping", type=Path, required=True)
    p.add_argument("--phasing-validation", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--validation-output", type=Path, required=True)
    args = p.parse_args()
    for path in (args.od, args.od_validation, args.routing_anchors, args.route_universe, args.scenario_route_mapping, args.phasing_validation):
        if not path.is_file():
            raise FileNotFoundError(path)

    od_validation = read_json(args.od_validation)
    phasing = read_json(args.phasing_validation)
    if int(od_validation.get("resident_workers", -1)) != 8754:
        raise ValueError("OD validation is not the certified 2021 resident-worker profile")
    if phasing.get("status") != "PASS_S8_PHASE_OPPORTUNITY_V2_BUILD" or phasing.get("contract") != "PHASE2_S8_PHASE_OPPORTUNITY_SURFACE_V2":
        raise ValueError("S8 route/mapping lineage is not certified")
    if int(phasing.get("scenario_count", -1)) != 100000 or int(phasing.get("unique_route_count", -1)) != 50115:
        raise ValueError("Unexpected S8 route/mapping universe size")
    lineage = phasing.get("lineage", {})
    if lineage.get("route_universe_sha256") != sha256_path(args.route_universe):
        raise ValueError("Unique-route universe hash differs from certified S8 lineage")
    if lineage.get("scenario_route_mapping_sha256") != sha256_path(args.scenario_route_mapping):
        raise ValueError("Scenario-route mapping hash differs from certified S8 lineage")

    anchor_municipalities = load_anchor_municipalities(args.routing_anchors)
    represented = set().union(*anchor_municipalities.values())
    evaluated, unrepresented, category_totals = load_od_relations(args.od, od_validation, represented)
    routes = load_routes(args.route_universe, set(anchor_municipalities))

    eval_workers = sum(r.workers for r in evaluated)
    eval_core_workers = sum(r.workers for r in evaluated if r.category == "OTHER_CORE")
    eval_ext_workers = sum(r.workers for r in evaluated if r.category == "OTHER_EXTERNAL")
    eval_core_relations = sum(r.category == "OTHER_CORE" for r in evaluated)
    eval_ext_relations = sum(r.category == "OTHER_EXTERNAL" for r in evaluated)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    raw = args.output.open("wb")
    gz = gzip.GzipFile(filename="", mode="wb", fileobj=raw, compresslevel=9, mtime=0)
    text = io.TextIOWrapper(gz, encoding="utf-8", newline="")
    scenario_count = 0
    family_counts: dict[str, int] = {}
    max_mass = -1
    max_scenarios: list[str] = []
    min_mass: int | None = None
    try:
        writer = csv.DictWriter(text, fieldnames=OUTPUT_FIELDS, lineterminator="\n")
        writer.writeheader()
        for row in read_gzip_csv(args.scenario_route_mapping):
            scenario_id = str(row["scenario_id"])
            family = str(row["topology_family"])
            public_ids = parse_json_ids(row["public_route_ids_json"], scenario_id=scenario_id, field="public_route_ids_json")
            unknown_routes = set(public_ids) - set(routes)
            if unknown_routes:
                raise ValueError(f"{scenario_id}: unknown public route IDs")
            result = evaluate_scenario(
                public_route_anchor_sequences=[routes[rid] for rid in public_ids],
                anchor_municipalities=anchor_municipalities,
                relations=evaluated,
            )
            mass = result.addressable_worker_mass
            if mass > max_mass:
                max_mass = mass
                max_scenarios = [scenario_id]
            elif mass == max_mass and len(max_scenarios) < 20:
                max_scenarios.append(scenario_id)
            min_mass = mass if min_mass is None else min(min_mass, mass)
            writer.writerow({
                "scenario_id": scenario_id,
                "topology_family": family,
                "public_route_count": len(public_ids),
                "evaluated_od_relation_count": len(evaluated),
                "evaluated_od_worker_mass": eval_workers,
                "evaluated_other_core_relation_count": eval_core_relations,
                "evaluated_other_core_worker_mass": eval_core_workers,
                "evaluated_other_external_relation_count": eval_ext_relations,
                "evaluated_other_external_worker_mass": eval_ext_workers,
                "structurally_addressable_od_relation_count": result.addressable_relation_count,
                "structurally_addressable_od_worker_mass_upper_bound": mass,
                "structurally_addressable_od_worker_mass_share": f"{mass / eval_workers:.12f}",
                "structurally_addressable_other_core_relation_count": result.other_core_addressable_relation_count,
                "structurally_addressable_other_core_worker_mass_upper_bound": result.other_core_addressable_worker_mass,
                "structurally_addressable_other_external_relation_count": result.other_external_addressable_relation_count,
                "structurally_addressable_other_external_worker_mass_upper_bound": result.other_external_addressable_worker_mass,
                "self_workers_excluded": category_totals["SELF"],
                "s8_direct_workers_excluded": category_totals["S8_DIRECT"],
                "passenger_assignment_inferred": "false",
                "mode_choice_inferred": "false",
                "ridership_forecast": "false",
            })
            scenario_count += 1
            family_counts[family] = family_counts.get(family, 0) + 1
    finally:
        text.flush()
        text.close()
        raw.close()

    if scenario_count != 100000:
        raise ValueError(f"Expected 100,000 scenarios, got {scenario_count}")

    unrepresented_workers = sum(r.workers for r in unrepresented)
    unrepresented_relations = len(unrepresented)
    validation = {
        "status": STATUS,
        "contract": CONTRACT,
        "evidence_label": "STRUCTURAL_MUNICIPAL_OD_ADDRESSABILITY_UPPER_BOUND_NOT_RIDERSHIP",
        "scenario_count": scenario_count,
        "family_counts": dict(sorted(family_counts.items())),
        "resident_workers_source_total": int(od_validation["resident_workers"]),
        "self_workers_excluded_submunicipal_geography_unavailable": category_totals["SELF"],
        "s8_direct_workers_excluded_to_avoid_feeder_double_count": category_totals["S8_DIRECT"],
        "territorial_categories": sorted(EVALUATED_CATEGORIES),
        "routing_anchor_represented_municipality_count": len(represented),
        "evaluated_od_relation_count": len(evaluated),
        "evaluated_od_worker_mass": eval_workers,
        "evaluated_other_core_worker_mass": eval_core_workers,
        "evaluated_other_external_worker_mass": eval_ext_workers,
        "otherwise_territorial_but_destination_not_in_routing_anchor_universe_relation_count": unrepresented_relations,
        "otherwise_territorial_but_destination_not_in_routing_anchor_universe_worker_mass": unrepresented_workers,
        "minimum_structurally_addressable_worker_mass": min_mass,
        "maximum_structurally_addressable_worker_mass": max_mass,
        "maximum_worker_mass_example_scenario_ids": max_scenarios,
        "directional_public_graph": True,
        "same_anchor_transfers_allowed": True,
        "technical_return_edges_used": False,
        "self_od_auto_addressable": False,
        "s8_direct_in_primary_territorial_metric": False,
        "passenger_assignment_inferred": False,
        "mode_choice_inferred": False,
        "ridership_forecast": False,
        "walking_access_to_exact_home_or_workplace_inferred": False,
        "lineage": {
            "od": str(args.od),
            "od_sha256": sha256_path(args.od),
            "od_validation": str(args.od_validation),
            "od_validation_sha256": sha256_path(args.od_validation),
            "routing_anchors": str(args.routing_anchors),
            "routing_anchors_sha256": sha256_path(args.routing_anchors),
            "route_universe": str(args.route_universe),
            "route_universe_sha256": sha256_path(args.route_universe),
            "scenario_route_mapping": str(args.scenario_route_mapping),
            "scenario_route_mapping_sha256": sha256_path(args.scenario_route_mapping),
            "phasing_validation": str(args.phasing_validation),
            "phasing_validation_sha256": sha256_path(args.phasing_validation),
            "output_sha256": sha256_path(args.output),
        },
        "epistemic_note": "Worker counts are municipal OD mass whose origin and destination municipalities are structurally connected by the scenario public-anchor graph. They are not predicted bus passengers. Exact household/workplace location, walking access, modal choice and route assignment remain unknown. S8_DIRECT is intentionally excluded from the primary territorial metric and is evaluated separately in the feeder block.",
    }
    args.validation_output.parent.mkdir(parents=True, exist_ok=True)
    args.validation_output.write_text(json.dumps(validation, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(validation, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
