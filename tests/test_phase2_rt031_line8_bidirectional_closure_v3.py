import gzip
import hashlib
import json
import unittest

from scripts.phase2_probe_rt031_line8_bidirectional_closure_v3 import OUTPUT as ROAD
from scripts.phase2_solve_rt031_line8_two_direction_timetable_v3 import OUTPUT as TIMETABLE


class BidirectionalClosureTests(unittest.TestCase):
    def test_reversed_order_not_reversed_polyline_or_approved_platform(self):
        r=json.loads(gzip.decompress(ROAD.read_bytes()))
        self.assertFalse(r['network_selected'])
        for c in r['cases']:
            self.assertTrue(c['reverse_reachable_in_represented_graph'])
            self.assertFalse(c['physical_platform_sides_certified'])
            for wing,f in c['forward_loops'].items():
                back=c['reverse_loops'][wing]
                fsids=[e['stop_place_id'] for e in sorted(f['events'],key=lambda e:e['path_node_index'])]
                rsids=[e['stop_place_id'] for e in sorted(back['events'],key=lambda e:e['path_node_index'])]
                self.assertEqual(rsids,list(reversed(fsids)))
                self.assertTrue(all(a['path_node_index']<b['path_node_index'] for a,b in
                    zip(sorted(back['events'],key=lambda e:e['path_node_index']),
                        sorted(back['events'],key=lambda e:e['path_node_index'])[1:])))
            self.assertGreater(c['reverse_distance_m'],c['forward_distance_m'])
            self.assertLess(c['reverse_access_nominal_by_site']['FROZEN::300086']['to_fs_min'],9)

    def test_timeouts_are_not_negative_certificates(self):
        r=json.loads(gzip.decompress(TIMETABLE.read_bytes()))
        self.assertEqual(r['source_sha256'],hashlib.sha256(ROAD.read_bytes()).hexdigest())
        self.assertEqual(len(r['cases']),16)
        self.assertFalse(r['network_selected'])
        for c in r['cases']:
            self.assertEqual(c['full_trip_count'],16)
            self.assertEqual(c['infeasibility_proven'],c['solver_status']==2)
            if c['solver_status']==1:self.assertFalse(c['infeasibility_proven'])
            if c['infeasibility_proven']:self.assertFalse(c['witness_found'])
            if c['witness_found']:
                self.assertEqual(len(c['full_trips']),16)
                self.assertEqual(len(c['rail_assignments']),20)
                for wing in ('west_B','east_A'):
                    for kind in ('bus_to_rail','rail_to_bus'):
                        rows=sorted([a for a in c['rail_assignments'] if a['wing']==wing and a['kind']==kind],key=lambda a:a['rail_min'])
                        self.assertEqual(len(rows),5)
                        self.assertTrue(all(b['rail_min']-a['rail_min']==30 and
                            b['wing_fs_departure_min']-a['wing_fs_departure_min']==30
                            for a,b in zip(rows,rows[1:])))


if __name__=='__main__':unittest.main()
