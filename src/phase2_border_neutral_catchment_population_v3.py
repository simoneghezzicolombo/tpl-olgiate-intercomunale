from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Iterable, Mapping


DEFAULT_CORE_CODES = frozenset({"097010", "097012", "097058", "097074", "097092"})
DEFAULT_MAX_WALK_MINUTES = 12.0
DEFAULT_WALK_SPEED_KMH = 4.8


@dataclass(frozen=True)
class PopulationUnit:
    unit_id: str
    municipality_code: str
    population_weight: float


@dataclass(frozen=True)
class CatchmentPopulationSummary:
    core_covered_population: float
    external_spillover_population: float
    total_catchment_population: float
    core_covered_units: int
    external_covered_units: int
    external_municipalities: tuple[str, ...]

    def __post_init__(self) -> None:
        numeric = (
            self.core_covered_population,
            self.external_spillover_population,
            self.total_catchment_population,
        )
        if any(not isfinite(float(value)) or float(value) < 0 for value in numeric):
            raise ValueError("catchment population values must be finite and non-negative")
        if self.core_covered_units < 0 or self.external_covered_units < 0:
            raise ValueError("covered-unit counts must be non-negative")
        expected = self.core_covered_population + self.external_spillover_population
        if abs(self.total_catchment_population - expected) > 1e-9:
            raise ValueError("total catchment population must equal core plus external spillover")
        if tuple(sorted(set(self.external_municipalities))) != self.external_municipalities:
            raise ValueError("external municipalities must be unique and sorted")


def max_walk_distance_metres(
    max_walk_minutes: float = DEFAULT_MAX_WALK_MINUTES,
    walk_speed_kmh: float = DEFAULT_WALK_SPEED_KMH,
) -> float:
    """Return the maximum path length compatible with the walk-time threshold."""
    minutes = float(max_walk_minutes)
    speed = float(walk_speed_kmh)
    if not isfinite(minutes) or minutes <= 0:
        raise ValueError("max walk minutes must be finite and positive")
    if not isfinite(speed) or speed <= 0:
        raise ValueError("walk speed must be finite and positive")
    return speed * 1000.0 * minutes / 60.0


def discover_intersecting_municipality_codes(
    service_area_geometry,
    municipality_geometries: Mapping[str, object],
    *,
    buffer_metres: float,
) -> tuple[str, ...]:
    """Discover municipalities intersecting a metric buffer around the service area.

    The caller must supply geometries in the same projected metric CRS. No list of
    neighbouring municipalities is accepted: discovery is purely geometric.
    """
    distance = float(buffer_metres)
    if not isfinite(distance) or distance <= 0:
        raise ValueError("buffer metres must be finite and positive")
    if service_area_geometry is None or getattr(service_area_geometry, "is_empty", True):
        raise ValueError("service area geometry must be non-empty")
    if not municipality_geometries:
        raise ValueError("municipality geometries must not be empty")

    envelope = service_area_geometry.buffer(distance)
    discovered: list[str] = []
    for raw_code, geometry in municipality_geometries.items():
        code = str(raw_code).strip()
        if not code:
            raise ValueError("municipality codes must be non-empty")
        if geometry is None or getattr(geometry, "is_empty", True):
            raise ValueError(f"municipality geometry {code!r} must be non-empty")
        if envelope.intersects(geometry):
            discovered.append(code)
    return tuple(sorted(set(discovered)))


def split_discovered_municipalities(
    discovered_codes: Iterable[str],
    *,
    core_codes: Iterable[str] = DEFAULT_CORE_CODES,
) -> dict[str, tuple[str, ...]]:
    discovered = {str(code).strip() for code in discovered_codes if str(code).strip()}
    core = {str(code).strip() for code in core_codes if str(code).strip()}
    if not core:
        raise ValueError("core municipality set must not be empty")
    missing_core = core - discovered
    if missing_core:
        raise ValueError(f"discovered envelope is missing core municipalities: {sorted(missing_core)}")
    return {
        "core": tuple(sorted(core)),
        "external": tuple(sorted(discovered - core)),
        "all": tuple(sorted(discovered)),
    }


