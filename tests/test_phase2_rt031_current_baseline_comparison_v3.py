import json
from fractions import Fraction

import pytest

from src.phase2_rt031_current_baseline_comparison_v3 import (
    compare_with_structural_subset, exact_current_stop_subset, parse_candidate_vector,
)


def cluster(cid="C", members="300001", routes="D184"):
    return {"physical_stop_cluster_id": cid, "member_stop_ids": members, "routes": routes}


def stop(sid="FROZEN::300001", native="300001", service="CONVENTIONAL_TPL"):
    return {"stop_place_id": sid, "source_native_ids": native, "service_class": service}


def candidate(values):
    return {"exact_threshold_ratios": json.dumps([str(x) for x in values])}


def test_exact_bridge_uses_shared_official_id_and_preserves_lineage():
    result = exact_current_stop_subset([cluster(members="300001;L00001")], [stop(native="X|300001")])
    assert result["mapped_stop_place_ids"] == ["FROZEN::300001"]
    assert result["mapping_rows"][0]["official_source_ids"] == ["300001"]
    assert result["mapping_method"] == "EXACT_SOURCE_NATIVE_ID_INTERSECTION_ONLY"


def test_same_name_or_location_cannot_substitute_for_exact_identity():
    with pytest.raises(ValueError, match="no exact"):
        exact_current_stop_subset([cluster()], [{**stop(native="OTHER"), "stop_name": "same"}])


def test_special_service_is_not_promoted_into_conventional_baseline():
    with pytest.raises(ValueError, match="no exact"):
        exact_current_stop_subset([cluster()], [stop(service="SPECIAL_SERVICE")])


def test_duplicate_official_identity_across_clusters_fails_closed():
    with pytest.raises(ValueError, match="multiple clusters"):
        exact_current_stop_subset([cluster("A"), cluster("B")], [stop()])


def test_exact_comparison_finds_no_broad_replacement_despite_one_better_axis():
    base = (Fraction(1, 2),) * 6
    result = compare_with_structural_subset([
        candidate((Fraction(3, 4), Fraction(1, 4), Fraction(1, 4), Fraction(1, 4), Fraction(1, 4), Fraction(1, 4))),
        candidate((Fraction(1, 4),) * 6),
    ], base)
    assert result["status"] == "NO_BROAD_ACCESS_REPLACEMENT_CASE_IN_SUPPLIED_POOL"
    assert result["candidate_strictly_broadly_superior_count"] == 0
    assert result["baseline_no_worse_than_candidate_all_six_count"] == 1


def test_equal_vector_is_not_misreported_as_strict_superiority():
    base = (Fraction(1, 3),) * 6
    result = compare_with_structural_subset([candidate(base)], base)
    assert result["candidate_no_worse_than_baseline_all_six_count"] == 1
    assert result["candidate_strictly_broadly_superior_count"] == 0


def test_exact_fraction_not_collapsed_by_float_precision():
    base = (Fraction(2**60, 2**60 + 1),) * 6
    better = (Fraction(2**60 + 1, 2**60 + 2),) * 6
    assert float(base[0]) == float(better[0])
    assert compare_with_structural_subset([candidate(better)], base)["broad_replacement_case_established"]


@pytest.mark.parametrize("value", ["not-json", json.dumps(["2"] * 6), json.dumps(["1/2"] * 5)])
def test_invalid_candidate_vector_fails_closed(value):
    with pytest.raises(ValueError, match="candidate threshold vector"):
        parse_candidate_vector({"exact_threshold_ratios": value})
