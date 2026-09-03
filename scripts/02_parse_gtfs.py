#!/usr/bin/env python3
"""Legacy pseudo-GTFS generator, invalidated by Gate C.

This file previously constructed routes, stops and times manually and wrote
``network_structural`` / ``network_2026_emergency`` as if they were source
GTFS. Gate C classifies those artefacts as RECONSTRUCTED + INVALIDATED.

Use ``src/transit_integrity.py`` for frozen official GTFS evidence,
``scripts/gate_c_live_bus_timetables.py`` for current official bus timetables,
and ``scripts/gate_c_live_trenord.py`` for current official Trenord GTFS.
"""

INVALIDATED_EPISTEMIC_STATUS = "INVALIDATED_AS_EVIDENCE"


def main() -> None:
    raise RuntimeError(
        "Gate C fail-closed: scripts/02_parse_gtfs.py constructed pseudo-GTFS and is invalidated. "
        "Use official-source Gate C pipelines instead."
    )


if __name__ == "__main__":
    main()
