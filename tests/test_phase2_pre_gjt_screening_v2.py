from src.phase2_pre_gjt_screening_v2 import (
    TimingKey,
    build_timing_policy_masks,
    summarise_route_timing,
)


def test_timing_policy_masks_partition_extension_state():
    rows = [
        {"policy_index": "0", "uniform_headway_min": "30", "span_id": "A", "span_start_min": "360", "span_end_min": "1320", "extension_share": "0.00"},
        {"policy_index": "1", "uniform_headway_min": "30", "span_id": "A", "span_start_min": "360", "span_end_min": "1320", "extension_share": "0.50"},
        {"policy_index": "2", "uniform_headway_min": "60", "span_id": "A", "span_start_min": "360", "span_end_min": "1320", "extension_share": "0.00"},
    ]
    masks = build_timing_policy_masks(rows)
    key = TimingKey(30, "A", 360, 1320)
    assert masks[key].count((1 << 0) | (1 << 1) | (1 << 2)) == (2, 1, 1)
    assert masks[TimingKey(60, "A", 360, 1320)].count((1 << 0) | (1 << 1) | (1 << 2)) == (1, 1, 0)


def _gap(route_id, *, roundtrip, complete, evaluated=30, best="5", worst="15"):
    return {
        "route_id": route_id,
        "uniform_headway_min": "30",
        "span_id": "A",
        "roundtrip_passenger_supported": "true" if roundtrip else "false",
        "complete_match_phase_count": str(complete),
        "evaluated_phase_count": str(evaluated),
        "best_complete_phase_weighted_mean_gap_min": best if complete else "",
        "worst_complete_phase_weighted_mean_gap_min": worst if complete else "",
    }


def test_route_timing_summary_keeps_roundtrip_and_directional_metrics_separate():
    rows = [
        _gap("R1", roundtrip=True, complete=30, best="4", worst="12"),
        _gap("R2", roundtrip=True, complete=0),
        _gap("R3", roundtrip=False, complete=15, best="2", worst="20"),
    ]
    lookup = {(r["route_id"], 30, "A"): r for r in rows}
    summary = summarise_route_timing(["R1", "R2", "R3"], timing_key=TimingKey(30, "A", 360, 1320), gap_lookup=lookup)
    assert summary.route_count == 3
    assert summary.roundtrip_route_count == 2
    assert summary.directional_only_route_count == 1
    assert summary.roundtrip_complete_route_count == 1
    assert summary.roundtrip_incomplete_route_count == 1
    assert summary.directional_complete_route_count == 1
    assert summary.roundtrip_best_min == 4.0
    assert summary.roundtrip_best_max == 4.0
    assert summary.directional_best_min == 2.0
    assert summary.directional_worst_max == 20.0


def test_missing_route_timing_fails_closed():
    try:
        summarise_route_timing(["R_missing"], timing_key=TimingKey(30, "A", 360, 1320), gap_lookup={})
    except ValueError as exc:
        assert "Missing S8 transfer-gap row" in str(exc)
    else:
        raise AssertionError("Expected missing route timing to fail closed")
