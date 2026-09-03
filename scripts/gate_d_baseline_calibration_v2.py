#!/usr/bin/env python3
"""Run baseline calibration under the same bus-specific OSM policy as Gate D v3."""
from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

# Importing v3 applies the bus-specific OSM access and oneway policy to the shared
# gate_d_route_integrity module in this process before calibration builds its graph.
import gate_d_structural_candidates_v3  # noqa: F401
import gate_d_baseline_calibration as calibration


if __name__ == "__main__":
    raise SystemExit(calibration.main())
