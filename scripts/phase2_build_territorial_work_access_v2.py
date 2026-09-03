#!/usr/bin/env python3
"""Materialise territorial 2021 work-demand home-access evidence for Phase 2."""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.phase2_territorial_work_access_v2 import (
    CATEGORIES,
    CONTRACT,
    STATUS,
    aggregate_origin_demand,
    scenario_home_access_metrics,
)


THRESHOLDS = (5, 8, 10)
PROFILE_FIELDS = [
    "origin_code", "origin_name", "resident_workers", "self_workers", "other_core_workers",
    "core_local_workers", "s8_direct_workers", "other_external_workers",
]
SCENARIO_FIELDS = ["scenario_id", "topology_family"]
for threshold in THRESHOLDS:
    prefix = f"public_{threshold}min"
    SCENARIO_FIELDS += [
        f"{prefix}_worker_home_access_observed_lower_bound",
        f"{prefix}_worker_home_access_model_capacity_upper_bound",
        f"{prefix}_worker_home_access_model_capacity_upper_bound_share",
        f"{prefix}_worker_home_access_population_proportional_sensitivity",
        f"{prefix}_worker_home_access_population_proportional_sensitivity_share",
        f"{prefix}_self_worker_home_access_population_proportional_sensitivity",
        f"{prefix}_self_worker_home_access_population_proportional_sensitivity_share",
        f"{prefix}_other_core_worker_home_access_population_proportional_sensitivity",
        f"{prefix}_other_core_worker_home_access_population_proportional_sensitivity_share",
        f"{prefix}_core_local_worker_home_access_population_proportional_sensitivity",
        f"{prefix}_core_local_worker_home_access_population_proportional_sensitivity_share",
        f"{prefix}_s8_direct_worker_home_access_population_proportional_sensitivity",
        f"{prefix}_s8_direct_worker_home_access_population_proportional_sensitivity_share",
        f"{prefix}_other_external_worker_home_access_population_proportional_sensitivity",
        f"{prefix}_other_external_worker_home_access_population_proportional_sensitivity_share",
    ]
SCENARIO_FIELDS += [
    "worker_spatial_allocation_observed",
    "population_proportional_sensitivity_is_observed",
    "destination_endpoint_access_evaluated",
    "route_choice_inferred",
    "passenger_demand_assigned_to_routes",
    "full_trip_addressability_claimed",
    "full_gjt_calculated",
    "topology_ranked",
    "service_policy_selected",
]


