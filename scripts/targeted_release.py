"""Accept explicitly scoped current targeted evidence without inventing full scores."""
from pathlib import Path
import hashlib,json,csv

def read(path):
 try:
  value=json.loads(Path(path).read_text(encoding='utf-8'));return value if isinstance(value,dict) else {}
 except (OSError,ValueError):return {}

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def artifact(root,name,digest):
 try:
  path=(root/name).resolve()
  return path.is_relative_to(root/'sample_outputs') and path.is_file() and not path.is_symlink() and sha(path)==digest
 except (OSError,TypeError,ValueError):return False

def automated_ok(root,value,expected):
 counts=value.get('pytest',{});counts=counts if isinstance(counts,dict) else {};before=value.get('source_and_test_sha256_started',{});after=value.get('source_and_test_sha256_finished',{})
 return (value.get('complete') is True and value.get('exit_code')==0 and value.get('all_tested_bytes_unchanged') is True
  and before==after and all(after.get(k)==v for k,v in expected.items())
  and all((root/k).is_file() and sha(root/k)==v for k,v in after.items())
  and type(counts.get('tests')) is int and counts['tests']>0 and counts.get('passed')==counts['tests']
  and all(counts.get(k)==0 for k in ('failures','errors','skipped'))
  and isinstance(value.get('artifacts'),dict) and bool(value['artifacts']) and all(artifact(root,k,v) for k,v in value['artifacts'].items()))

def blockers(root):
 from scripts import release_evidence as evidence
 from scripts.retained_target_checks import retained_ok
 root=Path(root).resolve();out=root/'sample_outputs';problems=[]
 try:expected=evidence.snapshot(root)
 except (OSError,ValueError,KeyError):return ['Targeted release inputs cannot be bound']
 runtime=expected['runtime_source_sha256'];live=read(out/'targeted_live_validation.json')
 ids={'PC009','PC010','PC003','PC004','refund_coupon_context','refund_completed_date'}
 cases=live.get('cases',[])
 bound=(live.get('complete') is True and live.get('status')=='tested'
  and live.get('source_runtime_unchanged') is True
  and live.get('runtime_source_sha256')==runtime and live.get('runtime_source_sha256_finished')==runtime
  and isinstance(cases,list) and all(isinstance(c,dict) for c in cases) and len(cases)==len(ids) and {c.get('id') for c in cases}==ids)
 if not bound:problems.append('Current targeted live verification is missing, incomplete, stale or failed')
 else:
  dataset=next((root/k).parent.parent for k in expected['dataset_source_sha256'] if k.endswith('/practice/questions.csv'))
  for case in cases:
   if case.get('passed') is not True or not artifact(root,case.get('artifact',''),case.get('sha256')):
    problems.append('Targeted case evidence changed or failed: '+case['id']);continue
   value=read(root/case['artifact'])
   if case['id'].startswith('PC'):
    summary=value.get('summary',{});rows=value.get('results',[])
    with (dataset/'practice/conversations.csv').open(encoding='utf-8-sig') as f:
     expected_ids=[r['conversation_id']+'.'+r['turn'] for r in csv.DictReader(f) if r['conversation_id']==case['id']]
    if (not (evidence.current_practice(value,3,expected,dataset,root) or retained_ok(root,case,value,expected,dataset))
        or summary.get('complete') is not True or not rows or summary.get('passed')!=len(rows)
        or summary.get('total')!=len(rows) or [r.get('id') for r in rows]!=expected_ids
        or any(r.get('checks',{}).get('passed') is not True for r in rows)):
     problems.append('Targeted conversation is incomplete, stale or failed: '+case['id'])
   elif (('saved_output_revalidation' in case and not retained_ok(root,case,value,expected,dataset)) or value.get('passed') is not True or not value.get('checks') or any(v is not True for v in value['checks'].values())):
    problems.append('Targeted refund edge did not pass: '+case['id'])
 review=live.get('manual_semantic_review',{});review=review if isinstance(review,dict) else {}
 review_cases=review.get('cases',[]);review_cases=review_cases if isinstance(review_cases,list) else []
 case_hashes={c.get('id'):c.get('sha256') for c in (cases if isinstance(cases,list) else []) if isinstance(c,dict)}
 if (review.get('status')!='passed' or not all(isinstance(c,dict) for c in review_cases) or {c.get('id') for c in review_cases}!=ids
     or any(c.get('passed') is not True or c.get('artifact_sha256')!=case_hashes.get(c.get('id')) for c in review_cases)):
  problems.append('Targeted source-by-source semantic review remains incomplete')
 unit=read(out/'refund_scope_verification_20261031.json')
 if not automated_ok(root,unit,runtime):problems.append('Current targeted refund automated evidence is missing, changed or failing')
 voice=read(out/'targeted_voice_validation.json');batch=voice.get('batch',{});semantic=voice.get('semantic_validation',{})
 batch=batch if isinstance(batch,dict) else {};semantic=semantic if isinstance(semantic,dict) else {};checks=semantic.get('checks',[]);checks=checks if isinstance(checks,list) else []
 if (voice.get('status')!='tested' or voice.get('source_runtime_unchanged') is not True
     or voice.get('runtime_source_sha256')!=runtime or voice.get('runtime_source_sha256_finished')!=runtime
     or voice.get('speech_provider')!='Gnani only' or voice.get('live_llm_composition_enabled') is not True
     or batch.get('total')!=3 or batch.get('succeeded')!=3 or batch.get('failed')!=0
     or semantic.get('passed')!=3 or semantic.get('failed')!=0 or len(checks)!=3
     or not all(isinstance(c,dict) for c in checks) or {c.get('language') for c in checks}!={'en','hi','hi-en'} or any(c.get('passed') is not True for c in checks)
     or not isinstance(voice.get('artifacts'),dict) or not voice.get('artifacts') or not all(artifact(root,k,v) for k,v in voice.get('artifacts',{}).items())):
  problems.append('Current three-language targeted Gnani batch evidence is missing, stale, changed or failing')
 if voice.get('verification_mode')=='targeted_retest_with_retained_audio':
  from scripts.targeted_voice_evidence import composite_ok
  dataset=next((root/k).parent.parent for k in expected['dataset_source_sha256'] if k.endswith('/practice/questions.csv'))
  if not composite_ok(root,voice,runtime,dataset):problems.append('Retained speech artifacts or current spoken-output validation are missing, stale or failed')
 return problems

WARNINGS=[
 'Targeted verification only: no fresh full52 or full96 score is claimed.',
 'Preserved practice results span recorded revisions and are not unseen organizer scores.',
 'The historical baseline and current model are not a controlled same-model full comparison.',
 'Synthetic audio does not establish human-speech, accent, noise or subjective listening quality.'
]
