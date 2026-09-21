import pytest

from scripts.phase2_audit_rt031_arlate_retained_line_v3 import select_witnesses


def source():
    witness = {
        "arlate_stop_id": "ASF::ARLATE_CANTINA_PIROVANO",
        "additional_current_exact_stop_ids": ["a", "b", "c", "d"],
        "within_conditional_reference_cap": True,
        "minimum_witness_realization_ids": ["r1", "r2"],
        "minimum_distance_m": "20000",
        "minimum_witness_available_stop_ids": [
            "a", "b", "c", "d", "e", "ASF::ARLATE_CANTINA_PIROVANO"],
    }
    return {
        "contract": "RT031_ARLATE_RETENTION_TARGET_PROBES_V3",
        "retention_subset_size": 4, "probe_count": 32,
        "required_additional_current_stop_id": None,
        "candidate_domain_complete": False, "network_selected": False,
        "primary_selection_authorised": False,
        "runner_up_selection_authorised": False,
        "probes": [witness, {**witness,
                             "additional_current_exact_stop_ids": ["a", "b", "c", "e"]}],
    }


def test_same_path_deduplicates_without_losing_probe_targets():
    selected = select_witnesses(source())
    assert len(selected) == 1
    assert len(selected[0]["probe_target_sets"]) == 2


def test_conflicting_same_path_fails_closed():
    value = source()
    value["probes"][1]["minimum_distance_m"] = "20001"
    with pytest.raises(ValueError, match="conflicting"):
        select_witnesses(value)


def test_rovagnate_lane_is_explicitly_scoped():
    value = source()
    value["retention_subset_size"] = 3
    value["probe_count"] = 22
    value["required_additional_current_stop_id"] = "FROZEN::300879"
    assert len(select_witnesses(value, 3)) == 1
    with pytest.raises(ValueError, match="contract drift"):
        select_witnesses(value, 4)
