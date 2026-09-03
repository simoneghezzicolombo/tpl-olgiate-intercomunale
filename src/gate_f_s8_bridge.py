"""Derive scenario-specific S8 connection coverage from Gate C rail events and Gate E bus events.

The bridge never invents transfer windows or combines directions with hidden
weights. A policy must choose BUS_TO_S8 or S8_TO_BUS and explicit min/max waits.
"""
from __future__ import annotations

import json
from pathlib import Path
import pandas as pd


ALLOWED_EVENT_STATUSES = {"FACT", "DERIVED", "ESTIMATE", "RECONSTRUCTED", "MODEL OUTPUT"}
STATUS_ORDER = {"FACT": 0, "DERIVED": 1, "RECONSTRUCTED": 2, "MODEL OUTPUT": 3, "ESTIMATE": 4}
DIRECTIONS = {"BUS_TO_S8", "S8_TO_BUS"}
EVENT_TYPES = {"BUS_ARRIVAL", "BUS_DEPARTURE"}


def parse_time(value: str) -> float:
    parts = str(value).strip().split(":")
    if len(parts) not in {2, 3}:
        raise ValueError(f"Invalid service time {value!r}")
    try:
        hour = int(parts[0]); minute = int(parts[1]); second = int(parts[2]) if len(parts) == 3 else 0
    except ValueError as exc:
        raise ValueError(f"Invalid service time {value!r}") from exc
    if hour < 0 or not 0 <= minute < 60 or not 0 <= second < 60:
        raise ValueError(f"Invalid service time {value!r}")
    return hour * 60 + minute + second / 60.0


def load_policy(path: str | Path) -> dict[str, object]:
    try:
        policy = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot read S8 connection policy: {exc}") from exc
    required = {
        "schema_version", "comparison_id", "service_date", "service_day_group",
        "connection_direction", "evaluation_start_time", "evaluation_end_time",
        "minimum_transfer_min", "maximum_wait_min",
    }
    missing = required - set(policy)
    if missing:
        raise ValueError(f"S8 connection policy missing fields: {sorted(missing)}")
    if policy["schema_version"] != 1:
        raise ValueError("S8 connection policy schema_version must equal 1")
    direction = str(policy["connection_direction"]).strip().upper()
    if direction not in DIRECTIONS:
        raise ValueError(f"connection_direction must be one of {sorted(DIRECTIONS)}")
    start = parse_time(str(policy["evaluation_start_time"]))
    end = parse_time(str(policy["evaluation_end_time"]))
    if end <= start:
        raise ValueError("evaluation_end_time must be after evaluation_start_time")
    minimum = float(policy["minimum_transfer_min"])
    maximum = float(policy["maximum_wait_min"])
    if minimum < 0 or maximum <= 0 or maximum < minimum:
        raise ValueError("Transfer policy requires 0 <= minimum_transfer_min <= maximum_wait_min")
    comparison_id = str(policy["comparison_id"]).strip()
    day_group = str(policy["service_day_group"]).strip()
    service_date = str(policy["service_date"]).strip()
    if not comparison_id or not day_group or not service_date:
        raise ValueError("comparison_id, service_date and service_day_group must be non-empty")
    return {
        "comparison_id": comparison_id,
        "service_date": service_date,
        "service_day_group": day_group,
        "direction": direction,
        "start": start,
        "end": end,
        "minimum": minimum,
        "maximum": maximum,
    }


def load_gate_c_trains(path: str | Path, expected_date: str) -> tuple[list[dict], dict]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot read Gate C S8 events: {exc}") from exc
    if payload.get("gate") != "C" or payload.get("source_type") != "LIVE_OFFICIAL_GTFS":
        raise ValueError("Gate C S8 input must be LIVE_OFFICIAL_GTFS evidence")
    if str(payload.get("service_date")) != expected_date:
        raise ValueError("Gate C S8 service_date does not match the comparison policy")
    events = payload.get("events")
    if not isinstance(events, list) or not events:
        raise ValueError("Gate C S8 input contains no events")
    for event in events:
        if not event.get("arrival_time") or not event.get("departure_time"):
            raise ValueError("Every Gate C S8 event requires arrival_time and departure_time")
    return events, payload


