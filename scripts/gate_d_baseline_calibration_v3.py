#!/usr/bin/env python3
"""Run D184/D185 baseline calibration under Gate D v4 OSM access semantics."""
from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

# Import applies the same bus/psv/access hierarchy used by candidate routing.
import gate_d_structural_candidates_v4  # noqa: F401
import gate_d_baseline_calibration as calibration


if __name__ == "__main__":
    raise SystemExit(calibration.main())