def sha256_path(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def fmt(value: float) -> str:
    return f"{float(value):.9f}"


def check_close(a: float, b: float, *, label: str) -> None:
    if not math.isclose(float(a), float(b), rel_tol=0.0, abs_tol=1e-7):
        raise ValueError(f"{label}: {a} != {b}")


def deterministic_gzip_writer(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = path.open("wb")
    gz = gzip.GzipFile(filename="", mode="wb", fileobj=raw, compresslevel=9, mtime=0)
    text = io.TextIOWrapper(gz, encoding="utf-8", newline="")
    return raw, text


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--od-by-origin", type=Path, required=True)
    parser.add_argument("--od-validation", type=Path, required=True)
    parser.add_argument("--access", type=Path, required=True)
    parser.add_argument("--access-validation", type=Path, required=True)
    parser.add_argument("--profile-output", type=Path, required=True)
    parser.add_argument("--scenario-output", type=Path, required=True)
    parser.add_argument("--validation", type=Path, required=True)
    args = parser.parse_args()
    for path in (args.od_by_origin, args.od_validation, args.access, args.access_validation):
        if not path.is_file():
            raise FileNotFoundError(path)

    od_validation = read_json(args.od_validation)
    access_validation = read_json(args.access_validation)
    if od_validation.get("source_scope") != "ISTAT_2021_WORK_COMMUTING_ONLY":
        raise ValueError("Unexpected OD source scope")
    expected_od_hash = od_validation.get("outputs", {}).get(str(args.od_by_origin))
    if expected_od_hash != sha256_path(args.od_by_origin):
        raise ValueError("OD by-origin hash differs from certified demand profile")
    if access_validation.get("status") != "PASS_ACCESS_EQUITY_V2_BUILD" or access_validation.get("contract") != "PHASE2_BUILDING_CATCHMENT_ACCESS_EQUITY_V2":
        raise ValueError("Access Equity V2 is not certified")
    if access_validation.get("passenger_demand_inferred") is not False or access_validation.get("topology_ranked") is not False:
        raise ValueError("Access Equity upstream contains forbidden demand/ranking inference")
    if access_validation.get("lineage", {}).get("scenario_output_sha256") != sha256_path(args.access):
        raise ValueError("Access Equity scenario output hash mismatch")

    demand = aggregate_origin_demand(read_csv(args.od_by_origin))
    core_codes = tuple(sorted(str(v) for v in od_validation["core_codes"]))
    if tuple(sorted(demand)) != core_codes:
        raise ValueError("OD origin universe differs from certified five core municipalities")
    located_population = {
        str(row["code"]): float(row["located_population"])
        for row in access_validation["municipalities"]
    }
    if set(located_population) != set(demand):
        raise ValueError("Access Equity municipality universe differs from OD origin universe")

    total_workers = sum(v.worker_total for v in demand.values())
    self_workers = sum(float(v.by_category["SELF"]) for v in demand.values())
    other_core_workers = sum(float(v.by_category["OTHER_CORE"]) for v in demand.values())
    s8_workers = sum(float(v.by_category["S8_DIRECT"]) for v in demand.values())
    other_external_workers = sum(float(v.by_category["OTHER_EXTERNAL"]) for v in demand.values())
    check_close(total_workers, float(od_validation["resident_workers"]), label="resident_workers")
    check_close(self_workers, float(od_validation["self_workers"]), label="self_workers")
    check_close(other_core_workers, float(od_validation["other_core_workers"]), label="other_core_workers")
    check_close(s8_workers, float(od_validation["s8_direct_workers"]), label="s8_direct_workers")
    check_close(other_external_workers, float(od_validation["other_external_workers"]), label="other_external_workers")
    core_local_workers = self_workers + other_core_workers

    args.profile_output.parent.mkdir(parents=True, exist_ok=True)
    with args.profile_output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=PROFILE_FIELDS, lineterminator="\n")
        writer.writeheader()
        for code in sorted(demand):
            d = demand[code]
            writer.writerow({
                "origin_code": code,
                "origin_name": d.origin_name,
                "resident_workers": int(d.worker_total),
                "self_workers": int(d.by_category["SELF"]),
                "other_core_workers": int(d.by_category["OTHER_CORE"]),
                "core_local_workers": int(d.core_local_total),
                "s8_direct_workers": int(d.by_category["S8_DIRECT"]),
                "other_external_workers": int(d.by_category["OTHER_EXTERNAL"]),
            })

    maxima = {t: {"capacity": 0.0, "sensitivity": 0.0, "core_local": 0.0, "s8": 0.0, "other_external": 0.0} for t in THRESHOLDS}
    minima = {t: {"capacity": float("inf"), "sensitivity": float("inf")} for t in THRESHOLDS}
    family_counts: dict[str, int] = {}
    scenario_count = 0
    seen: set[str] = set()
    raw, text = deterministic_gzip_writer(args.scenario_output)
    try:
        writer = csv.DictWriter(text, fieldnames=SCENARIO_FIELDS, lineterminator="\n")
        writer.writeheader()
        with gzip.open(args.access, "rt", encoding="utf-8-sig", newline="") as source:
            reader = csv.DictReader(source)
            for access_row in reader:
                scenario_id = str(access_row["scenario_id"]).strip()
                family = str(access_row["topology_family"]).strip()
                if not scenario_id or scenario_id in seen or not family:
                    raise ValueError("Access scenario has missing/duplicate identity")
                seen.add(scenario_id)
                family_counts[family] = family_counts.get(family, 0) + 1
                row: dict[str, object] = {"scenario_id": scenario_id, "topology_family": family}
                for threshold in THRESHOLDS:
                    coverage = {
                        code: float(access_row[f"public_municipality_{code}_coverage_share_{threshold}min"])
                        for code in sorted(demand)
                    }
                    metrics = scenario_home_access_metrics(
                        origin_demand=demand,
                        located_population=located_population,
                        coverage_share=coverage,
                    )
                    total_prop = metrics["population_proportional_total"]
                    cat_sum = (
                        metrics["population_proportional_self"]
                        + metrics["population_proportional_other_core"]
                        + metrics["population_proportional_s8_direct"]
                        + metrics["population_proportional_other_external"]
                    )
                    check_close(total_prop, cat_sum, label=f"{scenario_id} {threshold}min sensitivity category sum")
                    prefix = f"public_{threshold}min"
                    row.update({
                        f"{prefix}_worker_home_access_observed_lower_bound": "0.000000000",
                        f"{prefix}_worker_home_access_model_capacity_upper_bound": fmt(metrics["capacity_upper_bound"]),
                        f"{prefix}_worker_home_access_model_capacity_upper_bound_share": fmt(metrics["capacity_upper_bound"] / total_workers),
                        f"{prefix}_worker_home_access_population_proportional_sensitivity": fmt(total_prop),
                        f"{prefix}_worker_home_access_population_proportional_sensitivity_share": fmt(total_prop / total_workers),
                        f"{prefix}_self_worker_home_access_population_proportional_sensitivity": fmt(metrics["population_proportional_self"]),
                        f"{prefix}_self_worker_home_access_population_proportional_sensitivity_share": fmt(metrics["population_proportional_self"] / self_workers),
                        f"{prefix}_other_core_worker_home_access_population_proportional_sensitivity": fmt(metrics["population_proportional_other_core"]),
                        f"{prefix}_other_core_worker_home_access_population_proportional_sensitivity_share": fmt(metrics["population_proportional_other_core"] / other_core_workers),
                        f"{prefix}_core_local_worker_home_access_population_proportional_sensitivity": fmt(metrics["population_proportional_core_local"]),
                        f"{prefix}_core_local_worker_home_access_population_proportional_sensitivity_share": fmt(metrics["population_proportional_core_local"] / core_local_workers),
                        f"{prefix}_s8_direct_worker_home_access_population_proportional_sensitivity": fmt(metrics["population_proportional_s8_direct"]),
                        f"{prefix}_s8_direct_worker_home_access_population_proportional_sensitivity_share": fmt(metrics["population_proportional_s8_direct"] / s8_workers),
                        f"{prefix}_other_external_worker_home_access_population_proportional_sensitivity": fmt(metrics["population_proportional_other_external"]),
                        f"{prefix}_other_external_worker_home_access_population_proportional_sensitivity_share": fmt(metrics["population_proportional_other_external"] / other_external_workers),
                    })
                    maxima[threshold]["capacity"] = max(maxima[threshold]["capacity"], metrics["capacity_upper_bound"])
                    maxima[threshold]["sensitivity"] = max(maxima[threshold]["sensitivity"], total_prop)
                    maxima[threshold]["core_local"] = max(maxima[threshold]["core_local"], metrics["population_proportional_core_local"])
                    maxima[threshold]["s8"] = max(maxima[threshold]["s8"], metrics["population_proportional_s8_direct"])
                    maxima[threshold]["other_external"] = max(maxima[threshold]["other_external"], metrics["population_proportional_other_external"])
                    minima[threshold]["capacity"] = min(minima[threshold]["capacity"], metrics["capacity_upper_bound"])
                    minima[threshold]["sensitivity"] = min(minima[threshold]["sensitivity"], total_prop)
                row.update({
                    "worker_spatial_allocation_observed": "false",
                    "population_proportional_sensitivity_is_observed": "false",
                    "destination_endpoint_access_evaluated": "false",
                    "route_choice_inferred": "false",
                    "passenger_demand_assigned_to_routes": "false",
                    "full_trip_addressability_claimed": "false",
                    "full_gjt_calculated": "false",
                    "topology_ranked": "false",
                    "service_policy_selected": "false",
                })
                writer.writerow(row)
                scenario_count += 1
    finally:
        text.close()
        raw.close()

    if scenario_count != int(access_validation["scenario_count"]):
        raise ValueError("Territorial work-access scenario count differs from Access Equity V2")
    if scenario_count != 100000:
        raise ValueError("Expected exactly 100,000 scenarios")

    report = {
        "status": STATUS,
        "contract": CONTRACT,
        "evidence_label": "MUNICIPAL_WORK_OD_PLUS_HOME_END_WALK_ACCESS_NO_ROUTE_ALLOCATION",
        "source_scope": "ISTAT_2021_WORK_COMMUTING_ONLY",
        "source_resolution": "MUNICIPAL_OD",
        "scenario_count": scenario_count,
        "origin_municipality_count": len(demand),
        "resident_workers": total_workers,
        "self_workers": self_workers,
        "other_core_workers": other_core_workers,
        "core_local_workers": core_local_workers,
        "s8_direct_workers": s8_workers,
        "other_external_workers": other_external_workers,
        "s8_direct_share_of_resident_workers": s8_workers / total_workers,
        "core_local_share_of_resident_workers": core_local_workers / total_workers,
        "other_external_share_of_resident_workers": other_external_workers / total_workers,
        "model_capacity_upper_bound_semantics": "MAX_WORKERS_THAT_COULD_FIT_INSIDE_MODELED_COVERED_RESIDENT_COUNT_NOT_OBSERVED_ACCESS",
        "observed_worker_home_access_lower_bound": 0.0,
        "population_proportional_sensitivity_semantics": "EXPLICIT_ASSUMPTION_WORKERS_DISTRIBUTED_LIKE_MODELED_RESIDENTS_WITHIN_EACH_ORIGIN_MUNICIPALITY",
        "population_proportional_sensitivity_is_observed": False,
        "category_sensitivity_estimates_additive": True,
        "destination_endpoint_access_evaluated": False,
        "worker_spatial_allocation_observed": False,
        "route_choice_inferred": False,
        "passenger_demand_assigned_to_routes": False,
        "full_trip_addressability_claimed": False,
        "full_gjt_calculated": False,
        "topology_ranked": False,
        "service_policy_selected": False,
        "scenario_family_counts": dict(sorted(family_counts.items())),
        "threshold_summary": {
            str(t): {
                "min_model_capacity_upper_bound_workers": minima[t]["capacity"],
                "max_model_capacity_upper_bound_workers": maxima[t]["capacity"],
                "min_population_proportional_sensitivity_workers": minima[t]["sensitivity"],
                "max_population_proportional_sensitivity_workers": maxima[t]["sensitivity"],
                "max_population_proportional_core_local_workers": maxima[t]["core_local"],
                "max_population_proportional_s8_direct_workers": maxima[t]["s8"],
                "max_population_proportional_other_external_workers": maxima[t]["other_external"],
            }
            for t in THRESHOLDS
        },
        "limitations": [
            "The observed 2021 work OD matrix has municipal origins and destinations only; no worker is observed at a building, stop or route.",
            "The model-capacity upper bound uses modeled covered resident counts and is not a statistical confidence interval or observed worker-access count.",
            "The population-proportional sensitivity is an explicit within-municipality assumption and must never be relabeled as observed 2021 worker accessibility.",
            "Only the home endpoint is tested against walking access; workplace endpoint access and full-trip bus usefulness are not established.",
            "The work matrix excludes complete school, healthcare, shopping, service and leisure demand.",
        ],
        "lineage": {
            "od_by_origin": str(args.od_by_origin),
            "od_by_origin_sha256": sha256_path(args.od_by_origin),
            "od_validation": str(args.od_validation),
            "od_validation_sha256": sha256_path(args.od_validation),
            "access": str(args.access),
            "access_sha256": sha256_path(args.access),
            "access_validation": str(args.access_validation),
            "access_validation_sha256": sha256_path(args.access_validation),
            "profile_output": str(args.profile_output),
            "profile_output_sha256": sha256_path(args.profile_output),
            "scenario_output": str(args.scenario_output),
            "scenario_output_sha256": sha256_path(args.scenario_output),
        },
    }
    args.validation.parent.mkdir(parents=True, exist_ok=True)
    args.validation.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": report["status"],
        "resident_workers": report["resident_workers"],
        "core_local_workers": report["core_local_workers"],
        "s8_direct_workers": report["s8_direct_workers"],
        "other_external_workers": report["other_external_workers"],
        "threshold_summary": report["threshold_summary"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
