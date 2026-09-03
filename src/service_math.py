"""Deterministic service mathematics for Gate E.

No routes, runtimes, timetables or recommendations are invented here. V2 inputs
must carry per-metric epistemic status and upstream C/D lineage. ASSUMPTION is
accepted only for sensitivity analysis.
"""
from __future__ import annotations

from dataclasses import dataclass
import csv
import math
from pathlib import Path
from typing import Mapping, Sequence

CONTRACT_VERSION = "GATE_E_V2"
ALLOWED = {"FACT", "DERIVED", "ESTIMATE", "ASSUMPTION", "RECONSTRUCTED", "MODEL OUTPUT"}
FORBIDDEN = {"PLACEHOLDER", "INVALIDATED"}
DIRECTIONS = {"CW", "CCW"}
SHARED_PATTERN = {"CONFIRMED", "PARTIAL", "UNKNOWN"}
STATUS_FIELDS = (
    "route_km_status", "pure_running_status", "dwell_status", "recovery_status",
    "target_headway_status", "daily_cycles_status", "service_days_status",
)
V2_COLUMNS = (
    "contract_version", "scenario_id", "service_day_group", "band_id",
    "band_start_time", "band_end_time", "direction", "analysis_mode",
    "upstream_gate_c_status", "upstream_gate_d_status", "gate_c_artifact",
    "gate_c_commit", "gate_d_artifact", "gate_d_commit", "shared_stop_pattern_status",
    "route_km", "route_km_status", "pure_running_min", "pure_running_status",
    "dwell_min", "dwell_status", "recovery_min", "recovery_status",
    "target_headway_min", "target_headway_status", "daily_cycles",
    "daily_cycles_status", "service_days_year", "service_days_status",
)
GATE_E_V2_COLUMNS = V2_COLUMNS


class ServiceMathError(ValueError):
    pass


def _positive(name: str, value: float) -> float:
    value = float(value)
    if not math.isfinite(value) or value <= 0:
        raise ServiceMathError(f"{name} must be finite and > 0, got {value!r}")
    return value


def _nonnegative(name: str, value: float) -> float:
    value = float(value)
    if not math.isfinite(value) or value < 0:
        raise ServiceMathError(f"{name} must be finite and >= 0, got {value!r}")
    return value


def _positive_int(name: str, value: int) -> int:
    try:
        ivalue = int(value)
    except (TypeError, ValueError) as exc:
        raise ServiceMathError(f"{name} must be a positive integer") from exc
    if ivalue != value or ivalue <= 0:
        raise ServiceMathError(f"{name} must be a positive integer, got {value!r}")
    return ivalue


def cycle_minutes(pure_running_min: float, dwell_min: float, recovery_min: float) -> float:
    return (_positive("pure_running_min", pure_running_min)
            + _nonnegative("dwell_min", dwell_min)
            + _nonnegative("recovery_min", recovery_min))


def minimum_vehicles_for_regular_headway(cycle_min: float, target_headway_min: float) -> int:
    """Lower bound only; excludes deadhead, reliefs, spares and interlining."""
    return max(1, math.ceil(_positive("cycle_min", cycle_min)
                            / _positive("target_headway_min", target_headway_min) - 1e-12))


def vehicles_required(cycle_min: float, target_headway_min: float) -> int:
    return minimum_vehicles_for_regular_headway(cycle_min, target_headway_min)


def combined_headway_rate_equivalent(headway_cw_min: float, headway_ccw_min: float) -> float:
    cw = _positive("headway_cw_min", headway_cw_min)
    ccw = _positive("headway_ccw_min", headway_ccw_min)
    return 1.0 / (1.0 / cw + 1.0 / ccw)


def annual_bus_km(route_km: float, cycles_per_day: int, service_days_year: int) -> float:
    return (_positive("route_km", route_km)
            * _positive_int("cycles_per_day", cycles_per_day)
            * _positive_int("service_days_year", service_days_year))


