#!/usr/bin/env python3
"""Exact compressed entrypoint for the Phase 2 S8 phase-opportunity builder.

The persisted envelope stores ranges across the complete integer phase domain,
not phase-indexed scores. Two exact symmetries are exploited:

1. adding an integer number of minutes to a cycle runtime only permutes the
   complete phase domain;
2. with the frozen S8 event times on integer minutes, every positive
   fractional-minute runtime has the same next-train matching pattern. Changing
   the fraction only translates every VEHICLE_CYCLE_TO_RAIL matched gap by a
   constant while leaving counts and RAIL_TO_BUS metrics unchanged.

The current factual S8 input is therefore evaluated with at most two runtime
classes per headway/span: integer and positive-fractional. Exact original
runtimes remain in the persisted route universe and envelope rows.
"""
from __future__ import annotations

import csv
from decimal import Decimal
from pathlib import Path

import scripts.phase2_build_s8_phasing_v2 as base


D = Decimal
_POSITIVE_FRACTION_REPRESENTATIVE = D("0.5")


def _fractional_part(runtime: Decimal) -> Decimal:
    if runtime <= 0:
        raise ValueError("Runtime must be positive")
    return runtime % D("1")


def representative_runtime_for_complete_phase_range(runtime: Decimal, headway_min: int) -> Decimal:
    """Return a positive representative preserving the exact phase-range class."""
    if runtime <= 0 or headway_min <= 0:
        raise ValueError("Runtime and headway must be positive")
    fractional = _fractional_part(runtime)
    representative_fraction = D("0") if fractional == 0 else _POSITIVE_FRACTION_REPRESENTATIVE
    return D(headway_min) + representative_fraction


def _require_integer_minute_rail_events(rail_events: list[base.RailEvent]) -> None:
    if not rail_events:
        raise ValueError("S8 phase compression requires rail events")
    for event in rail_events:
        if event.arrival_min != event.arrival_min.to_integral_value():
            raise ValueError("Exact positive-fraction runtime compression requires integer-minute S8 arrivals")
        if event.departure_min != event.departure_min.to_integral_value():
            raise ValueError("Exact positive-fraction runtime compression requires integer-minute S8 departures")


def _translated_phase_metrics(
    representative_rows: list[dict[str, object]],
    *,
    actual_fraction: Decimal,
) -> list[dict[str, object]]:
    """Translate positive-fraction vehicle-to-rail gaps to the actual fraction.

    For 0 < f < 1 and integer-minute rail targets, the next target identity is
    unchanged for every source event. Relative to the 0.5-minute representative,
    each matched vehicle-cycle-to-rail gap changes by 0.5 - f minutes. Source,
    matched and unmatched counts are invariant. RAIL_TO_BUS does not depend on
    cycle runtime at all.
    """
    if actual_fraction == 0:
        return representative_rows
    if not D("0") < actual_fraction < D("1"):
        raise ValueError("actual_fraction must be in (0,1) for translated metrics")
    shift = float(_POSITIVE_FRACTION_REPRESENTATIVE - actual_fraction)
    translated: list[dict[str, object]] = []
    for row in representative_rows:
        out = dict(row)
        for key, value in row.items():
            if (
                key.startswith("vehicle_cycle_to_rail_")
                and key.endswith("_gap_min")
                and value is not None
            ):
                out[key] = float(value) + shift
        translated.append(out)
    return translated


