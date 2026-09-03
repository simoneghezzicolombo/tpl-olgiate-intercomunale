#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from src.gate_d_pass_analysis import (add_composite,budget_envelope,build_directional_pairs,fleet_headway_envelope,load_pass_artifact_zip)
from src.service_math import ServiceMathError, load_pdb_budget

def _numbers(s): return [float(x.strip()) for x in s.split(',') if x.strip()]
def _ints(s): return [int(x.strip()) for x in s.split(',') if x.strip()]
def write(path,rows):
    path.parent.mkdir(parents=True,exist_ok=True)
    if not rows: raise ServiceMathError(f'refusing empty output {path}')
    with path.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0].keys()));w.writeheader();w.writerows(rows)

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--artifact-zip',type=Path,required=True)
    p.add_argument('--artifact-sha256',required=True)
    p.add_argument('--artifact-id',required=True)
    p.add_argument('--gate-d-commit',required=True)
    p.add_argument('--budget',type=Path,default=ROOT/'data'/'risorse_tpl_pdb.csv')
    p.add_argument('--composite-id')
    p.add_argument('--composite-families')
    p.add_argument('--headways',type=_numbers,default=[30.0,45.0,60.0,90.0])
    p.add_argument('--vehicles-each-direction',type=_ints,default=[1,2,3])
    p.add_argument('--budget-output',type=Path,required=True)
    p.add_argument('--fleet-output',type=Path,required=True)
    p.add_argument('--unpaired-output',type=Path,required=True)
    a=p.parse_args()
    try:
        metrics,wps,digest=load_pass_artifact_zip(a.artifact_zip,a.artifact_sha256)
        pairs,unpaired=build_directional_pairs(metrics,wps)
        routes=list(pairs)
        if bool(a.composite_id) != bool(a.composite_families):
            raise ServiceMathError('--composite-id and --composite-families must be supplied together')
        if a.composite_id:
            routes.append(add_composite(pairs,a.composite_id,a.composite_families.split(',')))
        lineage={'gate_d_status':'PASS','gate_d_commit':a.gate_d_commit,'gate_d_artifact_id':a.artifact_id,'gate_d_artifact_sha256':digest}
        budget=float(load_pdb_budget(a.budget)['D184+D185'])
        write(a.budget_output,budget_envelope(routes,budget,lineage))
        write(a.fleet_output,fleet_headway_envelope(routes,a.headways,a.vehicles_each_direction,lineage))
        write(a.unpaired_output,[{**lineage,**r} for r in unpaired])
        print(f'Gate D PASS directional pairs: {len(pairs)}; composite hypotheses: {len(routes)-len(pairs)}; unpaired rows: {len(unpaired)}')
        print(f'PdB benchmark: {budget:.0f} bus-km/year')
        print('Gate E scenario status: SENSITIVITY_ONLY until a future service policy is explicitly chosen')
        return 0
    except (OSError,ValueError,ServiceMathError) as e:
        print(f'GATE_E_GATE_D_PASS_ANALYSIS_FAIL: {e}',file=sys.stderr); return 1
if __name__=='__main__': raise SystemExit(main())
