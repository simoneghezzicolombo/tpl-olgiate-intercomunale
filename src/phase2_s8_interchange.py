"""Topology-neutral S8 interchange opportunity model for Phase 2.

This module consumes a Gate C active-day S8 event set and the exact official
Trenord GTFS snapshot identified by that Gate C evidence. It never selects a
bus topology. Bus scenarios are evaluated only through their hub arrival and
departure events at Olgiate-Calco-Brivio FS.

Epistemic contract:
- active rail service/date: Gate C DERIVED_FROM_LIVE_OFFICIAL_GTFS;
- stop sequences and direction: DERIVED from the matching official GTFS;
- work demand: ISTAT 2021 work commuting only;
- S8_DIRECT: infrastructure addressability, never modal share;
- transfer-quality parameters and delay cases: ASSUMPTION sensitivity inputs;
- non-direct rail destinations are assigned only with explicit verified
  transfer evidence.
"""
from __future__ import annotations

from dataclasses import dataclass
import csv
import hashlib
import io
import json
import math
from pathlib import Path
from statistics import mean, median
from typing import Iterable, Mapping, Sequence
import zipfile


STATION_ID = "S01514"
MILANO_ANCHOR = "S01645"  # Milano Porta Garibaldi on validated S8 stop pattern
LECCO_ANCHOR = "S01520"
CONNECTION_TYPES = {"BUS_TO_RAIL", "RAIL_TO_BUS"}
RAIL_DIRECTIONS = {"MILANO", "LECCO"}


class S8ModelError(ValueError):
    """Fail-closed error for unsupported or inconsistent evidence."""


@dataclass(frozen=True)
class TransferQualityProfile:
    """ASSUMPTION sensitivity parameters for a continuous transfer score."""

    transfer_walk_min: float
    preferred_wait_min: float
    miss_transition_scale_min: float
    wait_decay_min: float

    def validate(self) -> None:
        if self.transfer_walk_min < 0:
            raise S8ModelError("transfer_walk_min must be >= 0")
        if self.preferred_wait_min < 0:
            raise S8ModelError("preferred_wait_min must be >= 0")
        if self.miss_transition_scale_min <= 0:
            raise S8ModelError("miss_transition_scale_min must be > 0")
        if self.wait_decay_min <= 0:
            raise S8ModelError("wait_decay_min must be > 0")


@dataclass(frozen=True)
class DelayCase:
    """One deterministic joint bus/rail delay case used for robustness."""

    bus_delay_min: float
    rail_delay_min: float
    weight: float
    label: str = ""

    def validate(self) -> None:
        if self.weight < 0:
            raise S8ModelError("delay-case weights must be >= 0")
        if not math.isfinite(self.bus_delay_min) or not math.isfinite(self.rail_delay_min):
            raise S8ModelError("delay values must be finite")


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def parse_gtfs_time(value: str) -> float:
    """Return service minutes; GTFS hours greater than 23 are supported."""
    parts = str(value).strip().split(":")
    if len(parts) != 3:
        raise S8ModelError(f"invalid GTFS time {value!r}")
    try:
        hour, minute, second = map(int, parts)
    except ValueError as exc:
        raise S8ModelError(f"invalid GTFS time {value!r}") from exc
    if hour < 0 or not 0 <= minute < 60 or not 0 <= second < 60:
        raise S8ModelError(f"invalid GTFS time {value!r}")
    return hour * 60 + minute + second / 60.0


def format_gtfs_time(minutes: float) -> str:
    total_seconds = int(round(minutes * 60))
    hour, rem = divmod(total_seconds, 3600)
    minute, second = divmod(rem, 60)
    return f"{hour:02d}:{minute:02d}:{second:02d}"


def _read_zip_csv(zf: zipfile.ZipFile, name: str) -> list[dict[str, str]]:
    try:
        data = zf.read(name)
    except KeyError as exc:
        raise S8ModelError(f"official GTFS missing {name}") from exc
    text = data.decode("utf-8-sig")
    return list(csv.DictReader(io.StringIO(text)))


