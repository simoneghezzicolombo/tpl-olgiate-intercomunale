from datetime import date
from pathlib import Path

import pytest

from src.phase2_current_service_stop_timetable import (
    TimetableAmbiguity,
    _header_columns,
    _parse_clock,
    _parse_stop_rows,
    _resolve_direction,
    _unwrap_minutes,
    build_conditions,
)


def w(text, x0, top, width=10):
    return {"text": text, "x0": x0, "x1": x0 + width, "top": top}


def test_clock_normalises_dot_and_colon():
    assert _parse_clock("6.25") == "06:25"
    assert _parse_clock("19:45") == "19:45"
    assert _parse_clock("|") is None


def test_invalid_clock_fails_closed():
    with pytest.raises(TimetableAmbiguity):
        _parse_clock("08:99")


def test_header_columns_resolve_day_and_note_by_coordinates():
    words = [
        w("123456", 100, 10), w("12345", 140, 10), w("123456", 180, 10),
        w("A", 100, 22), w("B", 140, 22), w("D", 180, 22),
    ]
    columns, _ = _header_columns(words, date(2026, 9, 3))
    assert [c.note_code for c in columns] == ["A", "B", "D"]
    assert [c.active_on_reference_date for c in columns] == [True, False, True]


def test_header_ambiguous_multiple_notes_fails():
    words = [
        w("123456", 100, 10), w("123456", 140, 10),
        w("A", 100, 22), w("D", 101, 22),
    ]
    with pytest.raises(TimetableAmbiguity):
        _header_columns(words, date(2026, 9, 3))


def test_direction_requires_single_arrow_heading():
    heading, origin, terminal = _resolve_direction("x\nOLGIATE MOLGORA→RAVELLINO\ny")
    assert heading == "OLGIATE MOLGORA→RAVELLINO"
    assert origin == "OLGIATE MOLGORA"
    assert terminal == "RAVELLINO"
    with pytest.raises(TimetableAmbiguity):
        _resolve_direction("no heading")


def test_stop_rows_map_times_to_columns_without_filling_blanks():
    header = [w("123456", 100, 10), w("123456", 140, 10)]
    columns, day_top = _header_columns(header, date(2026, 9, 3))
    words = header + [
        w("STOP", 10, 40, 25), w("A", 38, 40), w("06:00", 100, 40), w("|", 140, 40),
        w("STOP", 10, 55, 25), w("B", 38, 55), w("06:10", 100, 55), w("07:10", 140, 55),
        w("SIMBOLOGIA", 10, 80, 50),
    ]
    rows = _parse_stop_rows(words, columns, day_top, 1)
    assert [r.stop_label for r in rows] == ["STOP A", "STOP B"]
    assert rows[0].values == ("06:00", None)
    assert rows[1].values == ("06:10", "07:10")


def test_stop_time_alignment_ambiguity_fails_closed():
    header = [w("123456", 100, 10), w("123456", 140, 10)]
    columns, day_top = _header_columns(header, date(2026, 9, 3))
    words = header + [
        w("STOP", 10, 40, 25), w("A", 38, 40), w("06:00", 120, 40),
        w("STOP", 10, 55, 25), w("B", 38, 55), w("06:10", 100, 55),
        w("SIMBOLOGIA", 10, 80, 50),
    ]
    with pytest.raises(TimetableAmbiguity):
        _parse_stop_rows(words, columns, day_top, 1)


def test_trip_times_must_be_monotonic():
    assert _unwrap_minutes(["23:55", "00:10"]) == [1435, 1450]
    with pytest.raises(TimetableAmbiguity):
        _unwrap_minutes(["08:30", "08:20"])


def test_d185_condition_requires_primary_source_detection():
    route = {
        "route_id": "D185",
        "url": "https://official.test/d185.pdf",
        "download_sha256": "a" * 64,
        "notes_detected": {"brivio_bridge_cantu_deviation": True},
    }
    condition = build_conditions([route])[0]
    assert condition["valid_from"] == "2026-05-04"
    assert condition["valid_to"] == "UNKNOWN_FROM_TIMETABLE_SOURCE"
    assert condition["ordinary_network_baseline_replaced"] is False


def test_d185_condition_missing_evidence_fails_closed():
    with pytest.raises(TimetableAmbiguity):
        build_conditions([{"route_id": "D185", "notes_detected": {}}])


def test_production_module_does_not_reference_forbidden_legacy_inputs():
    text = Path("src/phase2_current_service_stop_timetable.py").read_text(encoding="utf-8")
    assert "outputs/current_service_baseline.csv" not in text
    assert "scripts/05_current_service.py" not in text
    assert "np.random" not in text
