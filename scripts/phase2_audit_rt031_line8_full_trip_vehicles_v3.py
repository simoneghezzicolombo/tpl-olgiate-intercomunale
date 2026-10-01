"""Make full-eight vehicle blocks explicit; no wing-only buses or fleet approval."""

import argparse
import gzip
import hashlib
import json
import math
from pathlib import Path

from scripts.phase2_audit_rt031_line8_through_service_v3 import inputs, BASE
from scripts.phase2_rebuild_rt031_uniform_complete_line_v3 import timing_offsets, source_fingerprints

SOURCE = BASE / 'uniform_16_full_trips.json.gz'
OUTPUT = BASE / 'uniform_16_full_trip_vehicle_blocks.json'
SCENARIOS = {
    'nominal': (1.1, .5, 10),
    'slower_dwell_and_recovery': (1.1, 1., 15),
}


def checked_blocks(case, resource_case, timing):
    departures = case['full_trip_departures_min']
    blocks = resource_case['trip_index_blocks']
    recovery = resource_case['terminal_recovery_min']
    if len(blocks) != resource_case['minimum_vehicle_count_conditional']:
        raise ValueError('reported fleet does not match full-trip block count')
    if sorted(i for block in blocks for i in block) != list(range(len(departures))):
        raise ValueError('full-trip block coverage has a duplicate or omission')
    vehicles = []
    for vehicle_number, block in enumerate(blocks, 1):
        trips = []
        for position, i in enumerate(block):
            start = departures[i]
            end = start + timing['full_trip_arrival']
            next_start = departures[block[position + 1]] if position + 1 < len(block) else None
            if next_start is not None and next_start - end + 1e-8 < recovery:
                raise ValueError('vehicle block lacks terminal recovery after complete trip')
            trips.append({'full_trip_number': i + 1, 'fs_start_min': start,
                          'intermediate_fs_arrival_min': start + timing['midpoint_arrival'],
                          'intermediate_fs_departure_min': start + timing['midpoint_departure'],
                          'fs_end_min': end,
                          'terminal_layover_to_next_full_trip_min':
                              None if next_start is None else next_start - end})
        vehicles.append({'model_vehicle_id': f'B{vehicle_number}',
                         'complete_trip_numbers': [i + 1 for i in block],
                         'trips': trips})
    return vehicles


def build():
    source_bytes = SOURCE.read_bytes()
    source = json.loads(gzip.decompress(source_bytes))
    if source['contract'] != 'RT031_16_COMPLETE_TRIPS_TIMING_AUDIT_V3' or source['network_selected']:
        raise ValueError('unsupported full-trip source')
    _, p, _, _, loops = inputs()
    if source['parent_sources'] != source_fingerprints(p, loops):
        raise ValueError('upstream uniform full-trip inputs changed')
    cases = source['refined_115_minute_diagnostics']
    if len(cases) != 2 or {c['first_wing'] for c in cases} != {'west_B', 'east_A'}:
        raise ValueError('expected two same-route first-wing comparisons')
    results = []
    for case in cases:
        if case['full_trip_count'] != 16 or len(case['full_trip_stop_event_ledger_nominal']) != 16:
            raise ValueError('not sixteen complete trips')
        second = case['second_wing']
        if {case['first_wing'], second} != {'west_B', 'east_A'}:
            raise ValueError('missing wing in complete public pattern')
        for trip in case['full_trip_stop_event_ledger_nominal']:
            roles = [e['role'] for e in trip['events']]
            if (roles.count('FULL_TRIP_START_AT_FS') != 1
                    or roles.count('INTERMEDIATE_FS_PUBLIC_STOP_STAY_ONBOARD_DESIGN') != 1
                    or roles.count('FULL_TRIP_END_AT_FS') != 1
                    or trip['uniform_full_pattern_id'] != case['first_wing'] + '>' + second):
                raise ValueError('complete-trip vehicle/passenger event sequence missing')
        grid = timing_offsets(loops, case['first_wing'], case['midpoint_departure_offset_min'])
        resources = case['verification']['all_27_resource_cases']
        if len(resources) != 27:
            raise ValueError('incomplete runtime/dwell/recovery sensitivity')
        counts = {}
        detailed = {}
        for resource in resources:
            key = (resource['moving_multiplier'], resource['dwell_min'],
                   resource['terminal_recovery_min'])
            if key in counts:
                raise ValueError('duplicate sensitivity')
            timing = grid[key[:2]]
            vehicles = checked_blocks(case, resource, timing)
            cycle = timing['full_trip_arrival'] + key[2]
            overlap_floor = max(sum(s <= t and t < s + cycle - 1e-8
                                    for s in case['full_trip_departures_min'])
                                for t in case['full_trip_departures_min'])
            if len(vehicles) != overlap_floor:
                raise ValueError('vehicle blocks do not match independent interval-overlap lower bound')
            counts[key] = len(vehicles)
            for name, chosen in SCENARIOS.items():
                if key == chosen:
                    duration = timing['full_trip_arrival']
                    cycle_with_recovery = duration + key[2]
                    detailed[name] = {
                        'moving_multiplier': key[0], 'dwell_min': key[1],
                        'terminal_recovery_min': key[2],
                        'full_trip_duration_min': duration,
                        'full_trip_cycle_with_terminal_recovery_min': cycle_with_recovery,
                        'interval_overlap_lower_bound_vehicles': overlap_floor,
                        'thirty_minute_peak_theoretical_fleet_floor':
                            min(5, math.ceil((cycle_with_recovery - 1e-8) / 30)),
                        'minimum_vehicle_count_conditional': len(vehicles),
                        'vehicles': vehicles,
                    }
        if set(detailed) != set(SCENARIOS):
            raise ValueError('missing selected sensitivities')
        distribution = {str(n): sum(count == n for count in counts.values())
                        for n in sorted(set(counts.values()))}
        results.append({'first_wing': case['first_wing'], 'second_wing': second,
                        'uniform_full_pattern_id': case['first_wing'] + '>' + second,
                        'case_id': case['case_id'],
                        'full_trip_departures_min': case['full_trip_departures_min'],
                        'scenario_vehicle_count_distribution_27': distribution,
                        'detailed_scenarios': detailed})
    return {'contract': 'RT031_LINE8_FULL_TRIP_VEHICLE_BLOCKS_V3',
            'source_sha256': hashlib.sha256(source_bytes).hexdigest(),
            'source_contract': source['contract'],
            'semantics': 'Each model vehicle is assigned only complete same-pattern FS-wing-FS-wing-FS trips. '
                         'Intermediate FS is inside the trip and cannot be a vehicle change. Minimum path cover '
                         'is exact for the declared deterministic trip times and terminal recovery, without '
                         'depot or positioning travel. Bus and passenger physical continuity, driver duties, '
                         'observed times and station-side feasibility remain uncertified.',
            'cases': results, 'wing_separate_vehicle_assignment': False,
            'same_model_vehicle_through_intermediate_fs': True,
            'physical_vehicle_and_passenger_continuity_certified': False,
            'operating_plan_adopted': False, 'network_selected': False,
            'primary_selection_authorised': False,
            'runner_up_selection_authorised': False,
            'decision_budget_km': None, 'uncertainty_band_min': None}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default=OUTPUT)
    args = parser.parse_args()
    Path(args.output).write_text(json.dumps(build(), sort_keys=True, ensure_ascii=False,
                                           separators=(',', ':')) + '\n', encoding='utf-8')
