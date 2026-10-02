import hashlib
import subprocess

import pytest

from scripts.phase2_audit_certified_checkout_bytes_v3 import verify
from scripts.phase2_build_final_decision_sufficiency_gate_v3 import certified_external_bytes,read_json,ROOT
from scripts.phase2_redteam_tournament_readiness_rt001_v3 import scan_frontier_consumers,REVIEWED_VALIDATION_ONLY_CONSUMER_SHA256


def repo(tmp_path):
    subprocess.run(['git','init',str(tmp_path)],check=True,capture_output=True)
    path=tmp_path/'evidence.csv'
    path.write_bytes(b'a,b\n1,2\n')
    for command in (['config','core.autocrlf','false'],['config','user.name','Test'],
                    ['config','user.email','test@example.invalid'],['add','evidence.csv'],['commit','-m','frozen']):
        subprocess.run(['git',*command],cwd=tmp_path,check=True,capture_output=True)
    return path,[dict(path='evidence.csv',expected_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),ledger='test')]


def test_only_certified_newline_drift_may_be_repaired(tmp_path):
    path,rows=repo(tmp_path);path.write_bytes(b'a,b\r\n1,2\r\n')
    assert not verify(tmp_path,rows)['all_certified_hashes_match']
    result=verify(tmp_path,rows,repair=True)
    assert result['repaired_file_count']==1 and result['all_certified_hashes_match']
    assert path.read_bytes()==b'a,b\n1,2\n'
    assert not result['expected_hashes_modified'] and not result['semantic_content_modified']


def test_semantic_change_and_forged_expected_hash_are_not_repaired(tmp_path):
    path,rows=repo(tmp_path);path.write_bytes(b'a,b\r\n1,99\r\n')
    assert not verify(tmp_path,rows,repair=True)['all_certified_hashes_match']
    assert path.read_bytes()==b'a,b\r\n1,99\r\n'
    rows[0]['expected_sha256']='0'*64
    assert verify(tmp_path,rows,repair=True)['repaired_file_count']==0


def test_outside_checkout_target_is_rejected(tmp_path):
    with pytest.raises(ValueError):
        verify(tmp_path,[dict(path='../evidence.csv',expected_sha256='0'*64)],repair=True)


def test_missing_private_source_uses_exact_existing_git_object_not_fake_fields():
    cfg=read_json(ROOT/'config/phase2_final_decision_sufficiency_gate_v3.json')
    certificate=read_json(ROOT/'outputs/phase2/final_decision_sufficiency_gate_v3/final_decision_sufficiency_gate_v3_validation.json')
    for key,field in [('stage_f','stage_f_validation_sha256'),
                      ('current_service_baseline_v3','current_service_baseline_validation_sha256'),
                      ('stage_e_old_vs_new_audit','stage_e_old_vs_new_validation_sha256')]:
        source=cfg['external_sources'][key]
        value=certified_external_bytes(ROOT/source['materialized_path'],cfg,key)
        assert hashlib.sha256(value).hexdigest()==certificate['lineage'][field]
        if key=='stage_f':
            assert b'PASS_PHASE2_STAGE_F_ENGINEERING_SENSITIVITY_RT001_V3' in value


def test_explicit_missing_or_modified_source_is_not_silently_replaced(tmp_path):
    cfg=read_json(ROOT/'config/phase2_final_decision_sufficiency_gate_v3.json')
    path=tmp_path/'caller_source.json'
    with pytest.raises(FileNotFoundError):certified_external_bytes(path,cfg,'stage_f')
    path.write_bytes(b'{"status":"PASS"}')
    with pytest.raises(ValueError,match='differs from pinned'):certified_external_bytes(path,cfg,'stage_f')


def test_reviewed_validator_exemption_is_revoked_by_any_code_change(tmp_path):
    folder=tmp_path/'scripts';folder.mkdir()
    relative=next(iter(REVIEWED_VALIDATION_ONLY_CONSUMER_SHA256))
    target=tmp_path/relative
    target.write_bytes((ROOT/relative).read_bytes())
    redteam=folder/'audit.py';redteam.write_text('# audit\n',encoding='utf-8')
    assert scan_frontier_consumers(tmp_path,redteam)==[]
    target.write_bytes(target.read_bytes()+b'\nINPUT = "pareto_frontier_member"\n')
    assert scan_frontier_consumers(tmp_path,redteam)==[relative]
