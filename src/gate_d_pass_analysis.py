"""Gate E analysis of the exact Gate D PASS artifact.

This module never chooses a service plan. It validates Gate D structural metrics,
builds only directionally complete CW/CCW route families, and derives budget and
fleet/headway envelopes. Candidate topology remains a design ASSUMPTION even
when its OSM route kilometres are deterministically DERIVED inside Gate D.
"""
from __future__ import annotations

import csv
import hashlib
import io
import math
from pathlib import Path
import zipfile
from typing import Iterable, Mapping, Sequence

from src.service_math import ServiceMathError, combined_headway_rate_equivalent

EXPECTED_DISTANCE_STATUS = "DERIVED_OSM_STRUCTURAL"
EXPECTED_RUNNING_STATUS = "MODEL_OUTPUT"
EXPECTED_CANDIDATE_STATUS = "HYPOTHESIS_NOT_RECOMMENDATION"
EXPECTED_TURN_STATUS = "ENFORCED_OSM"
DIRECTIONS = {"CW", "CCW"}
WAYPOINT_STATUSES = {"FACT", "RECONSTRUCTED", "ASSUMPTION"}

METRIC_REQUIRED = {
    "candidate_id", "family", "direction", "route_km", "pure_running_minutes",
    "uncertain_road_km", "assumed_speed_share", "temporary_brivio_closure_used",
    "distance_status", "running_time_status", "turn_restrictions_status",
    "candidate_status", "epistemic_status",
}
WAYPOINT_REQUIRED = {
    "candidate_id", "family", "direction", "sequence", "anchor_id",
    "epistemic_status", "source_type", "source_detail",
}


def _read_csv_text(text: str, required: set[str], label: str) -> list[dict[str, str]]:
    reader = csv.DictReader(io.StringIO(text))
    missing = required - set(reader.fieldnames or [])
    if missing:
        raise ServiceMathError(f"{label} missing columns: {sorted(missing)}")
    rows = [{k: (v or "").strip() for k, v in row.items()} for row in reader]
    if not rows:
        raise ServiceMathError(f"{label} contains no rows")
    return rows