def load_bus_events(path: str | Path, service_day_group: str) -> pd.DataFrame:
    required = {"scenario_id", "service_day_group", "event_type", "event_time", "epistemic_status", "source"}
    frame = pd.read_csv(path)
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"Bus hub events missing columns: {missing}")
    frame = frame.loc[frame["service_day_group"].astype(str).eq(service_day_group)].copy()
    if frame.empty:
        raise ValueError("No bus hub events match the selected service_day_group")
    event_type = frame["event_type"].astype(str).str.strip().str.upper()
    if (~event_type.isin(EVENT_TYPES)).any():
        raise ValueError("Bus hub events contain unsupported event_type")
    frame["event_type"] = event_type
    status = frame["epistemic_status"].astype(str).str.strip().str.upper()
    if status.eq("ASSUMPTION").any():
        raise ValueError("ASSUMPTION bus events cannot feed Gate F production S8 evidence")
    bad = sorted(set(status) - ALLOWED_EVENT_STATUSES)
    if bad:
        raise ValueError(f"Unsupported bus-event epistemic statuses: {bad}")
    frame["epistemic_status"] = status
    if frame["source"].isna().any() or frame["source"].astype(str).str.strip().eq("").any():
        raise ValueError("Every bus hub event requires a traceable source")
    frame["event_minutes"] = frame["event_time"].map(parse_time)
    return frame


def _derived_status(statuses: set[str]) -> str:
    if not statuses:
        raise ValueError("Cannot derive epistemic status from empty event set")
    weakest = max(statuses, key=lambda value: STATUS_ORDER[value])
    return "DERIVED" if weakest == "FACT" else weakest


def _has_connection(origin: float, targets: list[float], minimum: float, maximum: float) -> bool:
    lower = origin + minimum
    upper = origin + maximum
    return any(lower <= target <= upper for target in targets)


def build_s8_fragment(
    gate_c_s8_path: str | Path,
    bus_events_path: str | Path,
    policy_path: str | Path,
) -> pd.DataFrame:
    policy = load_policy(policy_path)
    trains, train_payload = load_gate_c_trains(gate_c_s8_path, str(policy["service_date"]))
    buses = load_bus_events(bus_events_path, str(policy["service_day_group"]))
    start, end = float(policy["start"]), float(policy["end"])
    direction = str(policy["direction"])

    train_arrivals = [parse_time(e["arrival_time"]) for e in trains]
    train_departures = [parse_time(e["departure_time"]) for e in trains]
    train_arrivals = [t for t in train_arrivals if start <= t <= end]
    train_departures = [t for t in train_departures if start <= t <= end]
    if not train_arrivals or not train_departures:
        raise ValueError("No Gate C S8 events fall inside the selected evaluation window")

    rows: list[dict[str, object]] = []
    for scenario_id, group in buses.groupby("scenario_id", sort=True):
        if direction == "BUS_TO_S8":
            origins = group.loc[
                group["event_type"].eq("BUS_ARRIVAL") & group["event_minutes"].between(start, end),
                "event_minutes",
            ].astype(float).tolist()
            targets = train_departures
            denominator_semantics = "PERCENT_OF_BUS_HUB_ARRIVALS_WITH_S8_DEPARTURE_IN_POLICY_WINDOW"
        else:
            origins = train_arrivals
            targets = group.loc[
                group["event_type"].eq("BUS_DEPARTURE") & group["event_minutes"].between(start, end),
                "event_minutes",
            ].astype(float).tolist()
            denominator_semantics = "PERCENT_OF_S8_HUB_ARRIVALS_WITH_BUS_DEPARTURE_IN_POLICY_WINDOW"
        if not origins or not targets:
            raise ValueError(f"{scenario_id}: selected S8 connection direction has an empty denominator or target set")
        useful = sum(
            _has_connection(origin, targets, float(policy["minimum"]), float(policy["maximum"]))
            for origin in origins
        )
        pct = useful / len(origins) * 100.0
        statuses = set(group["epistemic_status"].astype(str))
        status = _derived_status(statuses)
        bus_sources = sorted(set(group["source"].astype(str)))
        source = (
            f"GateC:{Path(gate_c_s8_path).as_posix()}#sha256={train_payload.get('download_sha256', 'UNRECORDED')}"
            + ";GateE_bus_events=" + "|".join(bus_sources)
        )
        basis = (
            f"{policy['comparison_id']}|date={policy['service_date']}|day={policy['service_day_group']}"
            f"|direction={direction}|window={start:g}-{end:g}|min_transfer={policy['minimum']:g}"
            f"|max_wait={policy['maximum']:g}"
        )
        rows.append(
            {
                "scenario_id": str(scenario_id),
                "s8_useful_connection_pct": pct,
                "s8_useful_connection_pct__status": status,
                "s8_useful_connection_pct__source": source,
                "s8_useful_connection_pct__unit": "%",
                "s8_useful_connection_pct__semantics": "PERCENT_OF_DEFINED_S8_CONNECTION_DENOMINATOR",
                "s8_useful_connection_pct__comparison_basis": basis + "|denominator=" + denominator_semantics,
                "s8_connection_numerator": useful,
                "s8_connection_denominator": len(origins),
                "s8_connection_direction": direction,
            }
        )
    return pd.DataFrame(rows)
