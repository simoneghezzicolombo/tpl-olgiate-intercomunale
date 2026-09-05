from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import date
from typing import Iterable, Sequence
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class ODKey:
    from_id: str
    to_id: str


@dataclass(frozen=True)
class ExperimentSpec:
    schema_version: str
    candidate_id: str
    candidate_gtfs_sha256: str
    street_network_sha256: str
    service_date: str
    timezone: str
    departure_window_start_sec: int
    departure_window_end_sec: int
    modes: tuple[str, ...]
    od_keys: tuple[ODKey, ...]


@dataclass(frozen=True)
class FrozenExperiment:
    canonical_json: bytes
    manifest_sha256: str


@dataclass(frozen=True)
class EngineExecutionBinding:
    engine_label: str
    manifest_sha256: str


def _nonempty(value: str, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")
    return value.strip()


def _sha(value: str, label: str) -> str:
    value = _nonempty(value, label)
    if not _SHA256_RE.fullmatch(value):
        raise ValueError(f"{label} must be a lowercase SHA256")
    return value


def _validate_date(value: str) -> str:
    value = _nonempty(value, "service_date")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("service_date must use YYYY-MM-DD") from exc
    if parsed.isoformat() != value:
        raise ValueError("service_date must use YYYY-MM-DD")
    return value


def _validate_timezone(value: str) -> str:
    value = _nonempty(value, "timezone")
    try:
        ZoneInfo(value)
    except ZoneInfoNotFoundError as exc:
        raise ValueError("timezone must be a valid IANA timezone") from exc
    return value


def _normalize_modes(modes: Iterable[str]) -> tuple[str, ...]:
    normalized = tuple(sorted({_nonempty(m, "mode").upper() for m in modes}))
    if not normalized:
        raise ValueError("mode semantics must not be empty")
    return normalized


def _normalize_od(keys: Iterable[ODKey]) -> tuple[tuple[str, str], ...]:
    seen: set[tuple[str, str]] = set()
    out: list[tuple[str, str]] = []
    for key in keys:
        pair = (_nonempty(key.from_id, "from_id"), _nonempty(key.to_id, "to_id"))
        if pair in seen:
            raise ValueError(f"duplicate OD key: {pair}")
        seen.add(pair)
        out.append(pair)
    if not out:
        raise ValueError("OD universe must not be empty")
    return tuple(sorted(out))


def freeze_experiment(spec: ExperimentSpec) -> FrozenExperiment:
    schema_version = _nonempty(spec.schema_version, "schema_version")
    candidate_id = _nonempty(spec.candidate_id, "candidate_id")
    gtfs_sha = _sha(spec.candidate_gtfs_sha256, "candidate_gtfs_sha256")
    network_sha = _sha(spec.street_network_sha256, "street_network_sha256")
    service_date = _validate_date(spec.service_date)
    timezone = _validate_timezone(spec.timezone)
    if (
        isinstance(spec.departure_window_start_sec, bool)
        or isinstance(spec.departure_window_end_sec, bool)
        or not isinstance(spec.departure_window_start_sec, int)
        or not isinstance(spec.departure_window_end_sec, int)
    ):
        raise ValueError("departure window must use integer seconds")
    if spec.departure_window_start_sec < 0 or spec.departure_window_end_sec < 0:
        raise ValueError("departure window must be non-negative")
    if spec.departure_window_start_sec > spec.departure_window_end_sec:
        raise ValueError("departure window is reversed")

    payload = {
        "candidate_gtfs_sha256": gtfs_sha,
        "candidate_id": candidate_id,
        "departure_window_end_sec": spec.departure_window_end_sec,
        "departure_window_start_sec": spec.departure_window_start_sec,
        "modes": list(_normalize_modes(spec.modes)),
        "od_keys": [{"from_id": a, "to_id": b} for a, b in _normalize_od(spec.od_keys)],
        "schema_version": schema_version,
        "service_date": service_date,
        "street_network_sha256": network_sha,
        "timezone": timezone,
    }
    canonical = (json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")
    return FrozenExperiment(canonical_json=canonical, manifest_sha256=hashlib.sha256(canonical).hexdigest())


def authorize_cross_engine_comparison(bindings: Sequence[EngineExecutionBinding], *, expected_manifest_sha256: str) -> bool:
    expected = _sha(expected_manifest_sha256, "expected_manifest_sha256")
    if len(bindings) != 2:
        raise ValueError("exactly two engine bindings are required")
    labels = [_nonempty(b.engine_label, "engine_label") for b in bindings]
    if labels[0] == labels[1]:
        raise ValueError("engine labels must be distinct")
    for binding in bindings:
        actual = _sha(binding.manifest_sha256, "engine manifest_sha256")
        if actual != expected:
            raise ValueError(
                f"EXPERIMENT_IDENTITY_MISMATCH engine={binding.engine_label} "
                f"expected={expected} actual={actual}"
            )
    return True
