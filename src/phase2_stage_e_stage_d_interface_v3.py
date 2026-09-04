"""Interface validation between exact Stage D and Stage E robustness.

The validator is intentionally non-decisional. It verifies that an exact
Stage-D output can be consumed without silently collapsing context-dependent
phase choices introduced by the RT-001 budget repair.
"""
from __future__ import annotations

import json
from collections import Counter
from typing import Iterable, Mapping, Sequence

NON_DECISIONAL_FALSE_FIELDS = (
    "decision_budget_selected",
    "calendar_selected",
    "recovery_selected",
    "primary_selected",
    "runner_up_selected",
    "weighted_composite_score",
)

DEDICATED_EXACT_ID_FIELDS = ("exact_timetable_id", "selected_timetable_id")


def _strict_false(payload: Mapping[str, object], field: str) -> None:
    if payload.get(field) is not False:
        raise ValueError(f"Stage-D selection boundary violated: {field}")


def validate_stage_d_validation(payload: Mapping[str, object]) -> dict[str, object]:
    status = str(payload.get("status", ""))
    contract = str(payload.get("contract", ""))
    if not status.startswith("PASS_PHASE2_STAGE_D_EXACT"):
        raise ValueError(f"Stage-D exact validation is not PASS: {status!r}")
    if "EXACT" not in contract or "TIMETABLE" not in contract:
        raise ValueError(f"Stage-D contract is not an exact-timetable contract: {contract!r}")

    exact_constructed = payload.get("exact_timetable_constructed") is True
    if not exact_constructed:
        exact_constructed = (
            int(payload.get("unique_selected_exact_timetable_count", 0)) > 0
            and payload.get("exact_selected_annual_bus_km_derived_from_materialised_phase_vector") is True
        )
    if not exact_constructed:
        raise ValueError("Stage-D exact timetable is not demonstrably constructed")

    blocks_evaluated = payload.get("joint_vehicle_blocks_evaluated") is True
    if not blocks_evaluated:
        materialised = payload.get("vehicle_block_assignments_materialised_for_recovery_values")
        blocks_evaluated = isinstance(materialised, list) and bool(materialised)
    if not blocks_evaluated:
        raise ValueError("Stage-D exact vehicle-block evidence is not evaluated/materialised")

    for field in NON_DECISIONAL_FALSE_FIELDS:
        _strict_false(payload, field)

    recoveries = payload.get("recovery_values_evaluated_not_selected")
    if not isinstance(recoveries, list) or not recoveries:
        raise ValueError("Stage-D recovery sensitivities are missing")
    if payload.get("ridership_forecast") is True:
        raise ValueError("Stage-D unexpectedly contains a ridership forecast")
    if payload.get("municipal_od_downscaled") is True:
        raise ValueError("Stage-D unexpectedly downscales municipal OD")
    if payload.get("technical_vehicle_closure_used_as_passenger_return") is True:
        raise ValueError("Stage-D technical vehicle closure leaked into passenger service")

    represented = None
    for key in (
        "represented_stage_c_plan_context_count",
        "represented_plan_context_count",
        "passenger_plan_context_count_represented",
        "stage_c_plan_context_count",
    ):
        if key in payload:
            represented = int(payload[key])
            break
    return {
        "status": status,
        "contract": contract,
        "represented_plan_context_count_declared": represented,
        "recovery_values": tuple(int(v) for v in recoveries),
    }


def choose_exact_identity_field(summary_fields: Iterable[str], trip_fields: Iterable[str]) -> str:
    s = set(summary_fields)
    t = set(trip_fields)
    for field in DEDICATED_EXACT_ID_FIELDS:
        if field in s and field in t:
            return field
    if "stage_d_input_id" in s and "stage_d_input_id" in t:
        return "stage_d_input_id"
    raise ValueError("Stage-D summary/trips share no supported exact timetable identity")


def _parse_contexts(value: object) -> tuple[str, ...]:
    if value in (None, ""):
        return ()
    parsed = json.loads(str(value))
    if not isinstance(parsed, list):
        raise ValueError("represented_plan_context_ids_json must be a JSON list")
    contexts = tuple(str(v) for v in parsed)
    if any(not v for v in contexts) or len(set(contexts)) != len(contexts):
        raise ValueError("blank or duplicate plan context within exact timetable")
    return contexts


def _context_identity(row: Mapping[str, object]) -> str:
    for field in ("plan_context_id", "context_id"):
        value = str(row.get(field, ""))
        if value:
            return value
    raise ValueError("context mapping row lacks plan_context_id/context_id")


