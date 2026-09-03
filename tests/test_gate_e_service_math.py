from pathlib import Path
import csv
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.service_math import (  # noqa: E402
    CONTRACT_VERSION,
    GATE_E_V2_COLUMNS,
    DirectionPlan,
    ServiceBandDirectionPlan,
    ServiceMathError,
    aggregate_scenarios,
    aggregate_service_bands,
    aggregate_service_scenarios,
    annual_bus_km,
    budget_break_even_route_km,
    combined_headway_rate_equivalent,
    cycle_minutes,
    load_pdb_budget,
    minimum_vehicles_for_regular_headway,
    parse_gtfs_time_to_minutes,
    read_service_band_plans,
    vehicles_required,
)


def make_plan(direction="CW", **overrides):
    values = dict(
        contract_version=CONTRACT_VERSION,
        scenario_id="S",
        service_day_group="WEEKDAY",
        band_id="ALL_DAY",
        band_start_time="06:00:00",
        band_end_time="19:00:00",
        direction=direction,
        analysis_mode="SENSITIVITY",
        upstream_gate_c_status="IN_PROGRESS",
        upstream_gate_d_status="IN_PROGRESS",
        gate_c_artifact="",
        gate_c_commit="",
        gate_d_artifact="",
        gate_d_commit="",
        shared_stop_pattern_status="UNKNOWN",
        route_km=10.0,
        route_km_status="ASSUMPTION",
        pure_running_min=50.0,
        pure_running_status="ASSUMPTION",
        dwell_min=5.0,
        dwell_status="ASSUMPTION",
        recovery_min=5.0,
        recovery_status="ASSUMPTION",
        target_headway_min=60.0,
        target_headway_status="ASSUMPTION",
        daily_cycles=13,
        daily_cycles_status="ASSUMPTION",
        service_days_year=303,
        service_days_status="ASSUMPTION",
    )
    values.update(overrides)
    return ServiceBandDirectionPlan(**values)


def paired(**overrides):
    return [make_plan("CW", **overrides), make_plan("CCW", **overrides)]


def test_pdb_published_line_totals_are_internally_consistent():
    budget = load_pdb_budget(ROOT / "data" / "risorse_tpl_pdb.csv")
    assert budget["D184"] == 52560.0
    assert budget["D185"] == 58859.0
    assert budget["D184+D185"] == 111419.0
    assert budget["D184"] + budget["D185"] == budget["D184+D185"]


def test_pdb_component_rounding_mismatch_is_exposed_not_silently_fixed():
    budget = load_pdb_budget(ROOT / "data" / "risorse_tpl_pdb.csv")
    assert budget["D184_component_sum_delta_km"] == 0.0
    assert budget["D185_component_sum_delta_km"] == -1.0
    assert budget["D184+D185_component_sum_delta_km"] == -1.0
    assert budget["component_arithmetic_status"] == "RECONSTRUCTED_COMPONENT_ROUNDING_MISMATCH"


def test_cycle_time_keeps_running_dwell_recovery_separate():
    assert cycle_minutes(50.0, 5.0, 5.0) == 60.0


def test_negative_recovery_is_rejected():
    with pytest.raises(ServiceMathError, match="recovery_min"):
        cycle_minutes(50.0, 5.0, -1.0)


def test_60_min_cycle_one_bus_each_direction_means_60_each_not_30_each():
    cycle = cycle_minutes(50.0, 5.0, 5.0)
    assert minimum_vehicles_for_regular_headway(cycle, 60.0) == 1
    assert combined_headway_rate_equivalent(60.0, 60.0) == pytest.approx(30.0)


def test_30_min_each_direction_on_60_min_cycle_requires_four_buses_total():
    cycle = 60.0
    cw = vehicles_required(cycle, 30.0)
    ccw = vehicles_required(cycle, 30.0)
    assert cw == 2
    assert ccw == 2
    assert cw + ccw == 4
    assert combined_headway_rate_equivalent(30.0, 30.0) == pytest.approx(15.0)


