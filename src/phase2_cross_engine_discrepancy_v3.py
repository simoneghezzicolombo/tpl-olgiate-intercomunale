from __future__ import annotations

from dataclasses import dataclass
from math import ceil, isfinite
from typing import Iterable, Sequence


@dataclass(frozen=True)
class ODTravelTime:
    from_id: str
    to_id: str
    travel_time_min: float


@dataclass(frozen=True)
class ODDiscrepancy:
    from_id: str
    to_id: str
    engine_a_time_min: float
    engine_b_time_min: float
    signed_difference_min: float
    absolute_difference_min: float
    relative_difference_vs_a: float | None


def _normalize(rows: Iterable[ODTravelTime], engine_label: str) -> dict[tuple[str, str], float]:
    if not engine_label:
        raise ValueError("engine label must be non-empty")
    out: dict[tuple[str, str], float] = {}
    for row in rows:
        if not row.from_id or not row.to_id:
            raise ValueError("OD identifiers must be non-empty")
        key = (row.from_id, row.to_id)
        if key in out:
            raise ValueError(f"duplicate OD key for {engine_label}: {key}")
        value = float(row.travel_time_min)
        if not isfinite(value) or value < 0:
            raise ValueError(f"invalid travel time for {engine_label}: {key}")
        out[key] = value
    if not out:
        raise ValueError(f"{engine_label} matrix must not be empty")
    return out


def compare_engines(
    engine_a_rows: Iterable[ODTravelTime],
    engine_b_rows: Iterable[ODTravelTime],
    *,
    engine_a_label: str,
    engine_b_label: str,
) -> tuple[ODDiscrepancy, ...]:
    if engine_a_label == engine_b_label:
        raise ValueError("engine labels must be distinct")
    a = _normalize(engine_a_rows, engine_a_label)
    b = _normalize(engine_b_rows, engine_b_label)
    a_keys = set(a)
    b_keys = set(b)
    if a_keys != b_keys:
        missing_in_b = sorted(a_keys - b_keys)
        extra_in_b = sorted(b_keys - a_keys)
        raise ValueError(
            f"OD_ALIGNMENT_ERROR missing_in_b={missing_in_b} extra_in_b={extra_in_b}"
        )

    rows: list[ODDiscrepancy] = []
    for from_id, to_id in sorted(a_keys):
        av = a[(from_id, to_id)]
        bv = b[(from_id, to_id)]
        signed = bv - av
        relative = signed / av if av > 0 else None
        rows.append(
            ODDiscrepancy(
                from_id=from_id,
                to_id=to_id,
                engine_a_time_min=av,
                engine_b_time_min=bv,
                signed_difference_min=signed,
                absolute_difference_min=abs(signed),
                relative_difference_vs_a=relative,
            )
        )
    return tuple(rows)


def _nearest_rank(values: Sequence[float], quantile: float) -> float:
    if not values:
        raise ValueError("values must not be empty")
    if not 0 <= quantile <= 1:
        raise ValueError("quantile must be between 0 and 1")
    ordered = sorted(float(v) for v in values)
    rank = max(1, ceil(quantile * len(ordered)))
    return ordered[rank - 1]


def summarize_discrepancies(
    discrepancies: Iterable[ODDiscrepancy],
    *,
    reporting_bands_min: Sequence[float] = (1.0, 3.0, 5.0),
) -> dict[str, object]:
    rows = tuple(discrepancies)
    if not rows:
        raise ValueError("discrepancies must not be empty")
    bands = tuple(sorted(float(v) for v in reporting_bands_min))
    if len(set(bands)) != len(bands) or any((not isfinite(v) or v < 0) for v in bands):
        raise ValueError("reporting bands must be unique finite non-negative values")

    abs_values = [r.absolute_difference_min for r in rows]
    signed_values = [r.signed_difference_min for r in rows]
    relative_defined = [r.relative_difference_vs_a for r in rows if r.relative_difference_vs_a is not None]

    result: dict[str, object] = {
        "od_count": len(rows),
        "mean_signed_difference_min": sum(signed_values) / len(signed_values),
        "mean_absolute_difference_min": sum(abs_values) / len(abs_values),
        "median_absolute_difference_min": _nearest_rank(abs_values, 0.50),
        "p90_absolute_difference_min": _nearest_rank(abs_values, 0.90),
        "p95_absolute_difference_min": _nearest_rank(abs_values, 0.95),
        "max_absolute_difference_min": max(abs_values),
        "relative_difference_defined_count": len(relative_defined),
        "relative_difference_undefined_count": len(rows) - len(relative_defined),
        "reporting_bands_are_diagnostic_only": True,
        "automatic_equivalence_claim": False,
        "engine_average_constructed": False,
    }
    for band in bands:
        result[f"share_abs_diff_le_{band:g}_min"] = sum(v <= band for v in abs_values) / len(abs_values)
    return result
