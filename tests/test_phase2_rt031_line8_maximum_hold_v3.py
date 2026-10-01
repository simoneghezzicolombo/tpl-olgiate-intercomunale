import gzip
import hashlib
import json
import unittest

from scripts.phase2_close_rt031_line8_maximum_hold_v3 import OUTPUT, CUTS
from scripts.phase2_probe_rt031_line8_variable_fs_hold_v3 import solve, wing_offsets
from scripts.phase2_rebuild_rt031_uniform_complete_line_v3 import inputs


class MaximumHoldClosureTests(unittest.TestCase):
    def test_objectives_cannot_be_silently_mixed(self):
        _,policy,_,_,loops=inputs()
        with self.assertRaisesRegex(ValueError,'one holding objective'):
            solve(policy,loops,'west_B',False,minimize_hold=True,minimize_max_hold=True)
        with self.assertRaisesRegex(ValueError,'separate rail-coverage'):
            solve(policy,loops,'west_B',False,minimize_max_hold=True,anchor_policy='max_supported')

    def test_full_comparison_domain_and_non_adoption(self):
        r=json.loads(gzip.decompress(OUTPUT.read_bytes()))
        source=json.loads(gzip.decompress(CUTS.read_bytes()))
        self.assertEqual(r['cut_source_sha256'],hashlib.sha256(CUTS.read_bytes()).hexdigest())
        expected={(cid,wing) for cid in source['timetable_domain']['case_ids'] for wing in ('west_B','east_A')}
        self.assertEqual({(c['geometry_case_id'],c['first_wing']) for c in r['cases']},expected)
        for name in ('network_selected','primary_selection_authorised','runner_up_selection_authorised',
                     'trip_count_adopted','stop_omissions_adopted','calendar_adopted'):
            self.assertFalse(r[name])
        self.assertIsNone(r['decision_budget_km'])
        self.assertIsNone(r['uncertainty_band_min'])
        self.assertTrue(r['caller_tradeoff_adoption_missing'])
        self.assertTrue(r['lowest_hold_is_not_a_network_or_utility_selection'])

    def test_minimax_and_scenario_hold_are_verified_separately(self):
        r=json.loads(gzip.decompress(OUTPUT.read_bytes()))
        source=json.loads(gzip.decompress(CUTS.read_bytes()))
        geometry={c['case_id']:c for c in source['cases']}
        for c in r['cases']:
            self.assertEqual(c['full_trip_count'],17)
            self.assertEqual(c['infeasibility_proven'],c['solver_status']==2)
            self.assertEqual(c['maximum_holding_objective_proven_optimal'],c['solver_status']==0)
            if not c['witness_found']:continue
            self.assertTrue(c['maximum_intermediate_offset_minimized'])
            self.assertFalse(c['intermediate_holding_minimized'])
            self.assertEqual(len(c['full_trips']),17)
            self.assertEqual(len(c['rail_assignments']),20)
            loops=geometry[c['geometry_case_id']]['loops']
            offsets=wing_offsets(loops)
            max_offset=max(t['intermediate_offset_min'] for t in c['full_trips'])
            for s in c['maximum_fs_onboard_hold_by_scenario']:
                expected=max_offset-offsets[s['moving_multiplier'],s['dwell_min']][c['first_wing']]['road_minutes']
                self.assertAlmostEqual(s['maximum_wait_min'],expected)
            for bank in c['selected_real_train_banks_not_adopted']:
                for name in ('rail_minutes','bus_departures_min'):
                    self.assertEqual(len(bank[name]),5)
                    self.assertTrue(all(b-a==30 for a,b in zip(bank[name],bank[name][1:])))
            # A sum-optimal witness may or may not minimise the maximum; its
            # value is an upper bound, never treated as a minimax certificate.
            sum_witness=next(t for t in geometry[c['geometry_case_id']]['extra_trip_count_comparisons_not_adopted']
                             if t['full_trip_count']==17 and t['first_wing']==c['first_wing'])
            if c['maximum_holding_objective_proven_optimal'] and sum_witness['witness_found']:
                self.assertLessEqual(max_offset,max(t['intermediate_offset_min'] for t in sum_witness['full_trips']))


if __name__=='__main__':unittest.main()
