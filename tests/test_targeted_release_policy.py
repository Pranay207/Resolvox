"""Synthetic gate fixtures only, never live scores, real audio or user artifacts."""
import copy,csv,json,hashlib
from pathlib import Path
import pytest
from scripts import release_evidence as evidence
from scripts import targeted_release as targeted
from test_release_verification import verified_tree,write_json,read_json

def put(root,name,value):
 p=root/'sample_outputs'/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(value),encoding='utf-8');return p

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

@pytest.fixture
def targeted_tree(verified_tree):
 root=verified_tree;dataset=root/'Capstone_Project_Dataset_FTTT_2026'
 with (dataset/'practice/conversations.csv').open('w',newline='',encoding='utf-8') as f:
  writer=csv.DictWriter(f,fieldnames=['conversation_id','turn','customer_message']);writer.writeheader()
  writer.writerows({'conversation_id':case,'turn':'1','customer_message':'Synthetic input'} for case in ('PC009','PC010','PC003','PC004'))
 frozen=evidence.snapshot(root);runtime=frozen['runtime_source_sha256'];prefix=dataset.relative_to(root).as_posix()+'/'
 prov={'step':3,'evaluation_mode':'live_compose_true','runtime_source_sha256':dict(runtime,**{'scripts/resume_live_practice.py':frozen['driver_source_sha256']['scripts/resume_live_practice.py']}),'dataset_sha256':{k[len(prefix):]:v for k,v in frozen['dataset_source_sha256'].items()},'inference':{k:v for k,v in frozen['inference'].items() if k!='GNANI_TTS_MODEL'}}
 ids=['PC009','PC010','PC003','PC004','refund_coupon_context','refund_completed_date'];cases=[]
 for case in ids:
  if case.startswith('PC'):
   value={'configuration':{'evaluation_mode':'live_compose_true','provenance':prov,'inference_fingerprint':hashlib.sha256(json.dumps(prov,sort_keys=True,separators=(',',':')).encode()).hexdigest()},'summary':{'total':1,'passed':1,'complete':True},'results':[{'id':case+'.1','checks':{'passed':True}}]}
  else:value={'passed':True,'checks':{'synthetic_test_check':True}}
  p=put(root,'targeted/'+case+'.json',value);cases.append({'id':case,'passed':True,'artifact':p.relative_to(root).as_posix(),'sha256':sha(p)})
 live={'complete':True,'status':'tested','source_runtime_unchanged':True,'runtime_source_sha256':runtime,'runtime_source_sha256_finished':runtime,'cases':cases,'manual_semantic_review':{'status':'passed','cases':[{'id':c['id'],'artifact_sha256':c['sha256'],'passed':True} for c in cases]}}
 put(root,'targeted_live_validation.json',live)
 artifact=put(root,'targeted/automated-log.json',{'scope':'Synthetic unit fixture, not pytest execution evidence'})
 auto={'complete':True,'exit_code':0,'all_tested_bytes_unchanged':True,'source_and_test_sha256_started':runtime,'source_and_test_sha256_finished':runtime,'pytest':{'tests':3,'passed':3,'failures':0,'errors':0,'skipped':0},'artifacts':{artifact.relative_to(root).as_posix():sha(artifact)}}
 put(root,'refund_scope_verification_20261031.json',auto)
 voice={'status':'tested','source_runtime_unchanged':True,'speech_provider':'Gnani only','live_llm_composition_enabled':True,'runtime_source_sha256':runtime,'runtime_source_sha256_finished':runtime,'batch':{'total':3,'succeeded':3,'failed':0},'semantic_validation':{'passed':3,'failed':0,'checks':[{'language':lang,'passed':True} for lang in ('en','hi','hi-en')]},'artifacts':auto['artifacts']}
 put(root,'targeted_voice_validation.json',voice)
 # Old full-fixture files deliberately no longer match the changed fixture.
 return root

def test_current_targeted_evidence_satisfies_gate_without_a_full52_or96_run(targeted_tree):
 assert targeted.blockers(targeted_tree)==[]
 assert evidence.blockers(targeted_tree)==[]

