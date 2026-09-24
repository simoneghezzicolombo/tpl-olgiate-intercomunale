#!/usr/bin/env python3
"""Exact compact entrypoint for the Phase 2 S8 phase-opportunity builder.

The current factual S8 timetable has integer-minute station events. Combined
with evaluation of the complete integer bus-phase domain, this creates an exact
lossless representation with at most two cycle-runtime classes per headway and
span:

* INTEGER: fractional runtime = 0;
* POSITIVE_FRACTION: any 0 < fractional runtime < 1, represented at 0.5.

For POSITIVE_FRACTION, changing the actual fractional runtime does not change
which rail event is matched. Every matched VEHICLE_CYCLE_TO_RAIL gap is simply
translated by 0.5 - actual_fraction minutes. RAIL_TO_BUS is independent of
cycle runtime. The integer part of runtime only permutes the full bus phase
domain.

Exact cycle runtimes remain in ``unique_route_cycles_v2.csv``. Consequently the
small kernel written here plus that route table reconstructs the full runtime
opportunity envelope without persisting hundreds of thousands of redundant
rows.
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


def runtime_class(runtime: Decimal) -> str:
    return "INTEGER" if _fractional_part(runtime) == 0 else "POSITIVE_FRACTION"


def representative_runtime_for_class(runtime_class_name: str, headway_min: int) -> Decimal:
    if headway_min <= 0:
        raise ValueError("headway must be positive")
    if runtime_class_name == "INTEGER":
        fraction = D("0")
    elif runtime_class_name == "POSITIVE_FRACTION":
        fraction = _POSITIVE_FRACTION_REPRESENTATIVE
    else:
        raise ValueError(f"Unsupported runtime class {runtime_class_name!r}")
    return D(headway_min) + fraction


def representative_runtime_for_complete_phase_range(runtime: Decimal, headway_min: int) -> Decimal:
    """Backward-compatible helper used by tests and audit reasoning."""
    return representative_runtime_for_class(runtime_class(runtime), headway_min)


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
    """Translate positive-fraction representative metrics to one actual runtime."""
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
    """Persist the exact parametric phase kernel, not redundant runtime rows."""
    _require_integer_minute_rail_events(rail_events)
    if not runtime_archetypes:
        raise ValueError("S8 phase kernel requires runtime archetypes")
    classes = sorted({runtime_class(runtime) for runtime in runtime_archetypes.values()})
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rows = 0
    unique_metric_phase_evaluations = 0

    fields = [
        "runtime_class",
        "representative_fractional_runtime_min",
        "actual_runtime_transform",
        "uniform_headway_min",
        "span_id",
        "span_start_min",
        "span_end_min",
        "evaluated_phase_count",
        "phase_domain",
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

    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for runtime_class_name in classes:
            rep_fraction = D("0") if runtime_class_name == "INTEGER" else _POSITIVE_FRACTION_REPRESENTATIVE
            transform = (
                "REPRESENTATIVE_GAP_UNCHANGED"
                if runtime_class_name == "INTEGER"
                else "ACTUAL_VEHICLE_CYCLE_TO_RAIL_GAP=REPRESENTATIVE_GAP+(0.5-ACTUAL_FRACTIONAL_RUNTIME_MIN)"
            )
            for headway, span in timing_archetypes:
                representative = representative_runtime_for_class(runtime_class_name, headway)
                phase_metrics = [
                    base.phase_raw_gap_metrics(
                        rail_events=rail_events,
                        cycle_runtime_min=representative,
                        headway_min=headway,
                        span=span,
                        phase_min=phase,
                    )
                    for phase in range(headway)
                ]
                unique_metric_phase_evaluations += headway
                out = {
                    "runtime_class": runtime_class_name,
                    "representative_fractional_runtime_min": format(rep_fraction, "f"),
                    "actual_runtime_transform": transform,
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

    logical_phase_evaluations = len(runtime_archetypes) * sum(headway for headway, _ in timing_archetypes)
    return {
        "phase_envelope_rows": rows,
        "phase_envelope_representation": "LOSSLESS_PARAMETRIC_RUNTIME_CLASS_KERNEL",
        "runtime_class_count": len(classes),
        "runtime_classes": classes,
        "logical_runtime_timing_archetype_rows": len(runtime_archetypes) * len(timing_archetypes),
        "integer_phase_evaluations": logical_phase_evaluations,
        "unique_metric_phase_evaluations": unique_metric_phase_evaluations,
        "phase_metric_cache_key_count": rows,
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
