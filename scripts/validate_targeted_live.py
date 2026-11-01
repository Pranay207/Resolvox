"""Selected real local conversations and refund edges; never a full52 run."""
import argparse
from pathlib import Path
import sys,os,json,csv,hashlib,datetime,importlib.util,re,time
from urllib.parse import urlparse
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
parser=argparse.ArgumentParser();parser.add_argument('--hosted',action='store_true',help='Use the explicit Groq application profile; leave local evaluation settings unchanged.');parser.add_argument('--pacing-seconds',type=float,default=60,help='Verification pause after generated turns, 0 to 60 seconds; separate from model latency.');parser.add_argument('--conversations',nargs='+',default=['PC009','PC010','PC003','PC004']);parser.add_argument('--skip-refund-edges',action='store_true');parser.add_argument('--refund-edges-only',action='store_true');parser.add_argument('--completed-refund-only',action='store_true');parser.add_argument('--manifest',default='sample_outputs/targeted_live_validation.json');args=parser.parse_args();args.conversations=[] if args.refund_edges_only or args.completed_refund_only else args.conversations
if not 0<=args.pacing_seconds<=60:parser.error('--pacing-seconds must be from 0 to 60')
if args.hosted:
 from src.app_profile import hosted_environment
 os.environ.update(hosted_environment(ROOT,os.environ))
from dotenv import dotenv_values
for key,value in dotenv_values(ROOT/'.env').items():
 if isinstance(value,str):os.environ.setdefault(key,value)
if not args.hosted:assert os.environ.get('LLM_PROVIDER')=='ollama' and urlparse(os.environ.get('LLM_BASE_URL','')).hostname in {'localhost','127.0.0.1'}
assert not os.environ.get('LLM_FALLBACK_PROVIDER')
from src.agent import Resources
from src.multilingual import MultilingualAgent as Agent
from src.evals import rows,score
from src.document_answers import _date_mentions
from datetime import date
spec=importlib.util.spec_from_file_location('targeted_practice',ROOT/'scripts/resume_live_practice.py');practice=importlib.util.module_from_spec(spec);spec.loader.exec_module(practice)
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def sources():return {p.relative_to(ROOT).as_posix():sha(p) for p in sorted((ROOT/'src').glob('*.py'))+[ROOT/'src/rule_bindings.json']}
started=sources();stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ');out=ROOT/'sample_outputs'/('targeted_live_'+stamp);out.mkdir()
last_model_turn=[None]
record={'status':'running','complete':False,'inference_profile':'hosted_application' if args.hosted else 'local_ollama','scope':'Selected official conversations '+','.join(args.conversations)+(' without refund edges.' if args.skip_refund_edges else ' plus two refund edges.')+(' Approved Groq application profile' if args.hosted else ' Local Ollama profile')+' and supplied tools; not full52 or full96, not organizer scoring.','started_at_utc':now(),'runtime_source_sha256':started,'cases':[],'manual_semantic_review':{'status':'pending','reviewer_type':'assistant_source_review_not_human_certification'}}
if args.completed_refund_only:record['scope']='Only the completed-refund record date edge, with actual organizer authentication and local generation; no passing cases repeated.'
record['inter_turn_pacing_seconds']=args.pacing_seconds if args.hosted else 0

def paced_respond(agent, text):
 if args.hosted and last_model_turn[0] is not None:
  delay=args.pacing_seconds-(time.monotonic()-last_model_turn[0])
  if delay>0:time.sleep(delay)
 prediction=agent.respond(text)
 if prediction.get('generation',{}).get('generation_attempts',0):last_model_turn[0]=time.monotonic()
 return prediction

manifest=ROOT/args.manifest
def save():
 manifest.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 (out/'manifest.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
lock=ROOT/'tmp/targeted_release_live.lock';handle=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY);os.write(handle,json.dumps({'pid':os.getpid()}).encode());os.close(handle)
save();print('TARGETED_OUTPUT '+str(out),flush=True)
resources=Resources();agents={};current_id='';private=ROOT/'tmp'/('private_targeted_generation_'+stamp+'.jsonl');original=resources.llm.complete
def complete(*args,**kwargs):
 kwargs['cache']=False
 raw=original(*args,**kwargs)
 with private.open('a',encoding='utf-8') as f:f.write(json.dumps({'id':current_id,'raw_response':raw},ensure_ascii=False)+'\n')
 return raw
