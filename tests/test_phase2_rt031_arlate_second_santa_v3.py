import pytest

from scripts.phase2_probe_rt031_arlate_second_santa_v3 import target_sets


def fixture():
    return {
        "contract": "RT031_ARLATE_RETENTION_TARGET_PROBES_V3",
        "retention_subset_size": 3,
        "required_additional_current_stop_id": "FROZEN::300879",
        "probe_count": 22,
        "network_selected": False,
        "probes": [{
            "arlate_stop_id": "ASF::ARLATE_CANTINA_PIROVANO",
            "additional_current_exact_stop_ids": [
                "FROZEN::300879", "FROZEN::300487", other],
            "within_conditional_reference_cap": True,
        } for other in ("FROZEN::300398", "FROZEN::300634", "FROZEN::300956")],
    }


def test_all_three_under_reference_target_sets_are_retained():
    assert len(target_sets(fixture())) == 3


def test_diagnostic_source_change_fails_closed():
    source = fixture()
    source["probes"][0]["within_conditional_reference_cap"] = False
    with pytest.raises(ValueError, match="three under-reference"):
        target_sets(source)