def annual_component_hours(component_min: float, cycles_per_day: int, service_days_year: int) -> float:
    return (_nonnegative("component_min", component_min)
            * _positive_int("cycles_per_day", cycles_per_day)
            * _positive_int("service_days_year", service_days_year) / 60.0)


def annual_scheduled_vehicle_hours(cycle_min: float, cycles_per_day: int, service_days_year: int) -> float:
    return annual_component_hours(_positive("cycle_min", cycle_min), cycles_per_day, service_days_year)


def budget_delta(annual_km: float, budget_km: float) -> tuple[float, float]:
    annual = _nonnegative("annual_km", annual_km)
    budget = _positive("budget_km", budget_km)
    delta = annual - budget
    return delta, delta / budget * 100.0


def budget_break_even_route_km(budget_km: float, directional_cycles_per_year: int) -> float:
    return _positive("budget_km", budget_km) / _positive_int(
        "directional_cycles_per_year", directional_cycles_per_year
    )


def parse_gtfs_time_to_minutes(value: str) -> float:
    parts = value.strip().split(":")
    if len(parts) not in (2, 3):
        raise ServiceMathError(f"Invalid service time {value!r}")
    try:
        h, m = int(parts[0]), int(parts[1])
        s = int(parts[2]) if len(parts) == 3 else 0
    except ValueError as exc:
        raise ServiceMathError(f"Invalid service time {value!r}") from exc
    if h < 0 or not 0 <= m < 60 or not 0 <= s < 60:
        raise ServiceMathError(f"Invalid service time {value!r}")
    return h * 60 + m + s / 60.0


def validate_epistemic_status(status: str, analysis_mode: str, field: str = "value") -> None:
    status = status.strip().upper()
    mode = analysis_mode.strip().upper()
    if status in FORBIDDEN:
        raise ServiceMathError(f"{field}: {status} cannot feed Gate E")
    if status not in ALLOWED:
        raise ServiceMathError(f"{field}: unknown epistemic status {status!r}")
    if status == "ASSUMPTION" and mode != "SENSITIVITY":
        raise ServiceMathError(f"{field}: ASSUMPTION allowed only in SENSITIVITY")


def _int_field(row: Mapping[str, str], key: str) -> int:
    try:
        return int(row[key].strip())
    except ValueError as exc:
        raise ServiceMathError(f"{key} must be integer") from exc


