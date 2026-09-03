"""Complete stop x timetable-column representation for the Phase 2 current service.

This module never interpolates an unpublished time and never converts a blank
PDF timetable cell into a stop call. Only cells backed by an explicit published
clock time are time-usable for scheduled GJT. Explicit source notes, such as the
D185 CISANO Sosta suspension, may override an otherwise unknown blank cell.
"""
from __future__ import annotations

from collections import defaultdict


class CurrentServiceMatrixAmbiguity(RuntimeError):
    """Raised if parsed timetable records cannot be assembled one-to-one."""


def _normalise_label(value: str) -> str:
    return " ".join(value.upper().replace("'", "").split())


def enrich_trip_identity(trips: list[dict], stop_times: list[dict]) -> list[dict]:
    """Add actual first/last published stop labels without inventing operator IDs."""
    by_trip: dict[str, list[dict]] = defaultdict(list)
    for row in stop_times:
        by_trip[str(row["trip_id"])].append(row)
    output: list[dict] = []
    for source in trips:
        trip = dict(source)
        timed = sorted(by_trip.get(str(trip["trip_id"]), []), key=lambda row: int(row["trip_stop_sequence"]))
        if len(timed) < 2:
            raise CurrentServiceMatrixAmbiguity(f"{trip['trip_id']}: fewer than two published timed stops")
        trip["trip_first_published_stop_label"] = timed[0]["stop_label_pdf"]
        trip["trip_last_published_stop_label"] = timed[-1]["stop_label_pdf"]
        trip["operator_trip_id"] = ""
        trip["trip_identity_semantics"] = "RECONSTRUCTED_TIMETABLE_COLUMN_ID_NOT_OPERATOR_TRIP_ID"
        trip["page_direction_semantics"] = "PUBLISHED_PAGE_ORIENTATION_NOT_NECESSARILY_TRIP_ENDPOINTS"
        output.append(trip)
    return output


