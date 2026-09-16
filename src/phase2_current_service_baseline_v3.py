"""Conservative current-service PDF-row -> Stop Universe V2 physical-cluster bridge.

This module does not infer current service from GTFS. Current service activation
remains established only by the audited operator PDF rows. Stop Universe V2 is
used as a validity-bounded official identity/coordinate cross-check.

The V3 bridge supplements the existing historical-GTFS identity cross-check only
for rows that had *no historical GTFS name match*. It never overrides an
ambiguous historical match. A V2 route-name bridge is accepted only when:

* the V2 stop explicitly references the same route;
* the official V2 stop name has at least three normalized tokens;
* every official-name token is conservatively contained in the PDF label using
  the already-certified token matcher; and
* every compatible V2 record belongs to one physical cluster.

No edit distance, coordinate-nearest search, distance tolerance, manual alias map
or route-specific whitelist is used.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

from src.phase2_current_service_stop_identity import labels_compatible, normalize_stop_label


@dataclass(frozen=True)
class V2OfficialStop:
    stop_id: str
    stop_name: str
    physical_cluster_id: str
    route_ids: frozenset[str]


def parse_route_ids(value: str) -> frozenset[str]:
    return frozenset(part.strip() for part in str(value).split("|") if part.strip())


def make_v2_stops(rows: Iterable[Mapping[str, str]]) -> tuple[V2OfficialStop, ...]:
    stops: list[V2OfficialStop] = []
    for row in rows:
        stop_id = str(row.get("stop_id", "")).strip()
        stop_name = str(row.get("stop_name", "")).strip()
        cluster = str(row.get("physical_cluster_id", "")).strip()
        routes = parse_route_ids(str(row.get("official_routes_reference_gtfs", "")))
        if not stop_id or not stop_name or not cluster:
            raise ValueError("V2 official-stop rows require stop_id, stop_name and physical_cluster_id")
        stops.append(V2OfficialStop(stop_id, stop_name, cluster, routes))
    if not stops:
        raise ValueError("V2 official-stop universe is empty")
    return tuple(stops)


def v2_name_subset_cluster(
    *,
    route_id: str,
    pdf_label: str,
    stops: Iterable[V2OfficialStop],
) -> tuple[str, tuple[str, ...], tuple[str, ...]] | None:
    """Return one physical cluster only for a strong, route-bounded name subset.

    ``labels_compatible(official_name, pdf_label)`` intentionally reverses the
    historical resolver's direction: every official token must occur in the PDF
    label, while the PDF may contain extra address qualifiers such as ``VIA COMO``
    or ``INCROCIO``. Requiring >=3 official tokens prevents generic one-word labels
    such as HOE or BEVERATE from being promoted.
    """
    matches = [
        stop
        for stop in stops
        if route_id in stop.route_ids
        and len(normalize_stop_label(stop.stop_name)) >= 3
        and labels_compatible(stop.stop_name, pdf_label)
    ]
    if not matches:
        return None
    clusters = {stop.physical_cluster_id for stop in matches}
    if len(clusters) != 1:
        return None
    cluster = next(iter(clusters))
    return (
        cluster,
        tuple(sorted(stop.stop_id for stop in matches)),
        tuple(sorted({stop.stop_name for stop in matches})),
    )


def localize_identity_rows_v3(
    identity_rows: Iterable[Mapping[str, str]],
    *,
    v2_stops: Iterable[V2OfficialStop],
    route_scope: frozenset[str] = frozenset({"D184", "D185"}),
) -> list[dict[str, str]]:
    stops = tuple(v2_stops)
    by_id = {stop.stop_id: stop for stop in stops}
    output: list[dict[str, str]] = []

    for source in identity_rows:
        route_id = str(source.get("route_id", "")).strip()
        if route_id not in route_scope:
            continue
        identity_status = str(source.get("identity_status", "")).strip()
        historical_id = str(source.get("historical_gtfs_stop_id", "")).strip()
        cluster = ""
        status = ""
        evidence_ids: tuple[str, ...] = ()
        evidence_names: tuple[str, ...] = ()

        # Preserve the already-certified exact historical-ID -> V2 join whenever it exists.
        if identity_status.startswith("RESOLVED_") and historical_id:
            stop = by_id.get(historical_id)
            if stop is not None:
                cluster = stop.physical_cluster_id
                status = "LOCALIZED_EXACT_RESOLVED_GTFS_ID_TO_V2_CLUSTER"
                evidence_ids = (stop.stop_id,)
                evidence_names = (stop.stop_name,)
            else:
                status = "RESOLVED_GTFS_ID_NOT_IN_V2_STOP_UNIVERSE"
        elif identity_status == "NO_HISTORICAL_GTFS_NAME_MATCH":
            bridge = v2_name_subset_cluster(
                route_id=route_id,
                pdf_label=str(source.get("stop_label_pdf", "")),
                stops=stops,
            )
            if bridge is not None:
                cluster, evidence_ids, evidence_names = bridge
                status = "LOCALIZED_V2_ROUTE_NAME_SUBSET_UNIQUE_PHYSICAL_CLUSTER"
            else:
                status = "NO_HISTORICAL_MATCH_AND_NO_UNIQUE_V2_ROUTE_NAME_CLUSTER"
        else:
            # Historical ambiguity remains a hard ambiguity. V3 never uses another
            # source to overrule an already-demonstrated ambiguous identity set.
            status = "HISTORICAL_AMBIGUITY_NOT_SPATIALLY_USED"

        output.append({
            "route_id": route_id,
            "source_page": str(source.get("source_page", "")),
            "stop_sequence_on_page": str(source.get("stop_sequence_on_page", "")),
            "stop_label_pdf": str(source.get("stop_label_pdf", "")),
            "identity_status": identity_status,
            "historical_gtfs_stop_id": historical_id,
            "v2_physical_cluster_id": cluster,
            "localization_status": status,
            "v2_bridge_stop_ids": "|".join(evidence_ids),
            "v2_bridge_stop_names": "|".join(evidence_names),
        })
    return output
