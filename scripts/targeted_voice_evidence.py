"""Authenticate retained real speech artifacts and recheck final spoken text."""
from pathlib import Path
import hashlib,json,wave
from scripts.retained_target_checks import compatible_runtime_change,validate_response
NAMES={'01_en.wav':'en','02_hi.wav':'hi','03_hinglish.wav':'hi-en'}
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def spoken_contract(pred):
 flags=pred['generation']['model_flags']
 if set(flags)!={'covered','needs_clarification'}:raise ValueError('missing_actual_model_flags')
 return {'answer':pred['answer'],**flags}
def case_ok(root,case,runtime,dataset):
 from scripts.targeted_release import artifact,read
 try:
  if case['language']!=NAMES[case['input']]:return False
  if not all(artifact(root,case[k]['artifact'],case[k]['sha256']) for k in ('prediction','audio','origin')):return False
  origin=read(root/case['origin']['artifact']);pred=read(root/case['prediction']['artifact']);old=case['inference_runtime_source_sha256']
  if (origin.get('speech_provider')!='Gnani only' or origin.get('live_llm_composition_enabled') is not True
      or origin.get('source_runtime_unchanged') is not True or origin.get('runtime_source_sha256')!=old
      or origin.get('runtime_source_sha256_finished')!=old or pred.get('language')!=case['language']
      or pred.get('composition')!='grounded_llm'):return False
  entries=[e for e in origin['batch']['entries'] if e['input']==case['input']]
  checks=[c for c in origin['semantic_validation']['checks'] if c['case']==case['input']]
  if len(entries)!=1 or entries[0]['status']!='ok' or len(checks)!=1 or checks[0]['passed'] is not True:return False
  if not case['prediction']['artifact'].endswith('/'+entries[0]['output_prefix']+'.json') or not case['audio']['artifact'].endswith('/'+entries[0]['audio']):return False
  for key in ('prediction','audio'):
   if origin['artifacts'].get(case[key]['artifact'])!=case[key]['sha256']:return False
  with wave.open(str(root/case['audio']['artifact']),'rb') as f:
   seconds=f.getnframes()/f.getframerate();nonempty=seconds>0 and any(f.readframes(f.getnframes()))
  if not nonempty or abs(seconds-checks[0]['reply_seconds'])>.03:return False
  if old==runtime:return origin.get('status')=='tested'
  if not compatible_runtime_change(root,old,runtime):return False
  ref=case['saved_spoken_output_revalidation']
  if not artifact(root,ref['artifact'],ref['sha256']):return False
  proof=read(root/ref['artifact'])
  if (proof.get('status')!='passed' or proof.get('fresh_inference_or_speech') is not False
      or proof.get('prediction_sha256')!=case['prediction']['sha256'] or proof.get('input')!=case['input']
      or proof.get('runtime_source_sha256')!=runtime or proof.get('runtime_source_sha256_finished')!=runtime
      or proof.get('original_runtime_source_sha256')!=old or proof.get('contract')!=spoken_contract(pred)):return False
  from src.kb import KnowledgeBase
  kb=KnowledgeBase(dataset)
  for source in pred['sources']:
   if source['id'] not in kb.chunks:return False
   actual=kb.chunks[source['id']].public()
   if any(source.get(k)!=v for k,v in actual.items()):return False
  result=validate_response(pred,proof['contract'],dataset=dataset)
  return sha_text(result['answer'])==proof['validated_answer_sha256']
 except (KeyError,TypeError,ValueError,OSError,IndexError,EOFError,wave.Error,ZeroDivisionError):return False

def sha_text(text):return hashlib.sha256(text.encode()).hexdigest()
def composite_ok(root,voice,runtime,dataset):
 cases=voice.get('cases',[])
 return (isinstance(cases,list) and len(cases)==3 and all(isinstance(c,dict) for c in cases)
         and {c.get('input') for c in cases}==set(NAMES)
         and all(case_ok(root,c,runtime,dataset) for c in cases))
