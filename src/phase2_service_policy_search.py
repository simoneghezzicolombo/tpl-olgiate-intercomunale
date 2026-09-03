"""Compact, lossless Service-Policy Search V2 feasibility helpers.

This module evaluates a caller-declared service-policy design space against
scenario-level operational lower bounds and annual bus-km envelopes. It does not
calculate passenger utility, phase a timetable to S8, select a topology, or pick
one service policy.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import math
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class PolicyDesign:
    policy_index: int
    policy_id: str
    uniform_headway_min: int
    span_id: str
    span_start_min: int
    span_end_min: int
    calendar_id: str
    annual_service_days: int
    recovery_min: int
    extension_share: float

    @property
    def span_minutes(self) -> int:
        return self.span_end_min - self.span_start_min

    @property
    def pattern_sets_per_day_equivalent(self) -> float:
        return self.span_minutes / self.uniform_headway_min


@dataclass(frozen=True)
class PolicyScenarioMetrics:
    annual_bus_km: float
    aggregate_interlinable_fleet_lower_bound: int
    expected_pattern_set_cycle_distance_km: float
    expected_pattern_set_cycle_runtime_min: float


def _policy_payload(*, headway: int, span: dict, calendar: dict, recovery: int, extension_share: float) -> dict:
    return {
        "uniform_headway_min": int(headway),
        "span_id": str(span["span_id"]),
        "span_start_min": int(span["start_min"]),
        "span_end_min": int(span["end_min"]),
        "calendar_id": str(calendar["calendar_id"]),
        "annual_service_days": int(calendar["days"]),
        "recovery_min": int(recovery),
        "extension_share": float(extension_share),
    }


def load_design_space(path: Path) -> tuple[dict, list[PolicyDesign]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("contract") != "PHASE2_SERVICE_POLICY_DESIGN_SPACE_V2":
        raise ValueError("Unexpected service-policy design-space contract")
    if payload.get("status") != "ASSUMPTION_DESIGN_SPACE_NOT_SERVICE_PLAN":
        raise ValueError("Service-policy design space is not explicitly marked as an assumption")
    if payload.get("uniform_clockface_baseline") is not True:
        raise ValueError("This V2 sweep requires the declared uniform-clockface baseline")
    if payload.get("peak_offpeak_differentiation_in_this_sweep") is not False:
        raise ValueError("This V2 baseline must not silently introduce peak/off-peak differentiation")

    headways = [int(v) for v in payload["headways_min"]]
    spans = list(payload["spans"])
    calendars = list(payload["annual_service_days"])
    recoveries = [int(v) for v in payload["recovery_min"]]
    extension_shares = [float(v) for v in payload["scheduled_extension_shares"]]
    if sorted(headways) != [15, 20, 30, 60]:
        raise ValueError("Unexpected declared headway design grid")
    if any(h <= 0 or 60 % h != 0 for h in headways):
        raise ValueError("Uniform-clockface baseline headways must divide 60")
    if sorted(extension_shares) != [0.0, 0.25, 0.5, 1.0]:
        raise ValueError("Unexpected scheduled-extension share grid")
    if any(str(row.get("status", "")).startswith("ASSUMPTION") is False for row in spans):
        raise ValueError("Every span must be explicitly marked as an assumption")
    if any("ASSUMPTION" not in str(row.get("status", "")) for row in calendars):
        raise ValueError("Every annual-day count must be explicitly marked as an assumption")

    raw: list[dict] = []
    for extension_share in extension_shares:
        for headway in sorted(headways):
            for span in sorted(spans, key=lambda r: str(r["span_id"])):
                start = int(span["start_min"])
                end = int(span["end_min"])
                if not 0 <= start < end <= 1440:
                    raise ValueError(f"Invalid span {span}")
                for calendar in sorted(calendars, key=lambda r: str(r["calendar_id"])):
                    if int(calendar["days"]) <= 0:
                        raise ValueError("Annual service days must be positive")
                    for recovery in sorted(recoveries):
                        if recovery < 0:
                            raise ValueError("Recovery must be non-negative")
                        row = _policy_payload(
                            headway=headway,
                            span=span,
                            calendar=calendar,
                            recovery=recovery,
                            extension_share=extension_share,
                        )
                        canonical = json.dumps(row, sort_keys=True, separators=(",", ":"))
                        row["policy_id"] = f"SP2_{sha256(canonical.encode('utf-8')).hexdigest()[:14]}"
                        raw.append(row)

    raw.sort(key=lambda r: (
        r["extension_share"], r["uniform_headway_min"], r["span_id"],
        r["calendar_id"], r["recovery_min"], r["policy_id"],
    ))
    policies = [
        PolicyDesign(policy_index=index, **row)
        for index, row in enumerate(raw)
    ]
    ids = [p.policy_id for p in policies]
    if len(ids) != len(set(ids)):
        raise AssertionError("Service-policy ID collision")
    return payload, policies


def policy_applies_to_family(policy: PolicyDesign, topology_family: str) -> bool:
    if topology_family == "scheduled_extensions":
        return True
    return math.isclose(policy.extension_share, 0.0, rel_tol=0.0, abs_tol=1e-12)


def evaluate_policy_for_scenario(
    policy: PolicyDesign,
    *,
    topology_family: str,
    public_cycle_distance_km: float,
    public_cycle_runtime_min: float,
    public_route_count: int,
    extension_cycle_distance_km: float | None,
    extension_cycle_runtime_min: float | None,
) -> PolicyScenarioMetrics | None:
    if not policy_applies_to_family(policy, topology_family):
        return None
    if public_cycle_distance_km <= 0 or public_cycle_runtime_min <= 0 or public_route_count <= 0:
        raise ValueError("Scenario public operational lower bounds must be positive")

    share = policy.extension_share
    if topology_family == "scheduled_extensions":
        if extension_cycle_distance_km is None or extension_cycle_runtime_min is None:
            raise ValueError("Scheduled-extension scenario is missing its alternative extended cycle")
        if extension_cycle_distance_km <= 0 or extension_cycle_runtime_min <= 0:
            raise ValueError("Scheduled-extension cycle lower bounds must be positive")
        expected_distance = (
            (1.0 - share) * public_cycle_distance_km
            + share * extension_cycle_distance_km
        )
        expected_runtime = (
            (1.0 - share) * public_cycle_runtime_min
            + share * extension_cycle_runtime_min
        )
    else:
        expected_distance = public_cycle_distance_km
        expected_runtime = public_cycle_runtime_min

    annual_bus_km = (
        expected_distance
        * policy.pattern_sets_per_day_equivalent
        * policy.annual_service_days
    )
    fleet_lb = math.ceil(
        (expected_runtime + policy.recovery_min * public_route_count)
        / policy.uniform_headway_min
    )
    return PolicyScenarioMetrics(
        annual_bus_km=annual_bus_km,
        aggregate_interlinable_fleet_lower_bound=fleet_lb,
        expected_pattern_set_cycle_distance_km=expected_distance,
        expected_pattern_set_cycle_runtime_min=expected_runtime,
    )


def encode_policy_mask(indices: Iterable[int], *, policy_count: int) -> str:
    if policy_count <= 0:
        raise ValueError("policy_count must be positive")
    mask = 0
    for index in indices:
        if index < 0 or index >= policy_count:
            raise ValueError(f"Policy index {index} outside [0,{policy_count})")
        mask |= 1 << index
    width = math.ceil(policy_count / 4)
    return format(mask, f"0{width}x")


def decode_policy_mask(mask_hex: str, *, policy_count: int) -> tuple[int, ...]:
    if policy_count <= 0:
        raise ValueError("policy_count must be positive")
    value = int(mask_hex, 16)
    if value >> policy_count:
        raise ValueError("Policy mask contains bits outside declared policy universe")
    return tuple(index for index in range(policy_count) if value & (1 << index))
