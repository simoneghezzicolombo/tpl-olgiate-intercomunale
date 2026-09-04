#!/usr/bin/env python3
"""Dry-run the human-approved Phase 2 V3 policy without selecting a recommendation.

The dry-run fixes the human-selected reference budget, requires complete
bidirectional engineering evidence, applies a fail-closed operational gate and
then evaluates the explicit headway policy before any downstream efficiency
criterion. Frequent service (H<=30) is the default when robustly available.
Hourly service (H60) may displace it only through a no-weight, componentwise
territorial-access/equity exception. Current-Service Baseline V4 remains a
mandatory pre-finalizer input, so this script never materialises PRIMARY or
RUNNER-UP.
"""
from __future__ import annotations

import argparse
import csv
from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation
import gzip
import hashlib
import json
from pathlib import Path
from typing import Iterable, Mapping

STATUS = "PASS_PHASE2_FINAL_POLICY_DRY_RUN_V3"
CONTRACT = "PHASE2_HUMAN_APPROVED_FINAL_POLICY_V3"
READINESS_STATUS = "PASS_PHASE2_FINAL_TOURNAMENT_READINESS_AUDIT_RT001_V3"
EXPECTED_CONTEXTS = 16495
EXPECTED_REFERENCE_CONTEXTS = 2633
EXPECTED_REFERENCE_BIDIRECTIONAL = 2259


def sha256_path(path: Path) -> str:
    h = hashlib.sha256()
    if path.suffix.lower() in {".csv", ".json"}:
        h.update(path.read_bytes().replace(b"\r\n", b"\n"))
        return h.hexdigest()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def strict_bool(value: object, *, field: str) -> bool:
    text = str(value).strip().lower()
    if text == "true":
        return True
    if text == "false":
        return False
    raise ValueError(f"{field} must be true/false, got {value!r}")


def decimal_value(value: object, *, field: str) -> Decimal:
    try:
        number = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError(f"{field} must be numeric") from exc
    if not number.is_finite():
        raise ValueError(f"{field} must be finite")
    return number


def metric(row: Mapping[str, str], field: str) -> Decimal:
    value = row.get(field, "")
    if value == "":
        raise ValueError(f"missing required policy metric {field} for {row.get('plan_context_id')}")
    if field == "stage_e_any_block_infeasibility_under_sensitivity":
        return Decimal(int(strict_bool(value, field=field)))
    return decimal_value(value, field=field)


def dominates(left: Mapping[str, str], right: Mapping[str, str], dimensions: list[dict]) -> bool:
    strictly_better = False
    for item in dimensions:
        field = item["field"]
        lv = metric(left, field)
        rv = metric(right, field)
        if item["direction"] == "max":
            if lv < rv:
                return False
            strictly_better = strictly_better or lv > rv
        elif item["direction"] == "min":
            if lv > rv:
                return False
            strictly_better = strictly_better or lv < rv
        else:
            raise ValueError(f"invalid direction {item['direction']}")
    return strictly_better


