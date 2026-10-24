"""Transparent mechanical evaluation; semantic correctness still needs review."""
from collections import Counter
from datetime import datetime
from pathlib import Path
import csv,json,re,time,hashlib,os
from .config import ROOT,dataset_dir
from .normalize import redact,ascii_digits

def rows(name:str) -> list[dict]:
    with (dataset_dir()/'practice'/name).open(encoding='utf-8-sig',newline='') as f: return list(csv.DictReader(f))

def canonical(text:str) -> str:
    text=ascii_digits(text).lower().replace('₹','').replace(',','')
    months={'जनवरी': 'January', 'फरवरी': 'February', 'मार्च': 'March', 'अप्रैल': 'April', 'मई': 'May', 'जून': 'June', 'जुलाई': 'July', 'अगस्त': 'August', 'सितंबर': 'September', 'अक्टूबर': 'October', 'नवंबर': 'November', 'दिसंबर': 'December'}
    for a,b in months.items(): text=text.replace(a,b.lower())
    def date_replace(m):
        try: return datetime.strptime(m[0],'%d %B %Y').strftime('%Y-%m-%d')
        except ValueError: return m[0]
    text=re.sub(r'\b\d{1,2} (?:january|february|march|april|may|june|july|august|september|october|november|december) \d{4}\b',date_replace,text)
    return re.sub(r'\s+',' ',text).strip()

def facts_present(answer:str,expectation:str) -> tuple[list[str],list[str]]:
    norm=canonical(answer); found=[]; missing=[]
    for fact in filter(None,expectation.split(' ; ')):
        alternatives=fact.split(' / ')
        present=any(re.search(r'(?<!\d)'+re.escape(canonical(v))+r'(?!\d)',norm) if v.strip().isdigit() else canonical(v) in norm for v in alternatives)
        (found if present else missing).append(fact)
    return found,missing

def score(row:dict,result:dict,conversation:bool=False) -> dict:
    answer=result.get('answer',''); accepted=(row.get('acceptable_decisions') or row['expected_decision']).split(' ; ')
    _,missing=facts_present(answer,row.get('must_include',''))
    forbidden=[x for x in row.get('must_not_include','').split(' ; ') if x and canonical(x) in canonical(answer)]
    gold=set(filter(None,row.get('gold_evidence','').split(' ; '))); actual=set(result.get('retrieved_chunk_ids',[]))
    kb_gold={g for g in gold if not g.startswith('products.csv:')}
    search_ids={c['id'] for c in result.get('retrieval_candidates',[])}
    expected_tools=re.findall(r'(lookup_order|create_ticket)\(',row.get('expected_tool_calls',''))
    actual_tools=[t['name'] for t in result.get('tool_calls',[])]
    tools_ok=all(Counter(actual_tools)[t]>=n for t,n in Counter(expected_tools).items())
    decision_ok=result.get('decision') in accepted
    return {'passed':decision_ok and not missing and not forbidden and tools_ok and not result.get('error'),
            'decision_ok':decision_ok,'missing_facts':missing,'forbidden_claims':forbidden,'tools_ok':tools_ok,
            'search_hits':len(kb_gold&search_ids),'search_total':len(kb_gold),'evidence_hits':len(gold&actual),'evidence_total':len(gold),'evidence_recall':len(gold&actual)/len(gold) if gold else None}

def save(path:Path,results:list[dict],step:str) -> dict:
    n=len(results); count=sum(x['checks']['passed'] for x in results)
    hits=sum(x['checks']['evidence_hits'] for x in results); total=sum(x['checks']['evidence_total'] for x in results)
    search_hits=sum(x['checks'].get('search_hits',0) for x in results); search_total=sum(x['checks'].get('search_total',0) for x in results)
    ks=sorted(set(x['prediction'].get('retrieval_k',0) for x in results if x['prediction'].get('retrieval_candidates')))
    summary={'search_k':ks,'search_recall':search_hits/search_total if search_total else None,'step':step,'total':n,'passed':count,'pass_rate':count/n if n else 0,'decision_accuracy':sum(x['checks']['decision_ok'] for x in results)/n if n else 0,
             'evidence_recall':hits/total if total else None,'errors':sum(bool(x['prediction'].get('error')) for x in results),
             'composition_counts':dict(Counter(x['prediction'].get('composition',x['prediction'].get('mode','unknown')) for x in results)),
             'note':'Mechanical facts/decision/tool checks; not organizer scoring or semantic certification. Search recall uses all logged candidates at the reported k; guardrail lookups are separate.'}
    def percentile(values,p):
        values=sorted(values)
        return round(values[min(len(values)-1,int((len(values)-1)*p))],2) if values else None
    groups={}
    for row in results:
        pred=row['prediction']; model=pred.get('llm',{})
        label='cache_hit' if model.get('cache_hit') else ('uncached_llm_attempt' if model.get('attempts') else 'no_model_call')
        groups.setdefault(label,[]).append(row['latency_ms'])
    summary['latency_by_path']={k:{'count':len(v),'p50_ms':percentile(v,.5),'p95_ms':percentile(v,.95)} for k,v in groups.items()}
    files=sorted((ROOT/'src').glob('*.py'))+[ROOT/'src/rule_bindings.json']
    digest=hashlib.sha256(b''.join(p.name.encode()+p.read_bytes() for p in files if p.exists())).hexdigest()
    configuration={'recorded_at':datetime.now().isoformat(timespec='seconds'),'runtime_sha256':digest,
                   'llm_provider':os.getenv('LLM_PROVIDER','ollama'),'llm_model':os.getenv('LLM_MODEL','qwen3:1.7b'),
                   'reference_date':os.getenv('REFERENCE_DATE','2026-10-20')}
    path.parent.mkdir(parents=True,exist_ok=True); path.write_text(json.dumps({'configuration':configuration,'summary':summary,'results':results},ensure_ascii=False,indent=2),encoding='utf-8'); return summary

def evaluate(step:int,limit:int|None=None,offline:bool=True) -> dict:
    path=ROOT/'sample_outputs'/f'eval_step{step}.json'; results=[]
    if step==1:
        from .llm import baseline,LLM
        llm=LLM(); dataset=rows('questions.csv')
        for row in dataset[:limit]:
            started=time.perf_counter(); pred=baseline(row['question'],llm)
            results.append({'id':row['id'],'question':redact(row['question']),'prediction':pred,'checks':score(row,pred),'latency_ms':round(1000*(time.perf_counter()-started),1)})
            save(path,results,'prompt_only'); print(row['id'],results[-1]['checks']['passed'],flush=True)
    else:
        from .agent import Agent,Resources
        resources=Resources(); agent=None; current=None
        dataset=rows('questions.csv' if step==2 else 'conversations.csv')
        for row in dataset[:limit]:
            if step==2 or current!=row['conversation_id']: agent=Agent(resources=resources,compose=not offline)
            current=row.get('conversation_id'); text=row['question'] if step==2 else row['customer_message']
            started=time.perf_counter(); pred=agent.respond(text)
            ident=row.get('id') or row['conversation_id']+'.'+row['turn']
            results.append({'id':ident,'question':pred['transcript'],'prediction':pred,'checks':score(row,pred,step==3),'latency_ms':round(1000*(time.perf_counter()-started),1)})
            save(path,results,'grounded_single_turn' if step==2 else 'conversation')
            print(ident,results[-1]['checks']['passed'],pred.get('composition'),flush=True)
        save(path,results,'grounded_single_turn' if step==2 else 'conversation')
    return save(path,results,str(step))