def validate_exact_interface(
    validation: Mapping[str, object],
    summary_rows: Iterable[Mapping[str, object]],
    trip_rows: Iterable[Mapping[str, object]],
    *,
    summary_fields: Iterable[str],
    trip_fields: Iterable[str],
    context_rows: Iterable[Mapping[str, object]] | None = None,
    context_fields: Sequence[str] | None = None,
) -> dict[str, object]:
    v = validate_stage_d_validation(validation)
    identity_field = choose_exact_identity_field(summary_fields, trip_fields)

    summaries: dict[str, Mapping[str, object]] = {}
    stage_input_to_exact: dict[str, set[str]] = {}
    context_to_exact: dict[str, str] = {}
    context_rows_present = False

    for row in summary_rows:
        exact_id = str(row.get(identity_field, ""))
        if not exact_id or exact_id in summaries:
            raise ValueError(f"blank or duplicate exact timetable identity: {exact_id!r}")
        stage_input_id = str(row.get("stage_d_input_id", ""))
        if not stage_input_id:
            raise ValueError(f"{exact_id}: missing stage_d_input_id")
        summaries[exact_id] = row
        stage_input_to_exact.setdefault(stage_input_id, set()).add(exact_id)

        phase_text = str(row.get("selected_phase_vector_json", ""))
        if phase_text:
            parsed = json.loads(phase_text)
            if not isinstance(parsed, list):
                raise ValueError(f"{exact_id}: selected phase vector is not a list")

        contexts = _parse_contexts(row.get("represented_plan_context_ids_json"))
        if contexts:
            context_rows_present = True
        for context_id in contexts:
            if context_id in context_to_exact:
                raise ValueError(f"plan context represented by multiple exact timetables: {context_id}")
            context_to_exact[context_id] = exact_id

    if not summaries:
        raise ValueError("Stage-D exact summary is empty")

    if context_rows is not None:
        if context_fields is None:
            raise ValueError("context_fields required when context_rows are supplied")
        context_field_set = set(context_fields)
        mapping_exact_field = next((f for f in DEDICATED_EXACT_ID_FIELDS if f in context_field_set), None)
        if mapping_exact_field is None:
            raise ValueError("context mapping lacks a dedicated exact timetable id")
        if mapping_exact_field != identity_field:
            raise ValueError(
                f"context mapping exact identity {mapping_exact_field} differs from summary/trip identity {identity_field}"
            )
        if context_rows_present:
            raise ValueError("plan-context mapping is materialised both in summary and separate context rows")
        for row in context_rows:
            context_rows_present = True
            context_id = _context_identity(row)
            exact_id = str(row.get(mapping_exact_field, ""))
            if row.get("exact_budget_hard_eligible") not in (None, "", True, "true"):
                raise ValueError(f"ineligible plan context reached Stage-E exact mapping: {context_id}")
            if not exact_id:
                raise ValueError(f"eligible plan context lacks exact timetable mapping: {context_id}")
            if exact_id not in summaries:
                raise ValueError(f"plan context references unknown exact timetable: {exact_id}")
            if context_id in context_to_exact:
                raise ValueError(f"duplicate/overlapping plan context mapping: {context_id}")
            context_to_exact[context_id] = exact_id

            stage_input = str(row.get("stage_d_input_id", ""))
            if stage_input and stage_input != str(summaries[exact_id].get("stage_d_input_id", "")):
                raise ValueError(f"plan context Stage-D input disagrees with exact timetable: {context_id}")

            phase = str(row.get("selected_phase_vector_json", ""))
            summary_phase = str(summaries[exact_id].get("selected_phase_vector_json", ""))
            if phase and summary_phase and json.loads(phase) != json.loads(summary_phase):
                raise ValueError(f"plan context phase disagrees with exact timetable: {context_id}")

    split_stage_inputs = {k: ids for k, ids in stage_input_to_exact.items() if len(ids) > 1}
    if split_stage_inputs and identity_field not in DEDICATED_EXACT_ID_FIELDS:
        raise ValueError("context-dependent Stage-D timetable split lacks dedicated exact timetable identity")

    declared = v["represented_plan_context_count_declared"]
    if declared is not None and context_rows_present and len(context_to_exact) != declared:
        raise ValueError(
            f"lossless plan-context coverage mismatch: {len(context_to_exact)} != {declared}"
        )

    trip_counts: Counter[str] = Counter()
    seen_trip_keys: set[tuple[str, str, str]] = set()
    for row in trip_rows:
        exact_id = str(row.get(identity_field, ""))
        if exact_id not in summaries:
            raise ValueError(f"trip references unknown exact timetable: {exact_id!r}")
        route_id = str(row.get("route_id", ""))
        ordinal = str(row.get("trip_ordinal", ""))
        if not route_id or ordinal == "":
            raise ValueError(f"{exact_id}: trip lacks route_id/trip_ordinal")
        key = (exact_id, route_id, ordinal)
        if key in seen_trip_keys:
            raise ValueError(f"duplicate exact trip key: {key}")
        seen_trip_keys.add(key)
        trip_counts[exact_id] += 1

    missing_trip_sets = sorted(set(summaries) - set(trip_counts))
    if missing_trip_sets:
        raise ValueError(f"exact timetables without trips: {missing_trip_sets[:3]}")

    return {
        "interface_ready": True,
        "identity_field": identity_field,
        "exact_timetable_count": len(summaries),
        "stage_d_input_count": len(stage_input_to_exact),
        "stage_d_inputs_with_context_dependent_exact_split": len(split_stage_inputs),
        "represented_plan_context_count_observed": len(context_to_exact) if context_rows_present else None,
        "represented_plan_context_count_declared": declared,
        "trip_count": sum(trip_counts.values()),
        "all_exact_timetables_have_trips": True,
        "plan_context_mapping_lossless_when_present": True,
        "context_mapping_mode": (
            "SEPARATE_CONTEXT_TABLE" if context_rows is not None else
            "SUMMARY_EMBEDDED" if context_rows_present else "NOT_MATERIALISED"
        ),
        "context_dependent_split_requires_dedicated_exact_timetable_id": True,
        "stage_e_can_consume_without_context_collapse": True,
        "primary_selected": False,
        "runner_up_selected": False,
    }
