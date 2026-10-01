import pytest

from scripts.phase2_audit_rt031_arlate_second_santa_line_v3 import selected_rows


def fixture():
    row = {
        "within_conditional_reference_cap": True,
        "minimum_witness_realization_ids": ["r1"],
        "minimum_witness_retained_current_exact_stop_count": 7,
        "minimum_witness_available_stop_ids": [
            "FROZEN::300782", "FROZEN::300805"],
    }
    return {
        "contract": "RT031_ARLATE_ROVAGNATE_SECOND_SANTA_PROBES_V3",
        "probe_count": 9, "under_reference_count": 2,
        "network_selected": False,
        "primary_selection_authorised": False,
        "runner_up_selection_authorised": False,
        "probes": [row, {**row, "minimum_witness_realization_ids": ["r2"]}],
    }


def test_two_distinct_paths_are_required():
    assert len(selected_rows(fixture())) == 2
    source = fixture()
    source["probes"][1]["minimum_witness_realization_ids"] = ["r1"]
    with pytest.raises(ValueError, match="distinct"):
        selected_rows(source)