def _sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_pass_snapshot(
    metrics_path: str | Path,
    waypoints_path: str | Path,
    expected_metrics_sha256: str,
    expected_waypoints_sha256: str,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    metrics_path, waypoints_path = Path(metrics_path), Path(waypoints_path)
    got_metrics, got_waypoints = _sha256_file(metrics_path), _sha256_file(waypoints_path)
    exp_metrics = expected_metrics_sha256.strip().lower().removeprefix("sha256:")
    exp_waypoints = expected_waypoints_sha256.strip().lower().removeprefix("sha256:")
    if got_metrics != exp_metrics:
        raise ServiceMathError(f"Gate D metrics snapshot SHA256 mismatch: got {got_metrics}, expected {exp_metrics}")
    if got_waypoints != exp_waypoints:
        raise ServiceMathError(f"Gate D waypoints snapshot SHA256 mismatch: got {got_waypoints}, expected {exp_waypoints}")
    metrics = _read_csv_text(metrics_path.read_text(encoding="utf-8-sig"), METRIC_REQUIRED, "Gate D metrics")
    waypoints = _read_csv_text(waypoints_path.read_text(encoding="utf-8-sig"), WAYPOINT_REQUIRED, "Gate D waypoints")
    return metrics, waypoints


LOOP_EVIDENCE_REQUIRED = {
    "candidate_id", "family", "direction", "first_anchor", "last_anchor",
    "waypoint_count", "assumption_waypoint_count", "source_waypoints_sha256", "epistemic_status",
}


def load_compact_pass_snapshot(
    metrics_path: str | Path,
    loop_evidence_path: str | Path,
    expected_metrics_sha256: str,
    expected_loop_evidence_sha256: str,
    expected_source_waypoints_sha256: str,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    metrics_path, loop_evidence_path = Path(metrics_path), Path(loop_evidence_path)
    got_metrics, got_loops = _sha256_file(metrics_path), _sha256_file(loop_evidence_path)
    exp_metrics = expected_metrics_sha256.strip().lower().removeprefix("sha256:")
    exp_loops = expected_loop_evidence_sha256.strip().lower().removeprefix("sha256:")
    exp_source = expected_source_waypoints_sha256.strip().lower().removeprefix("sha256:")
    if got_metrics != exp_metrics:
        raise ServiceMathError(f"Gate D metrics snapshot SHA256 mismatch: got {got_metrics}, expected {exp_metrics}")
    if got_loops != exp_loops:
        raise ServiceMathError(f"Gate D loop evidence SHA256 mismatch: got {got_loops}, expected {exp_loops}")
    metrics = _read_csv_text(metrics_path.read_text(encoding="utf-8-sig"), METRIC_REQUIRED, "Gate D metrics")
    loops = _read_csv_text(loop_evidence_path.read_text(encoding="utf-8-sig"), LOOP_EVIDENCE_REQUIRED, "Gate D loop evidence")
    metric_ids = {r["candidate_id"] for r in metrics}
    loop_ids = {r["candidate_id"] for r in loops}
    if metric_ids != loop_ids:
        raise ServiceMathError("Gate D compact snapshot candidate IDs do not match metrics")
    waypoints: list[dict[str, str]] = []
    for row in loops:
        if row["source_waypoints_sha256"].lower() != exp_source:
            raise ServiceMathError(f"{row['candidate_id']}: loop evidence is not linked to expected Gate D waypoint SHA")
        if row["epistemic_status"].upper() != "DERIVED":
            raise ServiceMathError(f"{row['candidate_id']}: loop evidence must be DERIVED")
        try:
            count = int(row["waypoint_count"])
            assumptions = int(row["assumption_waypoint_count"])
        except ValueError as exc:
            raise ServiceMathError(f"{row['candidate_id']}: invalid loop evidence counts") from exc
        if count < 2 or assumptions < 0 or assumptions > count:
            raise ServiceMathError(f"{row['candidate_id']}: invalid loop evidence counts")
        status = "ASSUMPTION" if assumptions else "FACT"
        base = {
            "candidate_id": row["candidate_id"], "family": row["family"], "direction": row["direction"],
            "epistemic_status": status, "source_type": "DERIVED_GATE_D_LOOP_EVIDENCE",
            "source_detail": f"waypoint_count={count};assumption_waypoint_count={assumptions}",
        }
        waypoints.append({**base, "sequence": "1", "anchor_id": row["first_anchor"]})
        waypoints.append({**base, "sequence": "2", "anchor_id": row["last_anchor"]})
    return metrics, waypoints


def load_pass_artifact_zip(path: str | Path, expected_sha256: str) -> tuple[list[dict[str, str]], list[dict[str, str]], str]:
    path = Path(path)
    payload = path.read_bytes()
    digest = hashlib.sha256(payload).hexdigest()
    expected = expected_sha256.strip().lower().removeprefix("sha256:")
    if not expected or digest != expected:
        raise ServiceMathError(f"Gate D artifact SHA256 mismatch: got {digest}, expected {expected or '<missing>'}")
    try:
        with zipfile.ZipFile(io.BytesIO(payload)) as zf:
            names = set(zf.namelist())
            metric_name = next((n for n in names if n.endswith("structural_candidate_metrics.csv")), None)
            waypoint_name = next((n for n in names if n.endswith("structural_candidate_waypoints.csv")), None)
            if not metric_name or not waypoint_name:
                raise ServiceMathError("Gate D artifact missing structural candidate CSVs")
            metrics = _read_csv_text(zf.read(metric_name).decode("utf-8-sig"), METRIC_REQUIRED, "Gate D metrics")
            waypoints = _read_csv_text(zf.read(waypoint_name).decode("utf-8-sig"), WAYPOINT_REQUIRED, "Gate D waypoints")
    except zipfile.BadZipFile as exc:
        raise ServiceMathError("Gate D artifact is not a valid ZIP") from exc
    return metrics, waypoints, digest


def _bool_false(value: str, field: str) -> None:
    if value.strip().lower() not in {"false", "0", "no"}:
        raise ServiceMathError(f"{field} must be false for structural Gate E analysis")


def validate_gate_d_rows(metrics: Sequence[Mapping[str, str]], waypoints: Sequence[Mapping[str, str]]) -> None:
    wp_by_candidate: dict[str, list[Mapping[str, str]]] = {}
    for w in waypoints:
        cid = w["candidate_id"].strip()
        if not cid:
            raise ServiceMathError("Gate D waypoint candidate_id is required")
        if w["epistemic_status"].strip().upper() not in WAYPOINT_STATUSES:
            raise ServiceMathError(f"{cid}: invalid waypoint epistemic status {w['epistemic_status']!r}")
        try:
            int(w["sequence"])
        except ValueError as exc:
            raise ServiceMathError(f"{cid}: waypoint sequence must be integer") from exc
        wp_by_candidate.setdefault(cid, []).append(w)

    seen: set[str] = set()
    for row in metrics:
        cid = row["candidate_id"].strip()
        if not cid or cid in seen:
            raise ServiceMathError(f"duplicate or empty candidate_id {cid!r}")
        seen.add(cid)
        if row["distance_status"].strip().upper() != EXPECTED_DISTANCE_STATUS:
            raise ServiceMathError(f"{cid}: unexpected distance status")
        if row["running_time_status"].strip().upper() != EXPECTED_RUNNING_STATUS:
            raise ServiceMathError(f"{cid}: unexpected running time status")
        if row["candidate_status"].strip().upper() != EXPECTED_CANDIDATE_STATUS:
            raise ServiceMathError(f"{cid}: candidate is not explicitly a non-recommendation hypothesis")
        if row["turn_restrictions_status"].strip().upper() != EXPECTED_TURN_STATUS:
            raise ServiceMathError(f"{cid}: turn restrictions are not in enforced structural state")
        _bool_false(row["temporary_brivio_closure_used"], f"{cid}.temporary_brivio_closure_used")
        try:
            km = float(row["route_km"])
            run = float(row["pure_running_minutes"])
            uncertain = float(row["uncertain_road_km"])
            assumed_share = float(row["assumed_speed_share"])
        except ValueError as exc:
            raise ServiceMathError(f"{cid}: nonnumeric Gate D metric") from exc
        if not all(math.isfinite(x) for x in (km, run, uncertain, assumed_share)) or km <= 0 or run <= 0:
            raise ServiceMathError(f"{cid}: invalid distance/runtime")
        if uncertain < 0 or uncertain > km + 1e-9:
            raise ServiceMathError(f"{cid}: uncertain_road_km outside [0, route_km]")
        if not 0 <= assumed_share <= 1:
            raise ServiceMathError(f"{cid}: assumed_speed_share outside [0,1]")
        if cid not in wp_by_candidate:
            raise ServiceMathError(f"{cid}: no waypoint evidence in Gate D artifact")


def _ordered_waypoints(rows: Iterable[Mapping[str, str]]) -> list[Mapping[str, str]]:
    return sorted(rows, key=lambda r: int(r["sequence"]))


def _closed_loop_hub(candidate_id: str, waypoints: Sequence[Mapping[str, str]]) -> str:
    rows = _ordered_waypoints(w for w in waypoints if w["candidate_id"] == candidate_id)
    if len(rows) < 2:
        raise ServiceMathError(f"{candidate_id}: insufficient waypoint evidence for loop")
    first, last = rows[0]["anchor_id"], rows[-1]["anchor_id"]
    if not first or first != last:
        raise ServiceMathError(f"{candidate_id}: CW/CCW service candidate is not a closed loop")
    return first


def build_directional_pairs(metrics: Sequence[Mapping[str, str]], waypoints: Sequence[Mapping[str, str]]) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    validate_gate_d_rows(metrics, waypoints)
    by_family: dict[str, list[Mapping[str, str]]] = {}
    for row in metrics:
        by_family.setdefault(row["family"], []).append(row)
    pairs: list[dict[str, object]] = []
    unpaired: list[dict[str, object]] = []
    for family, rows in sorted(by_family.items()):
        directional = [r for r in rows if r["direction"].upper() in DIRECTIONS]
        by_dir = {r["direction"].upper(): r for r in directional}
        if len(directional) == 2 and set(by_dir) == DIRECTIONS:
            cw, ccw = by_dir["CW"], by_dir["CCW"]
            hub_cw = _closed_loop_hub(cw["candidate_id"], waypoints)
            hub_ccw = _closed_loop_hub(ccw["candidate_id"], waypoints)
            if hub_cw != hub_ccw:
                raise ServiceMathError(f"{family}: CW/CCW loops do not share a hub")
            pairs.append({
                "route_id": family,
                "route_type": "GATE_D_DIRECTIONAL_PAIR",
                "component_families": family,
                "common_hub_anchor": hub_cw,
                "route_definition_status": "ASSUMPTION",
                "route_definition_basis": "GATE_D_HYPOTHESIS_NOT_RECOMMENDATION",
                "cw_candidate_id": cw["candidate_id"],
                "ccw_candidate_id": ccw["candidate_id"],
                "route_km_CW": float(cw["route_km"]),
                "route_km_CCW": float(ccw["route_km"]),
                "pure_running_min_CW": float(cw["pure_running_minutes"]),
                "pure_running_min_CCW": float(ccw["pure_running_minutes"]),
                "uncertain_road_km_CW": float(cw["uncertain_road_km"]),
                "uncertain_road_km_CCW": float(ccw["uncertain_road_km"]),
                "route_km_status": "DERIVED",
                "running_time_status": EXPECTED_RUNNING_STATUS,
                "service_math_status": "SENSITIVITY_ONLY_ROUTE_DEFINITION_IS_ASSUMPTION",
            })
        else:
            for r in rows:
                unpaired.append({
                    "candidate_id": r["candidate_id"], "family": family, "direction": r["direction"],
                    "route_km": float(r["route_km"]), "pure_running_min": float(r["pure_running_minutes"]),
                    "gate_e_pairing_status": "UNPAIRED_NOT_ELIGIBLE_FOR_FULL_BIDIRECTIONAL_SERVICE_MATH",
                    "candidate_status": r["candidate_status"],
                })
    return pairs, unpaired


def add_composite(pairs: Sequence[Mapping[str, object]], composite_id: str, component_families: Sequence[str]) -> dict[str, object]:
    components = [x.strip() for x in component_families if x.strip()]
    if len(components) < 2:
        raise ServiceMathError("a composite requires at least two directional-pair families")
    by_id = {str(p["route_id"]): p for p in pairs}
    missing = [x for x in components if x not in by_id]
    if missing:
        raise ServiceMathError(f"composite references missing directional pairs: {missing}")
    selected = [by_id[x] for x in components]
    hubs = {str(p["common_hub_anchor"]) for p in selected}
    if len(hubs) != 1:
        raise ServiceMathError("composite component loops do not share a common hub")
    return {
        "route_id": composite_id,
        "route_type": "COMPOSITE_HYPOTHESIS",
        "component_families": ";".join(components),
        "common_hub_anchor": next(iter(hubs)),
        "route_definition_status": "ASSUMPTION",
        "route_definition_basis": "COMPOSITION_OF_GATE_D_DIRECTIONAL_HYPOTHESES_AT_COMMON_HUB",
        "cw_candidate_id": "+".join(str(p["cw_candidate_id"]) for p in selected),
        "ccw_candidate_id": "+".join(str(p["ccw_candidate_id"]) for p in selected),
        "route_km_CW": sum(float(p["route_km_CW"]) for p in selected),
        "route_km_CCW": sum(float(p["route_km_CCW"]) for p in selected),
        "pure_running_min_CW": sum(float(p["pure_running_min_CW"]) for p in selected),
        "pure_running_min_CCW": sum(float(p["pure_running_min_CCW"]) for p in selected),
        "uncertain_road_km_CW": sum(float(p["uncertain_road_km_CW"]) for p in selected),
        "uncertain_road_km_CCW": sum(float(p["uncertain_road_km_CCW"]) for p in selected),
        "route_km_status": "DERIVED",
        "running_time_status": EXPECTED_RUNNING_STATUS,
        "service_math_status": "SENSITIVITY_ONLY_COMPOSITE_IS_ASSUMPTION",
    }


def budget_envelope(route_rows: Sequence[Mapping[str, object]], budget_km: float, lineage: Mapping[str, str]) -> list[dict[str, object]]:
    if not math.isfinite(float(budget_km)) or float(budget_km) <= 0:
        raise ServiceMathError("budget_km must be finite and > 0")
    out: list[dict[str, object]] = []
    for row in route_rows:
        cw_km, ccw_km = float(row["route_km_CW"]), float(row["route_km_CCW"])
        cw_run, ccw_run = float(row["pure_running_min_CW"]), float(row["pure_running_min_CCW"])
        paired_km = cw_km + ccw_km
        paired_run = cw_run + ccw_run
        max_pairs = math.floor(float(budget_km) / paired_km + 1e-12)
        annual = max_pairs * paired_km
        next_annual = (max_pairs + 1) * paired_km
        out.append({
            **lineage,
            **dict(row),
            "paired_directional_cycle_km": paired_km,
            "paired_pure_running_min": paired_run,
            "budget_bus_km_year": float(budget_km),
            "budget_status": "DERIVED_FROM_PDB_RECONSTRUCTED_LINE_TOTALS",
            "max_equal_CW_CCW_cycles_year_under_budget": max_pairs,
            "annual_bus_km_at_max_equal_pairs": annual,
            "budget_margin_km_at_max_equal_pairs": float(budget_km) - annual,
            "annual_pure_running_vehicle_hours_at_max_equal_pairs": max_pairs * paired_run / 60.0,
            "next_equal_pair_annual_bus_km": next_annual,
            "next_equal_pair_delta_km_vs_budget": next_annual - float(budget_km),
            "annual_bus_km_formula": "route_km_CW*cycles_CW_year + route_km_CCW*cycles_CCW_year",
            "equal_pair_envelope_semantics": "INTEGER_MAX_FOR_EQUAL_CW_CCW_FULL_LOOPS_NOT_A_SERVICE_PLAN",
        })
    return out


def fleet_headway_envelope(route_rows: Sequence[Mapping[str, object]], headways: Sequence[float], vehicles_each_direction: Sequence[int], lineage: Mapping[str, str]) -> list[dict[str, object]]:
    out: list[dict[str, object]] = []
    for h in headways:
        h = float(h)
        if not math.isfinite(h) or h <= 0:
            raise ServiceMathError("headway must be finite and > 0")
        for n in vehicles_each_direction:
            if int(n) != n or int(n) <= 0:
                raise ServiceMathError("vehicle count must be positive integer")
            n = int(n)
            for row in route_rows:
                combined = combined_headway_rate_equivalent(h, h)
                for direction in ("CW", "CCW"):
                    running = float(row[f"pure_running_min_{direction}"])
                    allowance = n * h - running
                    out.append({
                        **lineage,
                        "route_id": row["route_id"], "route_type": row["route_type"], "direction": direction,
                        "route_definition_status": row["route_definition_status"],
                        "pure_running_min": running, "running_time_status": row["running_time_status"],
                        "target_headway_min": h, "target_headway_status": "ASSUMPTION",
                        "in_service_vehicles_direction": n, "vehicle_count_status": "ASSUMPTION",
                        "maximum_dwell_plus_recovery_min_compatible": allowance,
                        "headway_possible_with_zero_nonrunning": allowance >= -1e-9,
                        "combined_rate_equivalent_at_common_stops_if_symmetric_min": combined,
                        "combined_semantics": "RATE_EQUIVALENT_NOT_MAX_PASSENGER_GAP_REQUIRES_PHASED_TIMETABLE",
                        "result_status": "SENSITIVITY_ONLY_NOT_A_SERVICE_PLAN",
                    })
    return out
