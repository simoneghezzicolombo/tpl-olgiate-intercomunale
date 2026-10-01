import unittest

from scripts.phase2_build_rt031_line8_delivery_readiness_v3 import build, document


class DeliveryReadinessTests(unittest.TestCase):
    def test_unique_sites_not_platforms_and_no_selection(self):
        r=build()
        self.assertEqual(len(r['served_sites']),28)
        self.assertEqual(len({s['site_id'] for s in r['served_sites']}),28)
        self.assertIsNone(r['physical_platform_count'])
        self.assertFalse(r['ready_for_final_recommendation'])
        self.assertFalse(r['network_selected'])
        self.assertEqual(len(r['requirements']),13)
        self.assertEqual(len(r['desired_localities_not_automatically_certified']),18)
        self.assertEqual(len(r['old_rail_objectives_incompatible']),4)
        self.assertGreater(r['extra_km_above_specific_accepted_comparison'],1268)
        self.assertIsNone(r['demand_weighted_gjt_improvement_min'])
        self.assertIsNone(r['missed_connection_probability'])
        self.assertEqual(len(r['journey_quality_illustrative_examples_not_admissibility_threshold']),4)
        for sid in ('RT031::P2V2S_0031_PROJECTED_ROAD_POINT','PROXY::SAN_ZENO_VIA_CANTU_ROAD_NODE'):
            site=next(s for s in r['served_sites'] if s['site_id']==sid)
            self.assertEqual(len(site['ordered_occurrences']),2)
            self.assertNotEqual(*[e['occurrence_id'] for e in site['ordered_occurrences']])
            self.assertFalse(site['boarding_authorised'])

    def test_coordinate_and_proposed_point_semantics(self):
        r=build()
        for s in r['served_sites']:
            lon,lat=s['coordinates_lon_lat']
            self.assertTrue(9.3<lon<9.5)
            self.assertTrue(45.7<lat<45.8)
        self.assertEqual(sum(s['kind'].startswith('PROPOSED') for s in r['served_sites']),3)
        calco=next(s for s in r['served_sites'] if s['site_id']=='FROZEN::300634')
        self.assertNotEqual(calco['coordinates_lon_lat'],calco['inventory_coordinates_lon_lat'])
        self.assertIn('Calco',document(r))
        self.assertNotIn('FROZEN::300873',[s['site_id'] for s in r['served_sites']])


if __name__=='__main__':
    unittest.main()
