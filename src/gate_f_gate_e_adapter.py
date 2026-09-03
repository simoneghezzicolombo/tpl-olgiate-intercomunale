"""Adapt validated Gate E V2 outputs into the Gate F v2 service fragment.

No service window, headway band or fleet interpretation is chosen implicitly.
Those choices must be explicit in a policy file and are frozen into the
comparison_basis fields so scenarios cannot be compared on different bases.
"""
from __future__ import annotations

import json
from pathlib import Path
import pandas as pd


FLEET_COLUMNS = {
    "DIRECTION_LOCKED_TOTAL": "minimum_scheduled_vehicles_direction_locked_total",
    "HUB_INTERLINING_ALLOWED": "minimum_scheduled_vehicles_hub_interlining_allowed",
}


def load_policy(path: str | Path) -> dict[str, str]:
    try:
        policy = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot read Gate E-to-F policy: {exc}") from exc
    required = {"schema_version", "comparison_id", "service_day_group", "headway_band_id", "fleet_measure"}
    missing = required - set(policy)
    if missing:
        raise ValueError(f"Gate E-to-F policy missing fields: {sorted(missing)}")
    if policy["schema_version"] != 1:
        raise ValueError("Gate E-to-F policy schema_version must equal 1")
    for key in ("comparison_id", "service_day_group", "headway_band_id"):
        if not str(policy[key]).strip():
            raise ValueError(f"Gate E-to-F policy {key} must be non-empty")
    fleet_measure = str(policy["fleet_measure"]).strip().upper()
    if fleet_measure not in FLEET_COLUMNS:
        raise ValueError(f"Unsupported fleet_measure: {fleet_measure}")
    return {
        "comparison_id": str(policy["comparison_id"]).strip(),
        "service_day_group": str(policy["service_day_group"]).strip(),
        "headway_band_id": str(policy["headway_band_id"]).strip(),
        "fleet_measure": fleet_measure,
    }


def _read(path: str | Path, required: set[str], label: str) -> pd.DataFrame:
    frame = pd.read_csv(path)
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"{label}: missing columns {missing}")
    if frame.empty:
        raise ValueError(f"{label}: empty input")
    return frame


