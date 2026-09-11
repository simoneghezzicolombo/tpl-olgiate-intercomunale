"""Bind historical visits to frozen stop places only on explicit provenance."""
import argparse
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
from scripts.phase2_audit_rt031_historical_service_calibration_v3 import EXPECTED, inventory
from src.phase2_rt031_historical_stop_binding_v3 import bind_historical_stops
from src.phase2_rt031_typed_composition_v3 import payload_hash

ROOT=Path('outputs/phase2/network_design_method_audit_v3/master_stop_inventory_gpt_v3')
SOURCES={
 'existing_stop_places_operational_gpt_v5.csv':'53af82ccfc398719781faf526d482431d2258bd637a74349222e0c4967642076',
 'arriva_stop_place_service_crosswalk_validated_gpt_v4.csv':'d5ea86615d1198124edb86070ab2d6630f8dc25cfce66af5343cb30e88e46a32'}


def read(path,digest):
    if hashlib.sha256(path.read_bytes()).hexdigest()!=digest: raise ValueError('source hash mismatch: '+str(path))
    with path.open(encoding='utf-8-sig',newline='') as f: return list(csv.DictReader(f))


def main(out):
    tables={name:read(Path('data/raw/gtfs/agency_arriva')/name,digest) for name,digest in EXPECTED.items()}
    trips,_,_=inventory(tables)
    frozen=read(ROOT/'existing_stop_places_operational_gpt_v5.csv',SOURCES['existing_stop_places_operational_gpt_v5.csv'])
    if len(frozen)!=36 or sum(r['service_class']=='CONVENTIONAL_TPL' for r in frozen)!=35:
        raise ValueError('frozen stop universe changed')
    crosswalk=read(ROOT/'arriva_stop_place_service_crosswalk_validated_gpt_v4.csv',SOURCES['arriva_stop_place_service_crosswalk_validated_gpt_v4.csv'])
    stops={v['source_stop']['stop_id']:v['source_stop'] for t in trips for v in t['visits']}
    bindings=bind_historical_stops([stops[s] for s in sorted(stops)],frozen,crosswalk)
    occurrences=[]
    for trip in trips:
        for visit in trip['visits']:
            sid=visit['source_stop']['stop_id']
            occurrences.append(dict(source_trip=trip['source_trip'],source_stop=visit['source_stop'],
                source_stop_time=visit['source_stop_time'],binding=bindings[sid]))
    counts=Counter(r['binding']['status'] for r in occurrences)
    audit=dict(contract='RT031_HISTORICAL_STOP_PLACE_PROVENANCE_BINDING_V3',
        source_sha256={**EXPECTED,**SOURCES},historical_trip_count=len(trips),
        historical_stop_identity_count=len(stops),historical_occurrence_count=len(occurrences),
        occurrence_binding_status_counts=dict(sorted(counts.items())),
        unique_identity_status_counts=dict(sorted(Counter(r['status'] for r in bindings.values()).items())),
        occurrence_payload_sha256=payload_hash(occurrences),
        frozen_stop_count=36,conventional_stop_count=35,
        directional_boarding_bindings=0,rt017_attachments=0,
        feed_is_historical_not_current=True,current_service_inferred=False,
        physical_calibration_pass=False,production_rt031_pass=False)
    out.mkdir(parents=True,exist_ok=True)
    for name,payload in [('historical_stop_binding_audit.json',audit),('historical_bound_occurrences.json',occurrences),('historical_stop_bindings.json',bindings)]:
        (out/name).write_text(json.dumps(payload,sort_keys=True,indent=2)+'\n')
    print(json.dumps(audit,sort_keys=True))
    return audit


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);main(p.parse_args().out)
