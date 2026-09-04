#!/usr/bin/env python3
"""Dry-run the human-approved Phase 2 V3 policy without selecting a recommendation.

This diagnostic is intentionally non-decisional.  It operates only on the
certified final-tournament readiness table, fixes the explicitly selected
reference budget, applies the declared operational gate and then reports how
successive no-weight Pareto layers reduce the choice set.  A strict exact
lexicographic trace is emitted only to expose brittleness; it is never a
selection rule.
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
    # Deduplicate exact metric vectors first; all equivalent contexts survive.
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


def build(args: argparse.Namespace) -> dict:
    config = read_json(args.policy)
    readiness = read_json(args.readiness_validation)
    fields, all_rows = read_csv(args.context_readiness)

    if config.get("contract") != CONTRACT:
        raise ValueError("unexpected final policy contract")
    if config.get("status") != "APPROVED_FOR_DRY_RUN_PENDING_CURRENT_SERVICE_V4":
        raise ValueError("policy is not authorised for dry-run")
    if config.get("selection_boundary", {}).get("primary_selection_authorised") is not False:
        raise ValueError("PRIMARY unexpectedly authorised")
    if config.get("selection_boundary", {}).get("runner_up_selection_authorised") is not False:
        raise ValueError("RUNNER-UP unexpectedly authorised")
    if config.get("selection_boundary", {}).get("weighted_composite_score") is not False:
        raise ValueError("weighted score unexpectedly authorised")
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
    expected_hash = readiness.get("lineage", {}).get("context_readiness_output_sha256")
    if expected_hash != sha256_path(args.context_readiness):
        raise ValueError("context readiness lineage hash mismatch")

    # All policy dimensions must be certified fields in the readiness table.
    required_fields = {
        item["field"]
        for layer in config["ordered_no_weight_layers"]
        for item in layer["dimensions"]
    }
    required_fields |= {item["field"] for item in config["strict_lexicographic_diagnostic"]["ordered_criteria"]}
    required_fields |= {"plan_context_id", "selected_timetable_id", "scenario_id", "topology_family", "budget_suffix", "public_route_count", "stage_e_bus_to_rail_observed_profile_count"}
    missing = required_fields - set(fields)
    if missing:
        raise ValueError(f"policy references non-certified/missing fields: {sorted(missing)}")

    reference = [row for row in all_rows if row["budget_suffix"] == "reference"]
    if len(reference) != EXPECTED_REFERENCE_CONTEXTS:
        raise ValueError(f"reference context count changed: {len(reference)}")
    complete = [row for row in reference if int(row["stage_e_bus_to_rail_observed_profile_count"]) > 0]
    if len(complete) != EXPECTED_REFERENCE_BIDIRECTIONAL:
        raise ValueError(f"reference bidirectional context count changed: {len(complete)}")

    # Operational gate is deliberately fail-closed.  We only proceed when at
    # least one context has no Stage-E block infeasibility under sensitivity.
    robust = [row for row in complete if not strict_bool(row["stage_e_any_block_infeasibility_under_sensitivity"], field="stage_e_any_block_infeasibility_under_sensitivity")]
    if not robust:
        raise ValueError("no reference-budget context passes the declared operational robustness gate")

    layer_trace = [{
        "stage": "REFERENCE_BIDIRECTIONAL_INPUT",
        "method": "FILTER",
        "input_count": len(reference),
        "survivor_count": len(complete),
    }, {
        "stage": "OPERATIONAL_ROBUSTNESS_GATE",
        "method": "HARD_GATE",
        "input_count": len(complete),
        "survivor_count": len(robust),
    }]
    survivors = robust
    layer_survivor_sets: dict[str, list[dict[str, str]]] = {}
    for layer in config["ordered_no_weight_layers"]:
        before = len(survivors)
        survivors = pareto_rows(survivors, layer["dimensions"])
        layer_survivor_sets[layer["layer_id"]] = survivors
        layer_trace.append({
            "stage": layer["layer_id"],
            "method": layer["method"],
            "input_count": before,
            "survivor_count": len(survivors),
        })

    strict_trace, strict_survivors = strict_lexicographic_trace(robust, config["strict_lexicographic_diagnostic"]["ordered_criteria"])

    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(output_dir / "policy_layer_trace_v3.csv", ["stage", "method", "input_count", "survivor_count"], layer_trace)
    write_csv(output_dir / "headway_tradeoff_reference_v3.csv", [
        "uniform_headway_min", "context_count", "max_total_coverage_10m", "max_total_coverage_8m", "max_total_coverage_5m",
        "max_worst_municipality_coverage_10m", "max_bidirectional_reachable_share", "max_bidirectional_worst_retention", "min_exact_annual_bus_km"
    ], headway_summary(robust))
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
        "layer_trace": layer_trace,
        "final_layer_survivor_count": len(survivors),
        "final_layer_unique_scenario_count": len({row["scenario_id"] for row in survivors}),
        "final_layer_headway_values": sorted({float(row["uniform_headway_min"]) for row in survivors}),
        "strict_lexicographic_diagnostic": {
            "trace": strict_trace,
            "survivor_count": len(strict_survivors),
            "selection_authorized": False,
        },
        "diagnostic_interpretation": (
            "The layered Pareto cascade is a policy-shape diagnostic, not a final shortlist or recommendation. "
            "The strict lexicographic trace exists only to expose exact-zero-tolerance brittleness. "
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
