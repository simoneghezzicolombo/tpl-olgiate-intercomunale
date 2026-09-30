import unittest
import json
import gzip

from scripts.phase2_probe_rt031_line8_variable_fs_hold_v3 import OUTPUT, solve
from scripts.phase2_rebuild_rt031_uniform_complete_line_v3 import inputs


class VariableFsHoldTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _, cls.p, _, _, cls.loops = inputs()

    def test_known_witness_reproduces_under_looser_shoulder(self):
        result = solve(self.p, self.loops, 'west_B', True, 120, 30)
        self.assertTrue(result['witness_found'])
        self.assertEqual(result['solver_status'], 0)
        self.assertEqual(len(result['full_trips']), 16)
        self.assertEqual(len(result['rail_assignments']), 22)
        for trip in result['ordered_stop_event_ledger_nominal']:
            events = trip['events']
            self.assertEqual(len([e for e in events if e.get('site_id') ==
                                  'RT031::P2V2S_0031_PROJECTED_ROAD_POINT']), 2)
            self.assertEqual(len([e for e in events if e.get('site_id') ==
                                  'PROXY::SAN_ZENO_VIA_CANTU_ROAD_NODE']), 2)
            self.assertEqual(len([e for e in events if e['role'] ==
                                  'INTERMEDIATE_FS_STAY_ONBOARD_DESIGN']), 1)
        self.assertFalse(result['network_selected'])
        self.assertFalse(result['primary_selection_authorised'])
        self.assertFalse(result['runner_up_selection_authorised'])

    def test_variable_holding_does_not_solve_h90_shoulder(self):
        result = solve(self.p, self.loops, 'west_B', True, 90, 30)
        self.assertTrue(result['infeasibility_proven'])
        self.assertFalse(result['witness_found'])

    def test_h95_requires_longer_midpoint_offset(self):
        short = solve(self.p, self.loops, 'east_A', True, 95, 30, max_mid=75)
        feasible = solve(self.p, self.loops, 'east_A', True, 95, 30,
                         minimize_hold=True)
        self.assertTrue(short['infeasibility_proven'])
        self.assertTrue(feasible['witness_found'])
        self.assertEqual(max(q['intermediate_offset_min'] for q in
                             feasible['full_trips']), 80)
        self.assertGreater(feasible['maximum_intermediate_fs_onboard_wait_nominal_min'], 39)

    def test_published_frontier_remains_non_decisional(self):
        result = json.loads(gzip.decompress(OUTPUT.read_bytes()))
        self.assertEqual(result['contract'],
                         'RT031_LINE8_VARIABLE_FS_HOLD_16_FULL_TRIPS_DIAGNOSTIC_V3')
        self.assertTrue(result['six_reverse_edge_manoeuvres_all_bus_authorisation_missing'])
        self.assertEqual(result['manoeuvre_ids_requiring_vehicle_sweep'],
                         ['M1', 'M2', 'M3', 'M4', 'M5', 'M6'])
        self.assertEqual(len(result['local_fast_directional_passages_nominal']), 2)
        self.assertFalse(result['network_selected'])
        self.assertFalse(result['primary_selection_authorised'])
        self.assertFalse(result['runner_up_selection_authorised'])
        by_id = {c['case_id']: c for c in result['cases']}
        for first, max_mid in [('west_B', 80), ('east_A', 75)]:
            prefix = f'{first}_shifted_'
            self.assertTrue(by_id[prefix+'16_shoulder90_maxmidall_feasibility']
                            ['infeasibility_proven'])
            self.assertTrue(by_id[prefix+f'16_shoulder95_maxmid{max_mid}_feasibility']
                            ['infeasibility_proven'])
            self.assertTrue(by_id[prefix+'16_shoulder95_maxmidall_minhold']
                            ['witness_found'])
            self.assertTrue(by_id[prefix+'17_shoulder60_maxmidall_feasibility']
                            ['infeasibility_proven'])
            self.assertTrue(by_id[prefix+'18_shoulder60_maxmidall_minhold']
                            ['witness_found'])


if __name__ == '__main__':
    unittest.main()
