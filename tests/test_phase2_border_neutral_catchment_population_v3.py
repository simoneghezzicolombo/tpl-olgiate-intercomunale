from __future__ import annotations

import pytest
from shapely.geometry import box

from src.phase2_border_neutral_catchment_population_v3 import (
    PopulationUnit,
    calibrate_envelope_cell_weights,
    discover_intersecting_municipality_codes,
    max_walk_distance_metres,
    municipality_calibration_factor,
    split_discovered_municipalities,
    summarize_covered_population,
)


CORE = {"A", "B"}


def test_default_walk_distance_is_960_metres():
    assert max_walk_distance_metres() == pytest.approx(960.0)


@pytest.mark.parametrize(
    "minutes,speed",
    [(0, 4.8), (-1, 4.8), (12, 0), (12, -1), (float("inf"), 4.8)],
)
def test_invalid_walk_envelope_parameters_fail(minutes, speed):
    with pytest.raises(ValueError):
        max_walk_distance_metres(minutes, speed)


def test_municipalities_are_discovered_geometrically_not_from_a_neighbor_list():
    service_area = box(0, 0, 1000, 1000)
    municipalities = {
        "A": box(0, 0, 500, 1000),
        "B": box(500, 0, 1000, 1000),
        "EDGE": box(1500, 100, 2000, 900),
        "FAR": box(3000, 0, 3500, 1000),
    }
    discovered = discover_intersecting_municipality_codes(
        service_area,
        municipalities,
        buffer_metres=960,
    )
    assert discovered == ("A", "B", "EDGE")


def test_split_preserves_core_and_reports_external_separately():
    split = split_discovered_municipalities(["EDGE", "B", "A"], core_codes=CORE)
    assert split["core"] == ("A", "B")
    assert split["external"] == ("EDGE",)
    assert split["all"] == ("A", "B", "EDGE")


def test_missing_core_municipality_fails_closed():
    with pytest.raises(ValueError, match="missing core"):
        split_discovered_municipalities(["A", "EDGE"], core_codes=CORE)


def test_calibration_factor_uses_full_municipality_worldpop_sum():
    assert municipality_calibration_factor(
        official_population_total=200,
        full_municipality_worldpop_raw_sum=100,
    ) == pytest.approx(2.0)


def test_envelope_fragment_is_not_inflated_to_full_municipality_total():
    calibrated = calibrate_envelope_cell_weights(
        {"c1": 10.0, "c2": 20.0},
        official_population_total=200.0,
        full_municipality_worldpop_raw_sum=100.0,
    )
    assert calibrated == {"c1": 20.0, "c2": 40.0}
    assert sum(calibrated.values()) == pytest.approx(60.0)
    assert sum(calibrated.values()) != pytest.approx(200.0)


def test_coverage_deduplicates_units_and_separates_spillover():
    units = [
        PopulationUnit("core_1", "A", 100.0),
        PopulationUnit("core_2", "B", 80.0),
        PopulationUnit("ext_1", "EDGE", 40.0),
        PopulationUnit("ext_2", "EDGE2", 20.0),
    ]
    summary = summarize_covered_population(
        ["core_1", "ext_1", "ext_1", "ext_2"],
        population_units=units,
        core_codes=CORE,
    )
    assert summary.core_covered_population == pytest.approx(100.0)
    assert summary.external_spillover_population == pytest.approx(60.0)
    assert summary.total_catchment_population == pytest.approx(160.0)
    assert summary.core_covered_units == 1
    assert summary.external_covered_units == 2
    assert summary.external_municipalities == ("EDGE", "EDGE2")


def test_external_population_cannot_masquerade_as_core_coverage():
    units = [
        PopulationUnit("core", "A", 1.0),
        PopulationUnit("external", "EDGE", 1000.0),
    ]
    summary = summarize_covered_population(
        ["external"], population_units=units, core_codes=CORE
    )
    assert summary.total_catchment_population == pytest.approx(1000.0)
    assert summary.external_spillover_population == pytest.approx(1000.0)
    assert summary.core_covered_population == pytest.approx(0.0)


def test_unknown_covered_unit_fails_closed():
    with pytest.raises(ValueError, match="unknown covered"):
        summarize_covered_population(
            ["missing"],
            population_units=[PopulationUnit("known", "A", 1.0)],
            core_codes=CORE,
        )


def test_duplicate_population_unit_id_fails_closed():
    units = [PopulationUnit("x", "A", 1.0), PopulationUnit("x", "EDGE", 2.0)]
    with pytest.raises(ValueError, match="unique"):
        summarize_covered_population(["x"], population_units=units, core_codes=CORE)


@pytest.mark.parametrize("weight", [-1.0, float("nan"), float("inf")])
def test_invalid_population_weights_fail_closed(weight):
    with pytest.raises(ValueError, match="weights"):
        summarize_covered_population(
            ["x"],
            population_units=[PopulationUnit("x", "A", weight)],
            core_codes=CORE,
        )
