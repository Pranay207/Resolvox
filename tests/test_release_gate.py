"""Release refusal and freshness tests; no models, speech or ZIP creation."""
import copy, json
from pathlib import Path
import pytest
import package_submission as package
from scripts import release_evidence as evidence
from test_release_verification import verified_tree, read_json, write_json

def refresh_artifact(root,name):
    receipt=read_json(root,'live_sequence_receipt.json')
    next(stage for stage in receipt['stages'] if stage['stage']==name)['artifact']['sha256']=evidence.sha(root/'sample_outputs'/evidence.STAGES[name])
    write_json(root,'live_sequence_receipt.json',receipt)

@pytest.mark.parametrize('ready,blockers',[(False,['unfinished']),(True,['unfinished']),(None,[])])
def test_default_packaging_refuses_without_any_output(tmp_path,monkeypatch,ready,blockers):
    monkeypatch.setattr(package,'ROOT',tmp_path)
    monkeypatch.setattr(package,'status',lambda:{'ready_to_submit':ready,'blockers':blockers})
    monkeypatch.setattr(package.zipfile,'ZipFile',lambda *a,**k:pytest.fail('Archive creation attempted'))
    assert package.main()==2
    assert list(tmp_path.iterdir())==[]

def test_refusal_cannot_resolve_or_overwrite_existing_archive(monkeypatch):
    class UntouchableRoot:
        def __truediv__(self,name):pytest.fail('Refusal touched an existing output path: '+name)
    monkeypatch.setattr(package,'ROOT',UntouchableRoot())
    monkeypatch.setattr(package,'status',lambda:{'ready_to_submit':False,'blockers':['pending']})
    assert package.main()==2

@pytest.mark.parametrize('pages',[1,2,3,4])
def test_report_accepts_brief_maximum_with_complete_visual_qa(verified_tree,pages):
    pdf=b'%PDF synthetic test fixture\n'+b'/Type /Page\n'*pages
    (verified_tree/'report.pdf').write_bytes(pdf)
    qa=read_json(verified_tree,'pdf_qa.json');qa.update(pages=pages,visually_reviewed_pages=list(range(1,pages+1)),pdf_sha256=__import__('hashlib').sha256(pdf).hexdigest())
    write_json(verified_tree,'pdf_qa.json',qa)
    assert package.status()['ready_to_submit'] is True

@pytest.mark.parametrize('pages',[0,5])
def test_report_rejects_outside_brief_limit(verified_tree,pages):
    (verified_tree/'report.pdf').write_bytes(b'/Type /Page\n'*pages)
    assert any('1 to 4' in reason for reason in package.status()['blockers'])

@pytest.mark.parametrize('name',['src/agent.py','src/rule_bindings.json','run.py','scripts/resume_live_practice.py','Capstone_Project_Dataset_FTTT_2026/kb/current.md','Capstone_Project_Dataset_FTTT_2026/practice/questions.csv','tests/holdout_cases.json'])
def test_actual_input_mutation_rejects_saved_sequence(verified_tree,name):
    path=verified_tree/name;path.write_bytes(path.read_bytes()+b' changed')
    assert package.status()['ready_to_submit'] is False

@pytest.mark.parametrize('key,value',[('LLM_MODEL','other-model'),('LLM_PROVIDER','other-provider'),('LLM_BASE_URL','http://new-endpoint'),('LLM_TIMEOUT','999'),('DENSE_ENABLED','false'),('REFERENCE_DATE','2026-11-01'),('GNANI_TTS_MODEL','different')])
def test_selected_configuration_mutation_rejects_saved_sequence(verified_tree,monkeypatch,key,value):
    monkeypatch.setenv(key,value)
    assert any('snapshot' in reason for reason in package.status()['blockers'])

