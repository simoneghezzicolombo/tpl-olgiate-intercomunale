from __future__ import annotations

import math
from pathlib import Path

import pytest

import scripts.phase2_build_passenger_utility_frontier_v2_all_thresholds  # noqa: F401
import scripts.phase2_build_passenger_utility_frontier_v2 as pu
from src.phase2_access_equity_v2 import summarise_walk_coverage_thresholds
from src.phase2_service_policy_search import load_design_space

ROOT = Path(__file__).resolve().parents[1]


def _exact_departure_count(start: int, end: int, headway: int, phase: int) -> int:
    first = start + ((phase - start) % headway)
    return len(range(first, end, headway))


@pytest.mark.xfail(strict=True, reason="REDTEAM RT-001: continuous production is not an exact departure count")
def test_extended_span_h20_hard_budget_model_is_exact_departure_count() -> None:
    _, policies = load_design_space(ROOT / "config/phase2_service_policy_design_space_v2.json")
    policy = next(
        p for p in policies
        if p.uniform_headway_min == 20
        and p.span_id == "S8_EXTENDED_0530_2400"
        and p.calendar_id == "IDEALISED_5_DAY_52_WEEK"
        and p.recovery_min == 5
        and math.isclose(p.extension_share, 0.0)
    )
    # The production model uses 1110/20 = 55.5 pattern sets/day. An explicit
    # timetable cannot operate half a departure. This expected failure is the
    # regression witness for RT-001.
    exact_counts = {_exact_departure_count(policy.span_start_min, policy.span_end_min, 20, phase) for phase in range(20)}
    assert exact_counts == {55, 56}
    assert policy.pattern_sets_per_day_equivalent in exact_counts


def test_station_bridge_style_duplicate_catchment_does_not_double_count_population() -> None:
    summaries = summarise_walk_coverage_thresholds(
        ["rail:S01514", "existing:EX_039"],
        walk_by_anchor={
            "rail:S01514": {"unit": 3.0},
            "existing:EX_039": {"unit": 3.0},
        },
        unit_weights={"unit": 10.0},
        unit_municipality={"unit": "Olgiate Molgora"},
        municipality_totals={"Olgiate Molgora": 10.0},
        thresholds=(5, 8, 10, 12),
    )
    assert summaries[5].covered_population == 10.0
    assert summaries[5].coverage_share == 1.0


def test_missing_directional_gfa_is_worse_not_best() -> None:
    field = pu.PASSENGER_MIN_AXES[0]
    a = {field: None}
    b = {field: 12.0}
    assert pu.optional_min_compare(a, b, field) > 0
    assert pu.optional_min_compare(b, a, field) < 0


def _row(plan_id: str, value: float, *, days: int = 260, span: int = 960) -> dict[str, object]:
    row: dict[str, object] = {"plan_id": plan_id}
    for field in pu.PASSENGER_MAX_AXES:
        row[field] = value
    for field in pu.PASSENGER_MIN_AXES:
        row[field] = 10.0 - value
    row["annual_service_days"] = days
    row["span_minutes"] = span
    return row


def test_two_stage_context_dominance_cannot_resurrect_globally() -> None:
    better = _row("A", 0.8, days=312, span=1110)
    worse_same_context = _row("B", 0.7, days=312, span=1110)
    tradeoff_other_context = _row("C", 0.9, days=260, span=960)

    assert pu.dominates(better, worse_same_context, include_availability=False)
    stage1 = pu.pareto([better, worse_same_context], include_availability=False) + [tradeoff_other_context]
    staged = {r["plan_id"] for r in pu.pareto(stage1, include_availability=True)}
    direct = {r["plan_id"] for r in pu.pareto([better, worse_same_context, tradeoff_other_context], include_availability=True)}
    assert staged == direct
    assert "B" not in direct


def test_certified_passenger_axes_include_all_5_8_10_thresholds() -> None:
    axes = set(pu.PASSENGER_MAX_AXES)
    for threshold in (5, 8, 10):
        assert f"public_population_coverage_share_{threshold}min" in axes
        assert f"public_worst_municipality_coverage_share_{threshold}min" in axes
