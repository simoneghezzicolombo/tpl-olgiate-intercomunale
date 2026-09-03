"""Adapt the Gate D v2 handoff into Gate F structural eligibility evidence."""
from __future__ import annotations

from pathlib import Path
import pandas as pd


UNCERTAINTY_ORDER = {"RESOLVED": 0, "QUANTIFIED": 1, "UNKNOWN": 2}


def adapt_gate_d_handoff(path: str | Path, *, gate_d_commit: str) -> pd.DataFrame:
    if len(gate_d_commit) != 40 or any(ch not in "0123456789abcdef" for ch in gate_d_commit.lower()):
        raise ValueError("gate_d_commit must be a full 40-hex SHA")
    required = {
        "contract_version", "scenario_id", "upstream_gate_d_status", "gate_d_artifact", "gate_d_commit",
        "route_km", "route_km_status", "pure_running_min", "pure_running_status",
        "road_uncertainty_status",
    }
    frame = pd.read_csv(path)
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"Gate D handoff missing columns: {missing}")
    if frame.empty:
        raise ValueError("Gate D handoff is empty")
    if not frame["contract_version"].astype(str).str.strip().eq("GATE_D_TO_E_V2").all():
        raise ValueError("Gate D handoff must use GATE_D_TO_E_V2")
    if not frame["upstream_gate_d_status"].astype(str).str.strip().str.upper().eq("PASS").all():
        raise ValueError("Gate D handoff contains non-PASS rows")
    recorded = frame["gate_d_commit"].astype(str).str.strip().str.lower()
    if not recorded.eq(gate_d_commit.lower()).all():
        raise ValueError("Gate D handoff commit lineage does not match requested gate_d_commit")
    route_km = pd.to_numeric(frame["route_km"], errors="coerce")
    running = pd.to_numeric(frame["pure_running_min"], errors="coerce")
    if route_km.isna().any() or running.isna().any() or (route_km <= 0).any() or (running <= 0).any():
        raise ValueError("Gate D structural handoff requires positive finite route_km and pure_running_min")
    uncertainty = frame["road_uncertainty_status"].astype(str).str.strip().str.upper()
    if (~uncertainty.isin(UNCERTAINTY_ORDER)).any():
        raise ValueError("Gate D handoff contains invalid road_uncertainty_status")
    if frame["scenario_id"].isna().any() or frame["scenario_id"].astype(str).str.strip().eq("").any():
        raise ValueError("Gate D handoff requires scenario_id")

    rows = []
    for scenario_id, group in frame.groupby("scenario_id", sort=True):
        statuses = group["road_uncertainty_status"].astype(str).str.strip().str.upper().tolist()
        scenario_uncertainty = max(statuses, key=lambda status: UNCERTAINTY_ORDER[status])
        artifacts = sorted(set(group["gate_d_artifact"].astype(str)))
        if not artifacts or any(not item.strip() for item in artifacts):
            raise ValueError(f"{scenario_id}: Gate D artifact lineage is missing")
        source = f"gate-d:{gate_d_commit}:" + "|".join(artifacts)
        rows.append({
            "scenario_id": str(scenario_id),
            "road_feasible": True,
            "road_feasible__status": "DERIVED",
            "road_feasible__source": source,
            "road_feasible__unit": "boolean",
            "road_feasible__semantics": "STRUCTURAL_ROUTING_ELIGIBILITY_CONSTRAINT",
            "road_feasible__comparison_basis": f"GateD={gate_d_commit}|GATE_D_TO_E_V2_STRUCTURAL_ROUTING",
            "road_uncertainty_status": scenario_uncertainty,
            "road_uncertainty_source": source,
        })
    return pd.DataFrame(rows)
