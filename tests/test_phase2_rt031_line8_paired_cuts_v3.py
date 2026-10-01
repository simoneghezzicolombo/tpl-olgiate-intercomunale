import gzip
import hashlib
import json
import unittest
from fractions import Fraction

from scripts.phase2_probe_rt031_line8_paired_cuts_v3 import (
    OUTPUT, CALCO, FS, LOCAL, ARLATE, removal_domain, losses, km_walk_dominates,
    SPECIFIC_ACCEPTED_COMPARISON_KM)


class PairedCutsTests(unittest.TestCase):
    def test_domain_does_not_hand_pick_a_second_cut(self):
        self.assertEqual(removal_domain(['c','a','b','a']),
                         [(),('a',),('b',),('c',),('a','b'),('a','c'),('b','c')])

    def test_percentage_points_are_not_percent_change(self):
        self.assertAlmostEqual(losses({'x':{'5':'4/5'}},{'x':{'5':'3/5'}})['x']['5'],20)

    def test_machine_readable_evidence_matches_domain(self):
        r = json.loads(gzip.decompress(OUTPUT.read_bytes()))
        self.assertEqual(r['parent_source_sha256'],hashlib.sha256(CALCO.read_bytes()).hexdigest())
        self.assertEqual(len(r['removable_inventory_ids']),25)
        self.assertEqual(r['declared_domain_count'],326)
        self.assertEqual(len(r['cases']),326)
        self.assertEqual({tuple(c['omitted_stop_ids']) for c in r['cases']},
                         set(removal_domain(r['removable_inventory_ids'])))
        self.assertEqual(set(r['protected_ids']),{FS,ARLATE,*LOCAL.values()})
        self.assertTrue(r['original_28_site_reference_reproduced'])
        for name in ('network_selected','primary_selection_authorised','runner_up_selection_authorised',
                     'physical_boarding_authorised','full_history_legality_certified'):
            self.assertFalse(r[name])
        self.assertIsNone(r['decision_budget_km'])
        self.assertIsNone(r['uncertainty_band_min'])
        parent=json.loads(gzip.decompress(CALCO.read_bytes()))
        baseline=next(c for c in parent['cases'] if c['reachable'])['whole_wing_fixed_order_without_reversals']['loops']
        for c in r['cases']:
            if not c['reachable']:continue
            self.assertEqual(c['site_count_including_fs'],29-len(c['omitted_stop_ids']))
            self.assertAlmostEqual(c['annual_service_km_16_trips_260_days'],c['distance_m']*4.16)
            for wing,loop in c['loops'].items():
                expected=[e['stop_place_id'] for e in sorted(baseline[wing]['events'],
                         key=lambda e:(e['path_node_index'],e['stop_place_id']))
                         if e['stop_place_id'] not in c['omitted_stop_ids']]
                actual=[e['stop_place_id'] for e in sorted(loop['events'],
                       key=lambda e:(e['path_node_index'],e['stop_place_id']))]
                self.assertEqual(actual,expected)
                local=[e for e in loop['events'] if e['stop_place_id']==LOCAL[wing]]
                self.assertEqual(len(local),2)
                self.assertLess(local[0]['path_node_index'],local[1]['path_node_index'])
            for code,row in c['potential_walking_access_fraction'].items():
                for limit,value in row.items():
                    self.assertGreaterEqual(Fraction(value),0)
                    self.assertLessEqual(Fraction(value),Fraction(r['reference_access_fraction'][code][limit]))

    def test_frontier_does_not_hide_untested_timelines(self):
        r=json.loads(gzip.decompress(OUTPUT.read_bytes()))
        cases=[c for c in r['cases'] if c['reachable']]
        self.assertEqual(set(r['unweighted_km_municipal_walk_frontier_case_ids']),
            {c['case_id'] for c in cases if not any(km_walk_dominates(o,c) for o in cases)})
        self.assertFalse(r['timetable_pruning_by_km_walk_dominance'])
        expected={c['case_id'] for c in cases if c['annual_service_km_16_trips_260_days']<=SPECIFIC_ACCEPTED_COMPARISON_KM+1e-8}
        self.assertEqual(set(r['timetable_domain']['case_ids']),expected)
        for c in cases:
            if c['case_id'] not in expected:
                self.assertNotIn('h60_timetable_comparisons_not_adopted',c)
                continue
            self.assertEqual(len(c['h60_timetable_comparisons_not_adopted']),2)
            for t in c['h60_timetable_comparisons_not_adopted']:
                self.assertEqual(t['full_trip_count'],16)
                self.assertEqual(t['shoulder_headway_cap_min'],60)
                self.assertEqual(t['infeasibility_proven'],t['solver_status']==2)
                if t['witness_found']:
                    self.assertEqual(len(t['full_trips']),16)
                    self.assertEqual(len(t['rail_assignments']),20)

    def test_extra_trips_are_not_silently_adopted(self):
        r=json.loads(gzip.decompress(OUTPUT.read_bytes()))
        domain=r['extra_trip_count_domain_not_adopted']
        self.assertFalse(domain['extra_trips_authorised'])
        self.assertFalse(domain['territorial_losses_authorised'])
        for c in r['cases']:
            if c['case_id'] not in domain['case_ids']:continue
            cases=c['extra_trip_count_comparisons_not_adopted']
            self.assertEqual({(t['full_trip_count'],t['first_wing']) for t in cases},
                {(n,w) for n in (17,18) for w in ('west_B','east_A')})
            for t in cases:
                self.assertTrue(t['comparison_not_adopted'])
                self.assertEqual(t['infeasibility_proven'],t['solver_status']==2)
                if not t['witness_found']:continue
                self.assertEqual(len(t['full_trips']),t['full_trip_count'])
                self.assertEqual(len(t['rail_assignments']),20)
                self.assertTrue(t['intermediate_holding_minimized'])
                self.assertEqual(t['holding_objective_proven_optimal'],t['solver_status']==0)
                self.assertEqual(len(t['maximum_intermediate_fs_onboard_wait_by_engineering_scenario']),9)
                self.assertFalse(t['network_selected'])
                for bank in t['selected_real_train_banks_not_adopted']:
                    self.assertEqual(len(bank['rail_minutes']),5)
                    for column in ('rail_minutes','bus_departures_min'):
                        self.assertTrue(all(b-a==30 for a,b in zip(bank[column],bank[column][1:])))

    def test_single_losses_match_existing_upstream_walk_audit(self):
        r=json.loads(gzip.decompress(OUTPUT.read_bytes()))
        from scripts.phase2_measure_rt031_line8_omission_walk_v3 import OUTPUT as WALK
        old=json.loads(WALK.read_text(encoding='utf-8'))
        singles={c['omitted_stop_ids'][0]:c for c in r['cases'] if len(c['omitted_stop_ids'])==1}
        for c in old['cases']:
            new=singles[c['omitted_stop_identity']]
            self.assertEqual(c['potential_walking_access_fraction'],new['potential_walking_access_fraction'])
            self.assertEqual(c['potential_walking_access_loss_percentage_points'],new['potential_walking_access_loss_percentage_points'])


if __name__=='__main__':unittest.main()