def load_gate_c_active_s8(path: str | Path) -> dict:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise S8ModelError(f"cannot read Gate C S8 evidence: {exc}") from exc
    if payload.get("gate") != "C" or payload.get("source_type") != "LIVE_OFFICIAL_GTFS":
        raise S8ModelError("Gate C rail input must be LIVE_OFFICIAL_GTFS")
    station = payload.get("station") or {}
    if station.get("stop_id") != STATION_ID:
        raise S8ModelError(f"Gate C station must be {STATION_ID}")
    events = payload.get("events")
    if not isinstance(events, list) or not events:
        raise S8ModelError("Gate C rail input contains no S8 events")
    if payload.get("active_s8_station_events_count") != len(events):
        raise S8ModelError("Gate C S8 event count does not match payload")
    if not payload.get("download_sha256"):
        raise S8ModelError("Gate C S8 evidence lacks official GTFS SHA256")
    return payload


def _infer_direction(stop_ids_after_station: set[str]) -> str:
    has_milano = MILANO_ANCHOR in stop_ids_after_station
    has_lecco = LECCO_ANCHOR in stop_ids_after_station
    if has_milano == has_lecco:
        raise S8ModelError(
            "cannot infer S8 direction unambiguously from validated endpoint anchors"
        )
    return "MILANO" if has_milano else "LECCO"


def build_active_s8_events(
    gate_c_json: str | Path,
    gtfs_zip: str | Path,
) -> tuple[list[dict[str, object]], dict]:
    """Join Gate C active-day events to exact GTFS stop sequences and directions."""
    payload = load_gate_c_active_s8(gate_c_json)
    expected_sha = str(payload["download_sha256"]).lower()
    actual_sha = sha256_file(gtfs_zip)
    if actual_sha != expected_sha:
        raise S8ModelError(
            f"GTFS SHA256 mismatch: got {actual_sha}, Gate C requires {expected_sha}"
        )

    active_events = {str(e["trip_id"]): e for e in payload["events"]}
    if len(active_events) != len(payload["events"]):
        raise S8ModelError("duplicate trip_id in Gate C active S8 events")

    with zipfile.ZipFile(gtfs_zip) as zf:
        trips_all = _read_zip_csv(zf, "trips.txt")
        stops_all = _read_zip_csv(zf, "stops.txt")
        stop_times_all = _read_zip_csv(zf, "stop_times.txt")

    stops = {r["stop_id"]: r for r in stops_all}
    trip_meta = {
        r["trip_id"]: r
        for r in trips_all
        if r["trip_id"] in active_events
    }
    missing_trips = sorted(set(active_events) - set(trip_meta))
    if missing_trips:
        raise S8ModelError(f"active Gate C trips absent from matching GTFS: {missing_trips[:3]}")
    wrong_route = sorted(
        trip_id for trip_id, row in trip_meta.items() if row.get("route_id") != "S8"
    )
    if wrong_route:
        raise S8ModelError(f"Gate C active trips are not route S8: {wrong_route[:3]}")

    grouped: dict[str, list[dict[str, str]]] = {trip_id: [] for trip_id in active_events}
    for row in stop_times_all:
        trip_id = row.get("trip_id", "")
        if trip_id in grouped:
            grouped[trip_id].append(row)

    rows: list[dict[str, object]] = []
    for trip_id, gate_event in active_events.items():
        pattern = grouped[trip_id]
        if not pattern:
            raise S8ModelError(f"no stop_times for active S8 trip {trip_id}")
        try:
            pattern.sort(key=lambda r: int(r["stop_sequence"]))
        except (KeyError, ValueError) as exc:
            raise S8ModelError(f"invalid stop_sequence on {trip_id}") from exc
        station_positions = [i for i, r in enumerate(pattern) if r.get("stop_id") == STATION_ID]
        if len(station_positions) != 1:
            raise S8ModelError(f"{trip_id}: expected exactly one {STATION_ID} event")
        idx = station_positions[0]
        station_row = pattern[idx]
        if station_row.get("arrival_time") != gate_event.get("arrival_time"):
            raise S8ModelError(f"{trip_id}: Gate C arrival does not match GTFS")
        if station_row.get("departure_time") != gate_event.get("departure_time"):
            raise S8ModelError(f"{trip_id}: Gate C departure does not match GTFS")
        after_ids = {r["stop_id"] for r in pattern[idx + 1 :]}
        direction = _infer_direction(after_ids)
        terminal = pattern[-1]["stop_id"]
        origin = pattern[0]["stop_id"]
        if terminal not in stops or origin not in stops:
            raise S8ModelError(f"{trip_id}: terminal/origin stop missing from stops.txt")
        rows.append(
            {
                "service_date": str(payload["service_date"]),
                "trip_id": trip_id,
                "trip_short_name": str(gate_event.get("trip_short_name", "")),
                "direction": direction,
                "arrival_time": station_row["arrival_time"],
                "departure_time": station_row["departure_time"],
                "arrival_min": parse_gtfs_time(station_row["arrival_time"]),
                "departure_min": parse_gtfs_time(station_row["departure_time"]),
                "origin_stop_id": origin,
                "origin_stop_name": stops[origin]["stop_name"],
                "terminal_stop_id": terminal,
                "terminal_stop_name": stops[terminal]["stop_name"],
                "station_stop_sequence": int(station_row["stop_sequence"]),
                "trip_stop_count": len(pattern),
                "bus_to_rail_anchor_semantics": "BUS_ARRIVAL_SCORED_CONTINUOUSLY_AGAINST_RAIL_DEPARTURE",
                "rail_to_bus_anchor_semantics": "BUS_DEPARTURE_SCORED_CONTINUOUSLY_AGAINST_RAIL_ARRIVAL",
                "epistemic_status": "DERIVED_FROM_LIVE_OFFICIAL_GTFS",
            }
        )
    rows.sort(key=lambda r: (float(r["departure_min"]), str(r["trip_id"])))
    if len(rows) != int(payload["active_s8_station_events_count"]):
        raise S8ModelError("derived active event count changed during GTFS join")
    return rows, payload


