from __future__ import annotations

import math

from src.phase2_access_equity_v2 import (
    merge_anchor_sets,
    summarise_coverage,
    summarise_walk_coverage_thresholds,
)


def test_summarise_coverage_unions_overlapping_units_once() -> None:
    summary = summarise_coverage(
        ["A", "B"],
        by_anchor={
            "A": frozenset({"u1", "u2"}),
            "B": frozenset({"u2", "u3"}),
        },
        unit_weights={"u1": 10.0, "u2": 20.0, "u3": 30.0},
        unit_municipality={"u1": "M1", "u2": "M1", "u3": "M2"},
        municipality_totals={"M1": 30.0, "M2": 30.0},
    )
    assert math.isclose(summary.covered_population, 60.0)
    assert math.isclose(summary.coverage_share, 1.0)
    assert summary.municipality_coverage_share == {"M1": 1.0, "M2": 1.0}


def test_walk_thresholds_are_nested_and_use_minimum_stop_walk() -> None:
    summaries = summarise_walk_coverage_thresholds(
        ["B", "A"],
        walk_by_anchor={
            "A": {"u1": 7.0, "u2": 11.0},
            "B": {"u1": 4.0, "u3": 9.0},
        },
        unit_weights={"u1": 10.0, "u2": 20.0, "u3": 30.0, "u4": 40.0},
        unit_municipality={"u1": "M1", "u2": "M1", "u3": "M2", "u4": "M2"},
        municipality_totals={"M1": 30.0, "M2": 70.0},
        thresholds=(5, 8, 10, 12),
    )
    assert summaries[5].covered_population == 10.0
    assert summaries[8].covered_population == 10.0
    assert summaries[10].covered_population == 40.0
    assert summaries[12].covered_population == 60.0
    assert summaries[5].coverage_share <= summaries[8].coverage_share <= summaries[10].coverage_share <= summaries[12].coverage_share


def test_walk_summary_is_independent_of_anchor_input_order() -> None:
    kwargs = dict(
        walk_by_anchor={
            "A": {"u1": 3.0, "u2": 9.0},
            "B": {"u1": 5.0, "u3": 7.0},
        },
        unit_weights={"u1": 0.1, "u2": 0.2, "u3": 0.3},
        unit_municipality={"u1": "M1", "u2": "M1", "u3": "M2"},
        municipality_totals={"M1": 0.3, "M2": 0.3},
        thresholds=(5, 8, 10, 12),
    )
    forward = summarise_walk_coverage_thresholds(["A", "B"], **kwargs)
    reverse = summarise_walk_coverage_thresholds(["B", "A"], **kwargs)
    assert forward == reverse


def test_worst_municipality_tie_break_is_stable_lexicographic() -> None:
    summary = summarise_coverage(
        [],
        by_anchor={},
        unit_weights={"u1": 1.0, "u2": 1.0},
        unit_municipality={"u1": "B", "u2": "A"},
        municipality_totals={"B": 1.0, "A": 1.0},
    )
    assert summary.worst_municipality == "A"
    assert summary.worst_municipality_coverage_share == 0.0


def test_merge_anchor_sets_deduplicates_without_selection_semantics() -> None:
    assert merge_anchor_sets(["A", "B"], ["B", "C"]) == frozenset({"A", "B", "C"})
