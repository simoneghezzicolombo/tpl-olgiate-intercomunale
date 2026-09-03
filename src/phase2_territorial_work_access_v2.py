"""Territorial 2021 work-demand home-access helpers for Phase 2 V2.

This module keeps observed municipal work OD separate from modeled walking
access. It provides two deliberately different quantities:

1. a model-capacity upper bound on how many resident workers could fit inside
   the modeled resident population covered by the public stop set; and
2. an explicit within-municipality population-proportional sensitivity.

Neither quantity identifies which worker lives in a covered building, which
stop they would use, which bus route they would board, or whether their work
endpoint is served. They are not passenger-demand observations.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable, Mapping


CONTRACT = "PHASE2_TERRITORIAL_WORK_HOME_ACCESS_V2"
STATUS = "PASS_TERRITORIAL_WORK_HOME_ACCESS_V2_BUILD"
CATEGORIES = ("SELF", "OTHER_CORE", "S8_DIRECT", "OTHER_EXTERNAL")


@dataclass(frozen=True)
class OriginDemand:
    origin_code: str
    origin_name: str
    by_category: Mapping[str, float]

    def validate(self) -> None:
        if not self.origin_code or not self.origin_name:
            raise ValueError("Origin demand requires code and name")
        if set(self.by_category) != set(CATEGORIES):
            raise ValueError(f"Origin demand must contain exactly {CATEGORIES}")
        for category, value in self.by_category.items():
            number = float(value)
            if not math.isfinite(number) or number < 0:
                raise ValueError(f"Invalid worker count for {category}")

    @property
    def worker_total(self) -> float:
        self.validate()
        return sum(float(self.by_category[c]) for c in CATEGORIES)

    @property
    def core_local_total(self) -> float:
        self.validate()
        return float(self.by_category["SELF"]) + float(self.by_category["OTHER_CORE"])


def aggregate_origin_demand(rows: Iterable[Mapping[str, object]]) -> dict[str, OriginDemand]:
    names: dict[str, str] = {}
    counts: dict[str, dict[str, float]] = {}
    for row in rows:
        code = str(row.get("procom_res", "")).strip()
        name = str(row.get("origin_name", "")).strip()
        category = str(row.get("category", "")).strip()
        if not code or not name or category not in CATEGORIES:
            raise ValueError("OD row has invalid origin/category identity")
        workers = float(row.get("workers", 0))
        if not math.isfinite(workers) or workers < 0:
            raise ValueError("OD worker count must be finite and non-negative")
        if code in names and names[code] != name:
            raise ValueError(f"Conflicting municipality name for {code}")
        names[code] = name
        bucket = counts.setdefault(code, {c: 0.0 for c in CATEGORIES})
        bucket[category] += workers
    if not counts:
        raise ValueError("OD origin-demand universe is empty")
    result = {
        code: OriginDemand(code, names[code], dict(counts[code]))
        for code in sorted(counts)
    }
    for demand in result.values():
        demand.validate()
    return result


def modeled_worker_capacity_upper_bound(*, worker_count: float, modeled_covered_residents: float) -> float:
    """Maximum workers that could fit inside a modeled covered-resident count.

    This is a capacity bound only. Because covered residents are model outputs,
    it is not an observed statistical confidence bound and has no positive
    lower-bound implication for worker accessibility.
    """
    workers = float(worker_count)
    covered = float(modeled_covered_residents)
    if not all(math.isfinite(v) and v >= 0 for v in (workers, covered)):
        raise ValueError("Worker count and covered residents must be finite and non-negative")
    return min(workers, covered)


def population_proportional_sensitivity(*, worker_count: float, resident_coverage_share: float) -> float:
    """Explicit sensitivity assuming workers follow resident coverage shares."""
    workers = float(worker_count)
    share = float(resident_coverage_share)
    if not math.isfinite(workers) or workers < 0:
        raise ValueError("worker_count must be finite and non-negative")
    if not math.isfinite(share) or not 0.0 <= share <= 1.0:
        raise ValueError("resident_coverage_share must lie in [0,1]")
    return workers * share


def scenario_home_access_metrics(
    *,
    origin_demand: Mapping[str, OriginDemand],
    located_population: Mapping[str, float],
    coverage_share: Mapping[str, float],
) -> dict[str, float]:
    """Compute total capacity upper bound plus additive sensitivity categories."""
    if set(origin_demand) != set(located_population) or set(origin_demand) != set(coverage_share):
        raise ValueError("Demand, population and coverage municipality universes must match exactly")
    totals = {c: 0.0 for c in CATEGORIES}
    capacity_upper = 0.0
    for code in sorted(origin_demand):
        demand = origin_demand[code]
        demand.validate()
        pop = float(located_population[code])
        share = float(coverage_share[code])
        if not math.isfinite(pop) or pop <= 0:
            raise ValueError(f"Invalid located population for {code}")
        if not math.isfinite(share) or not 0.0 <= share <= 1.0:
            raise ValueError(f"Invalid resident coverage share for {code}")
        covered = pop * share
        capacity_upper += modeled_worker_capacity_upper_bound(
            worker_count=demand.worker_total,
            modeled_covered_residents=covered,
        )
        for category in CATEGORIES:
            totals[category] += population_proportional_sensitivity(
                worker_count=float(demand.by_category[category]),
                resident_coverage_share=share,
            )
    total_sensitivity = sum(totals.values())
    return {
        "capacity_upper_bound": capacity_upper,
        "population_proportional_total": total_sensitivity,
        "population_proportional_self": totals["SELF"],
        "population_proportional_other_core": totals["OTHER_CORE"],
        "population_proportional_core_local": totals["SELF"] + totals["OTHER_CORE"],
        "population_proportional_s8_direct": totals["S8_DIRECT"],
        "population_proportional_other_external": totals["OTHER_EXTERNAL"],
    }
