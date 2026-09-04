import pytest

from scripts.phase2_build_finalist_simplicity_diagnostic_v3 import (
    circular_gap_summary,
    finalist_alias,
    jaccard_nonhub,
    stable_stage_d_timetable_id,
)


def test_two_opposed_phases_create_half_headway_combined_spacing():
    result = circular_gap_summary([0, 30], 60)
    assert result["combined_phase_gap_minutes_json"] == "[30,30]"
    assert result["max_combined_phase_gap_min"] == 30
    assert result["min_combined_phase_gap_min"] == 30


def test_same_phase_keeps_full_headway_combined_spacing():
    result = circular_gap_summary([10, 10], 60)
    assert result["combined_phase_gap_minutes_json"] == "[60]"
    assert result["max_combined_phase_gap_min"] == 60


def test_route_overlap_excludes_station_hub():
    shared, union, ratio = jaccard_nonhub(
        ["rail:S01514", "A", "B", "rail:S01514"],
        ["rail:S01514", "B", "C", "rail:S01514"],
    )
    assert shared == 1
    assert union == 3
    assert abs(ratio - 1 / 3) < 1e-12


def test_disjoint_loops_have_zero_nonhub_overlap():
    shared, union, ratio = jaccard_nonhub(["EX_039", "A", "B"], ["EX_039", "C", "D"])
    assert shared == 0
    assert union == 4
    assert ratio == 0.0


def test_stage_d_timetable_identity_is_deterministic_and_phase_sensitive():
    a = stable_stage_d_timetable_id("INPUT-X", [0, 30])
    b = stable_stage_d_timetable_id("INPUT-X", [0, 30])
    c = stable_stage_d_timetable_id("INPUT-X", [30, 0])
    assert a == b
    assert a.startswith("D4RT001V3_")
    assert len(a) == len("D4RT001V3_") + 16
    assert a != c


def test_structural_finalist_aliases_cover_the_four_policy_labels():
    aliases = {
        finalist_alias("interlined_figure8", 960),
        finalist_alias("two_independent_loops", 960),
        finalist_alias("interlined_figure8", 1110),
        finalist_alias("two_independent_loops", 1110),
    }
    assert aliases == {"TT-FIG-16", "TT-TWO-16", "TT-FIG-18.5", "TT-TWO-18.5"}


def test_unknown_topology_alias_fails_closed():
    with pytest.raises(ValueError):
        finalist_alias("unknown_topology", 960)