@pytest.mark.parametrize('mutation',['missing_case','failed_case','missing_review','stale_runtime','changed_artifact','wrong_case_rows','stale_automated','failed_voice','missing_voice_artifact','malformed_record'])
def test_targeted_mode_never_clears_missing_changed_or_failed_evidence(targeted_tree,mutation):
 root=targeted_tree;live=read_json(root,'targeted_live_validation.json')
 if mutation=='missing_case':live['cases'].pop()
 elif mutation=='failed_case':live['cases'][0]['passed']=False
 elif mutation=='missing_review':live['manual_semantic_review']={}
 elif mutation=='stale_runtime':(root/'src/agent.py').write_text('# changed source')
 elif mutation=='changed_artifact':(root/live['cases'][0]['artifact']).write_text('{}')
 elif mutation=='wrong_case_rows':
  case=live['cases'][0];p=root/case['artifact'];value=json.loads(p.read_text());value['results'][0]['id']='PC010.1';p.write_text(json.dumps(value));case['sha256']=sha(p)
 elif mutation=='stale_automated':
  auto=read_json(root,'refund_scope_verification_20261031.json');auto['source_and_test_sha256_finished']={};put(root,'refund_scope_verification_20261031.json',auto)
 elif mutation=='failed_voice':
  voice=read_json(root,'targeted_voice_validation.json');voice['batch']['failed']=1;put(root,'targeted_voice_validation.json',voice)
 elif mutation=='missing_voice_artifact':
  voice=read_json(root,'targeted_voice_validation.json');voice['artifacts']={};put(root,'targeted_voice_validation.json',voice)
 elif mutation=='malformed_record':live=[]
 put(root,'targeted_live_validation.json',live)
 assert evidence.blockers(root)

def test_targeted_package_keeps_real_demo_and_pdf_checks(targeted_tree,monkeypatch):
 import package_submission
 monkeypatch.setattr(package_submission,'ROOT',targeted_tree)
 monkeypatch.setattr(package_submission,'mp4_duration',lambda path:None)
 status=package_submission.status()
 assert status['ready_to_submit'] is False
 assert 'User-recorded demo.mp4 missing or duration unverified' in status['blockers']
 assert status['verification_policy']=='targeted_live_with_disclosed_limits'
 assert any('no fresh full52' in warning for warning in status['evaluation_warnings'])


@pytest.mark.parametrize('prefix',['gsk_','vach_','ghp_','sk-proj-'])
def test_packager_rejects_credential_shapes(prefix):
 import package_submission
 assert package_submission.contains_credential((prefix+'a'*45).encode())


def test_archive_only_includes_root_evidence_and_its_referenced_files(tmp_path,monkeypatch):
 import package_submission
 monkeypatch.setattr(package_submission,'ROOT',tmp_path)
 needed=put(tmp_path,'targeted/needed.json',{'actual':'synthetic fixture'})
 junk=put(tmp_path,'history/unreferenced.json',{'unrelated':'synthetic fixture'})
 put(tmp_path,'targeted_live_validation.json',{'artifact':needed.relative_to(tmp_path).as_posix()})
 files=package_submission.referenced_evidence_files()
 assert needed in files and junk not in files

