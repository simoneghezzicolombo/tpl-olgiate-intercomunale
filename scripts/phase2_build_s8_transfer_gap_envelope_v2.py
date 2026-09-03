#!/usr/bin/env python3
"""Materialise exact phase-retained S8 transfer-gap envelopes by route."""
from __future__ import annotations

import argparse
import csv
from decimal import Decimal
import gzip
import hashlib
import io
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.phase2_build_s8_phasing_v2 import load_rail_events, load_timing_archetypes
from src.phase2_s8_transfer_gap_envelope_v2 import (
    TRANSFER_GAP_CONTRACT,
    TRANSFER_GAP_STATUS,
    build_representative_phase_metrics,
    exact_weighted_phase_envelope,
    runtime_parts,
)
from src.phase2_s8_work_transfer_utility_v2 import WorkDirectionWeights


OUTPUT_FIELDS = [
    "route_id",
    "runtime_archetype_id",
    "passenger_support_class",
    "roundtrip_passenger_supported",
    "uniform_headway_min",
    "span_id",
    "span_start_min",
    "span_end_min",
    "runtime_integer_mod_headway",
    "actual_fractional_runtime_min",
    "evaluated_phase_count",
    "complete_match_phase_count",
    "best_complete_phase_weighted_mean_gap_min",
    "worst_complete_phase_weighted_mean_gap_min",
    "demand_weight_reference_workers",
    "demand_weight_semantics",
    "passenger_demand_assigned_to_route",
    "phase_selected",
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


def load_work_weights(path: Path) -> WorkDirectionWeights:
    rows = load_csv(path)
    expected_semantics = "ISTAT_2021_WORKER_COUNT_ADDRESSABLE_TO_DIRECT_S8_NOT_MODAL_SHARE"
    cells: dict[tuple[str, str], float] = {}
    for row in rows:
        if row.get("demand_semantics") != expected_semantics:
            raise ValueError("Unexpected S8 work-direction demand semantics")
        key = (str(row["leg"]), str(row["direction"]))
        if key in cells:
            raise ValueError("Duplicate S8 work-direction summary cell")
        cells[key] = float(row["demand_weight"])
    expected = {
        ("OUTBOUND_BUS_TO_RAIL", "LECCO"),
        ("OUTBOUND_BUS_TO_RAIL", "MILANO"),
        ("RETURN_RAIL_TO_BUS", "LECCO"),
        ("RETURN_RAIL_TO_BUS", "MILANO"),
    }
    if set(cells) != expected:
        raise ValueError("Incomplete S8 work-direction summary")
    weights = WorkDirectionWeights(
        outbound_bus_to_rail={
            "LECCO": cells[("OUTBOUND_BUS_TO_RAIL", "LECCO")],
            "MILANO": cells[("OUTBOUND_BUS_TO_RAIL", "MILANO")],
        },
        return_rail_to_bus={
            "LECCO": cells[("RETURN_RAIL_TO_BUS", "LECCO")],
            "MILANO": cells[("RETURN_RAIL_TO_BUS", "MILANO")],
        },
    )
    weights.validate()
    if weights.worker_count != 1882.0:
        raise ValueError("Certified S8 work-direction reference must total 1,882 workers")
    return weights


def _bool(value: object, *, field: str) -> bool:
    if value is True or value == "true":
        return True
    if value is False or value == "false":
        return False
    raise ValueError(f"{field} must be explicit true/false")


def _fmt(value: float | None) -> str:
    return "" if value is None else f"{value:.9f}"


def deterministic_gzip_writer(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = path.open("wb")
    gz = gzip.GzipFile(filename="", mode="wb", fileobj=raw, compresslevel=9, mtime=0)
    text = io.TextIOWrapper(gz, encoding="utf-8", newline="")
    return raw, text


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--s8-validation", type=Path, required=True)
    parser.add_argument("--support-validation", type=Path, required=True)
    parser.add_argument("--route-support", type=Path, required=True)
    parser.add_argument("--s8-events", type=Path, required=True)
    parser.add_argument("--policy-grid", type=Path, required=True)
    parser.add_argument("--work-direction-summary", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--validation", type=Path, required=True)
    args = parser.parse_args()

    s8 = load_json(args.s8_validation)
    support = load_json(args.support_validation)
    if s8.get("status") != "PASS_S8_PHASE_OPPORTUNITY_V2_BUILD" or s8.get("contract") != "PHASE2_S8_PHASE_OPPORTUNITY_SURFACE_V2":
        raise ValueError("Audited S8 phase-opportunity contract is required")
    if support.get("status") != "PASS_S8_PASSENGER_SUPPORT_MASK_V2_BUILD" or support.get("contract") != "PHASE2_S8_PASSENGER_SUPPORT_MASK_V2":
        raise ValueError("Audited passenger-support mask is required")
    for field in ("passenger_demand_assigned_to_routes", "passenger_utility_calculated", "topology_ranked", "service_policy_selected"):
        if support.get(field) is not False:
            raise ValueError(f"Passenger-support mask violates {field}=false")
    if s8.get("phase_selected") is not False or s8.get("all_phases_retained_downstream") is not True:
        raise ValueError("S8 phase domain must remain complete and unselected")
    lineage = s8.get("lineage", {})
    if lineage.get("s8_events_sha256") != sha256_path(args.s8_events):
        raise ValueError("S8 events hash mismatch")
    if lineage.get("policy_grid_sha256") != sha256_path(args.policy_grid):
        raise ValueError("Service-policy grid hash mismatch")
    if support.get("lineage", {}).get("route_support_output_sha256") != sha256_path(args.route_support):
        raise ValueError("Route-support mask hash mismatch")

    route_rows = load_csv(args.route_support)
    if len(route_rows) != int(support["route_count"]):
        raise ValueError("Route-support row count mismatch")
    rail_events = load_rail_events(args.s8_events)
    timing_archetypes = load_timing_archetypes(args.policy_grid)
    weights = load_work_weights(args.work_direction_summary)

    cache: dict[tuple[int, str, int], list[dict[str, object]]] = {}
    row_count = 0
    roundtrip_rows = 0
    directional_rows = 0
    complete_match_rows = 0
    no_complete_match_rows = 0
    raw, text = deterministic_gzip_writer(args.output)
    try:
        writer = csv.DictWriter(text, fieldnames=OUTPUT_FIELDS, lineterminator="\n")
        writer.writeheader()
        for route in sorted(route_rows, key=lambda r: r["route_id"]):
            route_id = str(route["route_id"])
            roundtrip = _bool(route["roundtrip_passenger_supported"], field="roundtrip_passenger_supported")
            support_class = str(route["passenger_support_class"])
            if roundtrip != (support_class == "ROUNDTRIP_HUB_PASSENGER_SUPPORTED"):
                raise ValueError(f"{route_id}: passenger support class conflicts with roundtrip flag")
            integer_runtime, fractional_runtime = runtime_parts(route["cycle_runtime_min"])
            for headway, span in timing_archetypes:
                runtime_mod = integer_runtime % headway
                key = (headway, span.span_id, runtime_mod)
                metrics = cache.get(key)
                if metrics is None:
                    metrics = build_representative_phase_metrics(
                        rail_events=rail_events,
                        headway_min=headway,
                        span=span,
                        runtime_integer_mod_headway=runtime_mod,
                    )
                    cache[key] = metrics
                envelope = exact_weighted_phase_envelope(
                    phase_metrics=metrics,
                    weights=weights,
                    roundtrip_passenger_supported=roundtrip,
                    actual_fractional_runtime=fractional_runtime,
                )
                writer.writerow({
                    "route_id": route_id,
                    "runtime_archetype_id": route["runtime_archetype_id"],
                    "passenger_support_class": support_class,
                    "roundtrip_passenger_supported": "true" if roundtrip else "false",
                    "uniform_headway_min": headway,
                    "span_id": span.span_id,
                    "span_start_min": span.start_min,
                    "span_end_min": span.end_min,
                    "runtime_integer_mod_headway": runtime_mod,
                    "actual_fractional_runtime_min": format(fractional_runtime, "f"),
                    "evaluated_phase_count": envelope.evaluated_phase_count,
                    "complete_match_phase_count": envelope.complete_match_phase_count,
                    "best_complete_phase_weighted_mean_gap_min": _fmt(envelope.best_complete_phase_weighted_mean_gap_min),
                    "worst_complete_phase_weighted_mean_gap_min": _fmt(envelope.worst_complete_phase_weighted_mean_gap_min),
                    "demand_weight_reference_workers": f"{weights.worker_count:.9f}",
                    "demand_weight_semantics": "DIRECTION_WEIGHT_ONLY_NOT_ROUTE_DEMAND_NOT_MODAL_SHARE",
                    "passenger_demand_assigned_to_route": "false",
                    "phase_selected": "false",
                    "topology_ranked": "false",
                })
                row_count += 1
                if roundtrip:
                    roundtrip_rows += 1
                else:
                    directional_rows += 1
                if envelope.complete_match_phase_count > 0:
                    complete_match_rows += 1
                else:
                    no_complete_match_rows += 1
    finally:
        text.close()
        raw.close()

    expected_rows = len(route_rows) * len(timing_archetypes)
    if row_count != expected_rows:
        raise ValueError("Transfer-gap envelope row count mismatch")
    if roundtrip_rows != int(support["roundtrip_passenger_supported_route_count"]) * len(timing_archetypes):
        raise ValueError("Roundtrip transfer-gap row count mismatch")
    if directional_rows != int(support["rail_to_bus_only_route_count"]) * len(timing_archetypes):
        raise ValueError("Directional transfer-gap row count mismatch")

    report = {
        "status": TRANSFER_GAP_STATUS,
        "contract": TRANSFER_GAP_CONTRACT,
        "route_count": len(route_rows),
        "timing_archetype_count": len(timing_archetypes),
        "route_timing_row_count": row_count,
        "roundtrip_route_timing_row_count": roundtrip_rows,
        "rail_to_bus_only_route_timing_row_count": directional_rows,
        "rows_with_at_least_one_complete_match_phase": complete_match_rows,
        "rows_without_complete_match_phase": no_complete_match_rows,
        "representative_phase_metric_cache_count": len(cache),
        "worker_direction_weight_reference": weights.worker_count,
        "worker_reference_assigned_to_routes": False,
        "demand_weight_semantics": "DIRECTION_WEIGHT_ONLY_NOT_ROUTE_DEMAND_NOT_MODAL_SHARE",
        "phase_selected": False,
        "all_integer_phases_retained": True,
        "passenger_utility_calculated": False,
        "full_gjt_calculated": False,
        "topology_ranked": False,
        "service_policy_selected": False,
        "gap_metric": "EXACT_DIRECTION_WEIGHTED_MEAN_TRANSFER_GAP_MINUTES_OVER_COMPLETE_MATCH_PHASES",
        "epistemic_note": (
            "The 1,882-worker ISTAT reference is used only to weight Milano versus Lecco transfer directions. "
            "It is not assigned to any bus route. For roundtrip-supported routes the metric combines outbound "
            "BUS_TO_RAIL and return RAIL_TO_BUS mean gaps at the same clock phase. For open public routes it "
            "uses RAIL_TO_BUS only. Min/max values are exact across the retained integer phase domain and are "
            "reported only over phases with zero unmatched source events in every required direction cell."
        ),
        "lineage": {
            "s8_validation": str(args.s8_validation),
            "s8_validation_sha256": sha256_path(args.s8_validation),
            "support_validation": str(args.support_validation),
            "support_validation_sha256": sha256_path(args.support_validation),
            "route_support": str(args.route_support),
            "route_support_sha256": sha256_path(args.route_support),
            "s8_events": str(args.s8_events),
            "s8_events_sha256": sha256_path(args.s8_events),
            "policy_grid": str(args.policy_grid),
            "policy_grid_sha256": sha256_path(args.policy_grid),
            "work_direction_summary": str(args.work_direction_summary),
            "work_direction_summary_sha256": sha256_path(args.work_direction_summary),
            "output": str(args.output),
            "output_sha256": sha256_path(args.output),
        },
    }
    args.validation.parent.mkdir(parents=True, exist_ok=True)
    args.validation.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in (
        "status",
        "route_timing_row_count",
        "roundtrip_route_timing_row_count",
        "rail_to_bus_only_route_timing_row_count",
        "rows_with_at_least_one_complete_match_phase",
        "rows_without_complete_match_phase",
        "representative_phase_metric_cache_count",
    )}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
