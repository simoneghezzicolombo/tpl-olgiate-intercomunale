#!/usr/bin/env python3
"""Reduce exact passenger-equivalent Stage-C plans using only the declared tie-break order.

The Phase 2 specification permits a practical tie-break when alternatives are
within an uncertainty band. This stage uses the most conservative possible band:
zero. Plans are compared here only when their complete passenger-utility profile
and service-availability profile are numerically identical under the certified
Stage-C profile precision.

Tie-break order is the declared specification order insofar as current evidence
supports it: pre-timetable S8 opportunity, public-facing simplicity proxy
(public route count), annual bus-km, then field-check burden. Continuity with
existing corridors is not yet sufficiently materialised and is therefore not
invented. Exact ties after the supported fields are all retained.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import math
from collections import defaultdict
from pathlib import Path

STATUS = "PASS_PHASE2_ZERO_BAND_TIEBREAK_V2"
CONTRACT = "PHASE2_EXACT_PASSENGER_EQUIVALENCE_PRACTICAL_TIEBREAK_V2"
S8_CLASS_RANK = {
    "NO_PUBLIC_ROUTE_HAS_COMPLETE_MATCH_PHASE": 0,
    "SOME_PUBLIC_ROUTES_HAVE_SOME_COMPLETE_MATCH_PHASE": 1,
    "ALL_PUBLIC_ROUTES_HAVE_SOME_COMPLETE_MATCH_PHASE": 2,
}
EPS = 1e-9


def sha256_path(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def finite_float(row: dict[str, str], field: str) -> float:
    try:
        value = float(row[field])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"Invalid {field}: {row.get(field)!r}") from exc
    if not math.isfinite(value):
        raise ValueError(f"Non-finite {field}: {value}")
    return value


def optional_float(row: dict[str, str], field: str) -> float | None:
    text = str(row.get(field, "")).strip()
    if not text:
        return None
    value = float(text)
    if not math.isfinite(value):
        raise ValueError(f"Non-finite optional {field}: {value}")
    return value


def strict_bool(value: object, *, field: str) -> bool:
    text = str(value).strip().lower()
    if text == "true":
        return True
    if text == "false":
        return False
    raise ValueError(f"{field} must be explicit true/false")


def profile_key(row: dict[str, str], validation: dict) -> tuple:
    max_axes = tuple(validation["passenger_maximise_axes_within_service_context"])
    min_axes = tuple(validation["passenger_minimise_axes_within_service_context"])
    availability = tuple(validation["global_additional_availability_maximise_axes"])
    values: list[object] = []
    for field in (*max_axes, *availability):
        values.append(round(finite_float(row, field), 9))
    for field in min_axes:
        value = optional_float(row, field)
        values.append(None if value is None else round(value, 9))
    return tuple(values)


def best_achievable_worst_route_gap(row: dict[str, str]) -> float:
    values: list[float] = []
    class_specs = (
        ("s8_roundtrip_route_count", "s8_roundtrip_best_complete_gap_min_max"),
        ("s8_rail_to_bus_only_route_count", "s8_rail_to_bus_only_best_complete_gap_min_max"),
    )
    for count_field, gap_field in class_specs:
        count = int(float(row[count_field]))
        gap = optional_float(row, gap_field)
        if count > 0 and gap is not None:
            values.append(gap)
    return max(values) if values else math.inf


def reliability_tuple(row: dict[str, str]) -> tuple[float, float, float]:
    try:
        rank = S8_CLASS_RANK[str(row["s8_opportunity_class"])]
    except KeyError as exc:
        raise ValueError(f"Unknown S8 opportunity class {row.get('s8_opportunity_class')!r}") from exc
    share = finite_float(row, "s8_public_complete_match_route_share")
    gap = best_achievable_worst_route_gap(row)
    # Higher tuple is better: rank, share, then negative gap.
    return float(rank), share, -gap


def same_float(a: float, b: float) -> bool:
    if math.isinf(a) or math.isinf(b):
        return a == b
    return math.isclose(a, b, rel_tol=0.0, abs_tol=EPS)


def select_group(rows: list[dict[str, str]]) -> tuple[list[dict[str, str]], dict[str, object]]:
    if not rows:
        raise ValueError("Cannot tie-break an empty group")
    survivors = list(rows)
    invoked = len(rows) > 1

    # 1. Reliability / S8 opportunity.
    reliability = {id(row): reliability_tuple(row) for row in survivors}
    best_rank = max(v[0] for v in reliability.values())
    survivors = [r for r in survivors if same_float(reliability[id(r)][0], best_rank)]
    best_share = max(reliability[id(r)][1] for r in survivors)
    survivors = [r for r in survivors if same_float(reliability[id(r)][1], best_share)]
    best_gap_score = max(reliability[id(r)][2] for r in survivors)
    survivors = [r for r in survivors if same_float(reliability[id(r)][2], best_gap_score)]

    # 2. Simpler public-facing pattern. Current measurable proxy is route count.
    min_routes = min(int(float(r["public_route_count"])) for r in survivors)
    survivors = [r for r in survivors if int(float(r["public_route_count"])) == min_routes]

    # 3. Lower annual bus-km.
    min_km = min(finite_float(r, "annual_bus_km") for r in survivors)
    survivors = [r for r in survivors if same_float(finite_float(r, "annual_bus_km"), min_km)]

    # 4. Fewer unverified road/stop elements.
    min_field = min(int(float(r["public_explicit_field_check_pending_count"])) for r in survivors)
    survivors = [
        r for r in survivors
        if int(float(r["public_explicit_field_check_pending_count"])) == min_field
    ]

    survivors.sort(key=lambda r: (str(r["scenario_id"]), str(r["plan_id"])))
    return survivors, {
        "group_size": len(rows),
        "survivor_count": len(survivors),
        "tie_break_invoked": invoked,
        "continuity_tie_break_applied": False,
    }


def deterministic_gzip_writer(path: Path, fields: list[str]):
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = path.open("wb")
    gz = gzip.GzipFile(filename="", mode="wb", fileobj=raw, compresslevel=9, mtime=0)
    text = io.TextIOWrapper(gz, encoding="utf-8", newline="")
    writer = csv.DictWriter(text, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    return raw, text, writer


def validate_upstream(surface_path: Path, surface_validation_path: Path, passenger_validation_path: Path):
    surface = load_json(surface_validation_path)
    passenger = load_json(passenger_validation_path)
    if surface.get("status") != "PASS_PHASE2_S8_ROBUST_OPPORTUNITY_SURFACE_V2":
        raise ValueError("S8 opportunity surface is not PASS")
    if surface.get("contract") != "PHASE2_LINEAGE_PINNED_PRE_TIMETABLE_S8_OPPORTUNITY_V2":
        raise ValueError("Unexpected S8 opportunity contract")
    if surface.get("lineage_compatibility", {}).get("output_sha256") != sha256_path(surface_path):
        raise ValueError("S8 opportunity output hash mismatch")
    if surface.get("candidate_eliminated_by_s8_opportunity_class") is not False:
        raise ValueError("Upstream S8 stage already eliminated candidates")
    if surface.get("cross_route_phase_selected") is not False or surface.get("exact_timetable_constructed") is not False:
        raise ValueError("Upstream S8 stage contains timetable selection")
    if passenger.get("status") != "PASS_PHASE2_PASSENGER_UTILITY_FRONTIER_V2":
        raise ValueError("Passenger Utility Frontier is not PASS")
    if passenger.get("contract") != "PHASE2_NO_WEIGHT_PASSENGER_UTILITY_FRONTIER_V2":
        raise ValueError("Unexpected Passenger Utility contract")
    if surface.get("lineage_compatibility", {}).get("passenger_frontier_sha256") != passenger.get("lineage", {}).get("frontier_output_sha256"):
        raise ValueError("S8 opportunity surface is not based on the certified passenger frontier")
    if passenger.get("decision_budget_selected") is not False or passenger.get("weighted_composite_score") is not False:
        raise ValueError("Passenger upstream violates no-selection contract")
    return surface, passenger


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--s8-surface", type=Path, required=True)
    p.add_argument("--s8-validation", type=Path, required=True)
    p.add_argument("--passenger-validation", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--audit", type=Path, required=True)
    p.add_argument("--validation", type=Path, required=True)
    args = p.parse_args()

    surface_val, passenger_val = validate_upstream(args.s8_surface, args.s8_validation, args.passenger_validation)
    with gzip.open(args.s8_surface, "rt", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != int(surface_val["passenger_utility_plan_count"]):
        raise ValueError("S8 surface row count differs from validation")

    groups: dict[tuple[str, tuple], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        if strict_bool(row["primary_selected"], field="primary_selected") or strict_bool(row["runner_up_selected"], field="runner_up_selected"):
            raise ValueError("Stage-C/S8 input already contains final selection")
        groups[(str(row["budget_suffix"]), profile_key(row, passenger_val))].append(row)

    output_rows: list[dict[str, str]] = []
    audit_rows: list[dict[str, object]] = []
    budget_summary: dict[str, dict[str, int]] = {}
    multi_plan_groups = 0
    reduced_groups = 0
    exact_ties_after_supported_tiebreak = 0

    for (budget, _), group in sorted(groups.items(), key=lambda item: (item[0][0], str(item[0][1]))):
        survivors, meta = select_group(group)
        if len(group) > 1:
            multi_plan_groups += 1
        if len(survivors) < len(group):
            reduced_groups += 1
        if len(survivors) > 1:
            exact_ties_after_supported_tiebreak += 1
        group_id = hashlib.sha256(
            (budget + "|" + "|".join(sorted(str(r["plan_id"]) for r in group))).encode("utf-8")
        ).hexdigest()[:16]
        for row in survivors:
            out = dict(row)
            out.update({
                "zero_band_equivalence_group_id": f"ZB2_{group_id}",
                "zero_band_equivalence_group_size": str(len(group)),
                "zero_band_survivor_count": str(len(survivors)),
                "zero_band_tie_break_invoked": str(len(group) > 1).lower(),
                "zero_band_s8_best_achievable_worst_route_gap_min": (
                    "" if math.isinf(best_achievable_worst_route_gap(row))
                    else f"{best_achievable_worst_route_gap(row):.9f}"
                ),
                "zero_band_primary_selected": "false",
                "zero_band_runner_up_selected": "false",
            })
            output_rows.append(out)
        audit_rows.append({
            "budget_suffix": budget,
            "equivalence_group_id": f"ZB2_{group_id}",
            "input_plan_count": len(group),
            "survivor_plan_count": len(survivors),
            "tie_break_invoked": str(len(group) > 1).lower(),
            "reduced": str(len(survivors) < len(group)).lower(),
            "exact_tie_after_supported_tiebreak": str(len(survivors) > 1).lower(),
            "continuity_tie_break_applied": "false",
        })
        summary = budget_summary.setdefault(budget, {
            "input_plan_count": 0,
            "passenger_equivalence_group_count": 0,
            "multi_plan_equivalence_group_count": 0,
            "survivor_plan_count": 0,
            "survivor_unique_scenario_count": 0,
            "survivor_unique_scenario_count_headway_30_or_better": 0,
        })
        summary["input_plan_count"] += len(group)
        summary["passenger_equivalence_group_count"] += 1
        summary["multi_plan_equivalence_group_count"] += int(len(group) > 1)
        summary["survivor_plan_count"] += len(survivors)

    # Finish unique-scenario summaries from output rows.
    for budget, summary in budget_summary.items():
        subset = [r for r in output_rows if r["budget_suffix"] == budget]
        summary["survivor_unique_scenario_count"] = len({r["scenario_id"] for r in subset})
        summary["survivor_unique_scenario_count_headway_30_or_better"] = len({
            r["scenario_id"] for r in subset if int(r["uniform_headway_min"]) <= 30
        })

    output_rows.sort(key=lambda r: (str(r["budget_suffix"]), str(r["plan_id"]), str(r["scenario_id"])))
    appended = [
        "zero_band_equivalence_group_id", "zero_band_equivalence_group_size", "zero_band_survivor_count",
        "zero_band_tie_break_invoked", "zero_band_s8_best_achievable_worst_route_gap_min",
        "zero_band_primary_selected", "zero_band_runner_up_selected",
    ]
    fields = list(rows[0].keys()) + appended
    raw, text, writer = deterministic_gzip_writer(args.output, fields)
    try:
        writer.writerows(output_rows)
    finally:
        text.close()
        raw.close()

    args.audit.parent.mkdir(parents=True, exist_ok=True)
    audit_rows.sort(key=lambda r: (str(r["budget_suffix"]), str(r["equivalence_group_id"])))
    with args.audit.open("w", encoding="utf-8", newline="") as handle:
        writer2 = csv.DictWriter(handle, fieldnames=list(audit_rows[0].keys()), lineterminator="\n")
        writer2.writeheader()
        writer2.writerows(audit_rows)

    validation = {
        "status": STATUS,
        "contract": CONTRACT,
        "uncertainty_band_used": 0.0,
        "uncertainty_band_semantics": "EXACT_STAGE_C_PASSENGER_UTILITY_AND_AVAILABILITY_EQUIVALENCE_ONLY",
        "input_plan_count": len(rows),
        "passenger_equivalence_group_count": len(groups),
        "multi_plan_equivalence_group_count": multi_plan_groups,
        "reduced_equivalence_group_count": reduced_groups,
        "exact_tie_group_count_after_supported_tiebreak": exact_ties_after_supported_tiebreak,
        "survivor_plan_count": len(output_rows),
        "plans_removed_only_within_exact_passenger_equivalence_groups": len(rows) - len(output_rows),
        "budget_summary": dict(sorted(budget_summary.items())),
        "tie_break_order_applied": [
            "PRE_TIMETABLE_S8_OPPORTUNITY_CLASS_COMPLETE_MATCH_SHARE_AND_BEST_ACHIEVABLE_WORST_ROUTE_GAP",
            "LOWER_PUBLIC_ROUTE_COUNT_AS_MEASURABLE_SIMPLICITY_PROXY",
            "LOWER_ANNUAL_BUS_KM",
            "FEWER_PUBLIC_EXPLICIT_FIELD_CHECK_PENDING_ELEMENTS",
        ],
        "continuity_with_existing_stops_corridors_tiebreak_applied": False,
        "continuity_reason": "NOT_SUFFICIENTLY_MATERIALISED_AT_PLAN_LEVEL__NOT_INVENTED",
        "hard_s8_threshold_applied": False,
        "non_equivalent_passenger_tradeoff_eliminated": False,
        "decision_budget_selected": False,
        "service_policy_selected": False,
        "recovery_selected": False,
        "cross_route_phase_selected": False,
        "exact_timetable_constructed": False,
        "missed_connection_probability_calculated": False,
        "final_reliability_proven": False,
        "primary_selected": False,
        "runner_up_selected": False,
        "weighted_composite_score": False,
        "lineage": {
            "s8_surface_sha256": sha256_path(args.s8_surface),
            "s8_validation_sha256": sha256_path(args.s8_validation),
            "passenger_validation_sha256": sha256_path(args.passenger_validation),
            "output_sha256": sha256_path(args.output),
            "audit_sha256": sha256_path(args.audit),
        },
        "limitations": [
            "This stage uses an exact zero-width passenger-equivalence band only; it does not declare a substantive uncertainty band.",
            "S8 opportunity is pre-timetable evidence and does not prove a joint phase vector or missed-connection reliability.",
            "Lower public route count is the only currently materialised public-facing simplicity proxy; topology-family ordering is not invented.",
            "Continuity with existing stops/corridors remains unresolved and is not used to break residual exact ties.",
            "Final PRIMARY/RUNNER-UP remains downstream of exact timetable, perturbation robustness and explicit decision inputs.",
        ],
    }
    args.validation.write_text(json.dumps(validation, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(validation, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
