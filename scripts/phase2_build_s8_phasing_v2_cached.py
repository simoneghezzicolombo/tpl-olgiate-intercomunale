#!/usr/bin/env python3
"""Exact cached entrypoint for the Phase 2 S8 phase-opportunity builder.

The persisted envelope stores ranges across the complete integer phase domain,
not phase-indexed scores. For a fixed headway and span, adding an integer number
of minutes to a cycle runtime only permutes the complete phase domain. The
range statistics are therefore exactly invariant to the integer part of the
runtime. We cache the expensive metric sweep by fractional runtime part and
still retain the exact route runtime for downstream phase reconstruction.
"""
from __future__ import annotations

import csv
from decimal import Decimal
from pathlib import Path

import scripts.phase2_build_s8_phasing_v2 as base


D = Decimal


def representative_runtime_for_complete_phase_range(runtime: Decimal, headway_min: int) -> Decimal:
    """Return a positive representative with the same fractional-minute part."""
    if runtime <= 0 or headway_min <= 0:
        raise ValueError("Runtime and headway must be positive")
    fractional = runtime % D("1")
    return D(headway_min) + fractional


def build_phase_envelope_cached(
    *,
    runtime_archetypes: dict[str, Decimal],
    rail_events: list[base.RailEvent],
    timing_archetypes: list[tuple[int, base.Span]],
    output_path: Path,
) -> dict:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rows = 0
    logical_phase_evaluations = 0
    unique_metric_phase_evaluations = 0
    cache: dict[tuple[Decimal, int, str, int, int], list[dict[str, object]]] = {}

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
            fractional = runtime % D("1")
            for headway, span in timing_archetypes:
                cache_key = (fractional, headway, span.span_id, span.start_min, span.end_min)
                phase_metrics = cache.get(cache_key)
                if phase_metrics is None:
                    representative = representative_runtime_for_complete_phase_range(runtime, headway)
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
                    cache[cache_key] = phase_metrics
                    unique_metric_phase_evaluations += headway

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
    }


def main() -> int:
    base.build_phase_envelope = build_phase_envelope_cached
    return base.main()


if __name__ == "__main__":
    raise SystemExit(main())
