import pytest

from scripts.phase2_audit_rt031_arlate_priority_search_v3 import audit


def fixture():
    return {
        "contract": "RT031_BUDGETED_PHYSICAL_CLOSED_WALK_SEARCH_V3",
        "status": "RESOURCE_LIMIT_INCOMPLETE", "exhaustive": False,
        "search_priority_mode": "preferred_stop_count",
        "required_root_stop_id": "FROZEN::L00407",
        "conditional_span_minutes": 600,
        "execution_expansion_limit": 500000,
        "preferred_stop_ids_present_in_domain": [
            "FROZEN::300063", "FROZEN::300805",
            "ASF::ARLATE_BIVIO_PER_IL_PAESE",
            "ASF::ARLATE_CANTINA_PIROVANO"],
        "candidate_generation_priority_is_normative_selection": False,
        "final_recommendation": False,
        "distance_budget_m": "21426.73076923076923076923076",
        "expanded_states": 500000,
        "pending_heap_entries": 12,
        "candidates": [
            {"stop_set_id": "x", "available_stop_ids": [
                "FROZEN::L00407", "FROZEN::300063", "FROZEN::300805",
                "ASF::ARLATE_CANTINA_PIROVANO"],
             "minimum_found_distance_m": "20000"},
            {"stop_set_id": "y", "available_stop_ids": [
                "FROZEN::L00407", "FROZEN::300063"],
             "minimum_found_distance_m": "15000"},
        ],
    }


def test_preference_is_not_candidate_admission_filter():
    result = audit(fixture())
    assert result["physical_stop_set_count"] == 2
    assert result["brivio_santa_inner_arlate_co_present_count"] == 1
    assert result["joint_stop_set_ids"] == ["x"]
    assert result["named_stops_are_search_priority_not_admission_rule"]
    assert not result["absence_is_impossibility_proof"]


def test_exhaustive_requires_empty_pending_queue():
    source = fixture()
    source["status"] = "EXHAUSTIVE_WITHIN_DECLARED_PHYSICAL_DOMAIN"
    source["exhaustive"] = True
    with pytest.raises(ValueError, match="completion"):
        audit(source)
