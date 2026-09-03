"""Gate F closure audit.

This module answers a narrower but decisive question before any final Pareto run:
do the validated upstream artifacts contain at least two assumption-free future
alternatives that can lawfully enter the recommendation contract?

It deliberately does not invent stop sets, service calendars, headways or
connection phases. A Gate F PASS may therefore conclude that no definitive
recommendation is supportable from the current evidence.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import pandas as pd


PAIR_REQUIRED = {
    "route_id",
    "route_type",
    "component_families",
    "route_definition_status",
    "route_definition_basis",
    "service_math_status",
    "paired_directional_cycle_km",
    "paired_pure_running_min",
    "budget_bus_km_year",
    "max_equal_CW_CCW_cycles_year_under_budget",
    "annual_bus_km_at_max_equal_pairs",
    "budget_margin_km_at_max_equal_pairs",
}
UNPAIRED_REQUIRED = {
    "candidate_id",
    "family",
    "direction",
    "route_km",
    "pure_running_min",
    "gate_e_pairing_status",
    "candidate_status",
}
ASSUMPTION_STATUSES = {"ASSUMPTION", "PLACEHOLDER", "INVALIDATED"}


@dataclass(frozen=True)
class ClosureResult:
    verdict: str
    recommendation_status: str
    paired_hypotheses: int
    unpaired_candidates: int
    assumption_free_pairable_alternatives: int
    definitive_pareto_eligible: bool
    reasons: tuple[str, ...]


def _read_csv(path: str | Path, required: Iterable[str], label: str) -> pd.DataFrame:
    frame = pd.read_csv(path)
    missing = sorted(set(required) - set(frame.columns))
    if missing:
        raise ValueError(f"{label}: missing columns {missing}")
    if frame.empty:
        raise ValueError(f"{label}: empty upstream artifact")
    return frame.copy()


def build_scenario_inventory(
    paired_path: str | Path,
    unpaired_path: str | Path,
) -> pd.DataFrame:
    """Inventory every Gate E alternative without selecting a preferred topology."""
    paired = _read_csv(paired_path, PAIR_REQUIRED, "paired")
    unpaired = _read_csv(unpaired_path, UNPAIRED_REQUIRED, "unpaired")

    if paired["route_id"].isna().any() or paired["route_id"].astype(str).str.strip().eq("").any():
        raise ValueError("paired: route_id must be non-empty")
    if unpaired["candidate_id"].isna().any() or unpaired["candidate_id"].astype(str).str.strip().eq("").any():
        raise ValueError("unpaired: candidate_id must be non-empty")
    if paired["route_id"].astype(str).duplicated().any():
        raise ValueError("paired: duplicate route_id")
    if unpaired["candidate_id"].astype(str).duplicated().any():
        raise ValueError("unpaired: duplicate candidate_id")

    paired_rows = pd.DataFrame(
        {
            "scenario_id": paired["route_id"].astype(str),
            "scenario_family": paired["component_families"].astype(str),
            "inventory_class": "PAIRED_BIDIRECTIONAL_HYPOTHESIS",
            "route_definition_status": paired["route_definition_status"].astype(str).str.strip().str.upper(),
            "gate_e_eligibility": paired["service_math_status"].astype(str),
            "route_km_or_pair_km": pd.to_numeric(paired["paired_directional_cycle_km"], errors="raise"),
            "pure_running_min": pd.to_numeric(paired["paired_pure_running_min"], errors="raise"),
            "budget_bus_km_year": pd.to_numeric(paired["budget_bus_km_year"], errors="raise"),
            "max_equal_pairs_year": pd.to_numeric(
                paired["max_equal_CW_CCW_cycles_year_under_budget"], errors="raise"
            ),
            "annual_bus_km_at_envelope": pd.to_numeric(
                paired["annual_bus_km_at_max_equal_pairs"], errors="raise"
            ),
            "budget_margin_km": pd.to_numeric(
                paired["budget_margin_km_at_max_equal_pairs"], errors="raise"
            ),
            "source_basis": paired["route_definition_basis"].astype(str),
            "definitive_recommendation_eligible": False,
            "exclusion_or_limit": "ROUTE_DEFINITION_NOT_OBSERVED_FUTURE_SERVICE",
        }
    )
    paired_rows["definitive_recommendation_eligible"] = ~paired_rows[
        "route_definition_status"
    ].isin(ASSUMPTION_STATUSES)

    unpaired_rows = pd.DataFrame(
        {
            "scenario_id": unpaired["candidate_id"].astype(str),
            "scenario_family": unpaired["family"].astype(str),
            "inventory_class": "UNPAIRED_CANDIDATE",
            "route_definition_status": unpaired["candidate_status"].astype(str).str.strip().str.upper(),
            "gate_e_eligibility": unpaired["gate_e_pairing_status"].astype(str),
            "route_km_or_pair_km": pd.to_numeric(unpaired["route_km"], errors="raise"),
            "pure_running_min": pd.to_numeric(unpaired["pure_running_min"], errors="raise"),
            "budget_bus_km_year": pd.NA,
            "max_equal_pairs_year": pd.NA,
            "annual_bus_km_at_envelope": pd.NA,
            "budget_margin_km": pd.NA,
            "source_basis": "GATE_D_HYPOTHESIS_NOT_RECOMMENDATION",
            "definitive_recommendation_eligible": False,
            "exclusion_or_limit": "UNPAIRED_NOT_ELIGIBLE_FOR_FULL_BIDIRECTIONAL_SERVICE_MATH",
        }
    )

    inventory = pd.concat([paired_rows, unpaired_rows], ignore_index=True)
    if inventory["scenario_id"].duplicated().any():
        raise ValueError("Scenario inventory contains duplicate identifiers")
    return inventory.sort_values(["inventory_class", "scenario_id"]).reset_index(drop=True)


def close_gate_f_from_inventory(inventory: pd.DataFrame) -> ClosureResult:
    required = {
        "scenario_id",
        "inventory_class",
        "route_definition_status",
        "definitive_recommendation_eligible",
    }
    missing = sorted(required - set(inventory.columns))
    if missing:
        raise ValueError(f"inventory: missing columns {missing}")

    paired = inventory["inventory_class"].eq("PAIRED_BIDIRECTIONAL_HYPOTHESIS")
    unpaired = inventory["inventory_class"].eq("UNPAIRED_CANDIDATE")
    assumption_free = paired & inventory["definitive_recommendation_eligible"].astype(bool)
    n_assumption_free = int(assumption_free.sum())

    if n_assumption_free >= 2:
        return ClosureResult(
            verdict="READY_FOR_DEFINITIVE_PARETO",
            recommendation_status="DEFINITIVE_PARETO_REQUIRED",
            paired_hypotheses=int(paired.sum()),
            unpaired_candidates=int(unpaired.sum()),
            assumption_free_pairable_alternatives=n_assumption_free,
            definitive_pareto_eligible=True,
            reasons=("At least two assumption-free pairable alternatives exist.",),
        )

    reasons = (
        "Validated upstream service math contains fewer than two assumption-free pairable future alternatives.",
        "Gate F must not convert route, stop, headway, calendar or timetable assumptions into factual recommendation evidence.",
        "The scientifically valid closure is no definitive single recommendation from current evidence, not an invented winner.",
    )
    return ClosureResult(
        verdict="PASS",
        recommendation_status="NO_DEFINITIVE_RECOMMENDATION_SUPPORTED_BY_CURRENT_EVIDENCE",
        paired_hypotheses=int(paired.sum()),
        unpaired_candidates=int(unpaired.sum()),
        assumption_free_pairable_alternatives=n_assumption_free,
        definitive_pareto_eligible=False,
        reasons=reasons,
    )