def _percentile(values: Sequence[float], q: float) -> float:
    if not values:
        raise S8ModelError("cannot compute percentile of empty sequence")
    if not 0 <= q <= 1:
        raise S8ModelError("q must be in [0, 1]")
    xs = sorted(float(v) for v in values)
    if len(xs) == 1:
        return xs[0]
    pos = q * (len(xs) - 1)
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return xs[lo]
    frac = pos - lo
    return xs[lo] * (1 - frac) + xs[hi] * frac


def characterize_timetable(events: Sequence[Mapping[str, object]]) -> dict[str, object]:
    direction_summaries: dict[str, dict[str, object]] = {}
    for direction in sorted(RAIL_DIRECTIONS):
        departures = sorted(
            float(e["departure_min"]) for e in events if e.get("direction") == direction
        )
        arrivals = sorted(
            float(e["arrival_min"]) for e in events if e.get("direction") == direction
        )
        if not departures:
            raise S8ModelError(f"no active S8 events toward {direction}")
        headways = [b - a for a, b in zip(departures, departures[1:])]
        minute_offsets = sorted({int(round(t)) % 60 for t in departures})
        direction_summaries[direction] = {
            "event_count": len(departures),
            "first_arrival": format_gtfs_time(arrivals[0]),
            "first_departure": format_gtfs_time(departures[0]),
            "last_arrival": format_gtfs_time(arrivals[-1]),
            "last_departure": format_gtfs_time(departures[-1]),
            "service_span_min": departures[-1] - departures[0],
            "headway_count": len(headways),
            "headway_mean_min": mean(headways) if headways else None,
            "headway_median_min": median(headways) if headways else None,
            "headway_min_min": min(headways) if headways else None,
            "headway_p10_min": _percentile(headways, 0.10) if headways else None,
            "headway_p90_min": _percentile(headways, 0.90) if headways else None,
            "headway_max_min": max(headways) if headways else None,
            "departure_minute_offsets": minute_offsets,
        }
    m = direction_summaries["MILANO"]
    l = direction_summaries["LECCO"]
    asymmetry = {
        "event_count_difference_milano_minus_lecco": int(m["event_count"]) - int(l["event_count"]),
        "median_headway_difference_min": (
            float(m["headway_median_min"]) - float(l["headway_median_min"])
            if m["headway_median_min"] is not None and l["headway_median_min"] is not None
            else None
        ),
        "service_span_difference_min": float(m["service_span_min"]) - float(l["service_span_min"]),
        "semantics": "DESCRIPTIVE_TIMETABLE_ASYMMETRY_NOT_PASSENGER_DEMAND",
    }
    return {"directions": direction_summaries, "asymmetry": asymmetry}


