from pathlib import Path
import hashlib
import json
import pandas as pd

OUT=Path('outputs/phase2')


def test_validation_contract_and_frozen_lineage():
    v=json.loads((OUT/'stop_universe_validation.json').read_text(encoding='utf-8'))
    assert v['status']=='PASS_STOP_UNIVERSE_BUILD'
    assert v['scope']=='CANDIDATE_STOP_UNIVERSE_NOT_FINAL_NETWORK'
    assert v['gate_b_commit']=='55d726564e13acca55ce563cc911263ac513acb0'
    assert v['gate_d_computational_commit']=='7c220f7586d0f6e5cccd14a2d518be52eb1c4a55'
    assert abs(v['gate_b_population_denominator_2025']-22914.0)<1e-6
    assert abs(v['baseline_coverage_pct']['10']-80.00327161825983)<1e-9
    assert v['existing_official_stop_records']==66
    assert v['existing_snapped_stop_records']==62
    assert v['legacy_processed_population_used'] is False
    assert v['legacy_hardcoded_poi_dataset_used'] is False
    assert v['live_overpass_used'] is False


def test_proposed_candidates_are_field_check_pending_and_not_near_duplicates_of_existing_stops():
    df=pd.read_csv(OUT/'proposed_stop_candidates.csv')
    assert len(df)>0
    assert df['candidate_id'].is_unique
    assert df['epistemic_status'].eq('PROPOSED_STOP/FIELD_CHECK_PENDING').all()
    assert df['physical_status'].eq('FIELD_CHECK_PENDING').all()
    assert df['candidate_status'].eq('HYPOTHESIS_NOT_RECOMMENDATION').all()
    assert df['road_eligibility_status'].eq('DERIVED_GATE_D_BUS_ELIGIBLE').all()
    assert (df['nearest_official_stop_walk_network_m']>=150.0-1e-6).all()
    assert df['lat'].between(-90,90).all() and df['lon'].between(-180,180).all()
    gain=(df['population_additional_8min']>0)|(df['population_additional_10min']>0)|(df['settlement_additional_10min_count']>0)|(df['destination_additional_10min_count']>0)
    assert gain.all()


def test_existing_stops_are_gate_b_official_universe_and_arlate_is_neutral_interchange_evidence():
    stops=pd.read_csv(OUT/'existing_official_stops.csv',dtype={'stop_id':str})
    assert len(stops)==66
    assert stops['stop_type'].eq('EXISTING_OFFICIAL_STOP').all()
    assert stops['epistemic_status'].eq('FACT_OFFICIAL_GTFS_REFERENCE_PERIOD_NOT_CURRENT_SERVICE').all()
    arlate=stops[stops['stop_name'].str.contains('arlate',case=False,na=False)]
    assert not arlate.empty
    routes=set('|'.join(arlate['official_routes_reference_gtfs'].fillna('')).split('|'))
    assert {'D150','D170'} <= routes
    inter=pd.read_csv(OUT/'interchange_opportunities.csv')
    notes=' '.join(inter['arlate_hypothesis_note'].fillna('').astype(str))
    assert 'D201/D202 Circolare Meratese absent from validated 2025-2026 GTFS' in notes
    assert 'no shared-stop claim is made' in notes


def test_accessibility_gap_and_optimizer_catchment_outputs_preserve_gate_b_population():
    gap=pd.read_csv(OUT/'accessibility_gap_cells.csv')
    assert abs(gap['pop_calibrated_2025'].sum()-22914.0)<1e-6
    for t in (5,8,10,12):
        assert f'gap_{t}min' in gap
    cc=pd.read_csv(OUT/'proposed_stop_candidate_catchment_cells_10min.csv')
    candidates=set(pd.read_csv(OUT/'proposed_stop_candidates.csv')['candidate_id'])
    assert set(cc['candidate_id']) <= candidates
    assert (cc['walk_min_to_candidate']<=10.0+1e-9).all()


def test_checksums_cover_every_materialized_output():
    lines=(OUT/'stop_universe_checksums.sha256').read_text(encoding='utf-8').splitlines()
    got={line.split('  ',1)[1]:line.split('  ',1)[0] for line in lines if '  ' in line}
    expected={p.name for p in OUT.iterdir() if p.is_file() and p.name!='stop_universe_checksums.sha256' and p.name.startswith(('existing_','accessibility_','settlement_','proposed_','interchange_','candidate_','stop_universe_'))}
    assert expected <= set(got)
    for name in expected:
        h=hashlib.sha256((OUT/name).read_bytes()).hexdigest()
        assert got[name]==h


def test_generated_stop_universe_text_has_no_known_mojibake_markers():
    targets=[p for p in OUT.iterdir() if p.suffix.lower() in {'.csv','.geojson','.json'} and p.name.startswith(('existing_','accessibility_','settlement_','proposed_','interchange_','candidate_','stop_universe_'))]
    assert targets
    for path in targets:
        text=path.read_text(encoding='utf-8')
        assert 'Ã' not in text and 'Â' not in text, path


def test_no_final_service_design_fields_are_generated():
    df=pd.read_csv(OUT/'proposed_stop_candidates.csv')
    forbidden={'headway_min','timetable','annual_bus_km','budget_eur','recommended','rank','score','final_topology'}
    assert forbidden.isdisjoint(df.columns)
