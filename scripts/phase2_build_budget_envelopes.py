#!/usr/bin/env python3
"""Build Phase 2 budget envelopes from immutable validated Gate E evidence.

The annual production reference is NOT embedded in this module. It is read from
Gate E's structured PASS output at the validated computational commit. Search
proportions are explicit CLI inputs and are therefore design-space declarations,
not empirical facts.
"""
from __future__ import annotations

import argparse
import csv
from hashlib import sha256
import io
import json
from pathlib import Path
import urllib.request


GATE_E_COMMIT = "e2d096ca929c92da0d8a4abdacde827445e208bd"
GATE_E_PATH = "outputs/gate_e/gate_d_pass_budget_envelope.csv"
GATE_E_URL = (
    "https://raw.githubusercontent.com/"
    "simoneghezzicolombo/tpl-olgiate-intercomunale/"
    f"{GATE_E_COMMIT}/{GATE_E_PATH}"
)
EXPECTED_BUDGET_STATUS = "DERIVED_FROM_PDB_RECONSTRUCTED_LINE_TOTALS"
EXPECTED_GATE_D_STATUS = "PASS"


def fetch_pinned_gate_e(url: str = GATE_E_URL) -> tuple[list[dict[str, str]], str]:
    request = urllib.request.Request(url, headers={"User-Agent": "phase2-budget-envelopes/1.0"})
    with urllib.request.urlopen(request, timeout=60) as response:
        payload = response.read()
    digest = sha256(payload).hexdigest()
    rows = list(csv.DictReader(io.StringIO(payload.decode("utf-8"))))
    if not rows:
        raise ValueError("Pinned Gate E budget envelope is empty")
    return rows, digest


def extract_reference_budget(rows: list[dict[str, str]]) -> tuple[float, dict[str, object]]:
    required = {
        "gate_d_status",
        "gate_d_commit",
        "gate_d_artifact_id",
        "gate_d_artifact_sha256",
        "route_id",
        "route_definition_status",
        "budget_bus_km_year",
        "budget_status",
        "equal_pair_envelope_semantics",
    }
    missing = sorted(required - set(rows[0]))
    if missing:
        raise ValueError(f"Gate E budget envelope missing columns: {missing}")

    if any(row["gate_d_status"] != EXPECTED_GATE_D_STATUS for row in rows):
        raise ValueError("Gate E budget envelope contains non-PASS Gate D rows")
    if any(row["budget_status"] != EXPECTED_BUDGET_STATUS for row in rows):
        raise ValueError("Gate E budget reference has unexpected epistemic status")
    if any(row["route_definition_status"] != "ASSUMPTION" for row in rows):
        raise ValueError("Gate E route-definition semantics changed unexpectedly")
    if any(
        row["equal_pair_envelope_semantics"]
        != "INTEGER_MAX_FOR_EQUAL_CW_CCW_FULL_LOOPS_NOT_A_SERVICE_PLAN"
        for row in rows
    ):
        raise ValueError("Gate E envelope semantics changed unexpectedly")

    budgets = {float(row["budget_bus_km_year"]) for row in rows}
    if len(budgets) != 1:
        raise ValueError(f"Gate E pairable rows disagree on annual budget: {sorted(budgets)}")
    reference = budgets.pop()
    if reference <= 0:
        raise ValueError("Gate E annual budget must be positive")

    gate_d_commits = {row["gate_d_commit"] for row in rows}
    gate_d_artifact_ids = {row["gate_d_artifact_id"] for row in rows}
    gate_d_artifact_sha256 = {row["gate_d_artifact_sha256"] for row in rows}
    if len(gate_d_commits) != 1 or len(gate_d_artifact_ids) != 1 or len(gate_d_artifact_sha256) != 1:
        raise ValueError("Gate E rows do not share a single Gate D lineage")

    metadata: dict[str, object] = {
        "gate_e_commit": GATE_E_COMMIT,
        "gate_e_artifact": GATE_E_PATH,
        "gate_d_commit": next(iter(gate_d_commits)),
        "gate_d_artifact_id": next(iter(gate_d_artifact_ids)),
        "gate_d_artifact_sha256": next(iter(gate_d_artifact_sha256)),
        "budget_status": EXPECTED_BUDGET_STATUS,
        "pairable_route_ids": sorted(row["route_id"] for row in rows),
        "pairable_route_count": len(rows),
        "reference_semantics": "D184_PLUS_D185_RECONSTRUCTED_ANNUAL_BUS_KM_RESOURCE_BENCHMARK",
        "not_a_service_plan": True,
    }
    return reference, metadata