def pareto_rows(rows: list[dict[str, str]], dimensions: list[dict]) -> list[dict[str, str]]:
    if not rows:
        return []
    vectors: dict[tuple[Decimal, ...], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        vectors[tuple(metric(row, item["field"]) for item in dimensions)].append(row)

    def sort_key(item):
        vector, _ = item
        return tuple(-value if dim["direction"] == "max" else value for value, dim in zip(vector, dimensions))

    frontier_vectors: list[tuple[Decimal, ...]] = []
    vector_rows = {vec: members[0] for vec, members in vectors.items()}
    for vector, _members in sorted(vectors.items(), key=sort_key):
        candidate = vector_rows[vector]
        if any(dominates(vector_rows[existing], candidate, dimensions) for existing in frontier_vectors):
            continue
        frontier_vectors = [
            existing for existing in frontier_vectors
            if not dominates(candidate, vector_rows[existing], dimensions)
        ]
        frontier_vectors.append(vector)

    keep = set(frontier_vectors)
    survivors: list[dict[str, str]] = []
    for vector, members in vectors.items():
        if vector in keep:
            survivors.extend(members)
    return sorted(survivors, key=lambda row: row["plan_context_id"])


def strict_lexicographic_trace(rows: list[dict[str, str]], criteria: list[dict]) -> tuple[list[dict], list[dict[str, str]]]:
    survivors = list(rows)
    trace: list[dict] = []
    for index, item in enumerate(criteria, start=1):
        field = item["field"]
        values = [metric(row, field) for row in survivors]
        best = max(values) if item["direction"] == "max" else min(values)
        survivors = [row for row in survivors if metric(row, field) == best]
        trace.append({
            "step": index,
            "field": field,
            "direction": item["direction"],
            "best_exact_value": str(best),
            "survivor_count": len(survivors),
        })
        if len(survivors) <= 1:
            break
    return trace, survivors


def write_csv(path: Path, fields: list[str], rows: Iterable[Mapping[str, object]]) -> None:
    rows = list(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n", extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)


def headway_summary(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    groups: dict[Decimal, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        groups[metric(row, "uniform_headway_min")].append(row)
    output = []
    for headway, members in sorted(groups.items()):
        output.append({
            "uniform_headway_min": str(headway),
            "context_count": len(members),
            "max_total_coverage_10m": str(max(metric(r, "public_population_coverage_share_10min") for r in members)),
            "max_total_coverage_8m": str(max(metric(r, "public_population_coverage_share_8min") for r in members)),
            "max_total_coverage_5m": str(max(metric(r, "public_population_coverage_share_5min") for r in members)),
            "max_worst_municipality_coverage_10m": str(max(metric(r, "public_worst_municipality_coverage_share_10min") for r in members)),
            "max_worst_municipality_coverage_8m": str(max(metric(r, "public_worst_municipality_coverage_share_8min") for r in members)),
            "max_worst_municipality_coverage_5m": str(max(metric(r, "public_worst_municipality_coverage_share_5min") for r in members)),
            "max_bidirectional_reachable_share": str(max(metric(r, "bidirectional_reachable_share") for r in members)),
            "max_bidirectional_worst_retention": str(max(metric(r, "stage_e_bidirectional_worst_retention_share_engineering") for r in members)),
            "min_exact_annual_bus_km": str(min(metric(r, "exact_annual_bus_km") for r in members)),
        })
    return output


def topology_summary(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    counts = Counter((row.get("topology_family", ""), row.get("public_route_count", "")) for row in rows)
    return [
        {"topology_family": family, "public_route_count": route_count, "context_count": count}
        for (family, route_count), count in sorted(counts.items())
    ]


def classify_headway(row: Mapping[str, str]) -> str:
    h = metric(row, "uniform_headway_min")
    if h <= Decimal("30"):
        return "FREQUENT_H_LE_30"
    if h == Decimal("60"):
        return "HOURLY_H60"
    raise ValueError(f"unexpected robust headway outside declared classes: {h}")


def territorial_benchmark(rows: list[dict[str, str]], dimensions: list[dict]) -> dict[str, Decimal]:
    if not rows:
        return {}
    result: dict[str, Decimal] = {}
    for item in dimensions:
        field = item["field"]
        values = [metric(row, field) for row in rows]
        result[field] = max(values) if item["direction"] == "max" else min(values)
    return result


def h60_exception_test(
    frequent_frontier: list[dict[str, str]], hourly_frontier: list[dict[str, str]], dimensions: list[dict]
) -> tuple[list[dict[str, object]], list[dict[str, str]]]:
    """Test the explicit no-weight H60 territorial exception.

    One H60 candidate must match or exceed the componentwise best value observed
    anywhere on the frequent territorial frontier on all six coverage/equity
    axes, with at least one strict TOTAL gain and one strict EQUITY gain.
    """
    if not frequent_frontier or not hourly_frontier:
        return [], []
    benchmark = territorial_benchmark(frequent_frontier, dimensions)
    audit_rows: list[dict[str, object]] = []
    qualifying: list[dict[str, str]] = []
    total_fields = {item["field"] for item in dimensions if item.get("dimension_group") == "TOTAL"}
    equity_fields = {item["field"] for item in dimensions if item.get("dimension_group") == "EQUITY"}
    for row in hourly_frontier:
        no_worse_all = True
        strict_total = False
        strict_equity = False
        deltas: dict[str, str] = {}
        for item in dimensions:
            field = item["field"]
            value = metric(row, field)
            target = benchmark[field]
            if item["direction"] == "max":
                no_worse = value >= target
                strict = value > target
                delta = value - target
            else:
                no_worse = value <= target
                strict = value < target
                delta = target - value
            no_worse_all = no_worse_all and no_worse
            strict_total = strict_total or (field in total_fields and strict)
            strict_equity = strict_equity or (field in equity_fields and strict)
            deltas[field] = str(delta)
        passes = no_worse_all and strict_total and strict_equity
        if passes:
            qualifying.append(row)
        audit_rows.append({
            "plan_context_id": row["plan_context_id"],
            "selected_timetable_id": row["selected_timetable_id"],
            "no_worse_than_frequent_componentwise_benchmark": str(no_worse_all).lower(),
            "strict_total_access_gain": str(strict_total).lower(),
            "strict_equity_gain": str(strict_equity).lower(),
            "h60_exception_pass": str(passes).lower(),
            **{f"delta_{field}": value for field, value in deltas.items()},
        })
    return audit_rows, qualifying


def run_layers(class_id: str, initial: list[dict[str, str]], layers: list[dict]) -> tuple[list[dict], list[dict[str, str]]]:
    trace: list[dict] = []
    survivors = initial
    for layer in layers:
        before = len(survivors)
        survivors = pareto_rows(survivors, layer["dimensions"])
        trace.append({
            "headway_class": class_id,
            "stage": layer["layer_id"],
            "method": layer["method"],
            "input_count": before,
            "survivor_count": len(survivors),
        })
    return trace, survivors


def build(args: argparse.Namespace) -> dict:
    config = read_json(args.policy)
    readiness = read_json(args.readiness_validation)
    fields, all_rows = read_csv(args.context_readiness)

    if config.get("contract") != CONTRACT or config.get("contract_version") != 2:
        raise ValueError("unexpected final policy contract/version")
    if config.get("status") != "APPROVED_FOR_DRY_RUN_PENDING_CURRENT_SERVICE_V4":
        raise ValueError("policy is not authorised for dry-run")
    boundary = config.get("selection_boundary", {})
    for key in ("primary_selection_authorised", "runner_up_selection_authorised", "weighted_composite_score"):
        if boundary.get(key) is not False:
            raise ValueError(f"selection boundary changed: {key}")
    decisions = config["human_policy_decisions"]
    if decisions["decision_pathway"] != "V3_CERTIFIED_METRICS_DETERMINISTIC_ROBUSTNESS":
        raise ValueError("unexpected decision pathway")
    if decisions["budget_suffix"] != "reference" or Decimal(str(decisions["annual_bus_km_cap"])) != Decimal("111419.0"):
        raise ValueError("reference budget policy changed")
    if decisions["global_scalar_uncertainty_band"] is not None:
        raise ValueError("V3 must not silently restore a global scalar uncertainty band")
    if decisions["continuity_with_d184_d185_decision_role"] != "REPORTING_ONLY":
        raise ValueError("legacy continuity must not select the candidate")

    if readiness.get("status") != READINESS_STATUS or readiness.get("readiness_audit_pass") is not True:
        raise ValueError("certified tournament readiness is not PASS")
    if readiness.get("represented_plan_context_count") != EXPECTED_CONTEXTS or len(all_rows) != EXPECTED_CONTEXTS:
        raise ValueError("context readiness cardinality changed")
    if readiness.get("lineage", {}).get("context_readiness_output_sha256") != sha256_path(args.context_readiness):
        raise ValueError("context readiness lineage hash mismatch")

    layers = config["class_internal_layers"]
    exception_dimensions = config["headway_class_policy"]["territorial_exception_dimensions"]
    required_fields = {item["field"] for layer in layers for item in layer["dimensions"]}
    required_fields |= {item["field"] for item in exception_dimensions}
    required_fields |= {item["field"] for item in config["strict_lexicographic_diagnostic"]["ordered_criteria"]}
    required_fields |= {
        "plan_context_id", "selected_timetable_id", "scenario_id", "topology_family", "budget_suffix", "public_route_count",
        "stage_e_bus_to_rail_observed_profile_count", "uniform_headway_min",
    }
    missing = required_fields - set(fields)
    if missing:
        raise ValueError(f"policy references non-certified/missing fields: {sorted(missing)}")

    reference = [row for row in all_rows if row["budget_suffix"] == "reference"]
    if len(reference) != EXPECTED_REFERENCE_CONTEXTS:
        raise ValueError(f"reference context count changed: {len(reference)}")
    complete = [row for row in reference if int(row["stage_e_bus_to_rail_observed_profile_count"]) > 0]
    if len(complete) != EXPECTED_REFERENCE_BIDIRECTIONAL:
        raise ValueError(f"reference bidirectional context count changed: {len(complete)}")
    robust = [row for row in complete if not strict_bool(row["stage_e_any_block_infeasibility_under_sensitivity"], field="stage_e_any_block_infeasibility_under_sensitivity")]
    if not robust:
        raise ValueError("no reference-budget context passes the declared operational robustness gate")

    classes: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in robust:
        classes[classify_headway(row)].append(row)
    frequent = sorted(classes.get("FREQUENT_H_LE_30", []), key=lambda row: row["plan_context_id"])
    hourly = sorted(classes.get("HOURLY_H60", []), key=lambda row: row["plan_context_id"])
    if not frequent and not hourly:
        raise ValueError("no robust candidate in either declared headway class")

    territorial_layer = layers[0]
    frequent_territorial = pareto_rows(frequent, territorial_layer["dimensions"])
    hourly_territorial = pareto_rows(hourly, territorial_layer["dimensions"])
    exception_rows, hourly_qualifying = h60_exception_test(frequent_territorial, hourly_territorial, exception_dimensions)

    if frequent:
        if hourly_qualifying:
            chosen_class = "HOURLY_H60"
            chosen_initial = hourly_territorial
            class_reason = "H60_EXCEPTION_TERRITORIALLY_JUSTIFIED"
        else:
            chosen_class = "FREQUENT_H_LE_30"
            chosen_initial = frequent_territorial
            class_reason = "FREQUENT_DEFAULT_H60_EXCEPTION_NOT_PROVEN"
    else:
        chosen_class = "HOURLY_H60"
        chosen_initial = hourly_territorial
        class_reason = "NO_ROBUST_FREQUENT_CONTEXT_AVAILABLE"

    class_trace = [
        {"headway_class": "FREQUENT_H_LE_30", "stage": "ROBUST_INPUT", "method": "FILTER", "input_count": len(frequent), "survivor_count": len(frequent)},
        {"headway_class": "FREQUENT_H_LE_30", "stage": territorial_layer["layer_id"], "method": territorial_layer["method"], "input_count": len(frequent), "survivor_count": len(frequent_territorial)},
        {"headway_class": "HOURLY_H60", "stage": "ROBUST_INPUT", "method": "FILTER", "input_count": len(hourly), "survivor_count": len(hourly)},
        {"headway_class": "HOURLY_H60", "stage": territorial_layer["layer_id"], "method": territorial_layer["method"], "input_count": len(hourly), "survivor_count": len(hourly_territorial)},
    ]
    chosen_trace, survivors = run_layers(chosen_class, chosen_initial, layers[1:])
    class_trace.extend(chosen_trace)

    other_class = "HOURLY_H60" if chosen_class == "FREQUENT_H_LE_30" else "FREQUENT_H_LE_30"
    other_initial = hourly_territorial if other_class == "HOURLY_H60" else frequent_territorial
    if other_initial:
        other_trace, _ = run_layers(other_class, other_initial, layers[1:])
        class_trace.extend({**item, "stage": "DIAGNOSTIC_" + item["stage"]} for item in other_trace)

    strict_trace, strict_survivors = strict_lexicographic_trace(robust, config["strict_lexicographic_diagnostic"]["ordered_criteria"])

    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(output_dir / "headway_class_policy_trace_v3.csv", ["headway_class", "stage", "method", "input_count", "survivor_count"], class_trace)
    write_csv(output_dir / "headway_tradeoff_reference_v3.csv", [
        "uniform_headway_min", "context_count", "max_total_coverage_10m", "max_total_coverage_8m", "max_total_coverage_5m",
        "max_worst_municipality_coverage_10m", "max_worst_municipality_coverage_8m", "max_worst_municipality_coverage_5m",
        "max_bidirectional_reachable_share", "max_bidirectional_worst_retention", "min_exact_annual_bus_km"
    ], headway_summary(robust))

    exception_fields = [
        "plan_context_id", "selected_timetable_id", "no_worse_than_frequent_componentwise_benchmark", "strict_total_access_gain", "strict_equity_gain", "h60_exception_pass"
    ] + [f"delta_{item['field']}" for item in exception_dimensions]
    write_csv(output_dir / "h60_exception_test_v3.csv", exception_fields, exception_rows)
    write_csv(output_dir / "final_layer_topology_diagnostic_v3.csv", ["topology_family", "public_route_count", "context_count"], topology_summary(survivors))
    write_csv(output_dir / "strict_lexicographic_brittleness_trace_v3.csv", ["step", "field", "direction", "best_exact_value", "survivor_count"], strict_trace)

    diagnostic_fields = [
        "plan_context_id", "selected_timetable_id", "scenario_id", "topology_family", "public_route_count", "uniform_headway_min", "span_minutes",
        "exact_annual_bus_km", "public_population_coverage_share_10min", "public_population_coverage_share_8min", "public_population_coverage_share_5min",
        "public_worst_municipality_coverage_share_10min", "public_worst_municipality_coverage_share_8min", "public_worst_municipality_coverage_share_5min",
        "bidirectional_reachable_share", "stage_e_bidirectional_worst_retention_share_engineering", "stage_e_worst_minimum_block_slack_min_engineering",
        "public_explicit_field_check_pending_count", "public_operational_unknown_distance_share_lower_bound"
    ]
    write_csv(output_dir / "final_layer_survivors_diagnostic_v3.csv", diagnostic_fields, [{field: row.get(field, "") for field in diagnostic_fields} for row in survivors])

    result = {
        "status": STATUS,
        "contract": CONTRACT,
        "policy_contract_version": 2,
        "dry_run_only": True,
        "primary_selected": False,
        "runner_up_selected": False,
        "final_selection_authorized": False,
        "current_service_v4_required_before_final_selection": True,
        "current_service_v4_consumed": False,
        "decision_pathway": decisions["decision_pathway"],
        "budget_suffix": decisions["budget_suffix"],
        "annual_bus_km_cap": decisions["annual_bus_km_cap"],
        "global_scalar_uncertainty_band_used": False,
        "weighted_composite_score": False,
        "continuity_used_for_selection": False,
        "olgiate_frazione_diagnostic_used_for_selection": False,
        "reference_context_count": len(reference),
        "reference_bidirectional_context_count": len(complete),
        "operational_gate_survivor_count": len(robust),
        "robust_frequent_context_count": len(frequent),
        "robust_hourly_context_count": len(hourly),
        "frequent_territorial_frontier_count": len(frequent_territorial),
        "hourly_territorial_frontier_count": len(hourly_territorial),
        "h60_exception_qualifying_context_count": len(hourly_qualifying),
        "headway_class_diagnostic_choice": chosen_class,
        "headway_class_diagnostic_reason": class_reason,
        "headway_class_selection_authorized": False,
        "final_layer_survivor_count": len(survivors),
        "final_layer_unique_scenario_count": len({row["scenario_id"] for row in survivors}),
        "final_layer_headway_values": sorted({float(row["uniform_headway_min"]) for row in survivors}),
        "strict_lexicographic_diagnostic": {
            "trace": strict_trace,
            "survivor_count": len(strict_survivors),
            "selection_authorized": False,
        },
        "diagnostic_interpretation": (
            "The headway-class choice is a dry-run policy diagnostic, not PRIMARY/RUNNER-UP selection. "
            "H60 cannot be rescued by later cost/fleet criteria after failing the explicit territorial exception. "
            "Current-Service Baseline V4 must be reviewed before the finalizer may run."
        ),
        "lineage": {
            "policy_sha256": sha256_path(args.policy),
            "readiness_validation_sha256": sha256_path(args.readiness_validation),
            "context_readiness_sha256": sha256_path(args.context_readiness),
        },
    }
    (output_dir / "final_policy_dry_run_v3_validation.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", type=Path, default=Path("config/phase2_final_policy_contract_v3.json"))
    parser.add_argument("--context-readiness", type=Path, default=Path("outputs/phase2/final_tournament_readiness_rt001_v3/final_tournament_context_readiness_rt001_v3.csv.gz"))
    parser.add_argument("--readiness-validation", type=Path, default=Path("outputs/phase2/final_tournament_readiness_rt001_v3/final_tournament_readiness_rt001_v3_validation.json"))
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/phase2/final_policy_dry_run_v3"))
    return parser.parse_args()


if __name__ == "__main__":
    summary = build(parse_args())
    print(json.dumps(summary, indent=2, sort_keys=True))
