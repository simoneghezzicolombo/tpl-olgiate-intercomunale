"""Independent semantic comparison of two Stage-D RT001 V3 implementations.

The comparator intentionally ignores implementation-specific timetable-ID
prefixes and contract labels.  It compares the decision-relevant exact evidence
by plan context and by the canonical identity `(stage_d_input_id, phase vector)`.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import json
from typing import Iterable, Mapping, Sequence

FALSE_BOUNDARY_FIELDS = (
    "decision_budget_selected",
    "calendar_selected",
    "recovery_selected",
    "primary_selected",
    "runner_up_selected",
    "weighted_composite_score",
)

CONTEXT_EXACT_FIELDS = (
    "plan_id",
    "budget_suffix",
    "stage_d_input_id",
    "scenario_id",
    "topology_family",
    "uniform_headway_min",
    "span_id",
    "calendar_id",
    "annual_service_days",
    "phase_vectors_evaluated_once_for_daily_input",
    "exact_budget_feasible_phase_vector_count",
    "exact_budget_hard_eligible",
    "selected_phase_vector_json",
    "exact_fleet_recovery5",
    "exact_fleet_recovery10",
    "exact_fleet_recovery15",
    "retained_current_localizable_cluster_count",
    "retained_current_localizable_cluster_share",
    "s8_target_selection_semantics",
)

CONTEXT_NUMERIC_FIELDS = (
    ("budget_cap_annual_bus_km", Decimal("0.000001")),
    ("robust_min_transfer_quality", Decimal("0.000000000001")),
    ("robust_unweighted_mean_transfer_quality", Decimal("0.000000000001")),
    ("exact_daily_bus_km", Decimal("0.000000001")),
    ("exact_annual_bus_km", Decimal("0.000001")),
)

TIMETABLE_EXACT_FIELDS = (
    "stage_d_input_id",
    "scenario_id",
    "topology_family",
    "uniform_headway_min",
    "span_id",
    "span_start_min",
    "span_end_min",
    "public_route_count",
    "public_route_ids_json",
    "selected_phase_vector_json",
    "explicit_public_trip_count",
    "exact_fleet_recovery5",
    "exact_fleet_recovery10",
    "exact_fleet_recovery15",
    "s8_target_selection_semantics",
)

TIMETABLE_NUMERIC_FIELDS = (
    ("robust_min_transfer_quality", Decimal("0.000000000001")),
    ("robust_unweighted_mean_transfer_quality", Decimal("0.000000000001")),
    ("exact_daily_bus_km", Decimal("0.000000001")),
)


@dataclass(frozen=True)
class Dataset:
    label: str
    validation: Mapping[str, object]
    contexts: Sequence[Mapping[str, object]]
    timetables: Sequence[Mapping[str, object]]
    trips: Sequence[Mapping[str, object]]


def _bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text == "true":
        return True
    if text == "false":
        return False
    raise ValueError(f"not an explicit boolean: {value!r}")


def _decimal(value: object, field: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"invalid decimal {field}={value!r}") from exc
    if not result.is_finite():
        raise ValueError(f"non-finite decimal {field}={value!r}")
    return result


def _phase(value: object) -> tuple[int, ...]:
    parsed = json.loads(str(value))
    if not isinstance(parsed, list) or not parsed:
        raise ValueError(f"invalid phase vector {value!r}")
    return tuple(int(v) for v in parsed)


def _json_list(value: object) -> tuple[str, ...]:
    parsed = json.loads(str(value))
    if not isinstance(parsed, list):
        raise ValueError(f"expected JSON list, got {value!r}")
    return tuple(str(v) for v in parsed)


def _canonical_text(field: str, value: object) -> object:
    if field in {"selected_phase_vector_json"}:
        return _phase(value)
    if field in {"public_route_ids_json"}:
        return _json_list(value)
    if field in {
        "uniform_headway_min", "annual_service_days",
        "phase_vectors_evaluated_once_for_daily_input",
        "exact_budget_feasible_phase_vector_count",
        "exact_fleet_recovery5", "exact_fleet_recovery10", "exact_fleet_recovery15",
        "retained_current_localizable_cluster_count", "span_start_min", "span_end_min",
        "public_route_count", "explicit_public_trip_count",
    }:
        return int(str(value))
    if field in {"exact_budget_hard_eligible"}:
        return _bool(value)
    if field == "retained_current_localizable_cluster_share":
        return _decimal(value, field)
    return str(value)


def _validate_dataset(ds: Dataset) -> dict[str, object]:
    status = str(ds.validation.get("status", ""))
    if not status.startswith("PASS_PHASE2_STAGE_D_EXACT_TIMETABLE_RT001_V3"):
        raise ValueError(f"{ds.label}: validation not Stage-D RT001 V3 PASS: {status!r}")
    for field in FALSE_BOUNDARY_FIELDS:
        if ds.validation.get(field) is not False:
            raise ValueError(f"{ds.label}: non-decisional boundary violated: {field}")
    if ds.validation.get("exact_budget_hard_cap_reapplied_after_materialisation") is not True:
        raise ValueError(f"{ds.label}: exact hard budget was not re-applied")
    if ds.validation.get("s8_target_selection_semantics") != "MAX_CONTINUOUS_TRANSFER_QUALITY_OVER_FINITE_EXPLICIT_TARGET_EVENTS":
        raise ValueError(f"{ds.label}: S8 target semantics changed")
    technical = ds.validation.get("technical_vehicle_closure_used_as_passenger_return")
    if technical is None:
        technical = ds.validation.get("vehicle_only_technical_return_used_as_passenger_service")
    if technical is not False:
        raise ValueError(f"{ds.label}: technical vehicle return leaked into passenger service")

    contexts = {str(r["plan_context_id"]): r for r in ds.contexts}
    if len(contexts) != len(ds.contexts):
        raise ValueError(f"{ds.label}: duplicate plan_context_id")
    if not contexts:
        raise ValueError(f"{ds.label}: empty context output")

    table_by_id: dict[str, Mapping[str, object]] = {}
    table_key_to_id: dict[tuple[str, tuple[int, ...]], str] = {}
    for row in ds.timetables:
        tid = str(row.get("selected_timetable_id", ""))
        if not tid or tid in table_by_id:
            raise ValueError(f"{ds.label}: blank/duplicate selected_timetable_id {tid!r}")
        key = (str(row["stage_d_input_id"]), _phase(row["selected_phase_vector_json"]))
        if key in table_key_to_id:
            raise ValueError(f"{ds.label}: duplicate semantic timetable key {key}")
        table_by_id[tid] = row
        table_key_to_id[key] = tid

    trip_counts: Counter[str] = Counter()
    trip_keys: set[tuple[str, str, int]] = set()
    block_assignment_fields: set[int] = set()
    for row in ds.trips:
        tid = str(row.get("selected_timetable_id", ""))
        if tid not in table_by_id:
            raise ValueError(f"{ds.label}: trip references unknown timetable {tid!r}")
        key = (tid, str(row["route_id"]), int(row["trip_ordinal"]))
        if key in trip_keys:
            raise ValueError(f"{ds.label}: duplicate trip key {key}")
        trip_keys.add(key)
        trip_counts[tid] += 1
        for recovery in (5, 10, 15):
            if row.get(f"vehicle_id_recovery{recovery}") not in (None, ""):
                block_assignment_fields.add(recovery)
    missing = set(table_by_id) - set(trip_counts)
    if missing:
        raise ValueError(f"{ds.label}: timetables with no trips: {sorted(missing)[:3]}")

    mapped_contexts = 0
    for cid, row in contexts.items():
        if not _bool(row["exact_budget_hard_eligible"]):
            raise ValueError(f"{ds.label}: ineligible Stage-C context survived exact Stage D: {cid}")
        tid = str(row.get("selected_timetable_id", ""))
        if tid not in table_by_id:
            raise ValueError(f"{ds.label}: context references unknown timetable {cid} -> {tid}")
        table = table_by_id[tid]
        if str(row["stage_d_input_id"]) != str(table["stage_d_input_id"]):
            raise ValueError(f"{ds.label}: stage_d_input mismatch for {cid}")
        if _phase(row["selected_phase_vector_json"]) != _phase(table["selected_phase_vector_json"]):
            raise ValueError(f"{ds.label}: context/table phase mismatch for {cid}")
        if _decimal(row["exact_annual_bus_km"], "exact_annual_bus_km") > _decimal(row["budget_cap_annual_bus_km"], "budget_cap") + Decimal("0.000001"):
            raise ValueError(f"{ds.label}: exact timetable over budget for {cid}")
        mapped_contexts += 1

    return {
        "status": status,
        "context_count": len(contexts),
        "semantic_timetable_count": len(table_key_to_id),
        "trip_count": len(ds.trips),
        "mapped_context_count": mapped_contexts,
        "materialised_block_assignment_recoveries": sorted(block_assignment_fields),
        "context_index": contexts,
        "table_by_id": table_by_id,
        "table_key_to_id": table_key_to_id,
    }


def _compare_rows(
    label: str,
    a: Mapping[str, object],
    b: Mapping[str, object],
    exact_fields: Sequence[str],
    numeric_fields: Sequence[tuple[str, Decimal]],
) -> list[str]:
    mismatches: list[str] = []
    for field in exact_fields:
        if field not in a or field not in b:
            mismatches.append(f"{label}: missing field {field}")
            continue
        av = _canonical_text(field, a[field])
        bv = _canonical_text(field, b[field])
        if field == "retained_current_localizable_cluster_share":
            if abs(av - bv) > Decimal("0.000000001"):
                mismatches.append(f"{label}: {field} {av} != {bv}")
        elif av != bv:
            mismatches.append(f"{label}: {field} {av!r} != {bv!r}")
    for field, tolerance in numeric_fields:
        if field not in a or field not in b:
            mismatches.append(f"{label}: missing numeric field {field}")
            continue
        av = _decimal(a[field], field)
        bv = _decimal(b[field], field)
        if abs(av - bv) > tolerance:
            mismatches.append(f"{label}: {field} {av} != {bv} (tol {tolerance})")
    return mismatches


def compare_datasets(a: Dataset, b: Dataset, *, max_examples: int = 25) -> dict[str, object]:
    aa = _validate_dataset(a)
    bb = _validate_dataset(b)
    mismatches: list[str] = []

    a_contexts = aa["context_index"]
    b_contexts = bb["context_index"]
    a_ids = set(a_contexts)
    b_ids = set(b_contexts)
    missing_in_b = sorted(a_ids - b_ids)
    missing_in_a = sorted(b_ids - a_ids)
    if missing_in_b:
        mismatches.append(f"contexts missing in {b.label}: {missing_in_b[:5]}")
    if missing_in_a:
        mismatches.append(f"contexts missing in {a.label}: {missing_in_a[:5]}")

    differing_context_count = 0
    differing_phase_count = 0
    for cid in sorted(a_ids & b_ids):
        row_a = a_contexts[cid]
        row_b = b_contexts[cid]
        row_mismatch = _compare_rows(
            f"context {cid}", row_a, row_b,
            CONTEXT_EXACT_FIELDS, CONTEXT_NUMERIC_FIELDS,
        )
        if _phase(row_a["selected_phase_vector_json"]) != _phase(row_b["selected_phase_vector_json"]):
            differing_phase_count += 1
        if row_mismatch:
            differing_context_count += 1
            if len(mismatches) < max_examples:
                mismatches.extend(row_mismatch[: max_examples - len(mismatches)])

    # Timetable IDs differ by implementation, so compare semantic keys only.
    a_tables = {
        (str(row["stage_d_input_id"]), _phase(row["selected_phase_vector_json"])): row
        for row in aa["table_by_id"].values()
    }
    b_tables = {
        (str(row["stage_d_input_id"]), _phase(row["selected_phase_vector_json"])): row
        for row in bb["table_by_id"].values()
    }
    a_tkeys, b_tkeys = set(a_tables), set(b_tables)
    timetable_key_only_a = sorted(a_tkeys - b_tkeys)
    timetable_key_only_b = sorted(b_tkeys - a_tkeys)
    if timetable_key_only_a:
        mismatches.append(f"semantic timetables only in {a.label}: {timetable_key_only_a[:3]}")
    if timetable_key_only_b:
        mismatches.append(f"semantic timetables only in {b.label}: {timetable_key_only_b[:3]}")

    differing_timetable_count = 0
    for key in sorted(a_tkeys & b_tkeys):
        row_mismatch = _compare_rows(
            f"timetable {key}", a_tables[key], b_tables[key],
            TIMETABLE_EXACT_FIELDS, TIMETABLE_NUMERIC_FIELDS,
        )
        if row_mismatch:
            differing_timetable_count += 1
            if len(mismatches) < max_examples:
                mismatches.extend(row_mismatch[: max_examples - len(mismatches)])

    equivalent = (
        not missing_in_a
        and not missing_in_b
        and differing_context_count == 0
        and not timetable_key_only_a
        and not timetable_key_only_b
        and differing_timetable_count == 0
    )
    return {
        "equivalent": equivalent,
        "dataset_a": a.label,
        "dataset_b": b.label,
        "context_count_a": aa["context_count"],
        "context_count_b": bb["context_count"],
        "context_ids_missing_in_a_count": len(missing_in_a),
        "context_ids_missing_in_b_count": len(missing_in_b),
        "differing_context_count": differing_context_count,
        "differing_selected_phase_context_count": differing_phase_count,
        "semantic_timetable_count_a": aa["semantic_timetable_count"],
        "semantic_timetable_count_b": bb["semantic_timetable_count"],
        "semantic_timetable_keys_only_a_count": len(timetable_key_only_a),
        "semantic_timetable_keys_only_b_count": len(timetable_key_only_b),
        "differing_semantic_timetable_count": differing_timetable_count,
        "trip_count_a": aa["trip_count"],
        "trip_count_b": bb["trip_count"],
        "materialised_block_assignment_recoveries_a": aa["materialised_block_assignment_recoveries"],
        "materialised_block_assignment_recoveries_b": bb["materialised_block_assignment_recoveries"],
        "mismatch_examples": mismatches[:max_examples],
        "comparison_identity": "PLAN_CONTEXT_ID_AND_STAGE_D_INPUT_PLUS_PHASE_VECTOR_NOT_IMPLEMENTATION_TIMETABLE_ID",
        "primary_selected": False,
        "runner_up_selected": False,
    }