def parse_changes(raw: str) -> list[float]:
    try:
        values = [float(item.strip()) for item in raw.split(",") if item.strip()]
    except ValueError as exc:
        raise ValueError("--changes must be comma-separated decimal proportions") from exc
    if not values:
        raise ValueError("At least one budget change must be declared")
    if len(set(values)) != len(values):
        raise ValueError("Duplicate budget changes are not allowed")
    if any(1.0 + value <= 0 for value in values):
        raise ValueError("A budget change produces a non-positive envelope")
    return sorted(values)


def build_envelopes(reference_bus_km: float, changes: list[float]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for change in changes:
        rows.append(
            {
                "budget_change_fraction": change,
                "budget_change_percent": change * 100.0,
                "annual_bus_km_cap": reference_bus_km * (1.0 + change),
                "reference_annual_bus_km": reference_bus_km,
                "envelope_status": "PHASE2_DECLARED_DESIGN_SEARCH_ENVELOPE",
                "reference_status": EXPECTED_BUDGET_STATUS,
                "reference_gate_e_commit": GATE_E_COMMIT,
                "reference_gate_e_artifact": GATE_E_PATH,
            }
        )
    return rows


def write_outputs(
    envelopes: list[dict[str, object]],
    *,
    metadata: dict[str, object],
    source_sha256: str,
    csv_path: Path,
    validation_path: Path,
) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    validation_path.parent.mkdir(parents=True, exist_ok=True)

    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(envelopes[0]))
        writer.writeheader()
        writer.writerows(envelopes)

    validation = {
        "status": "PASS",
        **metadata,
        "gate_e_artifact_sha256": source_sha256,
        "reference_annual_bus_km": envelopes[0]["reference_annual_bus_km"],
        "declared_changes_fraction": [row["budget_change_fraction"] for row in envelopes],
        "annual_bus_km_caps": [row["annual_bus_km_cap"] for row in envelopes],
        "envelope_count": len(envelopes),
        "epistemic_note": (
            "The reference production is DERIVED from the validated Gate E/PdB reconstruction. "
            "The proportional Phase 2 envelopes are declared optimisation design-space choices, not facts."
        ),
    }
    validation_path.write_text(
        json.dumps(validation, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--changes",
        required=True,
        help="Comma-separated proportional changes, e.g. -0.2,-0.1,0,0.1,0.2,0.3",
    )
    parser.add_argument(
        "--csv-output",
        default="outputs/phase2/budget_envelopes.csv",
    )
    parser.add_argument(
        "--validation-output",
        default="outputs/phase2/budget_envelopes_validation.json",
    )
    args = parser.parse_args()

    source_rows, source_sha = fetch_pinned_gate_e()
    reference, metadata = extract_reference_budget(source_rows)
    changes = parse_changes(args.changes)
    envelopes = build_envelopes(reference, changes)
    write_outputs(
        envelopes,
        metadata=metadata,
        source_sha256=source_sha,
        csv_path=Path(args.csv_output),
        validation_path=Path(args.validation_output),
    )
    print(f"Validated Gate E annual production reference: {reference:.3f} bus-km/year")
    for row in envelopes:
        print(f"{row['budget_change_percent']:+.1f}% -> {row['annual_bus_km_cap']:.3f} bus-km/year")


if __name__ == "__main__":
    main()