def transfer_quality_from_slack(
    slack_after_walk_min: float,
    profile: TransferQualityProfile,
) -> float:
    """Continuous [0,1] quality with no arbitrary make/miss score cutoff.

    ``slack_after_walk_min`` is time remaining after the station transfer walk.
    A logistic factor makes the make/miss boundary smooth. An exponential
    factor penalises waits far from the preferred wait. The profile is an
    explicit ASSUMPTION and should be varied in sensitivity analysis.
    """
    profile.validate()
    x = max(-60.0, min(60.0, slack_after_walk_min / profile.miss_transition_scale_min))
    catch_factor = 1.0 / (1.0 + math.exp(-x))
    nonnegative_wait = max(0.0, slack_after_walk_min)
    timing_factor = math.exp(
        -abs(nonnegative_wait - profile.preferred_wait_min) / profile.wait_decay_min
    )
    return catch_factor * timing_factor


def scheduled_slack_after_walk(
    connection_type: str,
    bus_time_min: float,
    rail_event: Mapping[str, object],
    profile: TransferQualityProfile,
) -> float:
    profile.validate()
    connection_type = connection_type.upper()
    if connection_type == "BUS_TO_RAIL":
        return float(rail_event["departure_min"]) - bus_time_min - profile.transfer_walk_min
    if connection_type == "RAIL_TO_BUS":
        return bus_time_min - float(rail_event["arrival_min"]) - profile.transfer_walk_min
    raise S8ModelError(f"connection_type must be one of {sorted(CONNECTION_TYPES)}")


def score_bus_event_against_rail(
    bus_time_min: float,
    events: Sequence[Mapping[str, object]],
    connection_type: str,
    rail_direction: str,
    profile: TransferQualityProfile,
) -> dict[str, object]:
    connection_type = connection_type.upper()
    rail_direction = rail_direction.upper()
    if connection_type not in CONNECTION_TYPES:
        raise S8ModelError(f"unsupported connection type {connection_type}")
    if rail_direction not in RAIL_DIRECTIONS:
        raise S8ModelError(f"unsupported rail direction {rail_direction}")
    candidates = [e for e in events if e.get("direction") == rail_direction]
    if not candidates:
        raise S8ModelError(f"no S8 events for direction {rail_direction}")
    scored: list[tuple[float, float, Mapping[str, object]]] = []
    for event in candidates:
        slack = scheduled_slack_after_walk(connection_type, bus_time_min, event, profile)
        quality = transfer_quality_from_slack(slack, profile)
        scored.append((quality, slack, event))
    quality, slack, event = max(scored, key=lambda item: (item[0], -abs(item[1])))
    return {
        "quality": quality,
        "slack_after_walk_min": slack,
        "rail_trip_id": event["trip_id"],
        "rail_direction": rail_direction,
        "connection_type": connection_type,
    }


