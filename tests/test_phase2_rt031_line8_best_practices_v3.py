import json
import re
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from scripts.phase2_audit_rt031_line8_best_practices_v3 import (
    ROOT, OUTPUT, DOC, PRINCIPLES, LEDGER, digest, journeys, cadence,
    anchor_phase_conflicts, clockface_probe, report)
from scripts.phase2_compare_rt031_line8_deep_offpeak_v3 import build_problem
from scripts.phase2_solve_rt031_line8_joint_evening_v3 import FLAGS, verify


class BestPracticeReadinessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result=json.loads(OUTPUT.read_text(encoding='utf-8'))
        cls.ledger=json.loads(LEDGER.read_text(encoding='utf-8'))
        cls.problem=build_problem((600,960),120)

    def test_all_twelve_original_principles_and_pinned_sources(self):
        ids=re.findall(r'^### (BP-\d+)',PRINCIPLES.read_text(encoding='utf-8'),re.M)
        self.assertEqual([r['id'] for r in self.result['principles']],ids)
        self.assertEqual(len(ids),12)
        for name,sha in self.result['source_sha256_normalized_newlines'].items():
            self.assertEqual(digest(ROOT/name),sha,name)
        for row in self.result['principles']:
            self.assertFalse(row['fully_certified'])
            self.assertTrue((ROOT/row['evidence_source']).is_file())
            self.assertTrue(row['remaining_action']);self.assertTrue(row['resolution_scope'])

    def test_current_witness_rides_not_inherited_other_timetable(self):
        actual=journeys(self.ledger)
        self.assertEqual(actual,self.result['nominal_site_rides'])
        self.assertEqual(len(actual),27)
        self.assertEqual(sum(len(r['journeys']) for r in actual),sum(len({e['stop_place_id'] for e in t['events_nominal']}) for t in self.ledger['trips']))
        for row in actual:
            for j in row['journeys']:
                self.assertFalse(j['boarding_authorised']);self.assertFalse(j['passenger_continuity_certified'])

    def test_distinct_occurrences_and_within_trip_only(self):
        def event(offset,occ):return {'stop_place_id':'S','name':'S','departure_min':offset,'occurrence_id':occ}
        row={'trips':[{'trip_index':0,'loop':'west_B','departure_min':0,'fs_return_nominal_min':40,
                       'events_nominal':[event(5.5,'early'),event(35,'late')]},
                      {'trip_index':1,'loop':'west_B','departure_min':60,'fs_return_nominal_min':100,
                       'events_nominal':[event(75.5,'other')]}]}
        j=journeys(row)[0]['journeys']
        self.assertEqual((j[0]['from_fs_ride_min'],j[0]['to_fs_ride_min']),(5,5))
        self.assertNotEqual(j[0]['from_fs_occurrence_id'],j[0]['to_fs_occurrence_id'])
        self.assertEqual((j[1]['from_fs_ride_min'],j[1]['to_fs_ride_min']),(15,24.5))
        row['trips'][0]['events_nominal'][0]['departure_min']=-1
        with self.assertRaises(ValueError):journeys(row)

    def test_clockface_descriptor_not_frequency_or_acceptance_score(self):
        trips=[{'loop':w+'_A','departure_min':t} for w in ('west','east') for t in (0,30,150)]
        for row in cadence(trips):
            self.assertEqual(row['departures_outside_most_common_half_hour_phase'],0)
            self.assertEqual(row['successive_departure_gaps_min'],[30,120])
        self.assertEqual(json.loads(json.dumps(cadence(self.ledger['trips']))),self.result['cadence'])

    def test_strict_infeasibility_has_independent_rail_anchor_certificate(self):
        certificates=anchor_phase_conflicts(self.problem)
        self.assertTrue(certificates)
        self.assertEqual(json.loads(json.dumps(certificates)),self.result['strict_phase_conflict_certificates'])
        for c in certificates:
            self.assertTrue(set(c['first_allowed_modulo_30']).isdisjoint(c['second_allowed_modulo_30']))
            for key in ('first_anchor','second_anchor'):
                self.assertIn(c[key],self.problem['anchors'])
                self.assertTrue(c[key]['eligible'])
        self.assertTrue(self.result['strict_clockface_comparison']['infeasibility_proven_in_this_domain'])

    def test_banded_witnesses_reverify_full_service_and_declared_phases(self):
        for key in ('banded_clockface_comparison','banded_same_peak_windows_comparison'):
            r=self.result[key]
            self.assertTrue(r['witness_found'])
            self.assertEqual(verify(self.problem,r['trips'],r['comparison_peak_windows'],4),r['conditional_scenarios'])
            cost=sum(self.problem['family']['loops'][t['loop']]['distance_m']*.26 for t in r['trips'])
            self.assertAlmostEqual(cost,r['annual_service_km'])
            if r['optimality_proven_in_this_domain']:
                self.assertAlmostEqual(cost,r['annual_service_km_lower_bound_in_domain'],places=3)
            for t in r['trips']:
                if t['departure_min']==1180:continue
                band='before_10' if t['departure_min']<600 else 'from_10'
                phase=next(p for p in r['clockface_phases'] if p['wing']==t['loop'].split('_')[0] and p['band']==band)
                self.assertEqual(t['departure_min']%30,phase['modulo_30'])
            self.assertFalse(r['policy_adopted'])
        same=self.result['banded_same_peak_windows_comparison']
        self.assertEqual(same['fixed_peak_starts_comparison'],{'AM':420,'PM':1015})
        self.assertEqual(same['comparison_peak_windows'],self.ledger['comparison_peak_windows'])

    def test_timeout_is_not_an_impossibility(self):
        with patch('scripts.phase2_audit_rt031_line8_best_practices_v3.milp',return_value=SimpleNamespace(status=1,message='timeout',success=False,x=None)):
            row=clockface_probe(self.problem,time_limit=.01)
        self.assertFalse(row['infeasibility_proven_in_this_domain'])
        self.assertFalse(row['optimality_proven_in_this_domain']);self.assertFalse(row['witness_found'])

    def test_report_and_non_decisional_semantics(self):
        self.assertEqual(report(self.result),DOC.read_text(encoding='utf-8'))
        for key in FLAGS:self.assertFalse(self.result[key])
        for key in ('decision_budget_km','uncertainty_band_min','demand_weighted_gjt_improvement_min','missed_connection_probability','total_operating_km'):
            self.assertIsNone(self.result[key])
        self.assertFalse(self.result['actual_timetable_certified'])


if __name__=='__main__':unittest.main()
