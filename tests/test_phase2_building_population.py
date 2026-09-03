import pandas as pd

from src.phase2_building_population import (
    allocate_section_population,
    classify_building,
    derive_section_targets,
    is_fictitious_section,
    reconcile_municipal_population,
)


def test_fictitious_sections_are_detected():
    assert is_fictitious_section("0970588888881")
    assert is_fictitious_section("0970589999999")
    assert not is_fictitious_section("0970580000123")


def test_explicit_residential_and_nonresidential_are_separated():
    residential = classify_building(status_code="03", type_code="01", use_codes=["0101"])
    industrial = classify_building(status_code="03", type_code="08", use_codes=["08"])
    assert residential.eligible_primary
    assert residential.plausibility == "EXPLICIT_RESIDENTIAL"
    assert not industrial.eligible_primary
    assert not industrial.eligible_fallback
    assert industrial.plausibility == "EXPLICIT_NONRESIDENTIAL"


def test_unknown_use_is_fallback_only_and_mixed_is_primary():
    unknown = classify_building(status_code="03", type_code="-99991", use_codes=[])
    mixed = classify_building(status_code="03", type_code="01", use_codes=["0101", "07"])
    assert unknown.eligible_fallback and not unknown.eligible_primary
    assert mixed.eligible_primary and mixed.mixed_use
    assert "mixed_use_no_residential_floor_area_share" in mixed.uncertainty_flags


def test_nonconstructed_never_receives_population():
    result = classify_building(status_code="02", type_code="01", use_codes=["0101"])
    assert not result.eligible_primary
    assert not result.eligible_fallback
    assert result.plausibility == "EXCLUDED_NOT_CONSTRUCTED"


def test_section_scaling_exactly_matches_municipal_target():
    sections = pd.DataFrame({
        "municipality_code": ["A", "A", "B"],
        "section_id": ["A1", "A2", "B1"],
        "population_2023_fact": [60, 40, 80],
    })
    municipalities = pd.DataFrame({
        "municipality_code": ["A", "B"],
        "population_2025_posas_fact": [110, 100],
    })
    out = derive_section_targets(sections, municipalities)
    sums = out.groupby("municipality_code")["section_population_2025_derived"].sum()
    assert abs(sums["A"] - 110) < 1e-10
    assert abs(sums["B"] - 100) < 1e-10


def test_primary_buildings_prevent_unknown_fallback_from_receiving_people():
    targets = pd.DataFrame({
        "section_id": ["S1"],
        "section_population_2025_derived": [100.0],
        "municipality_code": ["M"],
    })
    pieces = pd.DataFrame({
        "section_id": ["S1", "S1"],
        "building_id": ["R", "U"],
        "eligible_primary": [True, False],
        "eligible_fallback": [False, True],
        "allocation_weight": [50.0, 1000.0],
    })
    allocations, residuals = allocate_section_population(pieces, targets)
    assert allocations["building_id"].tolist() == ["R"]
    assert abs(allocations["building_piece_population_model"].sum() - 100) < 1e-10
    assert residuals.loc[0, "unallocated_population"] == 0


def test_unknown_buildings_used_only_when_no_primary_exists():
    targets = pd.DataFrame({
        "section_id": ["S1"],
        "section_population_2025_derived": [90.0],
        "municipality_code": ["M"],
    })
    pieces = pd.DataFrame({
        "section_id": ["S1", "S1"],
        "building_id": ["U1", "U2"],
        "eligible_primary": [False, False],
        "eligible_fallback": [True, True],
        "allocation_weight": [1.0, 2.0],
    })
    allocations, _ = allocate_section_population(pieces, targets)
    values = dict(zip(allocations["building_id"], allocations["building_piece_population_model"]))
    assert abs(values["U1"] - 30) < 1e-10
    assert abs(values["U2"] - 60) < 1e-10
    assert set(allocations["allocation_tier"]) == {"FALLBACK_UNKNOWN_USE_ONLY"}


def test_no_plausible_building_preserves_population_as_residual():
    targets = pd.DataFrame({
        "section_id": ["S1"],
        "section_population_2025_derived": [50.0],
        "municipality_code": ["M"],
    })
    pieces = pd.DataFrame({
        "section_id": ["S1"],
        "building_id": ["N"],
        "eligible_primary": [False],
        "eligible_fallback": [False],
        "allocation_weight": [100.0],
    })
    allocations, residuals = allocate_section_population(pieces, targets)
    assert allocations.empty
    assert residuals.loc[0, "unallocated_population"] == 50
    assert residuals.loc[0, "allocation_tier"] == "UNALLOCATED_NO_PLAUSIBLE_BUILDING"


def test_reconciliation_keeps_posas_total_exact_with_residuals():
    section_targets = pd.DataFrame({
        "section_id": ["S1", "S2"],
        "municipality_code": ["M", "M"],
    })
    allocations = pd.DataFrame({
        "section_id": ["S1"],
        "building_piece_population_model": [70.0],
    })
    residuals = pd.DataFrame({
        "section_id": ["S1", "S2"],
        "unallocated_population": [0.0, 30.0],
    })
    municipalities = pd.DataFrame({
        "municipality_code": ["M"],
        "population_2025_posas_fact": [100.0],
    })
    result = reconcile_municipal_population(
        building_allocations=allocations,
        section_targets=section_targets,
        section_residuals=residuals,
        municipal_targets=municipalities,
    )
    assert result.loc[0, "reconciliation_pass"]
    assert abs(result.loc[0, "accounted_population"] - 100) < 1e-10