@pytest.fixture
def retained_tree(targeted_tree):
 from test_refund_payment_timeline import context
 from scripts.retained_target_checks import validate_response
 root=targeted_tree;expected=evidence.snapshot(root);live=read_json(root,'targeted_live_validation.json');case=next(c for c in live['cases'] if c['id']=='PC010');p=root/case['artifact'];value=json.loads(p.read_text())
 old=copy.deepcopy(expected['runtime_source_sha256']);old['src/document_answers.py']='earlier-runtime'
 prov=value['configuration']['provenance'];prov['runtime_source_sha256']={**old,'scripts/resume_live_practice.py':expected['driver_source_sha256']['scripts/resume_live_practice.py']}
 value['configuration']['inference_fingerprint']=hashlib.sha256(json.dumps(prov,sort_keys=True,separators=(',',':')).encode()).hexdigest()
 facts,sources=context();contract={'answer':'UPI refunds take 23 to 37 business days after initiation.','covered':True,'needs_clarification':False}
 pred={'answer':contract['answer'],'transcript':'When will my refund arrive?','language':'en','sources':sources,'facts':facts,'verified':True,'generation':{'generation_attempts':1,'model_flags':{'covered':True,'needs_clarification':False}}}
 value['results'][0]['prediction']=pred;p.write_text(json.dumps(value));case['sha256']=sha(p)
 next(c for c in live['manual_semantic_review']['cases'] if c['id']=='PC010')['artifact_sha256']=case['sha256']
 result=validate_response(pred,contract);current=expected['runtime_source_sha256'];proof={'case_id':case['id'],'case_artifact_sha256':case['sha256'],'status':'passed','inference_repeated':False,'runtime_source_sha256':current,'runtime_source_sha256_finished':current,'original_runtime_source_sha256':old,'validations':[{'id':'PC010.1','passed':True,'contract':contract,'validated_answer_sha256':hashlib.sha256(result['answer'].encode()).hexdigest()}]}
 proofpath=put(root,'targeted/retained-check.json',proof);case['saved_output_revalidation']={'artifact':proofpath.relative_to(root).as_posix(),'sha256':sha(proofpath)};put(root,'targeted_live_validation.json',live)
 return root

def test_retained_output_is_validated_without_claiming_new_model_inference(retained_tree):
 assert evidence.blockers(retained_tree)==[]

@pytest.mark.parametrize('mutation',['changed_authentication','failed_guard','changed_contract','missing_proof','relabelled_fresh_inference'])
def test_retained_checks_cannot_hide_incompatible_code_or_failed_saved_answer(retained_tree,mutation):
 root=retained_tree;live=read_json(root,'targeted_live_validation.json');case=next(c for c in live['cases'] if c['id']=='PC010');ref=case['saved_output_revalidation'];p=root/ref['artifact'];proof=json.loads(p.read_text())
 if mutation=='changed_authentication':proof['original_runtime_source_sha256']['src/agent.py']='changed-auth-code'
 elif mutation=='failed_guard':proof['validations'][0]['passed']=False
 elif mutation=='changed_contract':proof['validations'][0]['contract']['answer']='UPI refunds take 29 to 43 business days after initiation.'
 elif mutation=='missing_proof':p.unlink()
 else:proof['inference_repeated']=True
 if p.exists():p.write_text(json.dumps(proof));ref['sha256']=sha(p)
 put(root,'targeted_live_validation.json',live)
 assert evidence.blockers(root)

@pytest.mark.parametrize('name,field',[('targeted_live_validation.json','cases'),('targeted_live_validation.json','manual_semantic_review'),('targeted_voice_validation.json','artifacts'),('refund_scope_verification_20261031.json','pytest')])
def test_malformed_nested_evidence_blocks_without_a_crash(targeted_tree,name,field):
 value=read_json(targeted_tree,name);value[field]=[None]*6;put(targeted_tree,name,value)
 assert evidence.blockers(targeted_tree)

def test_saved_host_validation_view_recovers_only_recorded_kb_ids(monkeypatch):
 from types import SimpleNamespace
 import src.kb
 from scripts.retained_target_checks import validation_sources
 source={'id':'bound-policy','text':'Synthetic recorded host section','doc_type':'policy','status':'current'}
 monkeypatch.setattr(src.kb,'KnowledgeBase',lambda:SimpleNamespace(chunks={'bound-policy':SimpleNamespace(public=lambda:source),'unseen-policy':SimpleNamespace(public=lambda:dict(source,id='unseen-policy'))}))
 pred={'sources':[],'generation':{'validation_source_ids':['bound-policy']}}
 assert validation_sources(pred)==[source]
 pred['generation']['validation_source_ids']=['missing-policy']
 with pytest.raises(ValueError,match='recorded_validation_source_missing'):validation_sources(pred)
