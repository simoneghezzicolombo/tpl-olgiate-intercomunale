from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.service_contract_integrity import (  # noqa: E402
    headway_cycle_count_audit,
    regular_pattern_departure_count_bounds,
    validate_nonoverlapping_bands,
)
from src.service_math import ServiceBandDirectionPlan, ServiceMathError  # noqa: E402


def plan(*, band_id="AM", start="06:00:00", end="09:00:00", direction="CW", headway=60, cycles=3):
    return ServiceBandDirectionPlan(
        contract_version="GATE_E_V2", scenario_id="S", service_day_group="WEEKDAY",
        band_id=band_id, band_start_time=start, band_end_time=end, direction=direction,
        analysis_mode="SENSITIVITY", upstream_gate_c_status="PASS", upstream_gate_d_status="IN_PROGRESS",
        gate_c_artifact="c.json", gate_c_commit="abc", gate_d_artifact="", gate_d_commit="",
        shared_stop_pattern_status="UNKNOWN", route_km=10, route_km_status="ASSUMPTION",
        pure_running_min=40, pure_running_status="ASSUMPTION", dwell_min=4, dwell_status="ASSUMPTION",
        recovery_min=6, recovery_status="ASSUMPTION", target_headway_min=headway,
        target_headway_status="ASSUMPTION", daily_cycles=cycles, daily_cycles_status="ASSUMPTION",
        service_days_year=300, service_days_status="ASSUMPTION",
    )


def paired(**kwargs):
    return [plan(direction="CW", **kwargs), plan(direction="CCW", **kwargs)]


def test_adjacent_bands_are_allowed_without_double_count():
    plans = paired(band_id="AM", start="06:00:00", end="09:00:00") + paired(
        band_id="MID", start="09:00:00", end="15:00:00", cycles=6
    )
    validate_nonoverlapping_bands(plans)


def test_overlapping_additive_bands_are_rejected():
    plans = paired(band_id="AM", start="06:00:00", end="10:00:00", cycles=4) + paired(
        band_id="MID", start="09:00:00", end="15:00:00", cycles=6
    )
    with pytest.raises(ServiceMathError, match="double-count"):
        validate_nonoverlapping_bands(plans)


def test_after_midnight_adjacent_bands_are_supported():
    plans = paired(band_id="LATE", start="23:00:00", end="25:00:00", cycles=2) + paired(
        band_id="NIGHT", start="25:00:00", end="27:00:00", cycles=2
    )
    validate_nonoverlapping_bands(plans)


def test_exact_regular_span_has_one_possible_departure_count():
    p = plan(start="06:00:00", end="09:00:00", headway=60, cycles=3)
    assert regular_pattern_departure_count_bounds(p) == (3, 3)
    assert headway_cycle_count_audit(p)["headway_cycle_count_audit"] == "CONSISTENT_WITH_EXACT_REGULAR_HEADWAY_FOR_SOME_PHASE"


def test_noninteger_span_allows_floor_or_ceil_due_to_phase():
    p = plan(start="06:00:00", end="09:10:00", headway=60, cycles=4)
    assert regular_pattern_departure_count_bounds(p) == (3, 4)
    assert headway_cycle_count_audit(p)["headway_cycle_count_audit"].startswith("CONSISTENT")


def test_implausibly_many_cycles_are_flagged_not_silently_accepted_as_exact_headway():
    p = plan(start="06:00:00", end="09:00:00", headway=60, cycles=13)
    audit = headway_cycle_count_audit(p)
    assert audit["headway_cycle_count_audit"] == "MORE_CYCLES_THAN_EXACT_REGULAR_HEADWAY_IMPLIES"
    assert audit["headway_cycle_count_semantics"].startswith("DIAGNOSTIC_ONLY")


def test_implausibly_few_cycles_are_flagged():
    p = plan(start="06:00:00", end="09:00:00", headway=30, cycles=2)
    assert headway_cycle_count_audit(p)["headway_cycle_count_audit"] == "FEWER_CYCLES_THAN_EXACT_REGULAR_HEADWAY_IMPLIES"
