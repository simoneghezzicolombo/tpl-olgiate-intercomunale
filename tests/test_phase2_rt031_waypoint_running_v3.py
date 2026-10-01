import unittest

from scripts.phase2_probe_rt031_current_stop_repair_v3 import waypoint_running_to_fs


class WaypointRunningTest(unittest.TestCase):
    def test_reversed_lobe_uses_reversed_waypoint_index(self):
        lobe = [("FS", "fs"), ("A", "a"), ("B", "b"), ("FS", "fs")]
        forward = {
            "ordered_waypoints": ["FS", "A", "B", "FS"],
            "legs": [{"running_minutes_model": value} for value in (2, 3, 5)],
        }
        reverse = {
            "ordered_waypoints": ["FS", "B", "A", "FS"],
            "legs": [{"running_minutes_model": value} for value in (7, 11, 13)],
        }
        rows = waypoint_running_to_fs(lobe, forward, reverse)
        self.assertEqual([row["waypoint_id"] for row in rows], ["a", "b"])
        self.assertEqual(rows[0]["forward_running_minutes_from_waypoint_to_next_fs_excluding_dwell"], 8)
        self.assertEqual(rows[0]["reverse_running_minutes_from_waypoint_to_next_fs_excluding_dwell"], 13)
        self.assertEqual(rows[1]["forward_running_minutes_from_waypoint_to_next_fs_excluding_dwell"], 5)
        self.assertEqual(rows[1]["reverse_running_minutes_from_waypoint_to_next_fs_excluding_dwell"], 24)


if __name__ == "__main__":
    unittest.main()