def test_fleet_formula_rounds_up_at_non_integer_ratio():
    assert minimum_vehicles_for_regular_headway(61.0, 60.0) == 2
    assert minimum_vehicles_for_regular_headway(120.0, 60.0) == 2
    assert minimum_vehicles_for_regular_headway(120.0001, 60.0) == 3


def test_combined_headway_is_harmonic_service_rate_equivalent():
    assert combined_headway_rate_equivalent(60.0, 30.0) == pytest.approx(20.0)
    assert combined_headway_rate_equivalent(45.0, 90.0) == pytest.approx(30.0)


def test_combined_headway_is_always_below_each_directional_headway():
    for cw in (15.0, 30.0, 60.0, 120.0):
        for ccw in (20.0, 45.0, 90.0):
            combined = combined_headway_rate_equivalent(cw, ccw)
            assert combined < cw
            assert combined < ccw


def test_gtfs_time_parser_allows_after_midnight_hours():
    assert parse_gtfs_time_to_minutes("25:30:00") == 1530.0
    assert parse_gtfs_time_to_minutes("06:30") == 390.0


def test_invalid_time_is_rejected():
    for value in ("6", "06:60", "-1:00", "aa:00"):
        with pytest.raises(ServiceMathError):
            parse_gtfs_time_to_minutes(value)


def test_v2_assumptions_are_allowed_only_in_sensitivity():
    make_plan().validate()
    with pytest.raises(ServiceMathError, match="SENSITIVITY"):
        make_plan(analysis_mode="PRODUCTION").validate()


def test_per_metric_status_prevents_hidden_assumption():
    plan = make_plan(
        analysis_mode="PRODUCTION",
        route_km_status="DERIVED",
        pure_running_status="DERIVED",
        dwell_status="DERIVED",
        recovery_status="DERIVED",
        target_headway_status="DERIVED",
        daily_cycles_status="DERIVED",
        service_days_status="ASSUMPTION",
    )
    with pytest.raises(ServiceMathError, match="service_days_status"):
        plan.validate()


def test_passed_upstream_gate_requires_lineage_artifact_and_commit():
    with pytest.raises(ServiceMathError, match="Gate C PASS"):
        make_plan(upstream_gate_c_status="PASS").validate()
    with pytest.raises(ServiceMathError, match="Gate D PASS"):
        make_plan(upstream_gate_d_status="PASS").validate()


def test_passed_upstream_lineage_is_accepted_when_present():
    plan = make_plan(
        upstream_gate_c_status="PASS",
        upstream_gate_d_status="PASS",
        gate_c_artifact="outputs/gate_c/service_math_handoff.csv",
        gate_c_commit="abc123",
        gate_d_artifact="outputs/gate_d/route_metrics.csv",
        gate_d_commit="def456",
    )
    plan.validate()


def test_band_pair_requires_exactly_one_cw_and_one_ccw():
    with pytest.raises(ServiceMathError, match="exactly one CW and one CCW"):
        aggregate_service_bands([make_plan("CW")], 111419.0)


def test_cw_ccw_band_boundaries_must_match():
    rows = [make_plan("CW"), make_plan("CCW", band_end_time="20:00:00")]
    with pytest.raises(ServiceMathError, match="band_end_time"):
        aggregate_service_bands(rows, 111419.0)


def test_shared_stop_pattern_must_be_confirmed_before_combined_headway_is_emitted():
    row = aggregate_service_bands(paired(shared_stop_pattern_status="UNKNOWN"), 111419.0)[0]
    assert row["headway_combined_rate_equiv_min"] is None
    assert row["combined_headway_applicability"].startswith("NOT_COMPUTED")


def test_confirmed_shared_stop_pattern_allows_combined_rate_equivalent():
    row = aggregate_service_bands(
        paired(shared_stop_pattern_status="CONFIRMED"), 111419.0
    )[0]
    assert row["headway_combined_rate_equiv_min"] == pytest.approx(30.0)


