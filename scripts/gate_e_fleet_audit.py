#!/usr/bin/env python3
"""Compute scheduled in-service fleet from actual Gate C hub departures + Gate E cycle times."""
from __future__ import annotations

import argparse
import csv
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.fleet_audit import minimum_fleet_from_intervals  # noqa: E402
from src.headway_audit import headway_evidence_status  # noqa: E402
from src.service_math import ServiceMathError, parse_gtfs_time_to_minutes, read_service_band_plans  # noqa: E402

DEP_REQUIRED = (
    "scenario_id", "service_day_group", "band_id", "stop_id", "direction",
    "departure_time", "analysis_mode", "epistemic_status", "upstream_gate_c_status",
    "gate_c_artifact", "gate_c_commit", "shared_stop_pattern_status",
)


def read_departures(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        missing = set(DEP_REQUIRED) - set(reader.fieldnames or [])
        if missing:
            raise ServiceMathError(f"departure handoff missing columns: {sorted(missing)}")
        rows = [{k: row[k].strip() for k in DEP_REQUIRED} for row in reader]
    if not rows:
        raise ServiceMathError("departure handoff contains no rows")
    return rows


def audit(plans, departures, hub_stop_id: str) -> list[dict[str, object]]:
    plan_map = {
        (p.scenario_id, p.service_day_group, p.band_id, p.direction.upper()): p for p in plans
    }
    if len(plan_map) != len(plans):
        raise ServiceMathError("duplicate Gate E plan key")
    hub = [r for r in departures if r["stop_id"] == hub_stop_id]
    if not hub:
        raise ServiceMathError(f"no departures found at hub_stop_id={hub_stop_id}")
    dep_map: dict[tuple[str, str, str, str], list[dict[str, str]]] = {}
    for row in hub:
        key = (row["scenario_id"], row["service_day_group"], row["band_id"], row["direction"].upper())
        dep_map.setdefault(key, []).append(row)
    if set(dep_map) != set(plan_map):
        only_plan = sorted(set(plan_map) - set(dep_map)); only_dep = sorted(set(dep_map) - set(plan_map))
        raise ServiceMathError(f"plan/departure keys differ; only_plan={only_plan[:5]} only_departures={only_dep[:5]}")

    grouped: dict[tuple[str, str], dict[str, list[tuple[float, float]]]] = {}
    statuses: dict[tuple[str, str], list[str]] = {}
    discrepancies: dict[tuple[str, str], list[str]] = {}
    for key, plan in plan_map.items():
        rows = dep_map[key]
        if len(rows) != plan.daily_cycles:
            discrepancies.setdefault((plan.scenario_id, plan.service_day_group), []).append(
                f"{plan.band_id}:{plan.direction} events={len(rows)} daily_cycles={plan.daily_cycles}"
            )
        evidence = headway_evidence_status(
            rows[0]["upstream_gate_c_status"], [r["epistemic_status"] for r in rows], rows[0]["analysis_mode"],
            rows[0]["gate_c_artifact"], rows[0]["gate_c_commit"],
        )
        if any(r["upstream_gate_c_status"] != rows[0]["upstream_gate_c_status"] or r["gate_c_commit"] != rows[0]["gate_c_commit"] for r in rows):
            raise ServiceMathError(f"{key}: inconsistent departure lineage")
        scenario_key = (plan.scenario_id, plan.service_day_group)
        statuses.setdefault(scenario_key, []).append(evidence)
        intervals = grouped.setdefault(scenario_key, {"CW": [], "CCW": []})[plan.direction.upper()]
        for row in rows:
            start = parse_gtfs_time_to_minutes(row["departure_time"])
            intervals.append((start, start + plan.cycle_min))

    if any(discrepancies.values()):
        detail = "; ".join(item for values in discrepancies.values() for item in values)
        raise ServiceMathError(f"hub departure count does not match daily_cycles: {detail}")

    out = []
    for (scenario, day_group), directions in sorted(grouped.items()):
        cw = minimum_fleet_from_intervals(directions["CW"])
        ccw = minimum_fleet_from_intervals(directions["CCW"])
        interlined = minimum_fleet_from_intervals(directions["CW"] + directions["CCW"])
        scenario_plans = [p for p in plans if p.scenario_id == scenario and p.service_day_group == day_group]
        has_assumption = any(p.assumption_fields for p in scenario_plans)
        c_eligible = all(s == "ELIGIBLE_FOR_GATE_E_HEADWAY_EVIDENCE" for s in statuses[(scenario, day_group)])
        d_pass = all(p.upstream_gate_d_status.upper() == "PASS" for p in scenario_plans)
        if has_assumption:
            evidence_status = "SENSITIVITY_ONLY_NOT_GATE_E_FLEET_EVIDENCE"
        elif not c_eligible or not d_pass:
            blockers = []
            if not c_eligible: blockers.append("GATE_C")
            if not d_pass: blockers.append("GATE_D")
            evidence_status = "PROVISIONAL/BLOCKED_BY_" + "_AND_".join(blockers)
        else:
            evidence_status = "ELIGIBLE_FOR_GATE_E_SCHEDULED_FLEET_EVIDENCE"
        out.append({
            "scenario_id": scenario, "service_day_group": day_group,
            "fleet_evidence_status": evidence_status,
            "hub_stop_id": hub_stop_id,
            "minimum_scheduled_vehicles_CW_direction_locked": cw,
            "minimum_scheduled_vehicles_CCW_direction_locked": ccw,
            "minimum_scheduled_vehicles_direction_locked_total": cw + ccw,
            "minimum_scheduled_vehicles_hub_interlining_allowed": interlined,
            "potential_interlining_saving_vs_direction_locked": cw + ccw - interlined,
            "fleet_scope": "THEORETICAL_IN_SERVICE_FROM_ACTUAL_HUB_DEPARTURES_AND_VALIDATED_CYCLE_TIMES",
            "excluded_from_fleet_scope": "DEPOT_DEADHEAD;DRIVER_RELIEFS;MAINTENANCE;SPARES",
        })
    return out


def write(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--gate-e-input", type=Path, required=True)
    p.add_argument("--departures", type=Path, required=True)
    p.add_argument("--hub-stop-id", required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    try:
        rows = audit(read_service_band_plans(args.gate_e_input), read_departures(args.departures), args.hub_stop_id)
        write(args.output, rows)
        print(f"Scheduled fleet audit rows: {len(rows)}")
        return 0
    except (OSError, ServiceMathError, ValueError) as exc:
        print(f"GATE_E_FLEET_FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