def adapt_gate_e_outputs(
    scenario_path: str | Path,
    band_path: str | Path,
    fleet_path: str | Path,
    policy_path: str | Path,
    *,
    gate_e_commit: str,
) -> pd.DataFrame:
    if len(gate_e_commit) != 40 or any(ch not in "0123456789abcdef" for ch in gate_e_commit.lower()):
        raise ValueError("gate_e_commit must be a full 40-hex SHA")
    policy = load_policy(policy_path)
    scenario = _read(
        scenario_path,
        {"scenario_id", "gate_status", "annual_bus_km", "assumption_present"},
        "Gate E scenario output",
    )
    bands = _read(
        band_path,
        {
            "scenario_id", "service_day_group", "band_id", "gate_status",
            "headway_combined_rate_equiv_min", "combined_headway_applicability",
        },
        "Gate E band output",
    )
    fleet = _read(
        fleet_path,
        {
            "scenario_id", "service_day_group", "fleet_evidence_status",
            "minimum_scheduled_vehicles_direction_locked_total",
            "minimum_scheduled_vehicles_hub_interlining_allowed",
            "fleet_scope", "excluded_from_fleet_scope",
        },
        "Gate E fleet output",
    )

    if scenario["scenario_id"].duplicated().any():
        raise ValueError("Gate E scenario output requires one row per scenario")
    if not scenario["gate_status"].astype(str).str.strip().eq("ELIGIBLE_FOR_GATE_E_VERDICT").all():
        raise ValueError("Gate E scenario rows must be ELIGIBLE_FOR_GATE_E_VERDICT")
    assumptions = scenario["assumption_present"].astype(str).str.strip().str.lower()
    if not assumptions.isin({"false", "0"}).all():
        raise ValueError("Gate E production fragment cannot contain assumption_present=true")

    selected_band = bands.loc[
        bands["service_day_group"].astype(str).eq(policy["service_day_group"])
        & bands["band_id"].astype(str).eq(policy["headway_band_id"])
    ].copy()
    if selected_band.empty or selected_band["scenario_id"].duplicated().any():
        raise ValueError("Gate E selected headway band must contain exactly one row per represented scenario")
    if not selected_band["gate_status"].astype(str).str.strip().eq("ELIGIBLE_FOR_GATE_E_VERDICT").all():
        raise ValueError("Selected Gate E headway band is not verdict-eligible")
    if not selected_band["combined_headway_applicability"].astype(str).str.strip().eq(
        "COMPUTED_SHARED_STOP_PATTERN_CONFIRMED"
    ).all():
        raise ValueError("Rate-equivalent combined headway requires confirmed shared stop pattern")
    headway = pd.to_numeric(selected_band["headway_combined_rate_equiv_min"], errors="coerce")
    if headway.isna().any() or (headway <= 0).any():
        raise ValueError("Selected combined headway must be finite and > 0")

    selected_fleet = fleet.loc[fleet["service_day_group"].astype(str).eq(policy["service_day_group"])].copy()
    if selected_fleet.empty or selected_fleet["scenario_id"].duplicated().any():
        raise ValueError("Gate E selected fleet day group must contain exactly one row per represented scenario")
    if not selected_fleet["fleet_evidence_status"].astype(str).str.strip().eq(
        "ELIGIBLE_FOR_GATE_E_SCHEDULED_FLEET_EVIDENCE"
    ).all():
        raise ValueError("Selected Gate E fleet rows are not evidence-eligible")

    fleet_column = FLEET_COLUMNS[policy["fleet_measure"]]
    vehicles = pd.to_numeric(selected_fleet[fleet_column], errors="coerce")
    if vehicles.isna().any() or (vehicles < 1).any() or not (vehicles == vehicles.astype(int)).all():
        raise ValueError("Selected minimum scheduled fleet must be an integer >= 1")
    annual = pd.to_numeric(scenario["annual_bus_km"], errors="coerce")
    if annual.isna().any() or (annual <= 0).any():
        raise ValueError("Gate E annual_bus_km must be finite and > 0")

    merged = scenario[["scenario_id", "annual_bus_km"]].merge(
        selected_band[["scenario_id", "headway_combined_rate_equiv_min"]],
        on="scenario_id",
        validate="one_to_one",
    ).merge(
        selected_fleet[["scenario_id", fleet_column]],
        on="scenario_id",
        validate="one_to_one",
    )
    if len(merged) != len(scenario):
        raise ValueError("Gate E adapter lost scenario rows while joining band/fleet evidence")

    source_base = f"gate-e:{gate_e_commit}"
    comparison_id = policy["comparison_id"]
    merged = merged.rename(
        columns={
            "headway_combined_rate_equiv_min": "headway_combined_min",
            fleet_column: "minimum_scheduled_vehicles",
        }
    )
    merged["headway_combined_min__status"] = "MODEL OUTPUT"
    merged["headway_combined_min__source"] = source_base + ":gate_e_service_math_bands.csv"
    merged["headway_combined_min__unit"] = "min"
    merged["headway_combined_min__semantics"] = "RATE_EQUIVALENT_NOT_MAX_GAP"
    merged["headway_combined_min__comparison_basis"] = (
        comparison_id + "|day=" + policy["service_day_group"] + "|band=" + policy["headway_band_id"]
    )
    merged["annual_bus_km__status"] = "MODEL OUTPUT"
    merged["annual_bus_km__source"] = source_base + ":gate_e_service_math.csv"
    merged["annual_bus_km__unit"] = "bus-km/year"
    merged["annual_bus_km__semantics"] = "ANNUAL_SCHEDULED_BUS_DISTANCE"
    merged["annual_bus_km__comparison_basis"] = comparison_id + "|annual_service_plan"
    merged["minimum_scheduled_vehicles__status"] = "MODEL OUTPUT"
    merged["minimum_scheduled_vehicles__source"] = source_base + ":gate_e_fleet_audit.csv"
    merged["minimum_scheduled_vehicles__unit"] = "vehicles"
    merged["minimum_scheduled_vehicles__semantics"] = (
        "THEORETICAL_IN_SERVICE_SCHEDULED_MINIMUM_EXCLUDES_DEADHEAD_RELIEFS_MAINTENANCE_SPARES"
    )
    merged["minimum_scheduled_vehicles__comparison_basis"] = (
        comparison_id + "|day=" + policy["service_day_group"] + "|fleet=" + policy["fleet_measure"]
    )
    return merged
