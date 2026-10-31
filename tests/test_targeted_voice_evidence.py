"""Synthetic offline gate fixtures only; no actual speech/service scores."""
import copy,json,wave
from pathlib import Path
from types import SimpleNamespace
import pytest
from scripts.targeted_voice_evidence import case_ok,spoken_contract,sha,sha_text
from scripts.retained_target_checks import validate_response
from test_refund_payment_timeline import context

def write(path,value):
 path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value),encoding='utf-8');return path

def reference(root,path):return {'artifact':path.relative_to(root).as_posix(),'sha256':sha(path)}

@pytest.fixture
def speech_case(tmp_path,monkeypatch):
 root=tmp_path;folder=root/'sample_outputs/test';folder.mkdir(parents=True)
 facts,sources=context();facts.pop('verified_order');facts['public_context']={'payment_method':'upi'}
 pred={'transcript':'When will my refund arrive?','answer':'UPI refunds take 23 to 37 business days after initiation.','language':'en','composition':'grounded_llm','verified':False,'sources':sources,'facts':facts,'generation':{'model_flags':{'covered':True,'needs_clarification':False}}}
 runtime={'src/document_answers.py':'new','src/agent.py':'same','src/voice.py':'same'};old={**runtime,'src/document_answers.py':'old'}
 prediction=write(folder/'en.json',pred);audio=folder/'en_reply.wav'
 with wave.open(str(audio),'wb') as f:f.setnchannels(1);f.setsampwidth(2);f.setframerate(8000);f.writeframes(b'\x01\x00'*8000)
 origin={'status':'tested','speech_provider':'Gnani only','live_llm_composition_enabled':True,'source_runtime_unchanged':True,'runtime_source_sha256':old,'runtime_source_sha256_finished':old,'batch':{'entries':[{'input':'01_en.wav','output_prefix':'en','audio':audio.name,'status':'ok'}]},'semantic_validation':{'checks':[{'case':'01_en.wav','passed':True,'reply_seconds':1.0}]},'artifacts':{prediction.relative_to(root).as_posix():sha(prediction),audio.relative_to(root).as_posix():sha(audio)}}
 op=write(folder/'origin.json',origin);contract=spoken_contract(pred);result=validate_response(pred,contract)
 proof={'status':'passed','input':'01_en.wav','fresh_inference_or_speech':False,'prediction_sha256':sha(prediction),'original_runtime_source_sha256':old,'runtime_source_sha256':runtime,'runtime_source_sha256_finished':runtime,'contract':contract,'validated_answer_sha256':sha_text(result['answer'])};pp=write(folder/'proof.json',proof)
 case={'input':'01_en.wav','language':'en','prediction':reference(root,prediction),'audio':reference(root,audio),'origin':reference(root,op),'inference_runtime_source_sha256':old,'saved_spoken_output_revalidation':reference(root,pp)}
 import src.kb
 monkeypatch.setattr(src.kb,'KnowledgeBase',lambda dataset=None:SimpleNamespace(chunks={s['id']:SimpleNamespace(public=lambda s=s:s) for s in sources}))
 return root,case,runtime,folder

def test_retained_real_artifact_checks_accept_current_guard_validation(speech_case):
 root,case,runtime,_=speech_case
 assert case_ok(root,case,runtime,root/'dataset')

@pytest.mark.parametrize('mutation',['corrupt_audio','incompatible_runtime','wrong_answer','changed_policy','missing_proof','failed_original_semantics','relabel_fresh'])
def test_retained_speech_cannot_hide_changed_or_failing_evidence(speech_case,mutation,monkeypatch):
 root,case,runtime,folder=speech_case;op=root/case['origin']['artifact'];origin=json.loads(op.read_text());pp=root/case['saved_spoken_output_revalidation']['artifact'];proof=json.loads(pp.read_text());prediction=root/case['prediction']['artifact']
 if mutation=='corrupt_audio':
  audio=root/case['audio']['artifact'];audio.write_bytes(b'not WAV');case['audio']['sha256']=sha(audio);origin['artifacts'][case['audio']['artifact']]=sha(audio)
 elif mutation=='incompatible_runtime':
  case['inference_runtime_source_sha256']['src/agent.py']='unrelated-change';origin['runtime_source_sha256']=origin['runtime_source_sha256_finished']=case['inference_runtime_source_sha256'];proof['original_runtime_source_sha256']=case['inference_runtime_source_sha256']
 elif mutation=='wrong_answer':
  p=json.loads(prediction.read_text());p['answer']='UPI refunds take 99 business days after initiation.';write(prediction,p);case['prediction']['sha256']=sha(prediction);origin['artifacts'][case['prediction']['artifact']]=sha(prediction);proof.update(prediction_sha256=sha(prediction),contract=spoken_contract(p),validated_answer_sha256=sha_text(p['answer']))
 elif mutation=='changed_policy':
  import src.kb
  monkeypatch.setattr(src.kb,'KnowledgeBase',lambda dataset=None:SimpleNamespace(chunks={}))
 elif mutation=='missing_proof':pp.unlink()
 elif mutation=='failed_original_semantics':origin['semantic_validation']['checks'][0]['passed']=False
 else:proof['fresh_inference_or_speech']=True
 write(op,origin);case['origin']['sha256']=sha(op)
 if pp.exists():write(pp,proof);case['saved_spoken_output_revalidation']['sha256']=sha(pp)
 assert not case_ok(root,case,runtime,root/'dataset')
