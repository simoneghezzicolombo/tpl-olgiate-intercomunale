from scripts.phase2_audit_rt031_joint_corridor_search_v3 import audit_search
import pytest


def fixture():
    return {
        "contract": "RT031_BUDGETED_PHYSICAL_CLOSED_WALK_SEARCH_V3",
        "status": "RESOURCE_LIMIT_INCOMPLETE", "exhaustive": False,
        "search_priority_mode": "preferred_stop_count",
        "required_root_stop_id": "FROZEN::L00407",
        "conditional_span_minutes": 600,
        "execution_expansion_limit": 500000,
        "preferred_stop_ids_present_in_domain": [
            "FROZEN::300063", "FROZEN::300782", "FROZEN::300805",
            "FROZEN::300873"],
        "candidate_generation_priority_is_normative_selection": False,
        "final_recommendation": False,
        "distance_budget_m": "21426.73076923076923076923076",
        "expanded_states": 500000,
        "pending_heap_entries": 1,
        "candidates": [
            {"stop_set_id": "x", "available_stop_ids": [
                "FROZEN::L00407", "FROZEN::300063", "FROZEN::300782"],
             "minimum_found_distance_m": "20000"},
            {"stop_set_id": "y", "available_stop_ids": [
                "FROZEN::L00407", "FROZEN::300063"],
             "minimum_found_distance_m": "19000"},
        ],
    }


def test_joint_target_is_diagnostic_not_admission():
    result = audit_search(fixture())
    assert result["physical_candidate_count"] == 2
    assert result["joint_brivio_at_least_one_santa_maria_candidate_count"] == 1
    assert result["joint_candidate_stop_set_ids"] == ["x"]
    assert result["preferred_stops_are_search_priority_not_admission_rule"]
    assert result["absence_is_impossibility_proof"] is False


def test_over_cap_envelope_fails_closed():
    source = fixture()
    source["distance_budget_m"] = "21426.73076923076923076923078"
    with pytest.raises(ValueError, match="exceeds reference cap"):
        audit_search(source)


def test_exhaustive_physical_scope_does_not_claim_global_impossibility():
    source = fixture()
    source["status"] = "EXHAUSTIVE_WITHIN_DECLARED_PHYSICAL_DOMAIN"
    source["exhaustive"] = True
    source["pending_heap_entries"] = 0
    source["candidates"] = source["candidates"][1:]
    result = audit_search(source)
    assert result["search_exhaustive"] is True
    assert result["joint_brivio_at_least_one_santa_maria_candidate_count"] == 0
    assert result["absence_is_impossibility_proof"] is False