def robust_connection_quality(
    bus_time_min: float,
    rail_event: Mapping[str, object],
    connection_type: str,
    profile: TransferQualityProfile,
    delay_cases: Sequence[DelayCase],
) -> dict[str, float]:
    """Deterministic delay robustness; no random sampling is used."""
    if not delay_cases:
        raise S8ModelError("at least one delay case is required")
    for case in delay_cases:
        case.validate()
    total_weight = sum(case.weight for case in delay_cases)
    if total_weight <= 0:
        raise S8ModelError("delay-case weights must sum to > 0")
    weighted_quality = 0.0
    weighted_slack = 0.0
    missed_weight = 0.0
    worst_quality = 1.0
    connection_type = connection_type.upper()
    for case in delay_cases:
        if connection_type == "BUS_TO_RAIL":
            actual_bus = bus_time_min + case.bus_delay_min
            actual_rail = float(rail_event["departure_min"]) + case.rail_delay_min
            slack = actual_rail - actual_bus - profile.transfer_walk_min
        elif connection_type == "RAIL_TO_BUS":
            actual_bus = bus_time_min + case.bus_delay_min
            actual_rail = float(rail_event["arrival_min"]) + case.rail_delay_min
            slack = actual_bus - actual_rail - profile.transfer_walk_min
        else:
            raise S8ModelError(f"unsupported connection type {connection_type}")
        q = transfer_quality_from_slack(slack, profile)
        weighted_quality += q * case.weight
        weighted_slack += slack * case.weight
        worst_quality = min(worst_quality, q)
        if slack < 0:
            missed_weight += case.weight
    return {
        "expected_quality": weighted_quality / total_weight,
        "worst_case_quality": worst_quality,
        "hard_miss_probability": missed_weight / total_weight,
        "expected_slack_after_walk_min": weighted_slack / total_weight,
    }


def score_bus_hub_timetable(
    bus_events: Sequence[Mapping[str, object]],
    rail_events: Sequence[Mapping[str, object]],
    profile: TransferQualityProfile,
) -> list[dict[str, object]]:
    """Score hub events without knowing whether the bus came from a loop/radial/etc."""
    rows: list[dict[str, object]] = []
    for i, bus_event in enumerate(bus_events):
        event_type = str(bus_event.get("event_type", "")).upper()
        if event_type not in {"BUS_ARRIVAL", "BUS_DEPARTURE"}:
            raise S8ModelError("bus timetable event_type must be BUS_ARRIVAL or BUS_DEPARTURE")
        raw_time = bus_event.get("event_time")
        bus_min = parse_gtfs_time(str(raw_time)) if isinstance(raw_time, str) else float(raw_time)
        connection_type = "BUS_TO_RAIL" if event_type == "BUS_ARRIVAL" else "RAIL_TO_BUS"
        for direction in sorted(RAIL_DIRECTIONS):
            score = score_bus_event_against_rail(
                bus_min, rail_events, connection_type, direction, profile
            )
            rows.append(
                {
                    "bus_event_index": i,
                    "scenario_id": str(bus_event.get("scenario_id", "")),
                    "event_type": event_type,
                    "event_time_min": bus_min,
                    **score,
                }
            )
    return rows


def load_direct_s8_municipalities(path: str | Path) -> dict[str, dict[str, str]]:
    with Path(path).open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    required = {"stop_id", "stop_name", "procom", "comune"}
    if not rows or not required <= set(rows[0]):
        raise S8ModelError("S8 municipality map has invalid schema")
    result: dict[str, dict[str, str]] = {}
    for row in rows:
        code = str(row["procom"]).zfill(6)
        entry = result.setdefault(code, {"comune": row["comune"], "stop_ids": ""})
        ids = [x for x in entry["stop_ids"].split("|") if x]
        ids.append(row["stop_id"])
        entry["stop_ids"] = "|".join(sorted(set(ids)))
    return result


def load_verified_transfer_map(path: str | Path | None) -> dict[str, dict[str, str]]:
    if path is None:
        return {}
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise S8ModelError(f"cannot read verified transfer map: {exc}") from exc
    if not isinstance(payload, dict):
        raise S8ModelError("verified transfer map must be a JSON object keyed by municipality code")
    required = {"transfer_station", "connecting_route_id", "service_date", "evidence_source"}
    result: dict[str, dict[str, str]] = {}
    for raw_code, evidence in payload.items():
        if not isinstance(evidence, dict) or not required <= set(evidence):
            raise S8ModelError(f"verified transfer {raw_code} lacks required evidence fields")
        result[str(raw_code).zfill(6)] = {k: str(v) for k, v in evidence.items()}
    return result


