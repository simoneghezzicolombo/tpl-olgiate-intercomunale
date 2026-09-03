"""Deterministic service-math primitives for Gate E.

No route, timetable, population or demand data are created here. All scenario
inputs must come from an upstream source and carry an epistemic status.
"""
from __future__ import annotations

from dataclasses import dataclass
import csv
import math
from pathlib import Path
from typing import Iterable, Mapping

ALLOWED_STATUSES = {
    "FACT",
    "DERIVED",
    "ESTIMATE",
    "ASSUMPTION",
    "RECONSTRUCTED",
    "MODEL OUTPUT",
}
FORBIDDEN_STATUSES = {"PLACEHOLDER", "INVALIDATED"}
DIRECTIONS = {"CW", "CCW"}


class ServiceMathError(ValueError):
    """Raised when Gate E inputs are mathematically or epistemically invalid."""


def _positive(name: str, value: float) -> float:
    value = float(value)
    if not math.isfinite(value) or value <= 0:
        raise ServiceMathError(f"{name} must be finite and > 0, got {value!r}")
    return value


def _non_negative(name: str, value: float) -> float:
    value = float(value)
    if not math.isfinite(value) or value < 0:
        raise ServiceMathError(f"{name} must be finite and >= 0, got {value!r}")
    return value


def cycle_minutes(pure_running_min: float, dwell_min: float, recovery_min: float) -> float:
    """Return full cycle time, keeping running, dwell and recovery explicit."""
    running = _positive("pure_running_min", pure_running_min)
    dwell = _non_negative("dwell_min", dwell_min)
    recovery = _non_negative("recovery_min", recovery_min)
    return running + dwell + recovery


def vehicles_required(cycle_min: float, target_headway_min: float) -> int:
    """Minimum vehicles needed to sustain a target headway on one direction."""
    cycle = _positive("cycle_min", cycle_min)
    headway = _positive("target_headway_min", target_headway_min)
    return max(1, math.ceil((cycle / headway) - 1e-12))


def combined_headway_rate_equivalent(headway_cw_min: float, headway_ccw_min: float) -> float:
    """Rate-equivalent combined headway for two independently served directions.

    This is 1 / (1/h_CW + 1/h_CCW). It is an average service-rate equivalent,
    not a guarantee of the maximum gap at a specific stop; exact stop-level gaps
    require phased departure times from Gate C/E timetable work.
    """
    cw = _positive("headway_cw_min", headway_cw_min)
    ccw = _positive("headway_ccw_min", headway_ccw_min)
    return 1.0 / ((1.0 / cw) + (1.0 / ccw))


def annual_bus_km(route_km: float, full_cycles_per_day: int, service_days_year: int) -> float:
    km = _positive("route_km", route_km)
    if int(full_cycles_per_day) != full_cycles_per_day or full_cycles_per_day <= 0:
        raise ServiceMathError("full_cycles_per_day must be a positive integer")
    if int(service_days_year) != service_days_year or service_days_year <= 0:
        raise ServiceMathError("service_days_year must be a positive integer")
    return km * int(full_cycles_per_day) * int(service_days_year)


def annual_scheduled_vehicle_hours(cycle_min: float, full_cycles_per_day: int, service_days_year: int) -> float:
    cycle = _positive("cycle_min", cycle_min)
    if int(full_cycles_per_day) != full_cycles_per_day or full_cycles_per_day <= 0:
        raise ServiceMathError("full_cycles_per_day must be a positive integer")
    if int(service_days_year) != service_days_year or service_days_year <= 0:
        raise ServiceMathError("service_days_year must be a positive integer")
    return cycle * int(full_cycles_per_day) * int(service_days_year) / 60.0


def validate_epistemic_status(status: str, analysis_mode: str) -> None:
    status = status.strip().upper()
    mode = analysis_mode.strip().upper()
    if status in FORBIDDEN_STATUSES:
        raise ServiceMathError(f"{status} inputs cannot feed Gate E production outputs")
    if status not in ALLOWED_STATUSES:
        raise ServiceMathError(f"Unknown epistemic status: {status!r}")
    if status == "ASSUMPTION" and mode != "SENSITIVITY":
        raise ServiceMathError("ASSUMPTION inputs are allowed only in SENSITIVITY analysis")