@dataclass(frozen=True)
class ServiceBandDirectionPlan:
    contract_version: str
    scenario_id: str
    service_day_group: str
    band_id: str
    band_start_time: str
    band_end_time: str
    direction: str
    analysis_mode: str
    upstream_gate_c_status: str
    upstream_gate_d_status: str
    gate_c_artifact: str
    gate_c_commit: str
    gate_d_artifact: str
    gate_d_commit: str
    shared_stop_pattern_status: str
    route_km: float
    route_km_status: str
    pure_running_min: float
    pure_running_status: str
    dwell_min: float
    dwell_status: str
    recovery_min: float
    recovery_status: str
    target_headway_min: float
    target_headway_status: str
    daily_cycles: int
    daily_cycles_status: str
    service_days_year: int
    service_days_status: str

    def validate(self) -> None:
        if self.contract_version.strip().upper() != CONTRACT_VERSION:
            raise ServiceMathError(f"contract_version must be {CONTRACT_VERSION}")
        if not self.scenario_id.strip() or not self.service_day_group.strip() or not self.band_id.strip():
            raise ServiceMathError("scenario_id, service_day_group and band_id are required")
        if self.direction.strip().upper() not in DIRECTIONS:
            raise ServiceMathError("direction must be CW or CCW")
        if self.shared_stop_pattern_status.strip().upper() not in SHARED_PATTERN:
            raise ServiceMathError("shared_stop_pattern_status invalid")
        start, end = parse_gtfs_time_to_minutes(self.band_start_time), parse_gtfs_time_to_minutes(self.band_end_time)
        if end <= start:
            raise ServiceMathError("band_end_time must be after band_start_time")
        for field in STATUS_FIELDS:
            validate_epistemic_status(getattr(self, field), self.analysis_mode, field)
        _positive("route_km", self.route_km)
        cycle_minutes(self.pure_running_min, self.dwell_min, self.recovery_min)
        _positive("target_headway_min", self.target_headway_min)
        annual_bus_km(self.route_km, self.daily_cycles, self.service_days_year)
        if self.upstream_gate_c_status.strip().upper() == "PASS" and (
            not self.gate_c_artifact.strip() or not self.gate_c_commit.strip()
        ):
            raise ServiceMathError("Gate C PASS requires artifact and commit lineage")
        if self.upstream_gate_d_status.strip().upper() == "PASS" and (
            not self.gate_d_artifact.strip() or not self.gate_d_commit.strip()
        ):
            raise ServiceMathError("Gate D PASS requires artifact and commit lineage")

    @property
    def cycle_min(self) -> float:
        return cycle_minutes(self.pure_running_min, self.dwell_min, self.recovery_min)

    @property
    def band_span_min(self) -> float:
        return parse_gtfs_time_to_minutes(self.band_end_time) - parse_gtfs_time_to_minutes(self.band_start_time)

    @property
    def assumption_fields(self) -> tuple[str, ...]:
        return tuple(f.removesuffix("_status") for f in STATUS_FIELDS if getattr(self, f).strip().upper() == "ASSUMPTION")

    def metrics(self) -> dict[str, object]:
        self.validate()
        fleet = minimum_vehicles_for_regular_headway(self.cycle_min, self.target_headway_min)
        nominal = math.ceil(self.band_span_min / self.target_headway_min - 1e-12)
        return {
            "contract_version": CONTRACT_VERSION, "scenario_id": self.scenario_id,
            "service_day_group": self.service_day_group, "band_id": self.band_id,
            "band_start_time": self.band_start_time, "band_end_time": self.band_end_time,
            "direction": self.direction.upper(), "analysis_mode": self.analysis_mode.upper(),
            "shared_stop_pattern_status": self.shared_stop_pattern_status.upper(),
            "route_km": self.route_km, "pure_running_min": self.pure_running_min,
            "dwell_min": self.dwell_min, "recovery_min": self.recovery_min,
            "cycle_min": self.cycle_min, "target_headway_min": self.target_headway_min,
            "minimum_in_service_vehicles": fleet,
            "fleet_semantics": "LOWER_BOUND_EXCLUDES_DEADHEAD_RELIEF_SPARES_INTERLINING",
            "daily_cycles": self.daily_cycles, "service_days_year": self.service_days_year,
            "nominal_departures_from_span_and_target_headway": nominal,
            "daily_cycles_minus_nominal_departures": self.daily_cycles - nominal,
            "cycle_count_consistency": "CHECK_PHASE_OR_BAND_BOUNDARIES" if abs(self.daily_cycles - nominal) > 1 else "PLAUSIBLE_WITHIN_ONE_DEPARTURE",
            "annual_bus_km": annual_bus_km(self.route_km, self.daily_cycles, self.service_days_year),
            "annual_running_vehicle_hours": annual_component_hours(self.pure_running_min, self.daily_cycles, self.service_days_year),
            "annual_dwell_vehicle_hours": annual_component_hours(self.dwell_min, self.daily_cycles, self.service_days_year),
            "annual_recovery_vehicle_hours": annual_component_hours(self.recovery_min, self.daily_cycles, self.service_days_year),
            "annual_scheduled_vehicle_hours": annual_scheduled_vehicle_hours(self.cycle_min, self.daily_cycles, self.service_days_year),
            "assumption_fields": ";".join(self.assumption_fields),
        }