@pytest.mark.parametrize('change',['missing','partial','error','mode','model','dataset','ids','fingerprint','with_sources'])
def test_baseline_requires_complete_current_same_model_comparison(verified_tree,change):
    file=evidence.STAGES['baseline'];data=read_json(verified_tree,file)
    if change=='missing':(verified_tree/'sample_outputs'/file).unlink()
    else:
        if change=='partial':data['results'].pop();data['summary'].update(total=51,complete=False)
        elif change=='error':data['summary']['errors']=1
        elif change=='mode':data['configuration']['evaluation_mode']='offline'
        elif change in ('model','dataset'):
            section='inference' if change=='model' else 'dataset_sha256';data['configuration']['provenance'][section]['changed']='stale'
        elif change=='ids':data['results'][0]['id']='different'
        elif change=='fingerprint':data['configuration']['inference_fingerprint']='stale'
        else:data['results'][0]['prediction']['sources']=[{'text':'Synthetic source'}]
        write_json(verified_tree,file,data);refresh_artifact(verified_tree,'baseline')
    assert any('Step 1' in reason for reason in package.status()['blockers'])

def test_completed_zero_score_baseline_is_valid_comparison(verified_tree):
    baseline=read_json(verified_tree,evidence.STAGES['baseline'])
    assert baseline['summary']['passed']==0
    assert package.status()['ready_to_submit'] is True

@pytest.mark.parametrize('name',['questions','conversations','adversarial','holdout','baseline','voice','silence'])
def test_changed_record_bytes_cannot_reuse_previous_receipt(verified_tree,name):
    path=verified_tree/'sample_outputs'/evidence.STAGES[name];path.write_bytes(path.read_bytes()+b' ')
    assert any('artifact bytes' in reason for reason in package.status()['blockers'])

@pytest.mark.parametrize('change',['missing','duplicate','partial','failed','changed_inputs'])
def test_sequence_requires_each_complete_unchanged_stage(verified_tree,change):
    data=read_json(verified_tree,'live_sequence_receipt.json')
    if change=='missing':data['stages'].pop()
    elif change=='duplicate':data['stages'].append(copy.deepcopy(data['stages'][0]))
    elif change=='partial':data['complete']=False
    elif change=='failed':data['stages'][0]['exit_code']=1
    else:data['stages'][0]['snapshot_finished']['inference']['LLM_MODEL']='stale'
    write_json(verified_tree,'live_sequence_receipt.json',data)
    assert package.status()['ready_to_submit'] is False

def test_generated_ticket_sidecar_and_secret_rotation_do_not_change_public_inputs(verified_tree,monkeypatch):
    before=evidence.snapshot(verified_tree)
    (verified_tree/'Capstone_Project_Dataset_FTTT_2026/tools/tickets_created.csv').write_text('generated output',encoding='utf-8')
    monkeypatch.setenv('GNANI_API_KEY','private-rotated-key')
    monkeypatch.setenv('LLM_API_KEY','private-rotated-llm-key')
    after=evidence.snapshot(verified_tree)
    assert before==after and 'private-rotated' not in json.dumps(after)
    assert package.status()['ready_to_submit'] is True

@pytest.mark.parametrize('step,complete,errors,expected',[(1,True,0,0),(1,True,1,1),(1,False,0,2),(2,True,0,1)])
def test_baseline_cli_separates_low_score_from_execution_failure(monkeypatch,step,complete,errors,expected):
    import sys
    from scripts import resume_live_practice as driver
    monkeypatch.setattr(sys,'argv',['resume_live_practice.py','--step',str(step)])
    monkeypatch.setattr(driver,'run_evaluation',lambda *a,**kw:{'complete':complete,'passed':0,'total':52,'errors':errors})
    assert driver.main()==expected


def test_recorded_temporary_runner_is_optional_extra_provenance(verified_tree):
    receipt=read_json(verified_tree,'live_sequence_receipt.json')
    for record in [receipt,*receipt['stages']]:
        for key in ('snapshot_started','snapshot_finished'):
            record[key]['driver_source_sha256']['tmp/recorded_launcher.py']='historical-launcher-hash'
    write_json(verified_tree,'live_sequence_receipt.json',receipt)
    assert package.status()['ready_to_submit'] is True


def test_every_shipped_driver_remains_required(verified_tree):
    (verified_tree/'run.py').unlink()
    assert package.status()['ready_to_submit'] is False


def test_malformed_baseline_prediction_returns_blockers_without_raising(verified_tree):
    file=evidence.STAGES['baseline'];data=read_json(verified_tree,file)
    data['results'][0]['prediction']=None
    write_json(verified_tree,file,data);refresh_artifact(verified_tree,'baseline')
    assert package.status()['ready_to_submit'] is False