def municipality_calibration_factor(
    *,
    official_population_total: float,
    full_municipality_worldpop_raw_sum: float,
) -> float:
    """Calibrate WorldPop using the full municipality, never an envelope fragment."""
    official = float(official_population_total)
    raw_sum = float(full_municipality_worldpop_raw_sum)
    if not isfinite(official) or official <= 0:
        raise ValueError("official municipality population must be finite and positive")
    if not isfinite(raw_sum) or raw_sum <= 0:
        raise ValueError("full-municipality WorldPop raw sum must be finite and positive")
    return official / raw_sum


def calibrate_envelope_cell_weights(
    raw_cell_weights: Mapping[str, float],
    *,
    official_population_total: float,
    full_municipality_worldpop_raw_sum: float,
) -> dict[str, float]:
    """Apply a full-municipality factor to only the cells inside the catchment envelope."""
    factor = municipality_calibration_factor(
        official_population_total=official_population_total,
        full_municipality_worldpop_raw_sum=full_municipality_worldpop_raw_sum,
    )
    calibrated: dict[str, float] = {}
    for raw_id, raw_weight in raw_cell_weights.items():
        unit_id = str(raw_id).strip()
        weight = float(raw_weight)
        if not unit_id or unit_id in calibrated:
            raise ValueError("population cell IDs must be unique and non-empty")
        if not isfinite(weight) or weight < 0:
            raise ValueError("raw population cell weights must be finite and non-negative")
        calibrated[unit_id] = weight * factor
    return dict(sorted(calibrated.items()))


def _validate_population_units(units: Iterable[PopulationUnit]) -> dict[str, PopulationUnit]:
    by_id: dict[str, PopulationUnit] = {}
    for unit in units:
        if not unit.unit_id or unit.unit_id in by_id:
            raise ValueError("population unit IDs must be unique and non-empty")
        if not unit.municipality_code:
            raise ValueError("population unit municipality codes must be non-empty")
        if not isfinite(float(unit.population_weight)) or float(unit.population_weight) < 0:
            raise ValueError("population unit weights must be finite and non-negative")
        by_id[unit.unit_id] = unit
    if not by_id:
        raise ValueError("population units must not be empty")
    return by_id


def summarize_covered_population(
    covered_unit_ids: Iterable[str],
    *,
    population_units: Iterable[PopulationUnit],
    core_codes: Iterable[str] = DEFAULT_CORE_CODES,
) -> CatchmentPopulationSummary:
    """Summarize a stop-set catchment without letting spillover replace core coverage.

    Repeated coverage of the same unit is counted once. Core and external population
    are returned separately, so a large external benefit can never satisfy a missing
    core municipality obligation in downstream policy checks.
    """
    by_id = _validate_population_units(population_units)
    core = {str(code).strip() for code in core_codes if str(code).strip()}
    if not core:
        raise ValueError("core municipality set must not be empty")

    covered = {str(unit_id).strip() for unit_id in covered_unit_ids if str(unit_id).strip()}
    unknown = covered - set(by_id)
    if unknown:
        raise ValueError(f"unknown covered population units: {sorted(unknown)}")

    core_population = 0.0
    external_population = 0.0
    core_units = 0
    external_units = 0
    external_municipalities: set[str] = set()

    for unit_id in sorted(covered):
        unit = by_id[unit_id]
        if unit.municipality_code in core:
            core_population += float(unit.population_weight)
            core_units += 1
        else:
            external_population += float(unit.population_weight)
            external_units += 1
            external_municipalities.add(unit.municipality_code)

    return CatchmentPopulationSummary(
        core_covered_population=core_population,
        external_spillover_population=external_population,
        total_catchment_population=core_population + external_population,
        core_covered_units=core_units,
        external_covered_units=external_units,
        external_municipalities=tuple(sorted(external_municipalities)),
    )
