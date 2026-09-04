#!/usr/bin/env python3
"""Attach lineage-compatible S8 phase-opportunity evidence to Stage-C plans.

This stage deliberately does not select a timetable phase or reject candidates.
It promotes only the narrow S8 transfer-gap envelope from a pinned historical
commit after proving that its frozen upstream hashes are identical to the
current S8 phase, route-universe, scenario-mapping, events and policy evidence.
No historical ranking/finalist output is consumed.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
from pathlib import Path

STATUS = "PASS_PHASE2_S8_ROBUST_OPPORTUNITY_SURFACE_V2"
CONTRACT = "PHASE2_LINEAGE_PINNED_PRE_TIMETABLE_S8_OPPORTUNITY_V2"
PINNED_SOURCE_COMMIT = "8d79cbd74c3ec99ec3eff5fca7a799975210356b"


def sha256_path(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def strict_bool(value: object, *, field: str) -> bool:
    text = str(value).strip().lower()
    if text == "true":
        return True
    if text == "false":
        return False
    raise ValueError(f"{field} must be explicit true/false, got {value!r}")


def deterministic_gzip_writer(path: Path, fields: list[str]):
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = path.open("wb")
    gz = gzip.GzipFile(filename="", mode="wb", fileobj=raw, compresslevel=9, mtime=0)
    text = io.TextIOWrapper(gz, encoding="utf-8", newline="")
    writer = csv.DictWriter(text, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    return raw, text, writer


def validate_lineage(args) -> tuple[dict, dict, dict, dict, dict]:
    pu = load_json(args.passenger_validation)
    current = load_json(args.current_s8_validation)
    env = load_json(args.legacy_envelope_validation)
    gap = load_json(args.legacy_transfer_validation)
    support = load_json(args.legacy_support_validation)
    weights = load_json(args.legacy_work_weights_validation)

    if pu.get("status") != "PASS_PHASE2_PASSENGER_UTILITY_FRONTIER_V2":
        raise ValueError("Passenger Utility Frontier V2 is not PASS")
    if pu.get("contract") != "PHASE2_NO_WEIGHT_PASSENGER_UTILITY_FRONTIER_V2":
        raise ValueError("Unexpected Passenger Utility contract")
    if pu.get("lineage", {}).get("frontier_output_sha256") != sha256_path(args.passenger_frontier):
        raise ValueError("Passenger Utility frontier hash mismatch")

    if current.get("status") != "PASS_S8_PHASE_OPPORTUNITY_V2_BUILD":
        raise ValueError("Current S8 phasing is not PASS")
    if current.get("contract") != "PHASE2_S8_PHASE_OPPORTUNITY_SURFACE_V2":
        raise ValueError("Unexpected current S8 contract")
    if current.get("phase_selected") is not False or current.get("all_phases_retained_downstream") is not True:
        raise ValueError("Current S8 phase domain is not complete/unselected")

    if env.get("status") != "PASS_S8_SCENARIO_FEEDER_ENVELOPE_V2_BUILD" or env.get("contract") != "PHASE2_S8_SCENARIO_FEEDER_ENVELOPE_V2":
        raise ValueError("Pinned S8 scenario envelope is not certified")
    if gap.get("status") != "PASS_S8_TRANSFER_GAP_ENVELOPE_V2_BUILD" or gap.get("contract") != "PHASE2_S8_TRANSFER_GAP_ENVELOPE_V2":
        raise ValueError("Pinned transfer-gap envelope is not certified")
    if support.get("status") != "PASS_S8_PASSENGER_SUPPORT_MASK_V2_BUILD" or support.get("contract") != "PHASE2_S8_PASSENGER_SUPPORT_MASK_V2":
        raise ValueError("Pinned passenger-support mask is not certified")
    if weights.get("status") != "PASS_S8_WORK_DIRECTION_WEIGHTS_V2_BUILD" or weights.get("contract") != "PHASE2_S8_WORK_DIRECTION_WEIGHTS_V2":
        raise ValueError("Pinned work-direction weights are not certified")

    current_hash = sha256_path(args.current_s8_validation)
    current_lineage = current.get("lineage", {})
    expected_actual = {
        "support/current S8 validation": (support.get("lineage", {}).get("s8_validation_sha256"), current_hash),
        "gap/current S8 validation": (gap.get("lineage", {}).get("s8_validation_sha256"), current_hash),
        "support/current route universe": (support.get("lineage", {}).get("s8_route_universe_sha256"), sha256_path(args.current_route_universe)),
        "support/current scenario mapping": (support.get("lineage", {}).get("s8_scenario_route_mapping_sha256"), sha256_path(args.current_scenario_mapping)),
        "envelope/current scenario mapping": (env.get("lineage", {}).get("scenario_mapping_sha256"), sha256_path(args.current_scenario_mapping)),
        "gap/current S8 events": (gap.get("lineage", {}).get("s8_events_sha256"), sha256_path(args.current_s8_events)),
        "gap/current policy grid": (gap.get("lineage", {}).get("policy_grid_sha256"), sha256_path(args.current_policy_grid)),
        "weights/current S8 events": (weights.get("lineage", {}).get("s8_events_sha256"), sha256_path(args.current_s8_events)),
        "weights/current S8 contract": (weights.get("lineage", {}).get("s8_contract_sha256"), sha256_path(args.current_s8_contract)),
    }
    for label, (expected, actual) in expected_actual.items():
        if expected != actual:
            raise ValueError(f"Pinned/current lineage mismatch for {label}: {expected} != {actual}")

    if current_lineage.get("route_universe_sha256") != sha256_path(args.current_route_universe):
        raise ValueError("Current S8 validation route-universe hash mismatch")
    if current_lineage.get("scenario_route_mapping_sha256") != sha256_path(args.current_scenario_mapping):
        raise ValueError("Current S8 validation scenario-mapping hash mismatch")
    if current_lineage.get("s8_events_sha256") != sha256_path(args.current_s8_events):
        raise ValueError("Current S8 validation event hash mismatch")
    if current_lineage.get("policy_grid_sha256") != sha256_path(args.current_policy_grid):
        raise ValueError("Current S8 validation policy-grid hash mismatch")

    if env.get("lineage", {}).get("output_sha256") != sha256_path(args.legacy_envelope):
        raise ValueError("Pinned S8 scenario envelope hash mismatch")
    if env.get("lineage", {}).get("transfer_gap_validation_sha256") != sha256_path(args.legacy_transfer_validation):
        raise ValueError("Pinned transfer validation hash mismatch")
    if env.get("lineage", {}).get("support_validation_sha256") != sha256_path(args.legacy_support_validation):
        raise ValueError("Pinned support validation hash mismatch")
    if gap.get("lineage", {}).get("output_sha256") != env.get("lineage", {}).get("transfer_gap_sha256"):
        raise ValueError("Pinned scenario envelope does not reference certified transfer-gap output")
    if weights.get("lineage", {}).get("summary_sha256") != sha256_path(args.legacy_work_direction_summary):
        raise ValueError("Pinned work-direction summary hash mismatch")
    if gap.get("lineage", {}).get("work_direction_summary_sha256") != sha256_path(args.legacy_work_direction_summary):
        raise ValueError("Transfer-gap envelope uses a different work-direction summary")

    if float(weights.get("demand_weight_sum", -1)) != 1882.0:
        raise ValueError("Unexpected pinned S8 worker-direction reference")
    if weights.get("S8_DIRECT_is_modal_share") is not False or weights.get("spatial_allocation_performed") is not False:
        raise ValueError("Pinned direction weighting violates epistemic contract")
    if weights.get("official_gtfs_sha256") != load_json(args.current_s8_contract).get("official_gtfs_sha256"):
        raise ValueError("Pinned/current official GTFS checksum differs")

    for obj in (env, gap, support):
        for field in ("passenger_utility_calculated", "full_gjt_calculated", "topology_ranked", "service_policy_selected"):
            if obj.get(field) is not False:
                raise ValueError(f"Pinned S8 evidence contains forbidden downstream selection {field}")
    if env.get("worker_reference_assigned_to_routes") is not False or env.get("route_weighting_applied") is not False:
        raise ValueError("Pinned S8 scenario envelope assigns/weights workers by route")
    if env.get("cross_route_phase_selected") is not False:
        raise ValueError("Pinned S8 scenario envelope already selected a cross-route phase")

    return pu, current, env, gap, weights


def load_passenger_rows(path: Path) -> tuple[list[dict[str, str]], set[tuple[str, int, str]]]:
    with gzip.open(path, "rt", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError("Passenger Utility frontier is empty")
    keys = {(str(r["scenario_id"]), int(r["uniform_headway_min"]), str(r["span_id"])) for r in rows}
    return rows, keys


def load_envelope_subset(path: Path, wanted: set[tuple[str, int, str]]) -> dict[tuple[str, int, str], dict[str, str]]:
    found: dict[tuple[str, int, str], dict[str, str]] = {}
    with gzip.open(path, "rt", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {
            "scenario_id", "uniform_headway_min", "span_id", "public_route_count",
            "public_complete_match_route_count", "public_complete_match_route_share",
            "public_all_routes_have_some_complete_match_phase", "public_any_route_has_some_complete_match_phase",
            "public_roundtrip_route_count", "public_roundtrip_complete_match_route_count",
            "public_roundtrip_complete_match_route_share", "public_roundtrip_best_complete_gap_min_min",
            "public_roundtrip_best_complete_gap_min_max", "public_roundtrip_worst_complete_gap_min_min",
            "public_roundtrip_worst_complete_gap_min_max", "public_rail_to_bus_only_route_count",
            "public_rail_to_bus_only_complete_match_route_count", "public_rail_to_bus_only_complete_match_route_share",
            "public_rail_to_bus_only_best_complete_gap_min_min", "public_rail_to_bus_only_best_complete_gap_min_max",
            "public_rail_to_bus_only_worst_complete_gap_min_min", "public_rail_to_bus_only_worst_complete_gap_min_max",
            "worker_direction_weight_reference", "demand_weight_semantics", "route_weighting_applied",
            "worker_reference_assigned_to_routes", "cross_route_phase_selected", "passenger_utility_calculated",
            "full_gjt_calculated", "topology_ranked", "service_policy_selected",
        }
        if not required <= set(reader.fieldnames or []):
            raise ValueError(f"Pinned S8 envelope schema missing {sorted(required-set(reader.fieldnames or []))}")
        for row in reader:
            key = (str(row["scenario_id"]), int(row["uniform_headway_min"]), str(row["span_id"]))
            if key not in wanted:
                continue
            if key in found:
                raise ValueError(f"Duplicate pinned S8 scenario/timing key {key}")
            if abs(float(row["worker_direction_weight_reference"]) - 1882.0) > 1e-9:
                raise ValueError("Pinned S8 row changed worker-direction reference")
            if row["demand_weight_semantics"] != "DIRECTION_WEIGHT_ONLY_NOT_ROUTE_DEMAND_NOT_MODAL_SHARE":
                raise ValueError("Pinned S8 row has unexpected demand semantics")
            for field in ("route_weighting_applied", "worker_reference_assigned_to_routes", "cross_route_phase_selected", "passenger_utility_calculated", "full_gjt_calculated", "topology_ranked", "service_policy_selected"):
                if strict_bool(row[field], field=field):
                    raise ValueError(f"Pinned S8 row violates {field}=false")
            found[key] = row
    missing = wanted - set(found)
    if missing:
        raise ValueError(f"Pinned S8 envelope missing {len(missing)} Stage-C scenario/timing keys")
    return found


def main() -> int:
    p = argparse.ArgumentParser()
    for name in (
        "passenger_frontier", "passenger_validation", "current_s8_validation", "current_route_universe",
        "current_scenario_mapping", "current_s8_events", "current_policy_grid", "current_s8_contract",
        "legacy_envelope", "legacy_envelope_validation", "legacy_transfer_validation", "legacy_support_validation",
        "legacy_work_direction_summary", "legacy_work_weights_validation", "output", "validation",
    ):
        p.add_argument("--" + name.replace("_", "-"), dest=name, type=Path, required=True)
    args = p.parse_args()
    pu, current, env, gap, weights = validate_lineage(args)
    rows, wanted = load_passenger_rows(args.passenger_frontier)
    evidence = load_envelope_subset(args.legacy_envelope, wanted)

    append_fields = [
        "s8_opportunity_class", "s8_public_complete_match_route_count", "s8_public_complete_match_route_share",
        "s8_public_all_routes_have_some_complete_match_phase", "s8_public_any_route_has_some_complete_match_phase",
        "s8_roundtrip_route_count", "s8_roundtrip_complete_match_route_count", "s8_roundtrip_complete_match_route_share",
        "s8_roundtrip_best_complete_gap_min_min", "s8_roundtrip_best_complete_gap_min_max",
        "s8_roundtrip_worst_complete_gap_min_min", "s8_roundtrip_worst_complete_gap_min_max",
        "s8_rail_to_bus_only_route_count", "s8_rail_to_bus_only_complete_match_route_count",
        "s8_rail_to_bus_only_complete_match_route_share", "s8_rail_to_bus_only_best_complete_gap_min_min",
        "s8_rail_to_bus_only_best_complete_gap_min_max", "s8_rail_to_bus_only_worst_complete_gap_min_min",
        "s8_rail_to_bus_only_worst_complete_gap_min_max", "s8_cross_route_phase_selected",
        "s8_exact_timetable_constructed", "s8_final_reliability_proven",
    ]
    fields = list(rows[0].keys()) + append_fields
    class_counts: dict[str, int] = {}
    budget_classes: dict[str, dict[str, int]] = {}
    raw, text, writer = deterministic_gzip_writer(args.output, fields)
    try:
        for row in rows:
            key = (str(row["scenario_id"]), int(row["uniform_headway_min"]), str(row["span_id"]))
            e = evidence[key]
            all_routes = strict_bool(e["public_all_routes_have_some_complete_match_phase"], field="public_all_routes_have_some_complete_match_phase")
            any_route = strict_bool(e["public_any_route_has_some_complete_match_phase"], field="public_any_route_has_some_complete_match_phase")
            if all_routes:
                klass = "ALL_PUBLIC_ROUTES_HAVE_SOME_COMPLETE_MATCH_PHASE"
            elif any_route:
                klass = "SOME_PUBLIC_ROUTES_HAVE_SOME_COMPLETE_MATCH_PHASE"
            else:
                klass = "NO_PUBLIC_ROUTE_HAS_COMPLETE_MATCH_PHASE"
            out = dict(row)
            out.update({
                "s8_opportunity_class": klass,
                "s8_public_complete_match_route_count": e["public_complete_match_route_count"],
                "s8_public_complete_match_route_share": e["public_complete_match_route_share"],
                "s8_public_all_routes_have_some_complete_match_phase": str(all_routes).lower(),
                "s8_public_any_route_has_some_complete_match_phase": str(any_route).lower(),
                "s8_roundtrip_route_count": e["public_roundtrip_route_count"],
                "s8_roundtrip_complete_match_route_count": e["public_roundtrip_complete_match_route_count"],
                "s8_roundtrip_complete_match_route_share": e["public_roundtrip_complete_match_route_share"],
                "s8_roundtrip_best_complete_gap_min_min": e["public_roundtrip_best_complete_gap_min_min"],
                "s8_roundtrip_best_complete_gap_min_max": e["public_roundtrip_best_complete_gap_min_max"],
                "s8_roundtrip_worst_complete_gap_min_min": e["public_roundtrip_worst_complete_gap_min_min"],
                "s8_roundtrip_worst_complete_gap_min_max": e["public_roundtrip_worst_complete_gap_min_max"],
                "s8_rail_to_bus_only_route_count": e["public_rail_to_bus_only_route_count"],
                "s8_rail_to_bus_only_complete_match_route_count": e["public_rail_to_bus_only_complete_match_route_count"],
                "s8_rail_to_bus_only_complete_match_route_share": e["public_rail_to_bus_only_complete_match_route_share"],
                "s8_rail_to_bus_only_best_complete_gap_min_min": e["public_rail_to_bus_only_best_complete_gap_min_min"],
                "s8_rail_to_bus_only_best_complete_gap_min_max": e["public_rail_to_bus_only_best_complete_gap_min_max"],
                "s8_rail_to_bus_only_worst_complete_gap_min_min": e["public_rail_to_bus_only_worst_complete_gap_min_min"],
                "s8_rail_to_bus_only_worst_complete_gap_min_max": e["public_rail_to_bus_only_worst_complete_gap_min_max"],
                "s8_cross_route_phase_selected": "false",
                "s8_exact_timetable_constructed": "false",
                "s8_final_reliability_proven": "false",
            })
            writer.writerow(out)
            class_counts[klass] = class_counts.get(klass, 0) + 1
            b = str(row["budget_suffix"])
            budget_classes.setdefault(b, {})[klass] = budget_classes.setdefault(b, {}).get(klass, 0) + 1
    finally:
        text.close()
        raw.close()

    validation = {
        "status": STATUS,
        "contract": CONTRACT,
        "pinned_source_commit": PINNED_SOURCE_COMMIT,
        "passenger_utility_plan_count": len(rows),
        "unique_stage_c_scenario_timing_key_count": len(wanted),
        "s8_opportunity_class_counts": dict(sorted(class_counts.items())),
        "budget_opportunity_class_counts": {k: dict(sorted(v.items())) for k, v in sorted(budget_classes.items())},
        "worker_direction_weight_reference": 1882.0,
        "outbound_direction_weight": weights["outbound_direction_demand"],
        "return_direction_weight": weights["return_direction_demand"],
        "worker_reference_assigned_to_routes": False,
        "route_weighting_applied": False,
        "cross_route_phase_selected": False,
        "exact_timetable_constructed": False,
        "joint_vehicle_block_timetable_feasibility_evaluated": False,
        "missed_connection_probability_calculated": False,
        "final_reliability_proven": False,
        "hard_s8_threshold_applied": False,
        "candidate_eliminated_by_s8_opportunity_class": False,
        "service_policy_selected": False,
        "decision_budget_selected": False,
        "primary_selected": False,
        "runner_up_selected": False,
        "historical_ranking_or_finalists_imported": False,
        "lineage_compatibility": {
            "current_s8_validation_sha256": sha256_path(args.current_s8_validation),
            "current_route_universe_sha256": sha256_path(args.current_route_universe),
            "current_scenario_mapping_sha256": sha256_path(args.current_scenario_mapping),
            "current_s8_events_sha256": sha256_path(args.current_s8_events),
            "current_policy_grid_sha256": sha256_path(args.current_policy_grid),
            "legacy_envelope_sha256": sha256_path(args.legacy_envelope),
            "legacy_envelope_validation_sha256": sha256_path(args.legacy_envelope_validation),
            "legacy_transfer_validation_sha256": sha256_path(args.legacy_transfer_validation),
            "legacy_support_validation_sha256": sha256_path(args.legacy_support_validation),
            "legacy_work_direction_summary_sha256": sha256_path(args.legacy_work_direction_summary),
            "legacy_work_weights_validation_sha256": sha256_path(args.legacy_work_weights_validation),
            "passenger_frontier_sha256": sha256_path(args.passenger_frontier),
            "output_sha256": sha256_path(args.output),
        },
        "upstream_statuses": {
            "passenger_utility": pu["status"],
            "current_s8": current["status"],
            "pinned_s8_scenario_envelope": env["status"],
            "pinned_transfer_gap": gap["status"],
        },
        "limitations": [
            "This is pre-timetable S8 phase-opportunity evidence, not final reliability or Passenger GJT.",
            "A route having some complete-match phase does not prove that one joint cross-route phase vector is feasible.",
            "No hard S8 transfer threshold is introduced because the Phase 2 specification does not declare one.",
            "The 1,882-worker reference weights Milano versus Lecco direction only and is never allocated to bus routes.",
            "Exact phase selection, explicit trips, vehicle blocks and delay/missed-connection robustness remain Stage D/F tasks.",
        ],
    }
    args.validation.parent.mkdir(parents=True, exist_ok=True)
    args.validation.write_text(json.dumps(validation, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(validation, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
