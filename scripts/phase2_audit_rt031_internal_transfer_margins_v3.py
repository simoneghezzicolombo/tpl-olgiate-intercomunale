"""Internal engineering margins and bounded phase repairs, not operator handoff.

Keep the caller-confirmed design unchanged. Audit every dated rail flow before
calling a local timing change an improvement. No probability or preference.
"""
import copy
import json

from scripts.phase2_package_rt031_confirmed_design_handoff_v3 import (
    BASE, DESIGN, OUTPUT as HANDOFF, canonical_sha256, build as handoff_build,
)
from scripts.phase2_package_rt031_current_16_trip_proposal_v3 import (
    SOURCE, RAIL, verify_schedule,
)
from scripts.phase2_probe_rt031_line8_variable_fs_hold_v3 import wing_offsets
from scripts.phase2_complete_rt031_current_design_evidence_v3 import (
    make_intervals, complete_trip_blocks,
)
from scripts.phase2_audit_rt031_line8_current_rail_connections_v3 import connection_row

OUTPUT = BASE / 'internal_transfer_margin_audit_20261002.json'


def bank_margins(schedule, offsets, walk):
    rows = []
    for bank in schedule['selected_real_train_banks_not_adopted']:
        pairs = zip(bank['rail_minutes'], bank['bus_departures_min'])
        if bank['kind'] == 'bus_to_rail':
            margins = [rail-dep-g[bank['wing']]['road_minutes']-walk
                       for rail, dep in pairs for g in offsets.values()]
        else:
            margins = [dep-rail-walk for rail, dep in pairs]
        rows.append(dict(wing=bank['wing'], kind=bank['kind'],
                         event_count=len(bank['rail_minutes']),
                         assumed_walk_min=walk, minimum_residual_margin_min=min(margins),
                         maximum_residual_margin_min=max(margins),
                         observed_walk_or_delay=False))
    return rows


def shifted_schedule(source, am_advance=0, west_delay=0):
    trial = copy.deepcopy(source)
    maps = {w: {} for w in ('east_A', 'west_B')}
    for i, trip in enumerate(trial['full_trips']):
        first, second = trip['first_fs_min'], trip['second_fs_min']
        trip['first_fs_min'] -= am_advance if i < 5 else 0
        # Moving the PM bank alone breaks the preceding service gap. Include
        # the two preceding west sections, keeping the complete-trip count.
        trip['second_fs_min'] += west_delay if 8 <= i <= 14 else 0
        trip['intermediate_offset_min'] = trip['second_fs_min']-trip['first_fs_min']
        maps['east_A'][first] = trip['first_fs_min']
        maps['west_B'][second] = trip['second_fs_min']
    for bank in trial['selected_real_train_banks_not_adopted']:
        bank['bus_departures_min'] = [maps[bank['wing']][v] for v in bank['bus_departures_min']]
    for assignment in trial['rail_assignments']:
        assignment['wing_fs_departure_min'] = maps[assignment['wing']][assignment['wing_fs_departure_min']]
    return trial


def flows(schedule, offsets, rail):
    departures = {w: [t['first_fs_min' if w == 'east_A' else 'second_fs_min']
                      for t in schedule['full_trips']] for w in ('east_A', 'west_B')}
    durations = {w: {k: g[w]['road_minutes'] for k, g in offsets.items()} for w in departures}
    return [connection_row(train, wing, departures[wing], durations[wing])
            for wing in departures for train in rail['events']]


def flow_changes(before, after):
    changed = []
    for old, new in zip(before, after):
        if (old['wing'], old['trip_id']) != (new['wing'], new['trip_id']):
            raise ValueError('Different dated rail-flow identity')
        a, b = old['rail_to_bus'], new['rail_to_bus']
        c, d = old['bus_to_rail'], new['bus_to_rail']
        if a != b or c != d:
            changed.append(dict(wing=new['wing'], train_number=new['train_number'],
                train_arrival_min=new['train_arrival_min'], train_departure_min=new['train_departure_min'],
                old_rail_to_bus_wait_min=a['wait_from_train_arrival_min'],
                new_rail_to_bus_wait_min=b['wait_from_train_arrival_min'],
                old_bus_to_rail_wait_min=c['wait_to_train_departure_min'],
                new_bus_to_rail_wait_min=d['wait_to_train_departure_min'],
                old_same_nominal_bus_feasible_all_nine=c['same_bus_feasible_in_all_nine_cases'],
                new_same_nominal_bus_feasible_all_nine=d['same_bus_feasible_in_all_nine_cases']))
    return changed


