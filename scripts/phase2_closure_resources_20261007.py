"""Read-only, non-normative resource accounting for the fixed weekday design.

No result adopts local exclusions, Saturday service, driver duties or funding.
Run with ``python -m scripts.phase2_closure_resources_20261007``.
"""
import json
import math
from pathlib import Path
from scripts.phase2_package_rt031_confirmed_design_handoff_v3 import canonical_sha256
from scripts.phase2_materialise_rt031_weekday_calendar_2027_v3 import build as calendar_build
from scripts.phase2_prepare_rt031_operating_closure_v3 import build as pack_build

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'outputs/phase2/rt031_line8_local_shortcuts_v3'


def exclusion_effect(calendar, dates):
    """Count each valid date once; already absent dates remove no weekday work."""
    ledger = {row['date']: row for row in calendar['date_ledger']}
    requested = sorted(set(dates))
    unknown = set(requested) - ledger.keys()
    if unknown:
        raise ValueError(f'Dates outside source ledger: {sorted(unknown)}')
    removed = [d for d in requested if ledger[d]['weekday_component_complete_trips'] > 0]
    trips = sum(ledger[d]['weekday_component_complete_trips'] for d in removed)
    return dict(hypothetical_only=True, removed_weekday_dates=removed,
                already_outside_weekday_base=[d for d in requested if d not in removed],
                removed_full_trips=trips,
                commercial_km_reduction=trips * calendar['complete_trip_commercial_km'],
                local_exception_policy_certified=False)


def comparison(calendar, annual_noncommercial_km=None):
    """Reference arithmetic only: never substitute reference km for a budget."""
    if annual_noncommercial_km is not None and (
            not isinstance(annual_noncommercial_km, (int, float))
            or isinstance(annual_noncommercial_km, bool)
            or not math.isfinite(annual_noncommercial_km) or annual_noncommercial_km < 0):
        raise ValueError('Noncommercial km must be finite and nonnegative, or unknown')
    commercial = calendar['weekday_base_commercial_km']
    reference = calendar['reference_published_pdb_annual_km']
    total = None if annual_noncommercial_km is None else commercial + annual_noncommercial_km
    return dict(commercial_weekday_km=commercial, published_reference_km=reference,
                commercial_reference_difference_km=reference-commercial,
                difference_per_base_weekday_km=(reference-commercial)/calendar['weekday_base_day_count_before_local_exceptions'],
                annual_noncommercial_km=annual_noncommercial_km,
                weekday_operating_km=total,
                operating_minus_reference_km=None if total is None else total-reference,
                reference_is_secured_funding=False, decision_budget_km=None,
                full_line_annual_km=None, saturday_selected=False)


def verify_sources(calendar, pack):
    """Authenticate the complete saved sources against their existing producers."""
    for name, saved, producer in (('calendar', calendar, calendar_build),
                                  ('operating pack', pack, pack_build)):
        if canonical_sha256(saved) != canonical_sha256(producer()):
            raise ValueError(f'Resource closure source drift: {name}')


def audit():
    calendar = json.loads((BASE / 'caller_confirmed_weekday_calendar_2027.json').read_text(encoding='utf-8'))
    pack = json.loads((BASE / 'operating_closure_working_pack_20261002.json').read_text(encoding='utf-8'))
    verify_sources(calendar, pack)
    bill = pack['weekday_bill_of_quantities']
    for key in ('decision_budget_km', 'uncertainty_band_min'):
        if pack[key] is not None or calendar[key] is not None:
            raise ValueError(f'Unselected authority changed: {key}')
    for key in ('funding_secured', 'primary_selection_authorised', 'runner_up_selection_authorised'):
        if pack[key] is not False or calendar[key] is not False:
            raise ValueError(f'Pending authority changed: {key}')
    if not math.isclose(bill['commercial_km'], calendar['weekday_base_commercial_km'], abs_tol=1e-8):
        raise ValueError('Commercial source mismatch')
    cases = {}
    for name in ('nominal', 'slower_dwell_recovery'):
        case = bill[name]
        gaps = [gap['duration_min'] for block in case['blocks'] for gap in block['uncommitted_gaps_after_recovery']]
        for block in case['blocks']:
            if block['actual_vehicle_id'] is not None or block['driver_duties'] is not None:
                raise ValueError('Model-only source has acquired actual duties; reassessment needed')
            accounted = block['occupation_hours_including_terminal_recovery'] + sum(g['duration_min'] for g in block['uncommitted_gaps_after_recovery'])/60
            if not math.isclose(accounted, block['first_to_last_block_span_hours'], abs_tol=1e-8):
                raise ValueError('Block span double counting or missing gap')
        cases[name] = dict(maximum_simultaneous_model_vehicles=case['maximum_simultaneously_occupied_model_vehicles'],
                           minimum_gap_after_recovery_min=min(gaps),
                           annual_model_occupation_hours=case['weekday_annual_vehicle_occupation_hours'],
                           actual_fleet=None, payable_driver_hours=None,
                           gap_is_certified_other_work=False)
    return dict(status='NON_NORMATIVE_ACCOUNTING_ONLY', reference_comparison=comparison(calendar),
                vehicle_model=cases,
                local_exception_impact_per_removed_base_weekday_km=16*calendar['complete_trip_commercial_km'],
                saturday_one_trip_each_nonholiday_date_commercial_km=calendar['saturday_nonholiday_date_count']*calendar['complete_trip_commercial_km'],
                open_items=[i['id'] for i in pack['closure_items'] if i['id'] in
                            ('FLEET_DUTIES', 'NONCOMMERCIAL', 'LOCAL_CALENDAR', 'FULL_COST_FUNDING', 'SATURDAY')],
                quotation_rule='Require priced scope and included cost categories; add only explicitly excluded costs. Model occupation hours are not driver hours; reference production is not transferable funding.')


if __name__ == '__main__':
    print(json.dumps(audit(), ensure_ascii=False, indent=2))
