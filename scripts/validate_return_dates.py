"""Selected return-date application checks; no complete practice rerun."""
from pathlib import Path
import os,json,hashlib,datetime,time,sys,argparse
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--hosted',action='store_true',help='Use the explicit Groq application profile from ignored .env.hosted.')
parser.add_argument('--only',nargs='+',choices=['missing_date_compound','missing_date_hindi','missing_date_hinglish','known_placement'])
args=parser.parse_args()
from src.app_profile import hosted_environment
root=ROOT
if args.hosted:os.environ.update(hosted_environment(root,os.environ))
from src.agent import Resources
from src.multilingual import MultilingualAgent
from src.response_runtime import response_scope
from generate_voice_samples import runtime_source_hashes
stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
folder=root/'sample_outputs'/('return_date_live_'+stamp);folder.mkdir()
start=runtime_source_hashes(root)
r=Resources();original=r.llm.complete;drafts=[]
def uncached(*args,**kwargs):
    kwargs['cache']=False
    raw=original(*args,**kwargs)
    try:drafts.append(json.loads(raw))
    except ValueError:drafts.append({'invalid_model_json':True})
    return raw
r.llm.complete=uncached
record={'scope':'Four uncached selected application return-date checks, paced for the provider quota. No full52 or full96 rerun.',
        'inference_profile':'hosted_application' if args.hosted else 'local_ollama','runtime_source_sha256':start,'cases':[],'complete':False}
cases=[('missing_date_compound','Before I return a pair of shoes, tell me both the return window and whether pickup costs anything.','en'),
       ('missing_date_hindi','जूते लौटाने के लिए कितने दिन मिलते हैं और पिकअप शुल्क कितना है? ऑर्डर की तारीख नहीं पता।','hi'),
       ('missing_date_hinglish','Mujhe kapde return karne hain. Order ki date nahi pata. Return window aur pickup charge kya hai?','hi-en'),
       ('known_placement','I placed my clothing order on 5 October 2026. What return window applies?','en')]
if args.only:cases=[case for case in cases if case[0] in args.only]
record['scope']=str(len(cases))+' uncached selected application return-date checks; not a full52 or full96 run.'
record['request_pacing_seconds']=60 if args.hosted else 0
record['verification_driver_sha256']={'scripts/validate_return_dates.py':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
record['manual_source_review']={'status':'pending'}
for index,(ident,question,lang) in enumerate(cases):
    if index and record['request_pacing_seconds']:time.sleep(record['request_pacing_seconds'])
    began=time.perf_counter();offset=len(drafts)
    try:
        with response_scope(45):out=MultilingualAgent(resources=r,compose=True).respond(question,language_hint=lang)
        checks={'answered_or_requested_missing_date':out['decision'] in {'answer','clarify'},'source_supported':out.get('evidence_supported') is True,
                'no_service_error':not out.get('service_error'),'no_order_or_ticket_actions':not out.get('tool_calls'),
                'correct_language':out.get('language')==lang}
        item={'id':ident,'question':question,'prediction':out,'checks':checks,'passed':all(checks.values())}
    except Exception as error:item={'id':ident,'passed':False,'error_type':type(error).__name__}
    item.update(seconds=round(time.perf_counter()-began,3),model_drafts=drafts[offset:])
    record['cases'].append(item)
    for path in (folder/'validation.json',root/'sample_outputs/return_date_validation.json'):
        path.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:item.get(k) for k in ('id','passed','seconds','checks','error_type')}),flush=True)
record.update(complete=True,runtime_source_sha256_finished=runtime_source_hashes(root))
record['source_runtime_unchanged']=record['runtime_source_sha256_finished']==start
for path in (folder/'validation.json',root/'sample_outputs/return_date_validation.json'):
    path.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('OUTPUT '+str(folder.relative_to(root)),flush=True)
raise SystemExit(0 if all(c['passed'] for c in record['cases']) and record['source_runtime_unchanged'] else 1)