def compare(source, design, rail, advance, delay):
    offsets = wing_offsets(design['loops'])
    trial = shifted_schedule(source, advance, delay)
    try:
        verify_schedule(trial, design['loops'])
        readiness_pass, violation = True, None
    except ValueError as exc:
        readiness_pass, violation = False, str(exc)
    cases = []
    for (moving, dwell), g in offsets.items():
        for recovery in (5, 10, 15):
            blocks = complete_trip_blocks(make_intervals(trial['full_trips'],
                g['east_A']['road_minutes'], g['west_B']['road_minutes'], recovery))
            cases.append(dict(moving_multiplier=moving, dwell_min=dwell,
                              recovery_min=recovery, minimum_model_vehicles=blocks['minimum_vehicle_count_conditional'],
                              overlap_witness=blocks['overlap_lower_bound_witness']))
    changes = flow_changes(flows(source, offsets, rail), flows(trial, offsets, rail))
    worsening = [r['new_rail_to_bus_wait_min']-r['old_rail_to_bus_wait_min']
                 for r in changes if r['old_rail_to_bus_wait_min'] is not None
                 and r['new_rail_to_bus_wait_min'] is not None]
    return dict(east_am_advance_min=advance, west_trips_9_to_15_delay_min=delay,
                event_readiness_and_complete_trip_checks_pass=readiness_pass,
                readiness_violation=violation, all_27_vehicle_cases=cases,
                maximum_model_vehicles=max(c['minimum_model_vehicles'] for c in cases),
                additional_full_trip_service_min_per_day=5*advance+7*delay,
                additional_commercial_km=0, full_trip_count=16,
                exact_fs_departure_pairs_min=[[t['first_fs_min'], t['second_fs_min']] for t in trial['full_trips']],
                bank_margins_assumed_3min_walk=bank_margins(trial, offsets, 3),
                rail_call_count=rail['event_count'], wing_train_rows_checked=2*rail['event_count'],
                transfer_flow_combinations_checked=4*rail['event_count'],
                lost_previous_all_nine_case_bus_to_rail=[r for r in changes
                    if r['old_same_nominal_bus_feasible_all_nine'] and not r['new_same_nominal_bus_feasible_all_nine']],
                maximum_increase_in_nominal_rail_to_bus_wait_min=max(worsening, default=0),
                rail_flow_changes=changes,
                full_service_event_ledger_rebuilt=False, proposed_timetable_adopted=False,
                semantics='Bounded phase diagnostic; every calling train and both flows recomputed. Passing inherited caps does not imply an overall improvement, empirical reliability or approval. Extra service time includes longer FS holds; cost is not assumed unchanged.')


def build():
    handoff = json.loads(HANDOFF.read_text(encoding='utf-8'))
    if canonical_sha256(handoff) != canonical_sha256(handoff_build()):
        raise ValueError('Confirmed upstream design drift')
    source, design, rail = [json.loads(p.read_text(encoding='utf-8')) for p in (SOURCE, DESIGN, RAIL)]
    offsets = wing_offsets(design['loops'])
    return dict(contract='RT031_INTERNAL_ENGINEERING_TRANSFER_MARGIN_AUDIT_V3',
                recorded_on='2026-10-02', rail_reference_date=rail['service_date'],
                source_canonical_sha256={p.name: canonical_sha256(v)
                    for p, v in ((HANDOFF, handoff), (SOURCE, source), (DESIGN, design), (RAIL, rail))},
                baseline_bank_margins_assumed_3min_walk=bank_margins(source, offsets, 3),
                diagnostic_5min_walk_not_adopted=bank_margins(source, offsets, 5),
                phase_comparisons=[compare(source, design, rail, a, d)
                    for a, d in [(0, 0)]+[(a, 0) for a in range(1, 6)]+[(0, d) for d in range(1, 6)]],
                design_engineering_solidification_complete=False,
                best_phase_selected=False, caller_uncertainty_band_selected=False,
                physical_operation_certified=False, rail_2027_certified=False,
                primary_selection_authorised=False, runner_up_selection_authorised=False,
                decision_budget_km=None, uncertainty_band_min=None,
                missed_connection_probability=None, demand_weighted_gjt_improvement_min=None,
                semantics='Internal design weaknesses and local diagnostic repairs. The caller-confirmed timetable stays unchanged. Transfer assumptions are sensitivity inputs, not normative new thresholds. No weighted winner, global infeasibility or probability is inferred.')


if __name__ == '__main__':
    result = build()
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(dict(baseline=result['baseline_bank_margins_assumed_3min_walk'],
                         phase_comparisons=len(result['phase_comparisons']),
                         best_phase_selected=False)))