@dataclass(frozen=True)
class DirectionPlan:
    scenario_id: str
    direction: str
    epistemic_status: str
    analysis_mode: str
    upstream_gate_c_status: str
    upstream_gate_d_status: str
    route_km: float
    pure_running_min: float
    dwell_min: float
    recovery_min: float
    target_headway_min: float
    daily_cycles: int
    service_days_year: int

    def validate(self) -> None:
        if not self.scenario_id.strip():
            raise ServiceMathError("scenario_id is required")
        if self.direction.strip().upper() not in DIRECTIONS:
            raise ServiceMathError(f"direction must be CW or CCW, got {self.direction!r}")
        validate_epistemic_status(self.epistemic_status, self.analysis_mode)
        _positive("route_km", self.route_km)
        cycle_minutes(self.pure_running_min, self.dwell_min, self.recovery_min)
        _positive("target_headway_min", self.target_headway_min)
        annual_bus_km(self.route_km, self.daily_cycles, self.service_days_year)

    @property
    def cycle_min(self) -> float:
        return cycle_minutes(self.pure_running_min, self.dwell_min, self.recovery_min)

    def metrics(self) -> dict[str, object]:
        self.validate()
        return {
            "scenario_id": self.scenario_id,
            "direction": self.direction.upper(),
            "epistemic_status": self.epistemic_status.upper(),
            "analysis_mode": self.analysis_mode.upper(),
            "upstream_gate_c_status": self.upstream_gate_c_status.upper(),
            "upstream_gate_d_status": self.upstream_gate_d_status.upper(),
            "route_km": self.route_km,
            "pure_running_min": self.pure_running_min,
            "dwell_min": self.dwell_min,
            "recovery_min": self.recovery_min,
            "cycle_min": self.cycle_min,
            "target_headway_min": self.target_headway_min,
            "vehicles_required": vehicles_required(self.cycle_min, self.target_headway_min),
            "daily_cycles": self.daily_cycles,
            "service_days_year": self.service_days_year,
            "annual_bus_km": annual_bus_km(self.route_km, self.daily_cycles, self.service_days_year),
            "annual_scheduled_vehicle_hours": annual_scheduled_vehicle_hours(
                self.cycle_min, self.daily_cycles, self.service_days_year
            ),
        }


def _int_field(row: Mapping[str, str], key: str) -> int:
    raw = row[key].strip()
    try:
        value = int(raw)
    except ValueError as exc:
        raise ServiceMathError(f"{key} must be an integer, got {raw!r}") from exc
    return value


def read_direction_plans(path: str | Path) -> list[DirectionPlan]:
    required = {
        "scenario_id",
        "direction",
        "epistemic_status",
        "analysis_mode",
        "upstream_gate_c_status",
        "upstream_gate_d_status",
        "route_km",
        "pure_running_min",
        "dwell_min",
        "recovery_min",
        "target_headway_min",
        "daily_cycles",
        "service_days_year",
    }
    with Path(path).open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ServiceMathError(f"Missing Gate E input columns: {sorted(missing)}")
        plans = []
        for row in reader:
            plan = DirectionPlan(
                scenario_id=row["scenario_id"].strip(),
                direction=row["direction"].strip(),
                epistemic_status=row["epistemic_status"].strip(),
                analysis_mode=row["analysis_mode"].strip(),
                upstream_gate_c_status=row["upstream_gate_c_status"].strip(),
                upstream_gate_d_status=row["upstream_gate_d_status"].strip(),
                route_km=float(row["route_km"]),
                pure_running_min=float(row["pure_running_min"]),
                dwell_min=float(row["dwell_min"]),
                recovery_min=float(row["recovery_min"]),
                target_headway_min=float(row["target_headway_min"]),
                daily_cycles=_int_field(row, "daily_cycles"),
                service_days_year=_int_field(row, "service_days_year"),
            )
            plan.validate()
            plans.append(plan)
    if not plans:
        raise ServiceMathError("Gate E input contains no rows")
    return plans


