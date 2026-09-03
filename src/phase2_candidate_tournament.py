"""Final Phase 2 tournament over topology + service-plan candidates.

Structural scenarios and operating plans are distinct model objects. This module
makes that distinction explicit so the same route geometry can compete under
multiple headways, spans, phases or calendars without overwriting itself.

No weighted composite score is used. The decision order follows the Phase 2 spec:
1. hard eligibility;
2. robust passenger utility;
3. explicit uncertainty band;
4. lexicographic practical tie-break.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import math
from statistics import median
from typing import Mapping, Sequence

from src.phase2_optimizer_core import HardConstraintResult
from src.phase2_service_engine import JourneyComparison


def _require_finite(name: str, value: float) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{name} must be finite")
    return number


@dataclass(frozen=True)
class CandidateKey:
    scenario_id: str
    plan_id: str

    def __post_init__(self) -> None:
        if not self.scenario_id or not self.plan_id:
            raise ValueError("CandidateKey requires scenario_id and plan_id")

    @property
    def candidate_id(self) -> str:
        raw = json.dumps(
            {"scenario_id": self.scenario_id, "plan_id": self.plan_id},
            sort_keys=True,
            separators=(",", ":"),
        )
        return f"CAND_{sha256(raw.encode('utf-8')).hexdigest()[:16]}"


@dataclass(frozen=True)
class CandidateSensitivityResult:
    key: CandidateKey
    sensitivity_id: str
    demand_weighted_gjt_improvement_min: float
    worst_municipality_utility_change_min: float
    missed_connection_probability: float

    def __post_init__(self) -> None:
        if not self.sensitivity_id:
            raise ValueError("sensitivity_id is required")
        _require_finite("demand_weighted_gjt_improvement_min", self.demand_weighted_gjt_improvement_min)
        _require_finite("worst_municipality_utility_change_min", self.worst_municipality_utility_change_min)
        missed = _require_finite("missed_connection_probability", self.missed_connection_probability)
        if not 0.0 <= missed <= 1.0:
            raise ValueError("missed_connection_probability must be within [0,1]")


@dataclass(frozen=True)
class CandidateEvaluation:
    key: CandidateKey
    eligible: bool
    median_gjt_improvement_min: float
    lower_quantile_gjt_improvement_min: float
    median_missed_connection_probability: float
    annual_bus_km: float
    public_pattern_complexity: int
    unverified_elements: int
    retained_existing_stops_share: float
    n_sensitivity_runs: int

    def __post_init__(self) -> None:
        _require_finite("median_gjt_improvement_min", self.median_gjt_improvement_min)
        _require_finite("lower_quantile_gjt_improvement_min", self.lower_quantile_gjt_improvement_min)
        missed = _require_finite(
            "median_missed_connection_probability",
            self.median_missed_connection_probability,
        )
        annual_km = _require_finite("annual_bus_km", self.annual_bus_km)
        retained = _require_finite("retained_existing_stops_share", self.retained_existing_stops_share)
        if annual_km <= 0:
            raise ValueError("annual_bus_km must be positive")
        if self.public_pattern_complexity <= 0 or self.unverified_elements < 0:
            raise ValueError("Invalid practical tie-break metrics")
        if not 0.0 <= retained <= 1.0:
            raise ValueError("retained_existing_stops_share must be within [0,1]")
        if self.n_sensitivity_runs <= 0:
            raise ValueError("n_sensitivity_runs must be positive")
        if not 0.0 <= missed <= 1.0:
            raise ValueError("median missed-connection probability must be within [0,1]")

    @property
    def candidate_id(self) -> str:
        return self.key.candidate_id


@dataclass(frozen=True)
class CandidateSelection:
    primary: CandidateEvaluation
    runner_up: CandidateEvaluation | None
    tie_break_invoked: bool
    uncertainty_band_min: float


def candidate_sensitivity_from_comparison(
    *,
    key: CandidateKey,
    comparison: JourneyComparison,
) -> CandidateSensitivityResult:
    return CandidateSensitivityResult(
        key=key,
        sensitivity_id=comparison.sensitivity_id,
        demand_weighted_gjt_improvement_min=comparison.demand_weighted_gjt_improvement_min,
        worst_municipality_utility_change_min=comparison.worst_municipality_gjt_improvement_min,
        missed_connection_probability=comparison.candidate_weighted_missed_connection_probability,
    )


def _linear_quantile(values: Sequence[float], q: float) -> float:
    q_value = _require_finite("q", q)
    ordered = sorted(_require_finite("quantile value", value) for value in values)
    if not ordered:
        raise ValueError("Cannot compute quantile of empty values")
    if not 0.0 <= q_value <= 1.0:
        raise ValueError("q must be within [0,1]")
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * q_value
    low = int(position)
    high = min(low + 1, len(ordered) - 1)
    fraction = position - low
    return ordered[low] * (1.0 - fraction) + ordered[high] * fraction


def aggregate_candidate_evaluation(
    *,
    key: CandidateKey,
    hard_constraints: HardConstraintResult,
    sensitivity_results: Sequence[CandidateSensitivityResult],
    annual_bus_km: float,
    public_pattern_complexity: int,
    unverified_elements: int,
    retained_existing_stops_share: float,
    lower_quantile: float = 0.10,
) -> CandidateEvaluation:
    matching = [row for row in sensitivity_results if row.key == key]
    if not matching:
        raise ValueError(f"No sensitivity results for candidate {key.candidate_id}")
    sensitivity_ids = [row.sensitivity_id for row in matching]
    if len(set(sensitivity_ids)) != len(sensitivity_ids):
        raise ValueError(f"Duplicate sensitivity_id for candidate {key.candidate_id}")
    gjt = [row.demand_weighted_gjt_improvement_min for row in matching]
    missed = [row.missed_connection_probability for row in matching]
    return CandidateEvaluation(
        key=key,
        eligible=hard_constraints.eligible,
        median_gjt_improvement_min=float(median(gjt)),
        lower_quantile_gjt_improvement_min=_linear_quantile(gjt, lower_quantile),
        median_missed_connection_probability=float(median(missed)),
        annual_bus_km=float(annual_bus_km),
        public_pattern_complexity=int(public_pattern_complexity),
        unverified_elements=int(unverified_elements),
        retained_existing_stops_share=float(retained_existing_stops_share),
        n_sensitivity_runs=len(matching),
    )


def _tie_key(row: CandidateEvaluation) -> tuple:
    return (
        row.median_missed_connection_probability,
        row.public_pattern_complexity,
        row.annual_bus_km,
        row.unverified_elements,
        -row.retained_existing_stops_share,
        -row.lower_quantile_gjt_improvement_min,
        row.candidate_id,
    )


def select_candidates(
    evaluations: Sequence[CandidateEvaluation],
    *,
    uncertainty_band_min: float,
) -> CandidateSelection:
    uncertainty_band = _require_finite("uncertainty_band_min", uncertainty_band_min)
    if uncertainty_band < 0:
        raise ValueError("uncertainty_band_min cannot be negative")
    ids = [row.candidate_id for row in evaluations]
    if len(set(ids)) != len(ids):
        raise ValueError("Duplicate candidate_id in tournament input")
    eligible = [row for row in evaluations if row.eligible]
    if not eligible:
        raise ValueError("No eligible Phase 2 topology+service candidates")

    best_median = max(row.median_gjt_improvement_min for row in eligible)
    contenders = [
        row for row in eligible
        if best_median - row.median_gjt_improvement_min <= uncertainty_band
    ]
    tie_break = len(contenders) > 1
    primary = sorted(contenders, key=_tie_key)[0] if tie_break else contenders[0]

    remaining = [row for row in eligible if row.candidate_id != primary.candidate_id]
    if not remaining:
        return CandidateSelection(primary, None, tie_break, uncertainty_band)

    second_best = max(row.median_gjt_improvement_min for row in remaining)
    second_contenders = [
        row for row in remaining
        if second_best - row.median_gjt_improvement_min <= uncertainty_band
    ]
    runner = sorted(second_contenders, key=_tie_key)[0] if len(second_contenders) > 1 else second_contenders[0]
    return CandidateSelection(primary, runner, tie_break, uncertainty_band)


def _dominates(left: CandidateEvaluation, right: CandidateEvaluation, *, tolerance: float) -> bool:
    no_worse = (
        left.median_gjt_improvement_min + tolerance >= right.median_gjt_improvement_min
        and left.lower_quantile_gjt_improvement_min + tolerance >= right.lower_quantile_gjt_improvement_min
        and left.median_missed_connection_probability <= right.median_missed_connection_probability + tolerance
        and left.annual_bus_km <= right.annual_bus_km + tolerance
    )
    strictly_better = (
        left.median_gjt_improvement_min > right.median_gjt_improvement_min + tolerance
        or left.lower_quantile_gjt_improvement_min > right.lower_quantile_gjt_improvement_min + tolerance
        or left.median_missed_connection_probability + tolerance < right.median_missed_connection_probability
        or left.annual_bus_km + tolerance < right.annual_bus_km
    )
    return no_worse and strictly_better


def candidate_frontier(
    evaluations: Sequence[CandidateEvaluation],
    *,
    tolerance: float = 1e-9,
) -> list[CandidateEvaluation]:
    tolerance_value = _require_finite("tolerance", tolerance)
    if tolerance_value < 0:
        raise ValueError("tolerance cannot be negative")
    eligible = [row for row in evaluations if row.eligible]
    frontier = [
        row for row in eligible
        if not any(
            other.candidate_id != row.candidate_id
            and _dominates(other, row, tolerance=tolerance_value)
            for other in eligible
        )
    ]
    return sorted(
        frontier,
        key=lambda row: (
            -row.median_gjt_improvement_min,
            -row.lower_quantile_gjt_improvement_min,
            row.median_missed_connection_probability,
            row.annual_bus_km,
            row.candidate_id,
        ),
    )


def candidate_budget_frontier(
    evaluations: Sequence[CandidateEvaluation],
    budget_envelopes_km: Sequence[float],
) -> list[dict[str, object]]:
    raw_budgets = [_require_finite("budget envelope", value) for value in budget_envelopes_km]
    if any(value <= 0 for value in raw_budgets):
        raise ValueError("Budget envelopes must all be positive")
    budgets = sorted(set(raw_budgets))
    if not budgets:
        raise ValueError("At least one positive budget envelope is required")

    rows: list[dict[str, object]] = []
    previous_utility: float | None = None
    previous_km: float | None = None
    for budget in budgets:
        feasible = [row for row in evaluations if row.eligible and row.annual_bus_km <= budget]
        if not feasible:
            rows.append({
                "budget_km": budget,
                "candidate_id": None,
                "scenario_id": None,
                "plan_id": None,
                "annual_bus_km": None,
                "median_gjt_improvement_min": None,
                "marginal_utility_per_1000_bus_km": None,
            })
            continue
        winner = sorted(
            feasible,
            key=lambda row: (-row.median_gjt_improvement_min, row.annual_bus_km, row.candidate_id),
        )[0]
        marginal = None
        if previous_utility is not None and previous_km is not None and winner.annual_bus_km > previous_km:
            marginal = (
                (winner.median_gjt_improvement_min - previous_utility)
                / (winner.annual_bus_km - previous_km)
                * 1000.0
            )
        rows.append({
            "budget_km": budget,
            "candidate_id": winner.candidate_id,
            "scenario_id": winner.key.scenario_id,
            "plan_id": winner.key.plan_id,
            "annual_bus_km": winner.annual_bus_km,
            "median_gjt_improvement_min": winner.median_gjt_improvement_min,
            "marginal_utility_per_1000_bus_km": marginal,
        })
        previous_utility = winner.median_gjt_improvement_min
        previous_km = winner.annual_bus_km
    return rows


def candidate_to_dict(row: CandidateEvaluation) -> dict[str, object]:
    return {
        "candidate_id": row.candidate_id,
        "scenario_id": row.key.scenario_id,
        "plan_id": row.key.plan_id,
        "eligible": row.eligible,
        "median_gjt_improvement_min": row.median_gjt_improvement_min,
        "lower_quantile_gjt_improvement_min": row.lower_quantile_gjt_improvement_min,
        "median_missed_connection_probability": row.median_missed_connection_probability,
        "annual_bus_km": row.annual_bus_km,
        "public_pattern_complexity": row.public_pattern_complexity,
        "unverified_elements": row.unverified_elements,
        "retained_existing_stops_share": row.retained_existing_stops_share,
        "n_sensitivity_runs": row.n_sensitivity_runs,
    }
