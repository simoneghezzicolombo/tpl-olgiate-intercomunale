from src.phase2_final_operational_robustness_v2 import ConnectionCandidate, ExactTrip
from src.phase2_stage_f_engineering_robustness_rt001_v3 import (
    RouteStressMeta,
    audit_stressed_blocks,
    fixed_target_retained,
    retained_count_from_sorted_slacks,
)


def meta(public=20.0, cycle=25.0, stops=4, b2r=True):
    return RouteStressMeta("R", public, cycle, stops, b2r)


def candidate(ctype="BUS_TO_RAIL", slack=4.0, target=True):
    return ConnectionCandidate(
        connection_id="C", stage_d_input_id="T", scenario_id="S", route_id="R",
        connection_type=ctype, direction="MILANO", profile_id="MID",
        transfer_walk_min=2.0, source_event_id="SRC", source_time_min=100.0,
        planned_target_event_id="TARGET" if target else None,
        planned_target_time_min=106.0 if target else None,
        nominal_slack_min=slack if target else None,
    )


def trip(ordinal, dep, block=0):
    return ExactTrip(
        stage_d_input_id="T", scenario_id="S", route_id="R", trip_ordinal=ordinal,
        hub_departure_min=dep, public_hub_return_min=dep+20.0,
        vehicle_hub_return_min=dep+25.0, block_by_recovery={5:block,10:block,15:block},
    )


def test_bus_to_rail_uses_same_frozen_target_under_runtime_and_rail_shift():
    c=candidate(slack=4.0)
    m=meta(public=20.0,cycle=25.0,stops=0)
    assert fixed_target_retained(c,route_meta=m,runtime_multiplier=1.0,dwell_per_stop_min=0,rail_clock_shift_min=0) is True
    assert fixed_target_retained(c,route_meta=m,runtime_multiplier=1.25,dwell_per_stop_min=0,rail_clock_shift_min=0) is False
    # The same TARGET can become reachable again only because that same train is shifted +5.
    assert fixed_target_retained(c,route_meta=m,runtime_multiplier=1.25,dwell_per_stop_min=0,rail_clock_shift_min=5) is True


def test_rail_to_bus_retention_does_not_depend_on_bus_runtime_when_departure_is_clockface_fixed():
    c=candidate(ctype="RAIL_TO_BUS",slack=4.0)
    m=meta()
    assert fixed_target_retained(c,route_meta=m,runtime_multiplier=0.9,dwell_per_stop_min=0,rail_clock_shift_min=5) is False
    assert fixed_target_retained(c,route_meta=m,runtime_multiplier=1.1,dwell_per_stop_min=1,rail_clock_shift_min=5) is False
    assert fixed_target_retained(c,route_meta=m,runtime_multiplier=1.1,dwell_per_stop_min=1,rail_clock_shift_min=-5) is True


def test_unmatched_nominal_connection_remains_unmatched_not_rebound():
    c=candidate(target=False)
    assert fixed_target_retained(c,route_meta=meta(),runtime_multiplier=1.0,dwell_per_stop_min=0,rail_clock_shift_min=0) is None


def test_sorted_slack_count_is_exact_at_boundary():
    slacks=[0.0,2.0,4.0,8.0]
    assert retained_count_from_sorted_slacks(slacks,4.0)==2
    assert retained_count_from_sorted_slacks(slacks,0.0)==4
    assert retained_count_from_sorted_slacks(slacks,9.0)==0


def test_dwell_is_applied_per_nonhub_public_stop_occurrence():
    m=meta(public=20.0,cycle=25.0,stops=4)
    assert m.public_runtime_stressed(1.0,0.5)==22.0
    assert m.cycle_runtime_stressed(1.1,1.0)==31.5


def test_block_stress_can_require_extra_vehicle_without_changing_nominal_assignment():
    # With recovery=5, nominal 25-minute cycles fit two 30-minute-spaced departures on one block.
    trips=[trip(0,0,0),trip(1,30,0)]
    nominal=audit_stressed_blocks(trips,{"R":meta(public=20,cycle=25,stops=0)},runtime_multiplier=1.0,dwell_per_stop_min=0,recovery_min=5)
    assert nominal["minimum_vehicle_requirement"]==1
    assert nominal["nominal_block_assignment_infeasible_under_case"] is False
    stressed=audit_stressed_blocks(trips,{"R":meta(public=20,cycle=25,stops=0)},runtime_multiplier=1.1,dwell_per_stop_min=0,recovery_min=5)
    assert stressed["minimum_vehicle_requirement"]==2
    assert stressed["minimum_additional_vehicle_requirement"]==1
    assert stressed["nominal_block_assignment_infeasible_under_case"] is True


def test_technical_route_metadata_does_not_create_passenger_semantics():
    m=meta(b2r=False)
    m.validate()
    assert m.bus_to_rail_passenger_event_supported is False
