"""Audit current PDF timetable stop labels against official historical GTFS identities.

The current 2026-09-03 bus timetable is reconstructed from primary operator PDFs.
Those PDFs publish stop labels and ordered rows but not GTFS stop IDs or coordinates.
This module uses the validity-bounded historical official Arriva GTFS only as an
identity cross-check. It never uses historical GTFS service activation to fill the
current timetable and never forces fuzzy name matches.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata
from typing import Iterable, Mapping, Sequence


_TOKEN_RE = re.compile(r"[A-Z0-9]+")


def normalize_stop_label(value: str) -> tuple[str, ...]:
    """Return conservative comparable tokens without stop-specific aliases."""
    text = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode("ascii")
    text = text.upper()
    replacements = (
        (r"\bF\s*[.]?\s*S\s*[.]?\b", " FS "),
        (r"\bP\s*[.]?\s*ZZA\b", " PIAZZA "),
        (r"\bPZZA\b", " PIAZZA "),
    )
    for pattern, replacement in replacements:
        text = re.sub(pattern, replacement, text)
    tokens = [token for token in _TOKEN_RE.findall(text) if len(token) > 1 or token.isdigit()]
    return tuple(tokens)


def _token_matches(left: str, right: str) -> bool:
    if left == right:
        return True
    # Long municipality/name tokens may differ only by an unabbreviated suffix,
    # e.g. CALOLZIO vs CALOLZIOCORTE. Short-token prefix matches are forbidden.
    return min(len(left), len(right)) >= 5 and (left.startswith(right) or right.startswith(left))


def labels_compatible(pdf_label: str, gtfs_name: str) -> bool:
    """Conservative deterministic containment test, not edit-distance fuzzy matching."""
    pdf_tokens = normalize_stop_label(pdf_label)
    gtfs_tokens = normalize_stop_label(gtfs_name)
    if not pdf_tokens or not gtfs_tokens:
        return False
    return all(any(_token_matches(token, candidate) for candidate in gtfs_tokens) for token in pdf_tokens)


@dataclass(frozen=True)
class GtfsStop:
    stop_id: str
    stop_name: str
    stop_lat: str = ""
    stop_lon: str = ""


@dataclass(frozen=True)
class PageRow:
    route_id: str
    source_page: int
    stop_sequence_on_page: int
    stop_label_pdf: str


@dataclass(frozen=True)
class IdentityResolution:
    row: PageRow
    status: str
    stop_id: str | None
    name_candidate_ids: tuple[str, ...]
    best_pattern_match_rows: int
    tied_best_pattern_count: int


@dataclass(frozen=True)
class _PatternAlignment:
    pattern: tuple[str, ...]
    feasible_by_row: tuple[frozenset[int], ...]
    matched_rows: int


def _feasible_monotonic_positions(
    rows: Sequence[PageRow],
    pattern: Sequence[str],
    stops: Mapping[str, GtfsStop],
) -> _PatternAlignment:
    candidates: list[set[int]] = []
    for row in rows:
        positions = {
            index
            for index, stop_id in enumerate(pattern)
            if stop_id in stops and labels_compatible(row.stop_label_pdf, stops[stop_id].stop_name)
        }
        candidates.append(positions)

    matched_indices = [index for index, positions in enumerate(candidates) if positions]
    if not matched_indices:
        return _PatternAlignment(tuple(pattern), tuple(frozenset() for _ in rows), 0)

    forward: dict[int, set[int]] = {}
    previous: set[int] | None = None
    for row_index in matched_indices:
        positions = candidates[row_index]
        if previous is None:
            reachable = set(positions)
        else:
            reachable = {position for position in positions if any(prev < position for prev in previous)}
        forward[row_index] = reachable
        previous = reachable
        if not reachable:
            return _PatternAlignment(tuple(pattern), tuple(frozenset() for _ in rows), 0)

    backward: dict[int, set[int]] = {}
    following: set[int] | None = None
    for row_index in reversed(matched_indices):
        positions = candidates[row_index]
        if following is None:
            reachable = set(positions)
        else:
            reachable = {position for position in positions if any(position < nxt for nxt in following)}
        backward[row_index] = reachable
        following = reachable
        if not reachable:
            return _PatternAlignment(tuple(pattern), tuple(frozenset() for _ in rows), 0)

    feasible: list[frozenset[int]] = []
    matched_rows = 0
    for row_index in range(len(rows)):
        if row_index not in forward:
            feasible.append(frozenset())
            continue
        positions = frozenset(forward[row_index] & backward[row_index])
        feasible.append(positions)
        if positions:
            matched_rows += 1
    return _PatternAlignment(tuple(pattern), tuple(feasible), matched_rows)


def resolve_page(
    rows: Sequence[PageRow],
    *,
    route_patterns: Sequence[Sequence[str]],
    stops: Mapping[str, GtfsStop],
) -> list[IdentityResolution]:
    """Resolve one ordered PDF page without forcing ambiguous identities.

    A stop name unique within the historical route stop universe is accepted from
    name evidence alone. Ambiguous names are resolved only when the maximum-agreement
    ordered historical pattern(s) leave one stop ID. Ties across best patterns remain
    ambiguous unless they imply the same stop ID.
    """
    if not rows:
        return []
    if len({row.route_id for row in rows}) != 1 or len({row.source_page for row in rows}) != 1:
        raise ValueError("resolve_page requires one route_id and one source_page")
    if [row.stop_sequence_on_page for row in rows] != sorted(row.stop_sequence_on_page for row in rows):
        raise ValueError("PDF page rows must be ordered by stop_sequence_on_page")

    route_stop_ids = sorted({stop_id for pattern in route_patterns for stop_id in pattern if stop_id in stops})
    name_candidates: list[tuple[str, ...]] = []
    for row in rows:
        candidates = tuple(
            stop_id
            for stop_id in route_stop_ids
            if labels_compatible(row.stop_label_pdf, stops[stop_id].stop_name)
        )
        name_candidates.append(candidates)

    alignments = [
        _feasible_monotonic_positions(rows, tuple(pattern), stops)
        for pattern in route_patterns
        if pattern
    ]
    best_score = max((alignment.matched_rows for alignment in alignments), default=0)
    best = [alignment for alignment in alignments if alignment.matched_rows == best_score and best_score > 0]

    results: list[IdentityResolution] = []
    for index, row in enumerate(rows):
        candidate_ids = name_candidates[index]
        if not candidate_ids:
            results.append(IdentityResolution(row, "NO_HISTORICAL_GTFS_NAME_MATCH", None, (), best_score, len(best)))
            continue
        if len(candidate_ids) == 1:
            results.append(
                IdentityResolution(
                    row,
                    "RESOLVED_ROUTE_NAME_UNIQUE",
                    candidate_ids[0],
                    candidate_ids,
                    best_score,
                    len(best),
                )
            )
            continue

        sequence_ids: set[str] = set()
        if best_score >= 2:
            for alignment in best:
                for position in alignment.feasible_by_row[index]:
                    sequence_ids.add(alignment.pattern[position])
        sequence_ids &= set(candidate_ids)
        if len(sequence_ids) == 1:
            results.append(
                IdentityResolution(
                    row,
                    "RESOLVED_BEST_SEQUENCE_UNIQUE",
                    next(iter(sequence_ids)),
                    candidate_ids,
                    best_score,
                    len(best),
                )
            )
        else:
            results.append(
                IdentityResolution(
                    row,
                    "AMBIGUOUS_HISTORICAL_GTFS",
                    None,
                    candidate_ids,
                    best_score,
                    len(best),
                )
            )
    return results


def unique_route_patterns(
    trips: Iterable[Mapping[str, str]],
    stop_times: Iterable[Mapping[str, str]],
    route_ids: set[str],
) -> dict[str, list[tuple[str, ...]]]:
    trip_route = {
        str(row.get("trip_id", "")): str(row.get("route_id", ""))
        for row in trips
        if str(row.get("route_id", "")) in route_ids
    }
    sequences: dict[str, list[tuple[int, str]]] = {trip_id: [] for trip_id in trip_route}
    for row in stop_times:
        trip_id = str(row.get("trip_id", ""))
        if trip_id not in sequences:
            continue
        sequences[trip_id].append((int(row["stop_sequence"]), str(row["stop_id"])))

    by_route: dict[str, set[tuple[str, ...]]] = {route_id: set() for route_id in route_ids}
    for trip_id, route_id in trip_route.items():
        sequence = tuple(stop_id for _, stop_id in sorted(sequences[trip_id]))
        if sequence:
            by_route[route_id].add(sequence)
    return {route_id: sorted(patterns) for route_id, patterns in by_route.items()}
