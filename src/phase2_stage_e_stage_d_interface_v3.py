"""Interface validation between exact Stage D and Stage E robustness.

The validator is intentionally non-decisional.  It verifies that an exact
Stage-D output can be consumed without silently collapsing context-dependent
phase choices introduced by the RT-001 budget repair.
"""
from __future__ import annotations

import json
from collections import Counter
from typing import Iterable, Mapping

NON_DECISIONAL_FALSE_FIELDS = (
    "decision_budget_selected",
    "calendar_selected",
    "recovery_selected",
    "primary_selected",
    "runner_up_selected",
    "weighted_composite_score",
)


def _strict_false(payload: Mapping[str, object], field: str) -> None:
    if payload.get(field) is not False:
        raise ValueError(f"Stage-D selection boundary violated: {field}")


def validate_stage_d_validation(payload: Mapping[str, object]) -> dict[str, object]:
    status = str(payload.get("status", ""))
    contract = str(payload.get("contract", ""))
    if not status.startswith("PASS_PHASE2_STAGE_D_EXACT"):
        raise ValueError(f"Stage-D exact validation is not PASS: {status!r}")
    if "EXACT_TIMETABLE" not in contract:
        raise ValueError(f"Stage-D contract is not an exact-timetable contract: {contract!r}")
    if payload.get("exact_timetable_constructed") is not True:
        raise ValueError("Stage-D exact timetable is not constructed")
    if payload.get("joint_vehicle_blocks_evaluated") is not True:
        raise ValueError("Stage-D joint vehicle blocks are not evaluated")
    for field in NON_DECISIONAL_FALSE_FIELDS:
        _strict_false(payload, field)

    recoveries = payload.get("recovery_values_evaluated_not_selected")
    if not isinstance(recoveries, list) or not recoveries:
        raise ValueError("Stage-D recovery sensitivities are missing")
    if payload.get("ridership_forecast") is not False:
        raise ValueError("Stage-D unexpectedly contains a ridership forecast")
    if payload.get("municipal_od_downscaled") is not False:
        raise ValueError("Stage-D unexpectedly downscales municipal OD")

    represented = None
    for key in (
        "represented_stage_c_plan_context_count",
        "represented_plan_context_count",
        "passenger_plan_context_count_represented",
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
    if "exact_timetable_id" in s and "exact_timetable_id" in t:
        return "exact_timetable_id"
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


def validate_exact_interface(
    validation: Mapping[str, object],
    summary_rows: Iterable[Mapping[str, object]],
    trip_rows: Iterable[Mapping[str, object]],
    *,
    summary_fields: Iterable[str],
    trip_fields: Iterable[str],
) -> dict[str, object]:
    v = validate_stage_d_validation(validation)
    identity_field = choose_exact_identity_field(summary_fields, trip_fields)

    summaries: dict[str, Mapping[str, object]] = {}
    stage_input_to_exact: dict[str, set[str]] = {}
    context_to_exact: dict[str, str] = {}
    phase_by_exact: dict[str, str] = {}
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
            phase_by_exact[exact_id] = json.dumps(parsed, separators=(",", ":"))

        contexts = _parse_contexts(row.get("represented_plan_context_ids_json"))
        if contexts:
            context_rows_present = True
        for context_id in contexts:
            if context_id in context_to_exact:
                raise ValueError(f"plan context represented by multiple exact timetables: {context_id}")
            context_to_exact[context_id] = exact_id

    if not summaries:
        raise ValueError("Stage-D exact summary is empty")

    # If Stage D has context-dependent timetable splits, a dedicated exact key is mandatory.
    split_stage_inputs = {k: ids for k, ids in stage_input_to_exact.items() if len(ids) > 1}
    if split_stage_inputs and identity_field != "exact_timetable_id":
        raise ValueError("context-dependent Stage-D timetable split lacks exact_timetable_id")

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
        "context_dependent_split_requires_exact_timetable_id": True,
        "stage_e_can_consume_without_context_collapse": True,
        "primary_selected": False,
        "runner_up_selected": False,
    }
