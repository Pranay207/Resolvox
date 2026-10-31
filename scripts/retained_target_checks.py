"""Recheck saved generated responses; never replay tools or claim fresh inference."""
from pathlib import Path
import hashlib,json,copy
BOUNDED_CHANGES={'src/document_answers.py','src/generation_diagnostics.py','src/pending_refund_context.py','src/refund_timeline.py'}

def validation_sources(prediction,dataset=None):
 # The spoken-source view can be smaller than the actual host validator view.
 # Restore only recorded validation IDs from the unchanged official dataset.
 # retained_ok separately requires the complete original dataset fingerprint.
 sources={s['id']:s for s in prediction['sources']}
 ids=prediction.get('generation',{}).get('validation_source_ids') or list(sources)
 missing=set(ids)-sources.keys()
 if missing:
  from src.kb import KnowledgeBase
  kb=KnowledgeBase(dataset) if dataset is not None else KnowledgeBase()
  for cid in missing:
   if cid in kb.chunks:sources[cid]=kb.chunks[cid].public()
  products=[cid for cid in missing if cid.startswith('products.csv:')]
  if products:
   from src.data import Data
   data=Data(dataset) if dataset is not None else Data()
   for cid in products:
    row=data.products.get(cid.split(':',1)[1])
    if row:sources[cid]={'id':cid,'file':'data/products.csv','text':json.dumps(row,ensure_ascii=False),'doc_type':'catalog','status':'current'}
 if set(ids)-sources.keys():raise ValueError('recorded_validation_source_missing')
 return [sources[cid] for cid in ids]

def validate_response(prediction,contract,*,dataset=None):
 from src.document_answers import _validate_context
 result=_validate_context(contract,validation_sources(prediction,dataset),prediction.get('facts',{}),prediction['language'],private=prediction.get('verified') is True,query=prediction.get('transcript',''))
 if not prediction['answer'].startswith(result['answer']):raise ValueError('saved_answer_does_not_match_validated_response')
 flags=prediction.get('generation',{}).get('model_flags',{})
 if flags and any(contract.get(k)!=v for k,v in flags.items() if k in contract):raise ValueError('saved_model_flags_changed')
 return result

def retained_ok(root,case,value,expected,dataset):
 from scripts import release_evidence as evidence
 from scripts.targeted_release import artifact,read
 try:
  ref=case['saved_output_revalidation']
  if not artifact(root,ref['artifact'],ref['sha256']):return False
  proof=read(root/ref['artifact']);current=expected['runtime_source_sha256']
  if (proof.get('status')!='passed' or proof.get('inference_repeated') is not False
      or proof.get('case_artifact_sha256')!=case['sha256'] or proof.get('case_id')!=case['id']
      or proof.get('runtime_source_sha256')!=current or proof.get('runtime_source_sha256_finished')!=current):return False
  if case['id'].startswith('PC'):
   old=dict(value['configuration']['provenance']['runtime_source_sha256']);old.pop('scripts/resume_live_practice.py',None)
   previous=copy.deepcopy(expected);previous['runtime_source_sha256']=old
   if not evidence.current_practice(value,3,previous,dataset,root):return False
   rows=value['results']
  else:
   old=proof['original_runtime_source_sha256'];rows=[value]
  if proof.get('original_runtime_source_sha256')!=old:return False
  changed={k for k in set(old)|set(current) if old.get(k)!=current.get(k)}
  if not changed or not changed<=BOUNDED_CHANGES:return False
  generated=[r for r in rows if r.get('prediction',{}).get('generation',{}).get('generation_attempts',0)>0]
  checks=proof.get('validations',[])
  if len(checks)!=len(generated) or not checks:return False
  for row,check in zip(generated,checks):
   if check.get('id')!=row.get('id',case['id']) or check.get('passed') is not True:return False
   result=validate_response(row['prediction'],check['contract'],dataset=dataset)
   if hashlib.sha256(result['answer'].encode()).hexdigest()!=check['validated_answer_sha256']:return False
  return True
 except (KeyError,TypeError,ValueError,OSError):return False
