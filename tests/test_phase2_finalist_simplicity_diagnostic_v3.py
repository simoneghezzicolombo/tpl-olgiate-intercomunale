from scripts.phase2_build_finalist_simplicity_diagnostic_v3 import circular_gap_summary, jaccard_nonhub


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
