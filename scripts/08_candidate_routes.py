#!/usr/bin/env python3
"""Gate D candidate-route entry point.

The pre-audit version of this module contained manually authored route-km, runtimes,
population coverage, OD capture and recommendation labels. Those values are
INVALIDATED and must never be used as evidence.

Gate D now fails closed until candidate metrics are produced by the real-road
pipeline in ``scripts/gate_d_route_integrity.py`` from traceable OSM geometry and
explicit candidate waypoint inputs.
"""
from __future__ import annotations

import sys
from pathlib import Path

REQUIRED_OUTPUT = Path("outputs/gate_d_route_metrics.csv")


def main() -> int:
    if not REQUIRED_OUTPUT.exists():
        print(
            "Gate D candidate metrics are not available. Run "
            "scripts/gate_d_route_integrity.py with a candidate waypoint CSV. "
            "Legacy hard-coded route metrics were INVALIDATED."
        )
        return 2
    print(f"Gate D metrics available at {REQUIRED_OUTPUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
