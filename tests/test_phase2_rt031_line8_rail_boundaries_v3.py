import json
from pathlib import Path
import unittest
from scripts.phase2_audit_rt031_line8_rail_boundaries_v3 import next_event


class RailBoundaryTests(unittest.TestCase):
    def test_transfer_boundary_not_raw_bus_arrival(self):
        trains=[{'departure_min':446},{'departure_min':476}]
        self.assertEqual(next_event(trains,445.476+3,'departure_min')['departure_min'],476)
        self.assertEqual(next_event(trains,445.476-5+3,'departure_min')['departure_min'],446)
        self.assertIsNone(next_event(trains,500,'departure_min'))

    def test_morning_phase_domain_is_not_selected(self):
        a=json.loads((Path(__file__).resolve().parents[1]/'outputs/phase2/rt031_line8_local_shortcuts_v3/rail_boundaries.json').read_text(encoding='utf-8'))
        self.assertEqual(len(a['cases']),180)
        self.assertEqual(a['service_date'],'2026-09-03')
        for key in ('actual_timetable_certified','empirical_probability_computed','network_selected','primary_selection_authorised','runner_up_selection_authorised'):
            self.assertFalse(a[key])
        self.assertIsNone(a['decision_budget_km'])
        self.assertIsNone(a['uncertainty_band_min'])
        acceptable=[]
        for c in a['cases']:
            if c['calendar_case']!='synchronised_07' or c['advance_scope']!='morning_only':
                continue
            row=next(r for r in c['interchange_rows'] if r['wing']=='west' and r['rail_direction']=='MILANO' and r['transfer_walk_min_assumption']==3)
            if row['first_reachable_train_departure_min']==446 and c['worst_optimistic_identity_gap']['minutes']<=60:
                acceptable.append(c['common_advance_min'])
            self.assertEqual(c['annual_km_before_extras'],109285.99)
            self.assertEqual(max(t['departure_min'] for t in c['departures'] if t['loop'].startswith('west')),1140)
        self.assertEqual(acceptable,[3,4,5,6,7,8])


if __name__=='__main__':
    unittest.main()
