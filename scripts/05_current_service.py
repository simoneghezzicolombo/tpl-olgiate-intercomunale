#!/usr/bin/env python3
"""Legacy current-service baseline, invalidated by Gate C.

The previous implementation embedded populations, trip counts, headways,
walking times and S8 connections manually. Those values are not admissible as
FACT/DERIVED transit evidence and the script is deliberately fail-closed.

Use Gate B outputs for validated spatial/accessibility quantities and Gate C
official-source pipelines for routes, service dates and timetables.
"""

INVALIDATED_EPISTEMIC_STATUS = "INVALIDATED_AS_EVIDENCE"


def main() -> None:
    raise RuntimeError(
        "Gate C fail-closed: scripts/05_current_service.py contained hard-coded transit metrics. "
        "Rebuild any current-service baseline from validated Gate B + Gate C source outputs."
    )


if __name__ == "__main__":
    main()
