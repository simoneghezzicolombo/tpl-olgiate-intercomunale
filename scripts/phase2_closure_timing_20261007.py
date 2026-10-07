"""Read-only operating budgets for the fixed 16-trip design, not certification.

Running, non-FS dwell, intermediate FS dwell/hold and terminal recovery are
separate costs. No reserve is selected. Last trips have no next-use deadline.
Run with python -m scripts.phase2_closure_timing_20261007 (JSON on stdout).
"""
import hashlib
import json
import math
from pathlib import Path

BASE = Path(__file__).resolve().parents[1] / 'outputs/phase2/rt031_line8_local_shortcuts_v3'
FS_DWELL_ASSUMPTION_MIN = 1.0
STARTS = [365, 395, 425, 455, 485, 540, 600, 715, 820, 940, 1000, 1030, 1060, 1090, 1120, 1180]
MIDS = [420, 450, 480, 510, 540, 595, 650, 770, 875, 995, 1055, 1085, 1115, 1145, 1175, 1230]


def canonical_sha256(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()


def nonnegative(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise ValueError('Finite nonnegative numeric minutes required')
    return value


def budgets(case, counts):
    """Derive constraints for this exact block assignment; no reblocking."""
    dwell = nonnegative(case['dwell_min'])
    recovery = nonnegative(case['terminal_recovery_min'])
    rows = []
    for vehicle in case['vehicles']:
        trips = vehicle['trips']
        if vehicle['complete_trip_numbers'] != [t['full_trip_number'] for t in trips]:
            raise ValueError('Block trip identity differs')
        for index, trip in enumerate(trips):
            number = trip['full_trip_number']
            if type(number) is not int or not 1 <= number <= 16:
                raise ValueError('Invalid fixed trip identity')
            start, mid = trip['fs_start_min'], trip['intermediate_fs_departure_min']
            if (start, mid) != (STARTS[number-1], MIDS[number-1]):
                raise ValueError('Fixed timetable drift')
            east = trip['intermediate_fs_arrival_min'] - start
            west = trip['fs_end_min'] - mid
            east_dwell, west_dwell = counts['east_A']*dwell, counts['west_B']*dwell
            east_running = nonnegative(east-east_dwell)
            west_running = nonnegative(west-west_dwell)
            hold = mid-trip['intermediate_fs_arrival_min']
            if hold < FS_DWELL_ASSUMPTION_MIN-1e-8:
                raise ValueError('Inherited intermediate FS dwell infeasible')
            if not math.isclose(trip['released_after_terminal_recovery_min'], trip['fs_end_min']+recovery, abs_tol=1e-8):
                raise ValueError('Recovery accounting differs')
            next_start = trips[index+1]['fs_start_min'] if index+1 < len(trips) else None
            next_budget = next_start-mid if next_start is not None else None
            if next_budget is not None and west+recovery > next_budget+1e-8:
                raise ValueError('Block reuse precedes release')
            rows.append(dict(full_trip_number=number, model_vehicle_id=vehicle['model_vehicle_id'],
                fs_start_min=start, fixed_intermediate_departure_min=mid,
                east_running_min=east_running, east_nonfs_dwell_min=east_dwell,
                east_running_plus_nonfs_dwell_budget_min=mid-start-FS_DWELL_ASSUMPTION_MIN,
                intermediate_fs_dwell_assumption_min=FS_DWELL_ASSUMPTION_MIN,
                intermediate_fs_hold_after_assumed_dwell_min=hold-FS_DWELL_ASSUMPTION_MIN,
                west_running_min=west_running, west_nonfs_dwell_min=west_dwell,
                west_scenario_arrival_budget_min=west,
                terminal_recovery_assumption_min=recovery,
                next_same_model_vehicle_departure_min=next_start,
                west_running_plus_dwell_plus_recovery_next_use_budget_min=next_budget,
                next_use_headroom_min=None if next_budget is None else next_budget-west-recovery))
    if sorted(r['full_trip_number'] for r in rows) != list(range(1, 17)):
        raise ValueError('Omitted or duplicate full trip')
    return sorted(rows, key=lambda r: r['full_trip_number'])


def check_measurement(row, *, east_running_min, east_nonfs_dwell_min,
                      intermediate_fs_dwell_min, west_running_min,
                      west_nonfs_dwell_min, terminal_recovery_min):
    """Arithmetic of a declared observation, without accepting rail/duty legality.

    FS dwell is the minimum necessary dwell, not the entire scheduled hold.
    Reserve, if desired, must be declared separately by the decision maker.
    """
    values = [east_running_min, east_nonfs_dwell_min, intermediate_fs_dwell_min,
              west_running_min, west_nonfs_dwell_min, terminal_recovery_min]
    for value in values:
        nonnegative(value)
    east_slack = row['fixed_intermediate_departure_min']-row['fs_start_min']-sum(values[:3])
    west = west_running_min+west_nonfs_dwell_min
    next_budget = row['west_running_plus_dwell_plus_recovery_next_use_budget_min']
    next_slack = None if next_budget is None else next_budget-west-terminal_recovery_min
    return dict(intermediate_departure_slack_min=east_slack,
                meets_fixed_intermediate_departure=east_slack >= 0,
                west_scenario_arrival_slack_min=row['west_scenario_arrival_budget_min']-west,
                next_use_slack_min=next_slack,
                meets_next_use=None if next_slack is None else next_slack >= 0,
                physical_operation_certified=False, rail_connection_certified=False)


def verify_sources(blocks, handoff, *, blocks_producer=None, handoff_producer=None):
    """Authenticate entire saved objects, rather than trusting their references.

    Injectable producers support isolated fixtures; production uses existing
    read-only builders. Their main/output-writing entry points are never called.
    """
    if blocks_producer is None:
        from scripts.phase2_complete_rt031_current_design_evidence_v3 import build as blocks_producer
    if handoff_producer is None:
        from scripts.phase2_package_rt031_confirmed_design_handoff_v3 import build as handoff_producer
    for name, saved, producer in [('blocks', blocks, blocks_producer), ('handoff', handoff, handoff_producer)]:
        if canonical_sha256(saved) != canonical_sha256(producer()):
            raise ValueError(f'Entire saved {name} differs from verified producer')


def build(base=BASE, *, blocks_producer=None, handoff_producer=None):
    names = ['caller_confirmed_vehicle_blocks_accounting_20261001.json',
             'caller_confirmed_design_handoff_20261001.json', 'calco_centre_adopted_design.json']
    blocks, handoff, design = [json.loads((base/name).read_text(encoding='utf-8')) for name in names]
    verify_sources(blocks, handoff, blocks_producer=blocks_producer, handoff_producer=handoff_producer)
    for name, value in zip(names[1:], [handoff, design]):
        if blocks['source_canonical_sha256'][name] != canonical_sha256(value):
            raise ValueError('Source identity drift')
    if [(t['first_fs_min'], t['second_fs_min']) for t in handoff['full_trips']] != list(zip(STARTS, MIDS)):
        raise ValueError('Confirmed handoff timetable differs')
    counts = {wing: len({e['path_node_index'] for e in loop['events']}) for wing, loop in design['loops'].items()}
    if counts != {'east_A': 14, 'west_B': 14}:
        raise ValueError('Non-FS dwell event counts drift')
    cases = blocks['all_27_resource_cases']
    if {(c['moving_multiplier'], c['dwell_min'], c['terminal_recovery_min']) for c in cases} != {
            (m, d, r) for m in (.9, 1., 1.1) for d in (0., .5, 1.) for r in (5, 10, 15)} or len(cases) != 27:
        raise ValueError('Resource grid differs')
    for case in cases:
        for vehicle in case['vehicles']:
            for trip in vehicle['trips']:
                for wing, actual in [
                        ('east_A', trip['intermediate_fs_arrival_min']-trip['fs_start_min']),
                        ('west_B', trip['fs_end_min']-trip['intermediate_fs_departure_min'])]:
                    expected = design['loops'][wing]['road_minutes']*case['moving_multiplier']+counts[wing]*case['dwell_min']
                    if not math.isclose(actual, expected, rel_tol=0, abs_tol=1e-8):
                        raise ValueError('Running/dwell decomposition differs from source')
    return dict(contract='RT031_CLOSURE_TIMING_20261007',
        semantics='Exact arithmetic against fixed FS departures and existing conditional blocks. Scenario arrival targets are not measured public guarantees. Last trips have no inferred next-use bound. No depot, driver duties, passenger rights or rail validity certified.',
        source_file_sha256={name: hashlib.sha256((base/name).read_bytes()).hexdigest() for name in names},
        reserve_selected=False, uncertainty_band_min=None, decision_budget_km=None,
        operating_plan_adopted=False, physical_operation_ready=False,
        cases=[dict(moving_multiplier=c['moving_multiplier'], dwell_min=c['dwell_min'],
                    terminal_recovery_assumption_min=c['terminal_recovery_min'], trips=budgets(c, counts)) for c in cases])


if __name__ == '__main__':
    print(json.dumps(build(), ensure_ascii=False, indent=2))
