#!/usr/bin/env python3
"""Pure deterministic helpers for Phase 2 current-service baseline V4."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import hashlib
import math
import re
import unicodedata

ROUTE_SCOPE = ("D184", "D185")
REFERENCE_DATE = "2026-09-04"
FUTURE_START_DATE = "2026-09-14"
STATUS = "PASS_PHASE2_CURRENT_SERVICE_ACCESS_BASELINE_V4"
CONTRACT = "PHASE2_CURRENT_SERVICE_STRUCTURAL_PHYSICAL_STOP_BASELINE_V4"
BASELINE_SEMANTICS = (
    "OFFICIAL_PHYSICAL_STOP_UNIVERSE_WITH_ROUTE_LEVEL_CURRENT_ACTIVATION_AND_"
    "D185_ORDINARY_STRUCTURAL_BASELINE_TEMPORARY_DISRUPTION_EXCLUDED"
)
D184_ACTIVATION_STATUS = "CURRENT_ROUTE_CONFIRMED_STOP_IDENTITY_FROM_OFFICIAL_GTFS"
D185_ACTIVATION_STATUS = (
    "CURRENT_ROUTE_CONFIRMED_HISTORICAL_ORDINARY_STOP_IDENTITY_"
    "TEMPORARY_BRIDGE_DISRUPTION_EXCLUDED"
)
PDF_TIMING_ROWS_TREATED_AS_COMPLETE_STOP_UNIVERSE = False
FUTURE_2026_09_14_USED_AS_CURRENT = False
CURRENT_SERVICE_EVIDENCE_IS_RIDERSHIP = False
OLGIATE_DIAGNOSTIC_IN_CANDIDATE_OPTIMISATION = False
MAX_EQUIVALENCE_PAIR_DISTANCE_M = 100.0

_SUFFIX_RE = re.compile(r"^(?:300|L00)(\d{3})$")


def normalise_official_name(value: str) -> str:
    """Conservative equality normalisation. It is not fuzzy matching."""
    text = unicodedata.normalize("NFKD", str(value))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower().replace("’", "'")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def equivalence_suffix(stop_id: str) -> str | None:
    match = _SUFFIX_RE.fullmatch(str(stop_id).strip())
    return match.group(1) if match else None


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6_371_000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2.0) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2.0) ** 2
    return 2.0 * radius * math.asin(math.sqrt(a))


def validate_official_coordinate(lat: float, lon: float) -> None:
    if not math.isfinite(lat) or not math.isfinite(lon):
        raise ValueError("Official stop coordinate must be finite")
    if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
        raise ValueError("Official stop coordinate outside geographic bounds")


def deterministic_pattern_id(route_id: str, direction_id: str, stop_ids: tuple[str, ...]) -> str:
    payload = route_id + "|" + direction_id + "|" + "|".join(stop_ids)
    return "PAT_" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True)
class StopForClustering:
    stop_id: str
    stop_name: str
    stop_lat: float
    stop_lon: float


def cluster_stop_records(
    stops: list[StopForClustering],
    *,
    frozen_cluster_by_stop_id: dict[str, str],
) -> tuple[dict[str, str], dict[str, str]]:
    """
    Deterministic hierarchy:
    1. exact stop_id -> already certified frozen physical cluster;
    2. otherwise only explicit 300xxx/L00xxx suffix equivalence, equal
       conservatively-normalised official name and <=100 m coordinates;
    3. otherwise singleton official-GTFS physical cluster.

    No nearest-neighbour or similarity search is used.
    """
    if len({s.stop_id for s in stops}) != len(stops):
        raise ValueError("Duplicate stop_id in clustering input")
    for stop in stops:
        validate_official_coordinate(stop.stop_lat, stop.stop_lon)

    assigned: dict[str, str] = {}
    reason: dict[str, str] = {}

    for stop in sorted(stops, key=lambda x: x.stop_id):
        frozen = frozen_cluster_by_stop_id.get(stop.stop_id)
        if frozen:
            assigned[stop.stop_id] = frozen
            reason[stop.stop_id] = "EXACT_STOP_ID_TO_FROZEN_CERTIFIED_CLUSTER"

    unassigned = [s for s in stops if s.stop_id not in assigned]
    groups: dict[tuple[str, str], list[StopForClustering]] = defaultdict(list)
    for stop in unassigned:
        suffix = equivalence_suffix(stop.stop_id)
        if suffix:
            groups[(suffix, normalise_official_name(stop.stop_name))].append(stop)

    for (suffix, norm_name), members in sorted(groups.items()):
        if len(members) < 2 or not norm_name:
            continue
        if len({m.stop_id[:1] for m in members}) < 2:
            continue
        max_dist = 0.0
        for i, left in enumerate(members):
            for right in members[i + 1:]:
                max_dist = max(
                    max_dist,
                    haversine_m(left.stop_lat, left.stop_lon, right.stop_lat, right.stop_lon),
                )
        if max_dist > MAX_EQUIVALENCE_PAIR_DISTANCE_M:
            continue
        cid = f"V4_EQ_{suffix}"
        for member in sorted(members, key=lambda x: x.stop_id):
            assigned[member.stop_id] = cid
            reason[member.stop_id] = (
                "EXACT_300_L00_SUFFIX_PLUS_EXACT_NORMALISED_OFFICIAL_NAME_PLUS_COORDINATE_COMPATIBILITY"
            )

    for stop in sorted(stops, key=lambda x: x.stop_id):
        if stop.stop_id not in assigned:
            assigned[stop.stop_id] = f"V4_SINGLE_{stop.stop_id}"
            reason[stop.stop_id] = "OFFICIAL_GTFS_SINGLETON_NO_CERTIFIED_EQUIVALENCE"

    return assigned, reason


def activation_status(route_id: str) -> str:
    if route_id == "D184":
        return D184_ACTIVATION_STATUS
    if route_id == "D185":
        return D185_ACTIVATION_STATUS
    raise ValueError(f"Unsupported route {route_id!r}")


def source_role_is_current_trip_activation(role: str) -> bool:
    return role == "CURRENT_ROUTE_LEVEL_ACTIVATION_EVIDENCE"
