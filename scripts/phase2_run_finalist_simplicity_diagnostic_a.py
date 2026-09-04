#!/usr/bin/env python3
"""Agent A runner for the frozen V3 finalist simplicity diagnostic.

This wrapper changes only the expected finalist timetable set.  All analytical
semantics remain in phase2_build_finalist_simplicity_diagnostic_v3.py.
"""
from __future__ import annotations

import json

import phase2_build_finalist_simplicity_diagnostic_v3 as diagnostic

CURRENT_FINALIST_TIMETABLES = {
    "D4RT001V3_a87577dd79b3cb3e",
    "D4RT001V3_a81a3718416f5cb2",
    "D4RT001V3_c7318c775dcc1931",
    "D4RT001V3_a83abc3b41a4ee68",
}


def main() -> None:
    diagnostic.EXPECTED_TIMETABLES = CURRENT_FINALIST_TIMETABLES
    result = diagnostic.build(diagnostic.parse_args())
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
