#!/usr/bin/env python3
"""Legacy train/bus coordination analysis, invalidated by Gate C.

The former implementation embedded S8 minute-of-hour values and manually
specified bus scenarios/coincidence counts. It must not create downstream
results after Gate C.

Current S8 events must come from ``scripts/gate_c_live_trenord.py``. Candidate
bus schedules belong to downstream service-math/scenario gates and must be
labelled MODEL OUTPUT / ASSUMPTION as appropriate.
"""

INVALIDATED_EPISTEMIC_STATUS = "INVALIDATED_AS_EVIDENCE"


def main() -> None:
    raise RuntimeError(
        "Gate C fail-closed: scripts/11_train_coordination.py used hard-coded S8 and scenario metrics. "
        "Use current official Trenord GTFS events and validated downstream scenarios instead."
    )


if __name__ == "__main__":
    main()