def read_service_band_plans(path: str | Path) -> list[ServiceBandDirectionPlan]:
    with Path(path).open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        missing = set(V2_COLUMNS) - set(reader.fieldnames or [])
        if missing:
            raise ServiceMathError(f"Missing Gate E V2 columns: {sorted(missing)}")
        plans = []
        for row in reader:
            kwargs = {k: row[k].strip() for k in V2_COLUMNS}
            for key in ("route_km", "pure_running_min", "dwell_min", "recovery_min", "target_headway_min"):
                kwargs[key] = float(kwargs[key])
            for key in ("daily_cycles", "service_days_year"):
                kwargs[key] = _int_field(row, key)
            plan = ServiceBandDirectionPlan(**kwargs)
            plan.validate()
            plans.append(plan)
    if not plans:
        raise ServiceMathError("Gate E V2 input contains no rows")
    validate_band_pairs(plans)
    return plans


def validate_band_pairs(plans: Sequence[ServiceBandDirectionPlan]) -> None:
    grouped: dict[tuple[str, str, str], list[ServiceBandDirectionPlan]] = {}
    for p in plans:
        grouped.setdefault((p.scenario_id, p.service_day_group, p.band_id), []).append(p)
    for key, rows in grouped.items():
        if len(rows) != 2 or {r.direction.upper() for r in rows} != DIRECTIONS:
            raise ServiceMathError(f"{key}: requires exactly one CW and one CCW row")
        a, b = rows
        for field in ("band_start_time", "band_end_time", "analysis_mode", "service_days_year"):
            if getattr(a, field) != getattr(b, field):
                raise ServiceMathError(f"{key}: CW/CCW {field} differ")


def load_pdb_budget(path: str | Path) -> dict[str, float | str]:
    """Preserve published totals and expose, never hide, reconstructed subcomponent mismatch."""
    with Path(path).open(newline="", encoding="utf-8-sig") as f:
        rows = {r["linea"].strip(): r for r in csv.DictReader(f)}
    for line in ("D184", "D185", "D184+D185"):
        if line not in rows:
            raise ServiceMathError(f"Missing {line} in PdB table")
    n = lambda line, field: float(rows[line][field])
    d184, d185, total = n("D184", "km_totali_anno"), n("D185", "km_totali_anno"), n("D184+D185", "km_totali_anno")
    p184, p185, peak = n("D184", "km_punta_anno"), n("D185", "km_punta_anno"), n("D184+D185", "km_punta_anno")
    o184, o185, off = n("D184", "km_morbida_anno"), n("D185", "km_morbida_anno"), n("D184+D185", "km_morbida_anno")
    if not math.isclose(d184 + d185, total, abs_tol=1e-9):
        raise ServiceMathError("Published D184+D185 line totals inconsistent")
    if not math.isclose(p184 + p185, peak, abs_tol=1e-9) or not math.isclose(o184 + o185, off, abs_tol=1e-9):
        raise ServiceMathError("Published peak/offpeak subtotals inconsistent")
    deltas = (p184 + o184 - d184, p185 + o185 - d185, peak + off - total)
    return {
        "D184": d184, "D185": d185, "D184+D185": total,
        "D184_peak": p184, "D185_peak": p185, "D184+D185_peak": peak,
        "D184_offpeak": o184, "D185_offpeak": o185, "D184+D185_offpeak": off,
        "D184_component_sum_delta_km": deltas[0], "D185_component_sum_delta_km": deltas[1],
        "D184+D185_component_sum_delta_km": deltas[2],
        "component_arithmetic_status": "EXACT_COMPONENT_SUM" if max(map(abs, deltas)) < 1e-9 else "RECONSTRUCTED_COMPONENT_ROUNDING_MISMATCH",
    }


def _gate_status(rows: Sequence[ServiceBandDirectionPlan]) -> str:
    blockers = []
    if not all(r.upstream_gate_c_status.strip().upper() == "PASS" for r in rows): blockers.append("GATE_C")
    if not all(r.upstream_gate_d_status.strip().upper() == "PASS" for r in rows): blockers.append("GATE_D")
    assumption = any(r.assumption_fields for r in rows)
    if not blockers and not assumption: return "ELIGIBLE_FOR_GATE_E_VERDICT"
    prefix = "SENSITIVITY_ONLY" if assumption else "PROVISIONAL"
    return prefix if not blockers else prefix + "/BLOCKED_BY_" + "_AND_".join(blockers)