resources.llm.complete=complete
try:
 gold=rows('conversations.csv')
 if args.refund_edges_only:
  setup=Agent(resources=resources,compose=True);agents['PC004']=setup;auth_rows=[]
  for auth_row in [r for r in gold if r['conversation_id']=='PC004'][:3]:
   current_id='coupon_auth.'+auth_row['turn'];auth_rows.append(setup.respond(auth_row['customer_message']))
  assert auth_rows[-1].get('verified') is True,'Real coupon order verification failed'
  auth_path=out/'edge_authentication.json';auth_path.write_text(json.dumps({'scope':'Actual redacted host/tool authentication; no policy inference','predictions':auth_rows},ensure_ascii=False,indent=2)+'\n',encoding='utf-8');record['authentication_setup_artifact']=auth_path.relative_to(ROOT).as_posix();save()
 for case in args.conversations:
  selected=[row for row in gold if row['conversation_id']==case];cursor=[0]
  def factory(**options):
   actual=Agent(**options);agents[case]=actual
   class Observed:
    def respond(self,text):
     global current_id
     row=selected[cursor[0]];assert row['customer_message']==text
     current_id=row['conversation_id']+'.'+row['turn'];prediction=paced_respond(actual,text);checks=score(row,prediction,True);cursor[0]+=1
     with (out/'turns.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps({'id':current_id,'prediction':prediction,'checks':checks},ensure_ascii=False)+'\n')
     return prediction
   return Observed()
  artifact=out/(case+'.json');summary=practice.run_evaluation(3,artifact,dataset=selected,resources_factory=lambda:resources,agent_factory=factory)
  case_record={'id':case,'kind':'official_conversation_subset','artifact':artifact.relative_to(ROOT).as_posix(),'sha256':sha(artifact),'summary':summary,'passed':summary['passed']==summary['total'] and summary['complete']}
  record['cases'].append(case_record);save()
  if not case_record['passed']:raise RuntimeError('Targeted conversation failed: '+case)
  assert sources()==started,'Runtime changed during live checks'
 if not args.skip_refund_edges:
  if not args.completed_refund_only:
   current_id='refund_coupon_context';query='When will my refund arrive, and how will my coupon discount affect a partial refund?';prediction=paced_respond(agents['PC004'],query)
   ids={s['id'] for s in prediction.get('generation_context_sources',[])}
   coupon=any('coupon discount' in s['text'].lower() for s in prediction.get('generation_context_sources',[]))
   case={'id':current_id,'kind':'refund_edge','question':query,'prediction':prediction,'checks':{'decision_answer':prediction['decision']=='answer','coupon_policy_in_model_context':coupon,'generated':prediction.get('composition')=='grounded_llm'}}
   case['passed']=all(case['checks'].values());case['authentication_setup_artifact']=record.get('authentication_setup_artifact');artifact=out/(current_id+'.json');artifact.write_text(json.dumps(case,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');record['cases'].append({'id':current_id,'kind':'refund_edge','artifact':artifact.relative_to(ROOT).as_posix(),'sha256':sha(artifact),'passed':case['passed']});save()
   if not case['passed']:raise RuntimeError('Coupon edge failed')
  dataset=resources.data.root
  with (dataset/'data/orders.csv').open(encoding='utf-8-sig') as f:completed=next(r for r in csv.DictReader(f) if r.get('return_refund_completed_on') and r.get('payment_method')=='upi')
  with (dataset/'data/customers.csv').open(encoding='utf-8-sig') as f:customer=next(r for r in csv.DictReader(f) if r['customer_id']==completed['customer_id'])
  actual=Agent(resources=resources,compose=True)
  current_id='completed_refund_auth';actual.respond('Hello');actual.respond('My order number is '+completed['order_id']+'.');auth=actual.respond('The last four digits are '+re.sub(r'\D','',customer['phone'])[-4:]+'.')
  assert auth.get('verified') is True,'Real organizer verification did not pass'
  current_id='refund_completed_date';query='When was my refund completed?';prediction=paced_respond(actual,query);expected=date.fromisoformat(completed['return_refund_completed_on'])
  case={'id':current_id,'kind':'refund_edge','question':query,'prediction':prediction,'checks':{'authenticated':prediction.get('verified') is True,'recorded_date_answered':expected in _date_mentions(prediction['answer']),'generated':prediction.get('composition')=='grounded_llm'}}
  case['passed']=all(case['checks'].values());case['authentication_setup_artifact']=record.get('authentication_setup_artifact');artifact=out/(current_id+'.json');artifact.write_text(json.dumps(case,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');record['cases'].append({'id':current_id,'kind':'refund_edge','artifact':artifact.relative_to(ROOT).as_posix(),'sha256':sha(artifact),'passed':case['passed']});save()
  if not case['passed']:raise RuntimeError('Completed-date edge failed')
 record.update(status='checks_passed_review_pending',complete=True)
except Exception as e:
 record.update(status='failed',error_type=type(e).__name__,error_summary=str(e) if isinstance(e,AssertionError) or isinstance(e,RuntimeError) else 'Targeted execution error')
 print('TARGETED_STOP '+record['error_summary'],flush=True)
finally:
 record.update(finished_at_utc=now(),runtime_source_sha256_finished=sources());record['source_runtime_unchanged']=started==record['runtime_source_sha256_finished'];save();lock.unlink(missing_ok=True)
print(json.dumps({'status':record['status'],'cases_passed':sum(c['passed'] for c in record['cases']),'cases_checked':len(record['cases'])}),flush=True)
raise SystemExit(0 if record['complete'] and record['source_runtime_unchanged'] else 1)