def load_pdb_budget(path: str | Path) -> dict[str, float]:
    """Load D184/D185 annual bus-km benchmark and verify internal arithmetic."""
    with Path(path).open(newline="", encoding="utf-8-sig") as f:
        rows = {row["linea"].strip(): row for row in csv.DictReader(f)}
    for line in ("D184", "D185", "D184+D185"):
        if line not in rows:
            raise ServiceMathError(f"Missing {line} in PdB resource table")
    d184 = float(rows["D184"]["km_totali_anno"])
    d185 = float(rows["D185"]["km_totali_anno"])
    total = float(rows["D184+D185"]["km_totali_anno"])
    if not math.isclose(d184 + d185, total, rel_tol=0.0, abs_tol=1e-9):
        raise ServiceMathError(f"PdB benchmark inconsistent: {d184} + {d185} != {total}")
    return {"D184": d184, "D185": d185, "D184+D185": total}


def aggregate_scenarios(plans: Iterable[DirectionPlan], budget_total_km: float) -> list[dict[str, object]]:
    grouped: dict[str, list[DirectionPlan]] = {}
    for plan in plans:
        grouped.setdefault(plan.scenario_id, []).append(plan)

    output: list[dict[str, object]] = []
    budget = _positive("budget_total_km", budget_total_km)
    for scenario_id, scenario_plans in sorted(grouped.items()):
        by_dir = {p.direction.upper(): p for p in scenario_plans}
        if set(by_dir) != DIRECTIONS or len(scenario_plans) != 2:
            raise ServiceMathError(
                f"{scenario_id}: Gate E bidirectional scenario requires exactly one CW and one CCW row"
            )
        cw = by_dir["CW"].metrics()
        ccw = by_dir["CCW"].metrics()
        if cw["service_days_year"] != ccw["service_days_year"]:
            raise ServiceMathError(f"{scenario_id}: CW/CCW service_days_year differ")

        annual_km = float(cw["annual_bus_km"]) + float(ccw["annual_bus_km"])
        vehicle_hours = float(cw["annual_scheduled_vehicle_hours"]) + float(
            ccw["annual_scheduled_vehicle_hours"]
        )
        delta = annual_km - budget
        blockers = []
        if not all(p.upstream_gate_c_status.strip().upper() == "PASS" for p in scenario_plans):
            blockers.append("GATE_C")
        if not all(p.upstream_gate_d_status.strip().upper() == "PASS" for p in scenario_plans):
            blockers.append("GATE_D")
        gate_status = (
            "ELIGIBLE_FOR_GATE_E_VERDICT"
            if not blockers
            else "PROVISIONAL/BLOCKED_BY_" + "_AND_".join(blockers)
        )
        output.append(
            {
                "scenario_id": scenario_id,
                "gate_status": gate_status,
                "headway_CW_min": float(cw["target_headway_min"]),
                "headway_CCW_min": float(ccw["target_headway_min"]),
                "headway_combined_rate_equiv_min": combined_headway_rate_equivalent(
                    float(cw["target_headway_min"]), float(ccw["target_headway_min"])
                ),
                "vehicles_required_CW": int(cw["vehicles_required"]),
                "vehicles_required_CCW": int(ccw["vehicles_required"]),
                "vehicles_required_total": int(cw["vehicles_required"]) + int(ccw["vehicles_required"]),
                "annual_bus_km": annual_km,
                "annual_scheduled_vehicle_hours": vehicle_hours,
                "pdb_budget_bus_km": budget,
                "delta_bus_km_vs_pdb": delta,
                "delta_pct_vs_pdb": delta / budget * 100.0,
                "combined_headway_semantics": "RATE_EQUIVALENT_NOT_MAX_GAP",
            }
        )
    return output
