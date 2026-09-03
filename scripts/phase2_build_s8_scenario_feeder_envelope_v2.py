#!/usr/bin/env python3
"""Materialise a scenario-level S8 feeder envelope without route demand imputation."""
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

from src.phase2_s8_scenario_feeder_envelope_v2 import (
    RouteTimingGap,
    SCENARIO_FEEDER_CONTRACT,
    SCENARIO_FEEDER_STATUS,
    summarise_role,
)


CLASS_NAMES = ("roundtrip", "rail_to_bus_only")
CLASS_FIELDS = (
    "route_count",
    "complete_match_route_count",
    "no_complete_match_route_count",
    "complete_match_route_share",
    "all_routes_have_complete_match_phase",
    "any_route_has_complete_match_phase",
    "best_complete_gap_min_min",
    "best_complete_gap_min_max",
    "worst_complete_gap_min_min",
    "worst_complete_gap_min_max",
)
ROLE_FIELDS = (
    "route_count",
    "complete_match_route_count",
    "complete_match_route_share",
    "all_routes_have_some_complete_match_phase",
    "any_route_has_some_complete_match_phase",
)
BASE_FIELDS = [
    "scenario_id",
    "topology_family",
    "uniform_headway_min",
    "span_id",
    "span_start_min",
    "span_end_min",
]
OUTPUT_FIELDS = list(BASE_FIELDS)
for role in ("public", "extension"):
    OUTPUT_FIELDS.extend(f"{role}_{field}" for field in ROLE_FIELDS)
    for class_name in CLASS_NAMES:
        OUTPUT_FIELDS.extend(f"{role}_{class_name}_{field}" for field in CLASS_FIELDS)
OUTPUT_FIELDS.extend([
    "worker_direction_weight_reference",
    "demand_weight_semantics",
    "route_weighting_applied",
    "worker_reference_assigned_to_routes",
    "cross_route_phase_selected",
    "joint_vehicle_block_timetable_feasibility_evaluated",
    "passenger_utility_calculated",
    "full_gjt_calculated",
    "topology_ranked",
    "service_policy_selected",
])


def sha256_path(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _bool(value: object, *, field: str) -> bool:
    text = str(value).strip().lower()
    if text == "true":
        return True
    if text == "false":
        return False
    raise ValueError(f"Invalid boolean for {field}: {value!r}")


def _optional_float(value: object) -> float | None:
    text = str(value).strip()
    return None if text == "" else float(text)


def _fmt(value: object) -> object:
    if value is None:
        return ""
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, float):
        return f"{value:.9f}"
    return value


