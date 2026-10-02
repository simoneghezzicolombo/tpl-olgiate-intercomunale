"""Verify frozen hash ledgers; repair only proven Git LF/CRLF checkout drift.

Expected hashes are never changed. A repair requires an exact certified Git
blob, UTF-8 text, and equality of bytes apart from CRLF-to-LF conversion.
"""
import argparse
import csv
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT/'outputs/phase2/rt031_line8_local_shortcuts_v3/certified_checkout_bytes_20261002.json'
TEXT_SUFFIXES = {'.csv','.json','.geojson','.txt','.md','.sha256','.xml','.osm'}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def records():
    with (ROOT/'data/manifest.csv').open(encoding='utf-8-sig',newline='') as handle:
        rows = [dict(path=r['filepath_locale'],expected_sha256=r['sha256_hash'],ledger='data/manifest.csv')
                for r in csv.DictReader(handle)]
    for folder,name in [('outputs/phase2/analysis_envelope','analysis_envelope_checksums.sha256'),
                        ('outputs/phase2','stop_universe_checksums.sha256')]:
        for line in (ROOT/folder/name).read_text(encoding='utf-8').splitlines():
            if not line.strip():
                continue
            expected,filename=line.split('  ',1)
            rows.append(dict(path=f'{folder}/{filename}',expected_sha256=expected,ledger=f'{folder}/{name}'))
    rows.append(dict(path='data/phase2/frozen_gate_d/source/structural_anchor_evidence.csv',
        expected_sha256='c3ab598a43bfb83f31f086d6a14f29d92941969a349ef9087b5e6d87fe10b3d1',
        ledger='tests/test_phase2_frozen_graph.py::EXPECTED_SOURCE_SHA'))
    return rows


def verify(root,rows,repair=False):
    root=root.resolve(); results=[]
    for row in rows:
        path=(root/row['path']).resolve()
        relative=path.relative_to(root).as_posix()  # fail closed outside checkout
        result={**row,'path':relative,'repaired':False}
        if not path.is_file():
            result['state']='MISSING';results.append(result);continue
        before=path.read_bytes();result['actual_sha256_before']=digest(before)
        if digest(before)==row['expected_sha256']:
            result['state']='EXACT_HASH_MATCH';results.append(result);continue
        git=subprocess.run(['git','show',f'HEAD:{relative}'],cwd=root,capture_output=True,check=False)
        blob=git.stdout
        result['git_blob_sha256']=digest(blob) if git.returncode==0 else None
        text=path.suffix.lower() in TEXT_SUFFIXES and b'\x00' not in before+blob
        if text:
            try:
                before.decode('utf-8');blob.decode('utf-8')
            except UnicodeDecodeError:
                text=False
        safe=(git.returncode==0 and text and digest(blob)==row['expected_sha256']
              and before.replace(b'\r\n',b'\n')==blob.replace(b'\r\n',b'\n'))
        if not safe:
            result['state']='HASH_MISMATCH_UNRESOLVED'
        else:
            result['state']='CERTIFIED_GIT_CHECKOUT_NEWLINE_DRIFT'
            if repair:
                if path.read_bytes()!=before:
                    raise ValueError(f'Concurrent modification: {relative}')
                # Bulk mechanical formatting only; certified source bytes stay
                # unchanged in Git and no semantic edit is permitted.
                path.write_bytes(blob)
                if digest(path.read_bytes())!=row['expected_sha256']:
                    raise ValueError(f'Certified newline repair failed: {relative}')
                result['repaired']=True
        result['actual_sha256_after']=digest(path.read_bytes())
        results.append(result)
    return dict(contract='CERTIFIED_CHECKOUT_BYTE_INTEGRITY_AUDIT_V3',rows=results,
        all_certified_hashes_match=all(r.get('actual_sha256_after',r.get('actual_sha256_before'))==r['expected_sha256'] for r in results),
        repaired_file_count=sum(r['repaired'] for r in results),
        expected_hashes_modified=False,semantic_content_modified=False,
        raw_source_evidence_manufactured=False,proposal_implementation_ready=False,
        primary_selection_authorised=False,runner_up_selection_authorised=False,
        decision_budget_km=None,uncertainty_band_min=None)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--repair-certified-newlines',action='store_true')
    p.add_argument('--output',type=Path,default=OUTPUT)
    args=p.parse_args();result=verify(ROOT,records(),args.repair_certified_newlines)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(dict(rows=len(result['rows']),repaired=result['repaired_file_count'],
        all_certified_hashes_match=result['all_certified_hashes_match'],
        unresolved=[r['path'] for r in result['rows'] if r['state'] in ('MISSING','HASH_MISMATCH_UNRESOLVED')]),ensure_ascii=False))