def test_sensitivity_rows_can_never_be_eligible_for_gate_e_verdict():
    row = aggregate_service_scenarios(paired(), 111419.0)[0]
    assert row["gate_status"] == "SENSITIVITY_ONLY/BLOCKED_BY_GATE_C_AND_GATE_D"
    assert row["assumption_present"] is True


def test_no_assumptions_and_passed_upstream_can_become_eligible():
    statuses = dict(
        analysis_mode="PRODUCTION",
        upstream_gate_c_status="PASS",
        upstream_gate_d_status="PASS",
        gate_c_artifact="outputs/gate_c/service_math_handoff.csv",
        gate_c_commit="abc123",
        gate_d_artifact="outputs/gate_d/route_metrics.csv",
        gate_d_commit="def456",
        route_km_status="DERIVED",
        pure_running_status="DERIVED",
        dwell_status="DERIVED",
        recovery_status="DERIVED",
        target_headway_status="DERIVED",
        daily_cycles_status="DERIVED",
        service_days_status="DERIVED",
    )
    row = aggregate_service_scenarios(paired(**statuses), 111419.0)[0]
    assert row["gate_status"] == "ELIGIBLE_FOR_GATE_E_VERDICT"
    assert row["assumption_present"] is False


def test_annual_vehicle_hours_are_decomposed_and_sum_to_scheduled_total():
    metrics = make_plan().metrics()
    total = (
        metrics["annual_running_vehicle_hours"]
        + metrics["annual_dwell_vehicle_hours"]
        + metrics["annual_recovery_vehicle_hours"]
    )
    assert total == pytest.approx(metrics["annual_scheduled_vehicle_hours"])


def test_directional_cycles_are_not_silently_treated_as_pairs():
    row = aggregate_service_scenarios(paired(route_km=10.0), 111419.0)[0]
    assert row["annual_bus_km"] == 10.0 * 13 * 303 * 2


def test_asymmetric_direction_distances_are_summed_correctly():
    rows = [make_plan("CW", route_km=9.0), make_plan("CCW", route_km=11.0)]
    row = aggregate_service_scenarios(rows, 111419.0)[0]
    assert row["annual_bus_km"] == (9.0 + 11.0) * 13 * 303


def test_multi_band_scenario_sums_km_and_uses_peak_band_as_fleet_lower_bound():
    morning = paired(
        band_id="AM",
        band_start_time="06:00:00",
        band_end_time="09:00:00",
        target_headway_min=30.0,
        daily_cycles=6,
    )
    midday = paired(
        band_id="MID",
        band_start_time="09:00:00",
        band_end_time="19:00:00",
        target_headway_min=60.0,
        daily_cycles=10,
    )
    row = aggregate_service_scenarios(morning + midday, 111419.0)[0]
    expected = 10.0 * (6 + 10) * 303 * 2
    assert row["annual_bus_km"] == expected
    assert row["minimum_in_service_vehicles_scenario_lower_bound"] == 4
    assert row["service_band_count"] == 2


def test_band_cycle_count_diagnostic_flags_large_headway_count_mismatch():
    metrics = make_plan(daily_cycles=2).metrics()
    assert metrics["daily_cycles_minus_nominal_departures"] == 2 - 13
    assert metrics["cycle_count_consistency"] == "CHECK_PHASE_OR_BAND_BOUNDARIES"


def test_budget_break_even_route_km_is_exact_inverse_of_cycle_count():
    budget = 111419.0
    cycles = 7878
    route_km = budget_break_even_route_km(budget, cycles)
    assert route_km * cycles == pytest.approx(budget)


def test_annual_bus_km_is_monotone_in_distance_cycles_and_days():
    base = annual_bus_km(10.0, 10, 300)
    assert annual_bus_km(11.0, 10, 300) > base
    assert annual_bus_km(10.0, 11, 300) > base
    assert annual_bus_km(10.0, 10, 301) > base