def aggregate_service_bands(plans: Sequence[ServiceBandDirectionPlan], budget_km: float) -> list[dict[str, object]]:
    validate_band_pairs(plans)
    grouped: dict[tuple[str, str, str], list[ServiceBandDirectionPlan]] = {}
    for p in plans: grouped.setdefault((p.scenario_id, p.service_day_group, p.band_id), []).append(p)
    out = []
    for (scenario, day_group, band), rows in sorted(grouped.items()):
        by = {r.direction.upper(): r for r in rows}; cw, ccw = by["CW"].metrics(), by["CCW"].metrics()
        annual = float(cw["annual_bus_km"]) + float(ccw["annual_bus_km"])
        shared = all(r.shared_stop_pattern_status.upper() == "CONFIRMED" for r in rows)
        combined = combined_headway_rate_equivalent(cw["target_headway_min"], ccw["target_headway_min"]) if shared else None
        out.append({
            "contract_version": CONTRACT_VERSION, "scenario_id": scenario, "service_day_group": day_group,
            "band_id": band, "band_start_time": cw["band_start_time"], "band_end_time": cw["band_end_time"],
            "gate_status": _gate_status(rows), "headway_CW_min": cw["target_headway_min"],
            "headway_CCW_min": ccw["target_headway_min"], "headway_combined_rate_equiv_min": combined,
            "combined_headway_applicability": "COMPUTED_SHARED_STOP_PATTERN_CONFIRMED" if shared else "NOT_COMPUTED_UNTIL_SHARED_STOP_PATTERN_CONFIRMED",
            "minimum_in_service_vehicles_band_total": int(cw["minimum_in_service_vehicles"]) + int(ccw["minimum_in_service_vehicles"]),
            "fleet_semantics": "LOWER_BOUND_EXCLUDES_DEADHEAD_RELIEF_SPARES_INTERLINING",
            "annual_bus_km": annual,
            "annual_running_vehicle_hours": cw["annual_running_vehicle_hours"] + ccw["annual_running_vehicle_hours"],
            "annual_dwell_vehicle_hours": cw["annual_dwell_vehicle_hours"] + ccw["annual_dwell_vehicle_hours"],
            "annual_recovery_vehicle_hours": cw["annual_recovery_vehicle_hours"] + ccw["annual_recovery_vehicle_hours"],
            "annual_scheduled_vehicle_hours": cw["annual_scheduled_vehicle_hours"] + ccw["annual_scheduled_vehicle_hours"],
            **dict(zip(("band_delta_bus_km_vs_full_pdb_budget", "band_delta_pct_vs_full_pdb_budget"), budget_delta(annual, budget_km))),
        })
    return out


def aggregate_service_scenarios(plans: Sequence[ServiceBandDirectionPlan], budget_km: float) -> list[dict[str, object]]:
    bands = aggregate_service_bands(plans, budget_km)
    by_scenario: dict[str, list[dict[str, object]]] = {}; source: dict[str, list[ServiceBandDirectionPlan]] = {}
    for row in bands: by_scenario.setdefault(str(row["scenario_id"]), []).append(row)
    for p in plans: source.setdefault(p.scenario_id, []).append(p)
    out = []
    for scenario, rows in sorted(by_scenario.items()):
        annual = sum(float(r["annual_bus_km"]) for r in rows); delta, pct = budget_delta(annual, budget_km)
        out.append({
            "contract_version": CONTRACT_VERSION, "scenario_id": scenario, "gate_status": _gate_status(source[scenario]),
            "service_band_count": len(rows),
            "minimum_in_service_vehicles_scenario_lower_bound": max(int(r["minimum_in_service_vehicles_band_total"]) for r in rows),
            "fleet_semantics": "LOWER_BOUND_MAX_BAND_NOT_EXACT_BLOCK_FLEET", "annual_bus_km": annual,
            "annual_running_vehicle_hours": sum(float(r["annual_running_vehicle_hours"]) for r in rows),
            "annual_dwell_vehicle_hours": sum(float(r["annual_dwell_vehicle_hours"]) for r in rows),
            "annual_recovery_vehicle_hours": sum(float(r["annual_recovery_vehicle_hours"]) for r in rows),
            "annual_scheduled_vehicle_hours": sum(float(r["annual_scheduled_vehicle_hours"]) for r in rows),
            "pdb_budget_bus_km": budget_km, "delta_bus_km_vs_pdb": delta, "delta_pct_vs_pdb": pct,
            "assumption_present": any(p.assumption_fields for p in source[scenario]),
            "headway_semantics": "SEE_BAND_OUTPUT_FOR_CW_CCW_AND_COMBINED",
        })
    return out