def deterministic_gzip_writer(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = path.open("wb")
    gz = gzip.GzipFile(filename="", mode="wb", fileobj=raw, compresslevel=9, mtime=0)
    text = io.TextIOWrapper(gz, encoding="utf-8", newline="")
    return raw, text


def validate_upstream(
    *,
    transfer_gap_path: Path,
    transfer_gap_validation_path: Path,
    scenario_mapping_path: Path,
    scenario_support_path: Path,
    support_validation_path: Path,
) -> tuple[dict, dict]:
    gap = load_json(transfer_gap_validation_path)
    support = load_json(support_validation_path)
    if gap.get("status") != "PASS_S8_TRANSFER_GAP_ENVELOPE_V2_BUILD" or gap.get("contract") != "PHASE2_S8_TRANSFER_GAP_ENVELOPE_V2":
        raise ValueError("S8 transfer-gap envelope is not certified")
    if support.get("status") != "PASS_S8_PASSENGER_SUPPORT_MASK_V2_BUILD" or support.get("contract") != "PHASE2_S8_PASSENGER_SUPPORT_MASK_V2":
        raise ValueError("S8 passenger-support mask is not certified")
    if gap.get("lineage", {}).get("output_sha256") != sha256_path(transfer_gap_path):
        raise ValueError("S8 transfer-gap output hash mismatch")
    if support.get("lineage", {}).get("s8_scenario_route_mapping_sha256") != sha256_path(scenario_mapping_path):
        raise ValueError("Scenario-route mapping hash mismatch")
    if support.get("lineage", {}).get("scenario_support_output_sha256") != sha256_path(scenario_support_path):
        raise ValueError("Scenario passenger-support output hash mismatch")
    if float(gap.get("worker_direction_weight_reference", -1)) != 1882.0:
        raise ValueError("Unexpected S8 worker-direction reference")
    if gap.get("worker_reference_assigned_to_routes") is not False:
        raise ValueError("Upstream transfer-gap envelope assigned workers to routes")
    if gap.get("demand_weight_semantics") != "DIRECTION_WEIGHT_ONLY_NOT_ROUTE_DEMAND_NOT_MODAL_SHARE":
        raise ValueError("Unexpected S8 transfer-gap demand semantics")
    for field in ("phase_selected", "passenger_utility_calculated", "full_gjt_calculated", "topology_ranked", "service_policy_selected"):
        if gap.get(field) is not False:
            raise ValueError(f"Upstream transfer-gap envelope violates {field}=false")
    for field in ("passenger_demand_assigned_to_routes", "passenger_utility_calculated", "full_gjt_calculated", "topology_ranked", "service_policy_selected"):
        if support.get(field) is not False:
            raise ValueError(f"Upstream passenger-support mask violates {field}=false")
    if int(gap.get("route_count", -1)) != int(support.get("route_count", -2)):
        raise ValueError("Route counts disagree across certified feeder inputs")
    if int(gap.get("timing_archetype_count", -1)) != 8:
        raise ValueError("Expected eight certified timing archetypes")
    if int(support.get("scenario_count", -1)) != 100_000:
        raise ValueError("Expected 100000 certified scenarios")
    return gap, support


def load_transfer_gaps(path: Path, validation: dict) -> tuple[dict[tuple[int, str], dict[str, RouteTimingGap]], dict[tuple[int, str], tuple[int, int]]]:
    timing_maps: dict[tuple[int, str], dict[str, RouteTimingGap]] = {}
    timing_spans: dict[tuple[int, str], tuple[int, int]] = {}
    row_count = 0
    with gzip.open(path, "rt", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {
            "route_id", "roundtrip_passenger_supported", "uniform_headway_min", "span_id",
            "span_start_min", "span_end_min", "complete_match_phase_count",
            "best_complete_phase_weighted_mean_gap_min", "worst_complete_phase_weighted_mean_gap_min",
            "demand_weight_reference_workers", "demand_weight_semantics",
            "passenger_demand_assigned_to_route", "phase_selected", "topology_ranked",
        }
        if not required <= set(reader.fieldnames or []):
            raise ValueError("Transfer-gap input has invalid schema")
        for line_no, row in enumerate(reader, start=2):
            if row["demand_weight_semantics"] != "DIRECTION_WEIGHT_ONLY_NOT_ROUTE_DEMAND_NOT_MODAL_SHARE":
                raise ValueError(f"Unexpected demand semantics at transfer-gap line {line_no}")
            if abs(float(row["demand_weight_reference_workers"]) - 1882.0) > 1e-9:
                raise ValueError(f"Unexpected worker reference at transfer-gap line {line_no}")
            if _bool(row["passenger_demand_assigned_to_route"], field="passenger_demand_assigned_to_route"):
                raise ValueError("Transfer-gap row assigns passenger demand to a route")
            if _bool(row["phase_selected"], field="phase_selected") or _bool(row["topology_ranked"], field="topology_ranked"):
                raise ValueError("Transfer-gap row contains forbidden downstream selection")
            headway = int(row["uniform_headway_min"])
            span_id = str(row["span_id"])
            timing = (headway, span_id)
            span = (int(row["span_start_min"]), int(row["span_end_min"]))
            existing_span = timing_spans.setdefault(timing, span)
            if existing_span != span:
                raise ValueError(f"Conflicting span definition for timing archetype {timing}")
            route_id = str(row["route_id"])
            gap = RouteTimingGap(
                route_id=route_id,
                roundtrip_passenger_supported=_bool(row["roundtrip_passenger_supported"], field="roundtrip_passenger_supported"),
                complete_match_phase_count=int(row["complete_match_phase_count"]),
                best_complete_phase_weighted_mean_gap_min=_optional_float(row["best_complete_phase_weighted_mean_gap_min"]),
                worst_complete_phase_weighted_mean_gap_min=_optional_float(row["worst_complete_phase_weighted_mean_gap_min"]),
            )
            gap.validate()
            route_map = timing_maps.setdefault(timing, {})
            if route_id in route_map:
                raise ValueError(f"Duplicate route/timing transfer-gap row: {route_id} {timing}")
            route_map[route_id] = gap
            row_count += 1
    if row_count != int(validation["route_timing_row_count"]):
        raise ValueError("Transfer-gap row count differs from certified validation")
    if len(timing_maps) != int(validation["timing_archetype_count"]):
        raise ValueError("Timing-archetype count differs from certified validation")
    expected_routes = int(validation["route_count"])
    for timing, route_map in timing_maps.items():
        if len(route_map) != expected_routes:
            raise ValueError(f"Timing archetype {timing} does not cover the complete route universe")
    return dict(sorted(timing_maps.items())), timing_spans


def _flatten_role(prefix: str, summary: dict[str, object], out: dict[str, object]) -> None:
    for field in ROLE_FIELDS:
        out[f"{prefix}_{field}"] = summary[field]
    for class_name in CLASS_NAMES:
        class_summary = summary[class_name]
        for field in CLASS_FIELDS:
            out[f"{prefix}_{class_name}_{field}"] = class_summary[field]


def _load_route_ids(value: str, *, field: str) -> list[str]:
    payload = json.loads(value)
    if not isinstance(payload, list) or any(not isinstance(v, str) or not v for v in payload):
        raise ValueError(f"Invalid {field}")
    if len(payload) != len(set(payload)):
        raise ValueError(f"Duplicate route IDs in {field}")
    return payload


def _crosscheck_support(mapping: dict[str, str], support: dict[str, str], public_ids: list[str], extension_ids: list[str]) -> None:
    if mapping["scenario_id"] != support["scenario_id"] or mapping["topology_family"] != support["topology_family"]:
        raise ValueError("Scenario mapping and support rows are not aligned")
    expected = {
        "public_route_count": len(public_ids),
        "extension_route_count": len(extension_ids),
    }
    for field, value in expected.items():
        if int(support[field]) != value:
            raise ValueError(f"Scenario support count mismatch for {field}")
    if int(support["public_roundtrip_supported_route_count"]) + int(support["public_rail_to_bus_only_route_count"]) != len(public_ids):
        raise ValueError("Public passenger-support partition mismatch")
    if int(support["extension_roundtrip_supported_route_count"]) + int(support["extension_rail_to_bus_only_route_count"]) != len(extension_ids):
        raise ValueError("Extension passenger-support partition mismatch")
    for field in ("passenger_demand_assigned_to_routes", "scenario_passenger_utility_calculated", "topology_ranked"):
        if _bool(support[field], field=field):
            raise ValueError(f"Scenario support row violates {field}=false")


def materialise(
    *,
    scenario_mapping_path: Path,
    scenario_support_path: Path,
    timing_maps: dict[tuple[int, str], dict[str, RouteTimingGap]],
    timing_spans: dict[tuple[int, str], tuple[int, int]],
    output_path: Path,
) -> dict:
    raw, text = deterministic_gzip_writer(output_path)
    scenario_count = 0
    output_rows = 0
    rows_with_all_public_routes_complete = 0
    rows_with_any_public_route_complete = 0
    rows_with_public_roundtrip_routes = 0
    rows_with_public_directional_only_routes = 0
    family_counts: dict[str, int] = {}
    try:
        writer = csv.DictWriter(text, fieldnames=OUTPUT_FIELDS, lineterminator="\n")
        writer.writeheader()
        with gzip.open(scenario_mapping_path, "rt", encoding="utf-8-sig", newline="") as mapping_handle, gzip.open(scenario_support_path, "rt", encoding="utf-8-sig", newline="") as support_handle:
            mapping_reader = csv.DictReader(mapping_handle)
            support_reader = csv.DictReader(support_handle)
            for mapping, support in zip(mapping_reader, support_reader):
                public_ids = _load_route_ids(mapping["public_route_ids_json"], field="public_route_ids_json")
                extension_ids = _load_route_ids(mapping["extension_route_ids_json"], field="extension_route_ids_json")
                _crosscheck_support(mapping, support, public_ids, extension_ids)
                scenario_id = str(mapping["scenario_id"])
                family = str(mapping["topology_family"])
                if not public_ids:
                    raise ValueError(f"Scenario {scenario_id} contains no public routes")
                for timing, gap_by_route in timing_maps.items():
                    headway, span_id = timing
                    span_start, span_end = timing_spans[timing]
                    public_summary = summarise_role(public_ids, gap_by_route)
                    extension_summary = summarise_role(extension_ids, gap_by_route)
                    if int(public_summary["roundtrip"]["route_count"]) != int(support["public_roundtrip_supported_route_count"]):
                        raise ValueError(f"Roundtrip support mismatch for scenario {scenario_id}")
                    if int(public_summary["rail_to_bus_only"]["route_count"]) != int(support["public_rail_to_bus_only_route_count"]):
                        raise ValueError(f"Directional-only support mismatch for scenario {scenario_id}")
                    if int(extension_summary["roundtrip"]["route_count"]) != int(support["extension_roundtrip_supported_route_count"]):
                        raise ValueError(f"Extension roundtrip support mismatch for scenario {scenario_id}")
                    if int(extension_summary["rail_to_bus_only"]["route_count"]) != int(support["extension_rail_to_bus_only_route_count"]):
                        raise ValueError(f"Extension directional-only support mismatch for scenario {scenario_id}")
                    out: dict[str, object] = {
                        "scenario_id": scenario_id,
                        "topology_family": family,
                        "uniform_headway_min": headway,
                        "span_id": span_id,
                        "span_start_min": span_start,
                        "span_end_min": span_end,
                    }
                    _flatten_role("public", public_summary, out)
                    _flatten_role("extension", extension_summary, out)
                    out.update({
                        "worker_direction_weight_reference": 1882.0,
                        "demand_weight_semantics": "DIRECTION_WEIGHT_ONLY_NOT_ROUTE_DEMAND_NOT_MODAL_SHARE",
                        "route_weighting_applied": False,
                        "worker_reference_assigned_to_routes": False,
                        "cross_route_phase_selected": False,
                        "joint_vehicle_block_timetable_feasibility_evaluated": False,
                        "passenger_utility_calculated": False,
                        "full_gjt_calculated": False,
                        "topology_ranked": False,
                        "service_policy_selected": False,
                    })
                    writer.writerow({field: _fmt(out[field]) for field in OUTPUT_FIELDS})
                    output_rows += 1
                    if public_summary["all_routes_have_some_complete_match_phase"] is True:
                        rows_with_all_public_routes_complete += 1
                    if public_summary["any_route_has_some_complete_match_phase"] is True:
                        rows_with_any_public_route_complete += 1
                    if int(public_summary["roundtrip"]["route_count"]) > 0:
                        rows_with_public_roundtrip_routes += 1
                    if int(public_summary["rail_to_bus_only"]["route_count"]) > 0:
                        rows_with_public_directional_only_routes += 1
                scenario_count += 1
                family_counts[family] = family_counts.get(family, 0) + 1
            try:
                next(mapping_reader)
                raise ValueError("Scenario mapping contains more rows than scenario support")
            except StopIteration:
                pass
            try:
                next(support_reader)
                raise ValueError("Scenario support contains more rows than scenario mapping")
            except StopIteration:
                pass
    finally:
        text.close()
        raw.close()
    return {
        "scenario_count": scenario_count,
        "timing_archetype_count": len(timing_maps),
        "scenario_timing_row_count": output_rows,
        "family_counts": dict(sorted(family_counts.items())),
        "rows_with_all_public_routes_having_some_complete_match_phase": rows_with_all_public_routes_complete,
        "rows_with_any_public_route_having_some_complete_match_phase": rows_with_any_public_route_complete,
        "rows_with_public_roundtrip_routes": rows_with_public_roundtrip_routes,
        "rows_with_public_rail_to_bus_only_routes": rows_with_public_directional_only_routes,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--transfer-gap", type=Path, required=True)
    parser.add_argument("--transfer-gap-validation", type=Path, required=True)
    parser.add_argument("--scenario-mapping", type=Path, required=True)
    parser.add_argument("--scenario-support", type=Path, required=True)
    parser.add_argument("--support-validation", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--validation", type=Path, required=True)
    args = parser.parse_args()
    for path in (args.transfer_gap, args.transfer_gap_validation, args.scenario_mapping, args.scenario_support, args.support_validation):
        if not path.is_file():
            raise FileNotFoundError(path)

    gap_validation, support_validation = validate_upstream(
        transfer_gap_path=args.transfer_gap,
        transfer_gap_validation_path=args.transfer_gap_validation,
        scenario_mapping_path=args.scenario_mapping,
        scenario_support_path=args.scenario_support,
        support_validation_path=args.support_validation,
    )
    timing_maps, timing_spans = load_transfer_gaps(args.transfer_gap, gap_validation)
    summary = materialise(
        scenario_mapping_path=args.scenario_mapping,
        scenario_support_path=args.scenario_support,
        timing_maps=timing_maps,
        timing_spans=timing_spans,
        output_path=args.output,
    )
    if summary["scenario_count"] != int(support_validation["scenario_count"]):
        raise ValueError("Scenario feeder envelope did not cover the certified scenario universe")
    expected_rows = summary["scenario_count"] * summary["timing_archetype_count"]
    if summary["scenario_timing_row_count"] != expected_rows:
        raise ValueError("Scenario/timing feeder row count mismatch")

    report = {
        "status": SCENARIO_FEEDER_STATUS,
        "contract": SCENARIO_FEEDER_CONTRACT,
        **summary,
        "worker_direction_weight_reference": float(gap_validation["worker_direction_weight_reference"]),
        "worker_reference_assigned_to_routes": False,
        "demand_weight_semantics": "DIRECTION_WEIGHT_ONLY_NOT_ROUTE_DEMAND_NOT_MODAL_SHARE",
        "route_weighting_applied": False,
        "route_mean_or_composite_score_calculated": False,
        "cross_route_phase_selected": False,
        "joint_vehicle_block_timetable_feasibility_evaluated": False,
        "all_integer_route_phases_retained_upstream": True,
        "passenger_utility_calculated": False,
        "full_gjt_calculated": False,
        "topology_ranked": False,
        "service_policy_selected": False,
        "fine_walking_access_combined_with_empirical_OD": False,
        "metric_semantics": "ROUTE_UNWEIGHTED_COUNTS_SHARES_AND_EXTREMA_SPLIT_BY_PASSENGER_SUPPORT_CLASS",
        "epistemic_note": (
            "This artifact lifts the certified route-level S8 transfer-gap envelope to the 100,000 structural scenarios without allocating the 1,882 ISTAT workers to routes. "
            "It reports only route counts, route shares and min/max extrema, separately for round-trip passenger routes and RAIL_TO_BUS-only public routes. "
            "It does not average routes, select a common or route-specific timetable phase, prove a joint vehicle-block timetable, calculate full Passenger GJT, or rank a topology."
        ),
        "lineage": {
            "transfer_gap": str(args.transfer_gap),
            "transfer_gap_sha256": sha256_path(args.transfer_gap),
            "transfer_gap_validation": str(args.transfer_gap_validation),
            "transfer_gap_validation_sha256": sha256_path(args.transfer_gap_validation),
            "scenario_mapping": str(args.scenario_mapping),
            "scenario_mapping_sha256": sha256_path(args.scenario_mapping),
            "scenario_support": str(args.scenario_support),
            "scenario_support_sha256": sha256_path(args.scenario_support),
            "support_validation": str(args.support_validation),
            "support_validation_sha256": sha256_path(args.support_validation),
            "output": str(args.output),
            "output_sha256": sha256_path(args.output),
        },
    }
    args.validation.parent.mkdir(parents=True, exist_ok=True)
    args.validation.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in (
        "status", "scenario_count", "timing_archetype_count", "scenario_timing_row_count",
        "rows_with_all_public_routes_having_some_complete_match_phase",
        "rows_with_any_public_route_having_some_complete_match_phase",
    )}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
