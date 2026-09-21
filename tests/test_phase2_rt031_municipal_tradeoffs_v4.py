from scripts.phase2_audit_rt031_municipal_tradeoffs_v4 import classify, build_audit
import pytest


def test_exact_comparison_distinguishes_strict_total_gain_from_equality():
    baseline = {
        "exact_total_coverage": {key: "1/2" for key in ("5", "8", "10")},
        "exact_municipality_coverage": {
            "97010": {key: "1/2" for key in ("5", "8", "10")}}}
    row = {
        "exact_total_coverage": {"5": "1/2", "8": "1/2", "10": "3/5"},
        "exact_municipality_coverage": {
            "97010": {"5": "1/2", "8": "3/5", "10": "1/2"}}}
    flags = classify(row, baseline)
    assert flags["total_all_three_nonregressing_with_some_strict_gain"]
    assert flags["brivio_all_three_nonregressing"]
    assert flags["total_10min_strict_gain"]
    assert flags["brivio_10min_nonregressing"]
    row["exact_total_coverage"]["5"] = "49/100"
    assert not classify(row, baseline)[
        "total_all_three_nonregressing_with_some_strict_gain"]


def test_incomplete_frontier_fails_closed():
    with pytest.raises(ValueError, match="contract drift"):
        build_audit({"contract": "RT031_SINGLE_LINE_MUNICIPAL_ACCESS_FRONTIER_V4",
                     "frontier_count": 777})