# V1 compatibility kept deliberately small.
@dataclass(frozen=True)
class DirectionPlan:
    scenario_id: str; direction: str; epistemic_status: str; analysis_mode: str
    upstream_gate_c_status: str; upstream_gate_d_status: str; route_km: float
    pure_running_min: float; dwell_min: float; recovery_min: float; target_headway_min: float
    daily_cycles: int; service_days_year: int
    def validate(self) -> None:
        validate_epistemic_status(self.epistemic_status, self.analysis_mode)
        if self.direction.upper() not in DIRECTIONS: raise ServiceMathError("direction must be CW/CCW")
        annual_bus_km(self.route_km, self.daily_cycles, self.service_days_year)
        cycle_minutes(self.pure_running_min, self.dwell_min, self.recovery_min)
    @property
    def cycle_min(self): return cycle_minutes(self.pure_running_min, self.dwell_min, self.recovery_min)
    def metrics(self):
        self.validate(); return {"scenario_id": self.scenario_id, "direction": self.direction.upper(),
            "target_headway_min": self.target_headway_min, "service_days_year": self.service_days_year,
            "minimum_in_service_vehicles": minimum_vehicles_for_regular_headway(self.cycle_min, self.target_headway_min),
            "annual_bus_km": annual_bus_km(self.route_km, self.daily_cycles, self.service_days_year),
            "annual_scheduled_vehicle_hours": annual_scheduled_vehicle_hours(self.cycle_min, self.daily_cycles, self.service_days_year)}


def aggregate_scenarios(plans: Sequence[DirectionPlan], budget_km: float) -> list[dict[str, object]]:
    grouped: dict[str, list[DirectionPlan]] = {}
    for p in plans: grouped.setdefault(p.scenario_id, []).append(p)
    out = []
    for scenario, rows in grouped.items():
        if len(rows) != 2 or {r.direction.upper() for r in rows} != DIRECTIONS: raise ServiceMathError("requires one CW and one CCW")
        by = {r.direction.upper(): r for r in rows}; cw, ccw = by["CW"].metrics(), by["CCW"].metrics()
        annual = cw["annual_bus_km"] + ccw["annual_bus_km"]; delta, pct = budget_delta(annual, budget_km)
        blockers = []
        if not all(r.upstream_gate_c_status.upper() == "PASS" for r in rows): blockers.append("GATE_C")
        if not all(r.upstream_gate_d_status.upper() == "PASS" for r in rows): blockers.append("GATE_D")
        out.append({"scenario_id": scenario, "gate_status": "ELIGIBLE_FOR_GATE_E_VERDICT" if not blockers else "PROVISIONAL/BLOCKED_BY_" + "_AND_".join(blockers),
            "headway_CW_min": cw["target_headway_min"], "headway_CCW_min": ccw["target_headway_min"],
            "headway_combined_rate_equiv_min": combined_headway_rate_equivalent(cw["target_headway_min"], ccw["target_headway_min"]),
            "minimum_in_service_vehicles_total": cw["minimum_in_service_vehicles"] + ccw["minimum_in_service_vehicles"],
            "annual_bus_km": annual, "annual_scheduled_vehicle_hours": cw["annual_scheduled_vehicle_hours"] + ccw["annual_scheduled_vehicle_hours"],
            "delta_bus_km_vs_pdb": delta, "delta_pct_vs_pdb": pct})
    return out
