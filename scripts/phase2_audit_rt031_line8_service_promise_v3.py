"""Audit the frequency/span promise for the inclusive Linea 8 road model.

Counts full west-plus-east traversals only. This is not a passenger timetable.
"""

import argparse
from decimal import Decimal, ROUND_FLOOR
import hashlib
import json
from pathlib import Path


INCLUSIVE = "FIVE_QUATTRO_STRADE_THEN_CARIPLO"


def digest(value):
    encoded = json.dumps(value, sort_keys=True, ensure_ascii=False,
                         separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build(envelope):
    if envelope["contract"] != "RT031_LINE8_CONDITIONAL_COMPLETE_TRAVERSAL_RESOURCE_ENVELOPE_V3":
        raise ValueError("unexpected source contract")
    if envelope["network_selected"] or envelope["primary_selection_authorised"] or envelope["runner_up_selection_authorised"]:
        raise ValueError("source unexpectedly authorises selection")
    rows = [row for row in envelope["variants"] if row["variant_id"] == INCLUSIVE]
    if len(rows) != 1 or rows[0]["current_exact_stop_ids_encountered_both_directions"] != 11:
        raise ValueError("inclusive 11/11 reference missing")
    row = rows[0]
    days = Decimal(str(envelope["assumed_annual_service_days"]))
    cap = Decimal(str(envelope["approved_annual_bus_km_cap"]))
    pair_km = Decimal(str(row["daily_bidirectional_pair_km"]))
    if min(days, cap, pair_km) <= 0:
        raise ValueError("invalid positive input")
    pair_cost = days * pair_km
    max_pairs = int((cap / pair_cost).to_integral_value(rounding=ROUND_FLOOR))
    if max_pairs != row["maximum_integer_daily_bidirectional_pairs_within_cap_before_extras"]:
        raise ValueError("source pair maximum inconsistent")
    scenarios = []
    for name, hours, departures_per_direction in (
        ("H60_8H", 8, 8),
        ("H60_10H", 10, 10),
        ("H60_16H", 16, 16),
        ("H30_4H_PLUS_H60_12H", 16, 20),
    ):
        annual = pair_cost * departures_per_direction
        scenarios.append({
            "scenario_id": name,
            "service_span_hours": hours,
            "full_traversals_per_direction_per_day": departures_per_direction,
            "annual_full_traversal_km_before_extras": float(annual),
            "additional_km_over_cap_before_extras": float(max(Decimal(0), annual - cap)),
            "within_cap_before_extras": annual <= cap,
        })
    return {
        "contract": "RT031_LINE8_SERVICE_PROMISE_AUDIT_V3",
        "status": "NON_DECISIONAL_FULL_TRAVERSAL_ARITHMETIC",
        "source_envelope_canonical_sha256": digest(envelope),
        "variant_id": INCLUSIVE,
        "current_stop_identities_encountered_not_boarding_guaranteed": 11,
        "assumed_annual_service_days": int(days),
        "approved_annual_bus_km_cap_not_decision_budget_km": float(cap),
        "full_forward_and_reverse_pair_km": float(pair_km),
        "maximum_daily_full_traversals_each_direction_before_extras": max_pairs,
        "maximum_daily_full_traversal_pair_km_before_extras": float(pair_cost * max_pairs),
        "uniform_departure_interval_hours_if_max_pairs_spread_across_16h": 16 / max_pairs,
        "four_peak_hours_at_h30_consume_pairs_each_direction": 8,
        "pairs_remaining_for_other_12h_under_cap_before_extras": max(0, max_pairs - 8),
        "scenarios": scenarios,
        "scope": "Only identical complete west-plus-east traversals in both directions; no claim about short turns, split wings, actual passenger departures or achievable train connections.",
        "missing_for_operational_decision": [
            "ordered directional boarding events and safe stops",
            "full-history legal paths and vehicle suitability",
            "dwell, traffic and recovery times",
            "vehicle blocks and depot/repositioning kilometres",
            "rail-event matching and timetable phase",
            "Saturday and annual service calendar",
        ],
        "decision_budget_km": None,
        "uncertainty_band_min": None,
        "network_selected": False,
        "primary_selection_authorised": False,
        "runner_up_selection_authorised": False,
    }


def main(source, output):
    envelope = json.loads(source.read_text(encoding="utf-8"))
    payload = build(envelope)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, sort_keys=True, ensure_ascii=False,
                                 separators=(",", ":")) + "\n", encoding="utf-8")
    return payload


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    main(args.source, args.output)