def annotate_work_demand_addressability(
    demand_path: str | Path,
    s8_municipalities_path: str | Path,
    verified_transfer_path: str | Path | None = None,
) -> list[dict[str, object]]:
    direct = load_direct_s8_municipalities(s8_municipalities_path)
    transfers = load_verified_transfer_map(verified_transfer_path)
    with Path(demand_path).open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise S8ModelError("work-demand file is empty")
    required = {"procom_res", "origin_name", "procom_lav", "destination_name", "workers", "category"}
    if not required <= set(rows[0]):
        raise S8ModelError("work-demand file has invalid schema")
    output: list[dict[str, object]] = []
    for row in rows:
        code = str(row["procom_lav"]).zfill(6)
        source_category = str(row["category"])
        if source_category == "S8_DIRECT" and code not in direct:
            raise S8ModelError(
                f"demand profile labels {code} S8_DIRECT but no GTFS station municipality supports it"
            )
        if source_category == "S8_DIRECT":
            addressability = "DIRECT_S8_GTFS_VERIFIED"
            evidence = direct[code]["stop_ids"]
            feeder_eligible = True
        elif code in transfers:
            addressability = "TRANSFER_RAIL_GTFS_VERIFIED"
            evidence = json.dumps(transfers[code], ensure_ascii=False, sort_keys=True)
            feeder_eligible = True
        else:
            addressability = "NOT_RAIL_ASSIGNED"
            evidence = ""
            feeder_eligible = False
        output.append(
            {
                **row,
                "rail_addressability": addressability,
                "rail_evidence": evidence,
                "feeder_objective_eligible": feeder_eligible,
                "rail_semantics": "INFRASTRUCTURE_ADDRESSABILITY_NOT_MODAL_SHARE",
            }
        )
    return output


def station_sfr_context(
    sfr_path: str | Path,
    station_std: str = "OLGIATE-CALCO-BRIVIO",
) -> dict[str, object]:
    with Path(sfr_path).open(encoding="utf-8-sig", newline="") as f:
        rows = [r for r in csv.DictReader(f) if r.get("Stazione_std") == station_std]
    if not rows:
        raise S8ModelError(f"SFR series has no station {station_std}")
    rows.sort(key=lambda r: int(r["Anno"]))
    latest = rows[-1]
    values = [float(r["Saliti24H"]) for r in rows]
    return {
        "station": latest["Stazione"],
        "first_year": int(rows[0]["Anno"]),
        "latest_year": int(latest["Anno"]),
        "latest_saliti24h": float(latest["Saliti24H"]),
        "latest_index_2019_100": float(latest["Indice_2019_100"]),
        "series_min_saliti24h": min(values),
        "series_max_saliti24h": max(values),
        "latest_source_period": latest["Fonte_periodo"],
        "epistemic_status": "DERIVED_SFR_CONTEXT_NOT_MODAL_SHARE",
    }


def summarize_addressable_workers(rows: Iterable[Mapping[str, object]]) -> dict[str, object]:
    total = 0
    direct = 0
    transfer = 0
    unassigned = 0
    for row in rows:
        workers = int(float(row["workers"]))
        total += workers
        addressability = row["rail_addressability"]
        if addressability == "DIRECT_S8_GTFS_VERIFIED":
            direct += workers
        elif addressability == "TRANSFER_RAIL_GTFS_VERIFIED":
            transfer += workers
        else:
            unassigned += workers
    return {
        "work_rows_workers_total": total,
        "direct_s8_workers": direct,
        "verified_transfer_workers": transfer,
        "not_rail_assigned_workers": unassigned,
        "direct_s8_semantics": "ADDRESSABLE_WORK_DESTINATION_COUNT_NOT_RAIL_MODE_SHARE",
    }
