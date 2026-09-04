"""Semantic cross-audit for independent Stage-D RT001 V3 implementations.

Implementation-specific timetable IDs and contract names are not compared.
Evidence is normalised by plan_context_id and by
(stage_d_input_id, selected phase vector).
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import json
from typing import Mapping, Sequence

FALSE_BOUNDARY_FIELDS = (
    "decision_budget_selected", "calendar_selected", "recovery_selected",
    "primary_selected", "runner_up_selected", "weighted_composite_score",
)

CONTEXT_EXACT_FIELDS = (
    "plan_id", "budget_suffix", "stage_d_input_id", "scenario_id",
    "topology_family", "uniform_headway_min", "span_id", "calendar_id",
    "annual_service_days", "phase_vectors_evaluated_once_for_daily_input",
    "exact_budget_feasible_phase_vector_count", "exact_budget_hard_eligible",
    "selected_phase_vector_json", "exact_fleet_recovery5",
    "exact_fleet_recovery10", "exact_fleet_recovery15",
    "retained_current_localizable_cluster_count",
    "retained_current_localizable_cluster_share", "s8_target_selection_semantics",
)
CONTEXT_NUMERIC_FIELDS = (
    ("budget_cap_annual_bus_km", Decimal("0.000001")),
    ("robust_min_transfer_quality", Decimal("0.000000000001")),
    ("robust_unweighted_mean_transfer_quality", Decimal("0.000000000001")),
    ("exact_daily_bus_km", Decimal("0.000000001")),
    ("exact_annual_bus_km", Decimal("0.000001")),
)
TIMETABLE_EXACT_FIELDS = (
    "stage_d_input_id", "scenario_id", "topology_family", "uniform_headway_min",
    "span_id", "span_start_min", "span_end_min", "public_route_count",
    "public_route_ids_json", "selected_phase_vector_json", "explicit_public_trip_count",
    "exact_fleet_recovery5", "exact_fleet_recovery10", "exact_fleet_recovery15",
    "s8_target_selection_semantics",
)
TIMETABLE_NUMERIC_FIELDS = (
    ("robust_min_transfer_quality", Decimal("0.000000000001")),
    ("robust_unweighted_mean_transfer_quality", Decimal("0.000000000001")),
    ("exact_daily_bus_km", Decimal("0.000000001")),
)
TRIP_NUMERIC_FIELDS = (
    ("departure_min", Decimal("0.000001")),
    ("public_service_end_min", Decimal("0.000001")),
    ("vehicle_return_hub_min", Decimal("0.000001")),
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
    if text == "true": return True
    if text == "false": return False
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


def _canonical(field: str, value: object) -> object:
    if field == "selected_phase_vector_json": return _phase(value)
    if field == "public_route_ids_json": return _json_list(value)
    if field in {
        "uniform_headway_min", "annual_service_days",
        "phase_vectors_evaluated_once_for_daily_input",
        "exact_budget_feasible_phase_vector_count", "exact_fleet_recovery5",
        "exact_fleet_recovery10", "exact_fleet_recovery15",
        "retained_current_localizable_cluster_count", "span_start_min", "span_end_min",
        "public_route_count", "explicit_public_trip_count",
    }:
        return int(str(value))
    if field == "exact_budget_hard_eligible": return _bool(value)
    if field == "retained_current_localizable_cluster_share": return _decimal(value, field)
    return str(value)


def _compare_rows(label, a, b, exact_fields, numeric_fields) -> list[str]:
    out: list[str] = []
    for field in exact_fields:
        if field not in a or field not in b:
            out.append(f"{label}: missing field {field}")
            continue
        av, bv = _canonical(field, a[field]), _canonical(field, b[field])
        if field == "retained_current_localizable_cluster_share":
            if abs(av - bv) > Decimal("0.000000001"):
                out.append(f"{label}: {field} {av} != {bv}")
        elif av != bv:
            out.append(f"{label}: {field} {av!r} != {bv!r}")
    for field, tol in numeric_fields:
        if field not in a or field not in b:
            out.append(f"{label}: missing numeric field {field}")
            continue
        av, bv = _decimal(a[field], field), _decimal(b[field], field)
        if abs(av - bv) > tol:
            out.append(f"{label}: {field} {av} != {bv} (tol {tol})")
    return out


def _canonical_partition(rows, recovery: int):
    field = f"vehicle_id_recovery{recovery}"
    groups: dict[str, list[tuple[str, int]]] = defaultdict(list)
    for row in rows:
        vehicle = str(row.get(field, ""))
        if not vehicle:
            raise ValueError(f"missing {field}")
        groups[vehicle].append((str(row["route_id"]), int(row["trip_ordinal"])))
    return tuple(sorted(tuple(sorted(v)) for v in groups.values()))


def _validate_dataset(ds: Dataset) -> dict[str, object]:
    v = ds.validation
    status = str(v.get("status", ""))
    if not status.startswith("PASS_PHASE2_STAGE_D_EXACT_TIMETABLE_RT001_V3"):
        raise ValueError(f"{ds.label}: not a PASS Stage-D RT001 V3 validation: {status!r}")
    for field in FALSE_BOUNDARY_FIELDS:
        if v.get(field) is not False:
            raise ValueError(f"{ds.label}: non-decisional boundary violated: {field}")
    if v.get("exact_budget_hard_cap_reapplied_after_materialisation") is not True:
        raise ValueError(f"{ds.label}: exact hard budget not re-applied")
    if v.get("s8_target_selection_semantics") != "MAX_CONTINUOUS_TRANSFER_QUALITY_OVER_FINITE_EXPLICIT_TARGET_EVENTS":
        raise ValueError(f"{ds.label}: S8 target semantics changed")
    technical = v.get("technical_vehicle_closure_used_as_passenger_return")
    if technical is None:
        technical = v.get("vehicle_only_technical_return_used_as_passenger_service")
    if technical is not False:
        raise ValueError(f"{ds.label}: technical return leaked into passenger service")

    contexts = {str(r["plan_context_id"]): r for r in ds.contexts}
    if not contexts or len(contexts) != len(ds.contexts):
        raise ValueError(f"{ds.label}: empty or duplicate plan-context output")

    table_by_id: dict[str, Mapping[str, object]] = {}
    table_by_semantic_key: dict[tuple[str, tuple[int, ...]], Mapping[str, object]] = {}
    semantic_key_by_id: dict[str, tuple[str, tuple[int, ...]]] = {}
    for row in ds.timetables:
        tid = str(row.get("selected_timetable_id", ""))
        if not tid or tid in table_by_id:
            raise ValueError(f"{ds.label}: blank/duplicate timetable id")
        skey = (str(row["stage_d_input_id"]), _phase(row["selected_phase_vector_json"]))
        if skey in table_by_semantic_key:
            raise ValueError(f"{ds.label}: duplicate semantic timetable {skey}")
        table_by_id[tid] = row
        table_by_semantic_key[skey] = row
        semantic_key_by_id[tid] = skey

    trips_by_semantic: dict[tuple[str, tuple[int, ...]], list[Mapping[str, object]]] = defaultdict(list)
    seen_trip: set[tuple[str, str, int]] = set()
    materialised_recoveries: set[int] = set()
    for row in ds.trips:
        tid = str(row.get("selected_timetable_id", ""))
        if tid not in table_by_id:
            raise ValueError(f"{ds.label}: orphan trip timetable {tid!r}")
        key = (tid, str(row["route_id"]), int(row["trip_ordinal"]))
        if key in seen_trip:
            raise ValueError(f"{ds.label}: duplicate trip {key}")
        seen_trip.add(key)
        trips_by_semantic[semantic_key_by_id[tid]].append(row)
        for recovery in (5, 10, 15):
            if row.get(f"vehicle_id_recovery{recovery}") not in (None, ""):
                materialised_recoveries.add(recovery)
    if set(table_by_semantic_key) != set(trips_by_semantic):
        raise ValueError(f"{ds.label}: timetable/trip semantic universe mismatch")
    for skey, rows in trips_by_semantic.items():
        rows.sort(key=lambda r: (str(r["route_id"]), int(r["trip_ordinal"])))
        expected = int(table_by_semantic_key[skey]["explicit_public_trip_count"])
        if len(rows) != expected:
            raise ValueError(f"{ds.label}: trip count mismatch for {skey}")

    for cid, row in contexts.items():
        if not _bool(row["exact_budget_hard_eligible"]):
            raise ValueError(f"{ds.label}: ineligible context survived: {cid}")
        tid = str(row.get("selected_timetable_id", ""))
        if tid not in table_by_id:
            raise ValueError(f"{ds.label}: context points to unknown timetable: {cid}")
        table = table_by_id[tid]
        if str(row["stage_d_input_id"]) != str(table["stage_d_input_id"]):
            raise ValueError(f"{ds.label}: context/timetable Stage-D id mismatch: {cid}")
        if _phase(row["selected_phase_vector_json"]) != _phase(table["selected_phase_vector_json"]):
            raise ValueError(f"{ds.label}: context/timetable phase mismatch: {cid}")
        annual = _decimal(row["exact_annual_bus_km"], "exact_annual_bus_km")
        cap = _decimal(row["budget_cap_annual_bus_km"], "budget_cap_annual_bus_km")
        if annual > cap + Decimal("0.000001"):
            raise ValueError(f"{ds.label}: exact annual km exceed cap: {cid}")

    return {
        "contexts": contexts,
        "tables": table_by_semantic_key,
        "trips": trips_by_semantic,
        "context_count": len(contexts),
        "timetable_count": len(table_by_semantic_key),
        "trip_count": len(ds.trips),
        "materialised_recoveries": sorted(materialised_recoveries),
    }


def compare_datasets(a: Dataset, b: Dataset, *, max_examples: int = 30) -> dict[str, object]:
    aa, bb = _validate_dataset(a), _validate_dataset(b)
    examples: list[str] = []

    a_ids, b_ids = set(aa["contexts"]), set(bb["contexts"])
    missing_a, missing_b = sorted(b_ids - a_ids), sorted(a_ids - b_ids)
    if missing_a: examples.append(f"contexts missing in {a.label}: {missing_a[:5]}")
    if missing_b: examples.append(f"contexts missing in {b.label}: {missing_b[:5]}")

    differing_contexts = differing_phases = 0
    for cid in sorted(a_ids & b_ids):
        ra, rb = aa["contexts"][cid], bb["contexts"][cid]
        diff = _compare_rows(f"context {cid}", ra, rb, CONTEXT_EXACT_FIELDS, CONTEXT_NUMERIC_FIELDS)
        if _phase(ra["selected_phase_vector_json"]) != _phase(rb["selected_phase_vector_json"]):
            differing_phases += 1
        if diff:
            differing_contexts += 1
            if len(examples) < max_examples:
                examples.extend(diff[:max_examples-len(examples)])

    a_t, b_t = aa["tables"], bb["tables"]
    a_keys, b_keys = set(a_t), set(b_t)
    only_a, only_b = sorted(a_keys-b_keys), sorted(b_keys-a_keys)
    if only_a: examples.append(f"semantic timetables only in {a.label}: {only_a[:3]}")
    if only_b: examples.append(f"semantic timetables only in {b.label}: {only_b[:3]}")
    differing_tables = 0
    for key in sorted(a_keys & b_keys):
        diff = _compare_rows(f"timetable {key}", a_t[key], b_t[key], TIMETABLE_EXACT_FIELDS, TIMETABLE_NUMERIC_FIELDS)
        if diff:
            differing_tables += 1
            if len(examples) < max_examples:
                examples.extend(diff[:max_examples-len(examples)])

    # Exact public-trip timing is part of Stage E's downstream contract.
    differing_trip_sets = 0
    common_tkeys = a_keys & b_keys
    for skey in sorted(common_tkeys):
        ta, tb = aa["trips"][skey], bb["trips"][skey]
        ia = {(str(r["route_id"]), int(r["trip_ordinal"])): r for r in ta}
        ib = {(str(r["route_id"]), int(r["trip_ordinal"])): r for r in tb}
        trip_diff = False
        if set(ia) != set(ib):
            trip_diff = True
            if len(examples) < max_examples:
                examples.append(f"trip identity mismatch for timetable {skey}")
        for key in sorted(set(ia) & set(ib)):
            ra, rb = ia[key], ib[key]
            if int(ra["route_phase_min"]) != int(rb["route_phase_min"]):
                trip_diff = True
                if len(examples) < max_examples:
                    examples.append(f"trip {skey}/{key}: route_phase_min differs")
            for field, tol in TRIP_NUMERIC_FIELDS:
                av, bv = _decimal(ra[field], field), _decimal(rb[field], field)
                if abs(av-bv) > tol:
                    trip_diff = True
                    if len(examples) < max_examples:
                        examples.append(f"trip {skey}/{key}: {field} {av} != {bv}")
        if trip_diff: differing_trip_sets += 1

    common_recoveries = sorted(set(aa["materialised_recoveries"]) & set(bb["materialised_recoveries"]))
    block_partition_mismatch = {r: 0 for r in common_recoveries}
    for recovery in common_recoveries:
        for skey in sorted(common_tkeys):
            if _canonical_partition(aa["trips"][skey], recovery) != _canonical_partition(bb["trips"][skey], recovery):
                block_partition_mismatch[recovery] += 1
                if len(examples) < max_examples:
                    examples.append(f"timetable {skey}: recovery {recovery} vehicle partition differs")

    equivalent = (
        not missing_a and not missing_b and differing_contexts == 0
        and not only_a and not only_b and differing_tables == 0
        and differing_trip_sets == 0 and all(v == 0 for v in block_partition_mismatch.values())
    )
    return {
        "equivalent": equivalent,
        "dataset_a": a.label, "dataset_b": b.label,
        "context_count_a": aa["context_count"], "context_count_b": bb["context_count"],
        "contexts_missing_in_a_count": len(missing_a), "contexts_missing_in_b_count": len(missing_b),
        "differing_context_count": differing_contexts,
        "differing_selected_phase_context_count": differing_phases,
        "semantic_timetable_count_a": aa["timetable_count"], "semantic_timetable_count_b": bb["timetable_count"],
        "semantic_timetables_only_a_count": len(only_a), "semantic_timetables_only_b_count": len(only_b),
        "differing_semantic_timetable_count": differing_tables,
        "trip_count_a": aa["trip_count"], "trip_count_b": bb["trip_count"],
        "differing_semantic_trip_set_count": differing_trip_sets,
        "materialised_block_assignment_recoveries_a": aa["materialised_recoveries"],
        "materialised_block_assignment_recoveries_b": bb["materialised_recoveries"],
        "common_block_assignment_recoveries_compared": common_recoveries,
        "block_partition_mismatch_count_by_recovery": block_partition_mismatch,
        "mismatch_examples": examples[:max_examples],
        "comparison_identity": "PLAN_CONTEXT_ID_AND_STAGE_D_INPUT_PLUS_PHASE_VECTOR_NOT_IMPLEMENTATION_TIMETABLE_ID",
        "primary_selected": False, "runner_up_selected": False,
    }