def build_phase_envelope_cached(
    *,
    runtime_archetypes: dict[str, Decimal],
    rail_events: list[base.RailEvent],
    timing_archetypes: list[tuple[int, base.Span]],
    output_path: Path,
) -> dict:
    _require_integer_minute_rail_events(rail_events)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rows = 0
    logical_phase_evaluations = 0
    unique_metric_phase_evaluations = 0
    cache: dict[tuple[str, int, str, int, int], list[dict[str, object]]] = {}

    with output_path.open("w", encoding="utf-8", newline="") as handle:
        fields = [
            "runtime_archetype_id", "cycle_runtime_min", "uniform_headway_min", "span_id",
            "span_start_min", "span_end_min", "evaluated_phase_count", "phase_domain",
            "all_phases_retained_downstream",
        ]
        for connection in ("vehicle_cycle_to_rail", "rail_to_bus"):
            for direction in ("milano", "lecco"):
                for metric in ("mean_gap_min", "median_gap_min", "p90_gap_min"):
                    fields.extend([
                        f"{connection}_{direction}_{metric}_min_across_phases",
                        f"{connection}_{direction}_{metric}_max_across_phases",
                    ])
                fields.extend([
                    f"{connection}_{direction}_unmatched_count_min_across_phases",
                    f"{connection}_{direction}_unmatched_count_max_across_phases",
                ])
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()

        for runtime_id in sorted(runtime_archetypes):
            runtime = runtime_archetypes[runtime_id]
            fractional = _fractional_part(runtime)
            runtime_class = "INTEGER" if fractional == 0 else "POSITIVE_FRACTION"
            for headway, span in timing_archetypes:
                cache_key = (runtime_class, headway, span.span_id, span.start_min, span.end_min)
                representative_rows = cache.get(cache_key)
                if representative_rows is None:
                    representative = representative_runtime_for_complete_phase_range(runtime, headway)
                    representative_rows = [
                        base.phase_raw_gap_metrics(
                            rail_events=rail_events,
                            cycle_runtime_min=representative,
                            headway_min=headway,
                            span=span,
                            phase_min=phase,
                        )
                        for phase in range(headway)
                    ]
                    cache[cache_key] = representative_rows
                    unique_metric_phase_evaluations += headway

                phase_metrics = _translated_phase_metrics(
                    representative_rows,
                    actual_fraction=fractional,
                )
                out = {
                    "runtime_archetype_id": runtime_id,
                    "cycle_runtime_min": format(runtime, "f"),
                    "uniform_headway_min": headway,
                    "span_id": span.span_id,
                    "span_start_min": span.start_min,
                    "span_end_min": span.end_min,
                    "evaluated_phase_count": headway,
                    "phase_domain": f"0..{headway-1}",
                    "all_phases_retained_downstream": "true",
                }
                for connection in ("vehicle_cycle_to_rail", "rail_to_bus"):
                    for direction in ("milano", "lecco"):
                        prefix = f"{connection}_{direction}"
                        for metric in ("mean_gap_min", "median_gap_min", "p90_gap_min"):
                            lo, hi = base._range([m[f"{prefix}_{metric}"] for m in phase_metrics])
                            out[f"{prefix}_{metric}_min_across_phases"] = "" if lo is None else f"{lo:.9f}"
                            out[f"{prefix}_{metric}_max_across_phases"] = "" if hi is None else f"{hi:.9f}"
                        unmatched = [int(m[f"{prefix}_unmatched_count"]) for m in phase_metrics]
                        out[f"{prefix}_unmatched_count_min_across_phases"] = min(unmatched)
                        out[f"{prefix}_unmatched_count_max_across_phases"] = max(unmatched)
                writer.writerow(out)
                rows += 1
                logical_phase_evaluations += headway

    return {
        "phase_envelope_rows": rows,
        "integer_phase_evaluations": logical_phase_evaluations,
        "unique_metric_phase_evaluations": unique_metric_phase_evaluations,
        "phase_metric_cache_key_count": len(cache),
        "phase_metric_cache_equivalence": "EXACT_FULL_INTEGER_PHASE_DOMAIN_PERMUTATION_BY_RUNTIME_INTEGER_PART",
        "positive_fraction_runtime_transform": "EXACT_FOR_INTEGER_MINUTE_RAIL_EVENTS_CONSTANT_GAP_TRANSLATION",
        "rail_event_times_integer_minutes": True,
        "metric_serialization_precision_decimal_places": 9,
    }


def main() -> int:
    base.build_phase_envelope = build_phase_envelope_cached
    return base.main()


if __name__ == "__main__":
    raise SystemExit(main())