def test_legacy_v1_still_rejects_assumption_outside_sensitivity():
    p = DirectionPlan(
        "S", "CW", "ASSUMPTION", "PRODUCTION", "PASS", "PASS",
        1.0, 50.0, 5.0, 5.0, 60.0, 1, 1,
    )
    with pytest.raises(ServiceMathError, match="SENSITIVITY"):
        p.validate()


def test_legacy_v1_upstream_nonpass_forces_provisional_gate_status():
    plans = [
        DirectionPlan("S", "CW", "ASSUMPTION", "SENSITIVITY", "IN_PROGRESS", "IN_PROGRESS", 1.0, 50, 5, 5, 60, 1, 1),
        DirectionPlan("S", "CCW", "ASSUMPTION", "SENSITIVITY", "IN_PROGRESS", "IN_PROGRESS", 1.0, 50, 5, 5, 60, 1, 1),
    ]
    row = aggregate_scenarios(plans, 111419.0)[0]
    assert row["gate_status"] == "PROVISIONAL/BLOCKED_BY_GATE_C_AND_GATE_D"
    assert row["minimum_in_service_vehicles_total"] == 2


def write_v2_csv(path, plans):
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=GATE_E_V2_COLUMNS)
        writer.writeheader()
        for plan in plans:
            writer.writerow({column: getattr(plan, column) for column in GATE_E_V2_COLUMNS})


def test_v2_reader_rejects_missing_columns(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("scenario_id,direction\nS,CW\n", encoding="utf-8")
    with pytest.raises(ServiceMathError, match="Missing Gate E V2"):
        read_service_band_plans(path)


def test_v2_reader_roundtrip(tmp_path):
    path = tmp_path / "input.csv"
    write_v2_csv(path, paired())
    rows = read_service_band_plans(path)
    assert len(rows) == 2
    assert {row.direction for row in rows} == {"CW", "CCW"}


def test_service_script_has_no_legacy_recommendation_constants():
    text = (ROOT / "scripts" / "10_service_simulation.py").read_text(encoding="utf-8")
    forbidden = ["SCENARI_SIMULATI", "SOLUZIONE OTTIMALE", "Raccomandato", "111419.0"]
    for token in forbidden:
        assert token not in text


def test_benchmark_only_exposes_one_km_component_discrepancy(tmp_path):
    out = tmp_path / "budget.csv"
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "10_service_simulation.py"), "--benchmark-only", "--budget-output", str(out)],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert proc.returncode == 0, proc.stderr
    text = out.read_text(encoding="utf-8")
    assert "111419" in text
    assert "-1.0" in text
    assert "ROUNDING_MISMATCH" in proc.stdout


def test_missing_input_blocks_scenario_generation(tmp_path):
    out = tmp_path / "scenario.csv"
    proc = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "10_service_simulation.py"),
            "--input",
            str(tmp_path / "missing.csv"),
            "--output",
            str(out),
            "--budget-output",
            str(tmp_path / "budget.csv"),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert proc.returncode == 2
    assert "BLOCKED_BY_GATE_C_AND_D" in proc.stderr
    assert not out.exists()


def test_validate_only_accepts_valid_v2_without_writing_scenario_output(tmp_path):
    source = tmp_path / "input.csv"
    write_v2_csv(source, paired())
    out = tmp_path / "scenario.csv"
    proc = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "10_service_simulation.py"),
            "--input",
            str(source),
            "--validate-only",
            "--output",
            str(out),
            "--budget-output",
            str(tmp_path / "budget.csv"),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert "input valid" in proc.stdout
    assert not out.exists()


def test_write_template_matches_machine_contract(tmp_path):
    out = tmp_path / "template.csv"
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "10_service_simulation.py"), "--write-template", str(out)],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert proc.returncode == 0, proc.stderr
    header = next(csv.reader(out.open(encoding="utf-8")))
    assert tuple(header) == GATE_E_V2_COLUMNS
