"""Tests for deterministic Phase 2 service-policy enumeration.

All numbers are TEST_FIXTURE_ONLY and are not territorial evidence.
"""
import pytest

from src.phase2_service_engine import OperatingCycle
from src.phase2_service_search import (
    ServiceWindowTemplate,
    WindowChoice,
    budget_envelopes_from_reference,
    enumerate_operating_plans,
)


def _cycles():
    return (
        OperatingCycle("WEST", ("R_W",), 10.0, 45.0, 5.0, "DERIVED"),
        OperatingCycle("EAST", ("R_E",), 12.0, 50.0, 10.0, "DERIVED"),
    )


def test_enumeration_uses_only_declared_choices_and_is_deterministic():
    templates = (
        ServiceWindowTemplate(
            "W_WEST", "WEST", "WK", 360, 480, 2,
            (WindowChoice(30, 0), WindowChoice(60, 0)),
        ),
        ServiceWindowTemplate(
            "W_EAST", "EAST", "WK", 360, 480, 2,
            (WindowChoice(30, 0), WindowChoice(60, 0)),
        ),
    )
    first = enumerate_operating_plans(
        scenario_id="S",
        cycles=_cycles(),
        templates=templates,
        budget_cap_km=10_000,
        fleet_cap=10,
        minimum_recovery_min=5,
        keep_infeasible=True,
    )
    second = enumerate_operating_plans(
        scenario_id="S",
        cycles=_cycles(),
        templates=templates,
        budget_cap_km=10_000,
        fleet_cap=10,
        minimum_recovery_min=5,
        keep_infeasible=True,
    )
    assert len(first) == 4
    assert [row.plan.plan_id for row in first] == [row.plan.plan_id for row in second]
    observed = {
        tuple(window.headway_min for window in row.plan.windows)
        for row in first
    }
    assert observed == {(30, 30), (30, 60), (60, 30), (60, 60)}


def test_operational_screening_filters_budget_and_fleet_without_utility_score():
    templates = (
        ServiceWindowTemplate(
            "W_WEST", "WEST", "WK", 360, 480, 100,
            (WindowChoice(20, 0), WindowChoice(60, 0)),
        ),
        ServiceWindowTemplate(
            "W_EAST", "EAST", "WK", 360, 480, 100,
            (WindowChoice(20, 0), WindowChoice(60, 0)),
        ),
    )
    all_rows = enumerate_operating_plans(
        scenario_id="S",
        cycles=_cycles(),
        templates=templates,
        budget_cap_km=20_000,
        fleet_cap=2,
        minimum_recovery_min=5,
        keep_infeasible=True,
    )
    feasible = [row for row in all_rows if row.operationally_feasible]
    filtered = enumerate_operating_plans(
        scenario_id="S",
        cycles=_cycles(),
        templates=templates,
        budget_cap_km=20_000,
        fleet_cap=2,
        minimum_recovery_min=5,
        keep_infeasible=False,
    )
    assert [row.plan.plan_id for row in filtered] == [row.plan.plan_id for row in feasible]
    assert len(filtered) < len(all_rows)


def test_phase_offsets_are_explicit_search_dimensions():
    templates = (
        ServiceWindowTemplate(
            "W", "WEST", "WK", 360, 480, 1,
            (WindowChoice(30, 0), WindowChoice(30, 10), WindowChoice(30, 20)),
        ),
    )
    rows = enumerate_operating_plans(
        scenario_id="S",
        cycles=(_cycles()[0],),
        templates=templates,
        budget_cap_km=10_000,
        fleet_cap=10,
        minimum_recovery_min=5,
        keep_infeasible=True,
    )
    assert len(rows) == 3
    assert {row.plan.windows[0].phase_offset_min for row in rows} == {0, 10, 20}


def test_max_plans_is_a_deterministic_safety_ceiling():
    templates = (
        ServiceWindowTemplate(
            "W", "WEST", "WK", 360, 480, 1,
            tuple(WindowChoice(value, 0) for value in (20, 30, 40, 60)),
        ),
    )
    rows = enumerate_operating_plans(
        scenario_id="S",
        cycles=(_cycles()[0],),
        templates=templates,
        budget_cap_km=10_000,
        fleet_cap=10,
        minimum_recovery_min=5,
        max_plans=2,
        keep_infeasible=True,
    )
    assert len(rows) == 2


def test_overlapping_templates_are_rejected_before_search():
    templates = (
        ServiceWindowTemplate("A", "WEST", "WK", 360, 480, 1, (WindowChoice(30),)),
        ServiceWindowTemplate("B", "WEST", "WK", 470, 600, 1, (WindowChoice(60),)),
    )
    with pytest.raises(ValueError, match="Overlapping service templates"):
        enumerate_operating_plans(
            scenario_id="S",
            cycles=(_cycles()[0],),
            templates=templates,
            budget_cap_km=10_000,
            fleet_cap=10,
            minimum_recovery_min=5,
        )


def test_budget_envelopes_are_derived_from_caller_reference_only():
    values = budget_envelopes_from_reference(100_000, (-0.2, -0.1, 0.0, 0.1, 0.2, 0.3))
    assert values == pytest.approx([80_000, 90_000, 100_000, 110_000, 120_000, 130_000])
