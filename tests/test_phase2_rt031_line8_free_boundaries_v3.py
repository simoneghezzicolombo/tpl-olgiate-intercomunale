import json
from pathlib import Path
import unittest

from scripts.phase2_probe_rt031_line8_free_boundaries_v3 import (
    ARLATE_NEW, BASE, directional_access,
)


class DirectionalAccessTest(unittest.TestCase):
    def test_distinct_occurrences_must_support_both_directions(self):
        events = [
            {'stop_place_id': 'x', 'road_minutes_from_previous_fs': 3.,
             'road_minutes_to_next_fs': 25.},
            {'stop_place_id': 'x', 'road_minutes_from_previous_fs': 27.,
             'road_minutes_to_next_fs': 4.},
        ]
        self.assertEqual(directional_access(events, 'x'), {
            'occurrence_count': 2,
            'best_fs_to_site_road_min': 3.,
            'best_site_to_fs_road_min': 4.,
        })
        self.assertEqual(directional_access(events[:1], 'x')['best_site_to_fs_road_min'], 25.)

    def test_missing_site_fails_closed(self):
        with self.assertRaises(ValueError):
            directional_access([], 'x')


class CommittedBoundaryAuditTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.audit = json.loads((BASE / 'free_boundary_road_comparison.json').read_text(encoding='utf-8'))
        cls.shape = json.loads((BASE / 'free_boundary_road_comparison.geojson').read_text(encoding='utf-8'))

    def test_distance_and_provenance(self):
        a = self.audit
        self.assertEqual(a['contract'], 'RT031_LINE8_FREE_BOUNDARY_ROAD_COMPARISON_V3')
        self.assertTrue(a['prior_recorded_wing_geometry_reproduced'])
        self.assertAlmostEqual(a['reference_total_distance_m'], 27678.66990692818, places=4)
        self.assertAlmostEqual(a['minimum_total_distance_m'], 24517.3472873864, places=4)
        self.assertAlmostEqual(a['distance_margin_to_target_m'], 85.914852105, places=3)
        self.assertEqual([x['required_site_count'] for x in a['audits']], [15, 13])
        self.assertIn(ARLATE_NEW, a['audits'][1]['required_site_ids'])

    def test_service_non_equivalence_fails_closed(self):
        a = self.audit
        self.assertFalse(a['both_local_directional_occurrence_guarantees_preserved'])
        self.assertFalse(a['network_selected'])
        self.assertFalse(a['primary_selection_authorised'])
        self.assertFalse(a['runner_up_selection_authorised'])
        self.assertFalse(a['full_history_legality_certified'])
        self.assertFalse(a['actual_timetable_certified'])
        self.assertIsNone(a['decision_budget_km'])
        self.assertIsNone(a['uncertainty_band_min'])
        self.assertTrue(all(x['reference']['occurrence_count'] == 2
                            and x['road_minimum']['occurrence_count'] == 1
                            for x in a['local_service_comparison'].values()))
        self.assertGreater(a['local_service_comparison']['west']['road_minimum']
                           ['best_fs_to_site_road_min'], 20)
        self.assertGreater(a['local_service_comparison']['east']['road_minimum']
                           ['best_site_to_fs_road_min'], 20)

    def test_geometry_is_explicitly_non_authorised(self):
        features = self.shape['features']
        self.assertEqual(sum(f['geometry']['type'] == 'LineString' for f in features), 2)
        self.assertEqual(sum('site_id' in f['properties'] for f in features), 29)
        self.assertEqual(sum(f['properties'].get('immediate_reversal', False) for f in features), 4)
        self.assertTrue(all(f['properties'].get('bus_manoeuvre_authorised') is False
                            for f in features if f['properties'].get('immediate_reversal')))


if __name__ == '__main__':
    unittest.main()