def build_complete_cell_matrix(
    trips: list[dict],
    stop_times: list[dict],
    page_stops: list[dict],
    temporary_conditions: list[dict],
) -> list[dict]:
    """Return one record for every parsed PDF stop row x timetable column.

    Cell states:
    - PUBLISHED_TIME: explicit clock time in the primary PDF, usable for scheduled GJT.
    - EXPLICITLY_SUSPENDED_STOP: primary-source temporary condition says the stop is suspended.
    - OUTSIDE_PUBLISHED_TIMED_SPAN: row lies before the first or after the last timed row in the column.
    - NO_PUBLISHED_TIME_WITHIN_COLUMN_SPAN: no clock time is published although the row lies between
      timed rows. The workstream deliberately does not decide whether the vehicle passes, calls or
      bypasses that location without further evidence.
    """
    trip_keys: dict[tuple[str, int, int], dict] = {}
    for trip in trips:
        key = (str(trip["route_id"]), int(trip["source_page"]), int(trip["source_column"]))
        if key in trip_keys:
            raise CurrentServiceMatrixAmbiguity(f"Duplicate timetable column {key}")
        trip_keys[key] = trip

    stop_keys: dict[tuple[str, int, int], dict] = {}
    for stop in page_stops:
        key = (str(stop["route_id"]), int(stop["source_page"]), int(stop["stop_sequence_on_page"]))
        if key in stop_keys:
            raise CurrentServiceMatrixAmbiguity(f"Duplicate PDF stop row {key}")
        stop_keys[key] = stop

    timed_index: dict[tuple[str, int], dict] = {}
    timed_by_trip: dict[str, list[dict]] = defaultdict(list)
    for row in stop_times:
        key = (str(row["trip_id"]), int(row["pdf_row_sequence"]))
        if key in timed_index:
            raise CurrentServiceMatrixAmbiguity(f"Duplicate published time {key}")
        timed_index[key] = row
        timed_by_trip[str(row["trip_id"])].append(row)

    suspended_labels: set[tuple[str, str]] = set()
    for condition in temporary_conditions:
        if condition.get("condition_type") == "TEMPORARY_DEVIATION_AND_STOP_SUSPENSION" and bool(condition.get("reference_date_active")):
            if str(condition.get("route_id")) == "D185" and condition.get("stop_effect") == "CISANO_SOSTA_SUSPENDED":
                suspended_labels.add(("D185", "CISANO SOSTA"))

    output: list[dict] = []
    pages = sorted({(route, page) for route, page, _ in trip_keys})
    for route_id, page in pages:
        page_trips = sorted(
            (trip for (route, p, _), trip in trip_keys.items() if route == route_id and p == page),
            key=lambda trip: int(trip["source_column"]),
        )
        page_rows = sorted(
            (stop for (route, p, _), stop in stop_keys.items() if route == route_id and p == page),
            key=lambda stop: int(stop["stop_sequence_on_page"]),
        )
        if not page_trips or not page_rows:
            raise CurrentServiceMatrixAmbiguity(f"{route_id} page {page}: missing trips or stop rows")

        for trip in page_trips:
            trip_id = str(trip["trip_id"])
            timed_rows = timed_by_trip.get(trip_id, [])
            if len(timed_rows) < 2:
                raise CurrentServiceMatrixAmbiguity(f"{trip_id}: incomplete timed-stop sequence")
            timed_sequences = [int(row["pdf_row_sequence"]) for row in timed_rows]
            first_timed = min(timed_sequences)
            last_timed = max(timed_sequences)
            for stop in page_rows:
                row_sequence = int(stop["stop_sequence_on_page"])
                timed = timed_index.get((trip_id, row_sequence))
                label_key = (route_id, _normalise_label(str(stop["stop_label_pdf"])))
                if timed is not None:
                    if label_key in suspended_labels:
                        raise CurrentServiceMatrixAmbiguity(
                            f"{trip_id}: primary PDF publishes a time at explicitly suspended stop {stop['stop_label_pdf']}"
                        )
                    cell_state = "PUBLISHED_TIME"
                    published_time = timed["published_time"]
                    service_minutes = timed["service_minutes"]
                    time_usable = True
                elif label_key in suspended_labels:
                    cell_state = "EXPLICITLY_SUSPENDED_STOP"
                    published_time = ""
                    service_minutes = ""
                    time_usable = False
                elif row_sequence < first_timed or row_sequence > last_timed:
                    cell_state = "OUTSIDE_PUBLISHED_TIMED_SPAN"
                    published_time = ""
                    service_minutes = ""
                    time_usable = False
                else:
                    cell_state = "NO_PUBLISHED_TIME_WITHIN_COLUMN_SPAN"
                    published_time = ""
                    service_minutes = ""
                    time_usable = False

                output.append({
                    "route_id": route_id,
                    "trip_id": trip_id,
                    "source_page": page,
                    "source_column": int(trip["source_column"]),
                    "active_on_reference_date": bool(trip["active_on_reference_date"]),
                    "direction_heading": trip["direction_heading"],
                    "stop_sequence_on_page": row_sequence,
                    "stop_label_pdf": stop["stop_label_pdf"],
                    "cell_state": cell_state,
                    "published_time": published_time,
                    "service_minutes": service_minutes,
                    "time_usable_for_scheduled_gjt": time_usable,
                    "unpublished_time_interpolated": False,
                    "source_url": stop["source_url"],
                    "source_pdf_sha256": stop["source_pdf_sha256"],
                    "epistemic_status": (
                        "RECONSTRUCTED_FROM_OFFICIAL_PRIMARY_TIMETABLE"
                        if cell_state == "PUBLISHED_TIME"
                        else "RECONSTRUCTED_CELL_STATE_NO_TIME_INFERENCE"
                    ),
                })

    expected_cells = 0
    for route_id, page in pages:
        n_trips = sum(1 for route, p, _ in trip_keys if route == route_id and p == page)
        n_stops = sum(1 for route, p, _ in stop_keys if route == route_id and p == page)
        expected_cells += n_trips * n_stops
    if len(output) != expected_cells:
        raise CurrentServiceMatrixAmbiguity(f"Cell matrix cardinality mismatch {len(output)} != {expected_cells}")
    if sum(row["cell_state"] == "PUBLISHED_TIME" for row in output) != len(stop_times):
        raise CurrentServiceMatrixAmbiguity("Published stop-time rows do not map one-to-one into the complete cell matrix")
    return output
