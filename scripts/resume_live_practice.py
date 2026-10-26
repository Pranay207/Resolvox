"""Checkpoint live practice runs without replacing earlier evaluation evidence.

Resume only when runtime, input data and inference settings are unchanged.
Conversation checkpoints are committed only after the entire conversation, so
resuming never invents agent state or repeats a completed ticket/action.
"""
from datetime import datetime, timezone
from itertools import groupby
from pathlib import Path
import argparse
import hashlib
import json
import os
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.config import dataset_dir
from src.evals import rows, save, score
from src.normalize import redact


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def provenance(step):
    dataset = dataset_dir()
    source_files = sorted((ROOT/'src').glob('*.py')) + [ROOT/'src/rule_bindings.json', Path(__file__)]
    inputs = sorted((dataset/'kb').rglob('*')) + sorted((dataset/'data').glob('*.csv'))
    inputs += sorted((dataset/'practice').glob('*.csv')) + [dataset/'tools/tools.py']
    # The organizer's append-only tools/tickets_created.csv is an output,
    # never a model/rubric input and intentionally not part of this fingerprint.
    inference = {key:os.getenv(key,default) for key,default in {
        'LLM_PROVIDER':'ollama', 'LLM_MODEL':'qwen3:4b-instruct', 'RAG_LLM_TIMEOUT':'120',
        'LLM_TIMEOUT':'120', 'DENSE_ENABLED':'true', 'REFERENCE_DATE':'2026-10-20',
        'LLM_FALLBACK_PROVIDER':'', 'LLM_FALLBACK_MODEL':'',
    }.items()}
    # Endpoint identity matters, but URLs can contain credentials. Hash them.
    for key in ('LLM_BASE_URL','LLM_FALLBACK_BASE_URL'):
        inference[key+'_sha256'] = hashlib.sha256(os.getenv(key,'').encode()).hexdigest()
    return {'step':step, 'evaluation_mode':'live_prompt_only' if step==1 else 'live_compose_true',
        'runtime_source_sha256':{str(p.relative_to(ROOT)).replace('\\','/'):_sha(p) for p in source_files if p.is_file()},
        'dataset_sha256':{str(p.relative_to(dataset)).replace('\\','/'):_sha(p) for p in inputs if p.is_file()},
        'inference':inference}


def fingerprint(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def _units(dataset,step):
    if step in (1,2):
        return [[row] for row in dataset]
    units=[list(group) for _,group in groupby(dataset,key=lambda row:row['conversation_id'])]
    if len({unit[0]['conversation_id'] for unit in units})!=len(units):
        raise ValueError('Conversation rows must be contiguous')
    return units


def _id(row,step):
    return row['id'] if step in (1,2) else row['conversation_id']+'.'+row['turn']



def _replace_checkpoint(temporary,output,*,replace=None,sleep=time.sleep,attempts=12):
    """Windows readers/scanners can briefly lock JSON; preserve the pending
    file and retry only that reversible rename, never the model/tool action.
    """
    replace=replace or (lambda source,target:source.replace(target))
    for attempt in range(attempts):
        try:
            replace(temporary,output)
            return
        except PermissionError:
            if attempt+1==attempts:
                raise
            sleep(min(.025*(2**attempt),.25))


def _write(output,results,step,configuration,planned,segments):
    # Existing summary/scoring logic is reused without overwriting its standard
    # eval_step2/3.json files. Same-directory replace makes checkpoints atomic.
    temporary=output.with_name(output.name+'.tmp')
    save(temporary,results,str(step))
    data=json.loads(temporary.read_text(encoding='utf-8'))
    complete=len(results)==planned
    data['configuration'].update(evaluation_mode='live_prompt_only' if step==1 else 'live_compose_true',
        inference_fingerprint=fingerprint(configuration), provenance=configuration)
    scope = ('Current prompt-only LLM baseline; no company documents, retrieval, agent or order/ticket tools enter model context. Mechanical checks are not organizer scoring.' if step==1 else
        'Current source-driven live practice; generation, guards, clarifications and abstentions are reported separately. No authored policy fallback. Mechanical checks are not organizer scoring.')
    data['summary'].update(planned=planned,complete=complete,scope=scope)
    data['segments']=segments
    data['complete']=complete
    temporary.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    _replace_checkpoint(temporary,output)
    return data['summary']


def run_evaluation(step,output,*,max_new_units=None,resources_factory=None,agent_factory=None,
                   dataset=None,provenance_factory=provenance,baseline_fn=None,llm_factory=None):
    if step not in (1,2,3):
        raise ValueError('Only live steps 1, 2 and 3 are supported')
    output=Path(output)
    protected={'eval_step1.json','eval_step2.json','eval_step3.json',
               'eval_step2_live_postfix_partial.json','final_evaluation.json'}
    if output.name in protected:
        raise ValueError('Choose a separate live artifact; historical/standard evidence is protected')
    if max_new_units is not None and max_new_units<1:
        raise ValueError('max_new_units must be positive')
    dataset=dataset if dataset is not None else rows('questions.csv' if step in (1,2) else 'conversations.csv')
    units=_units(dataset,step)
    expected_ids=[_id(row,step) for row in dataset]
    configuration=provenance_factory(step)
    digest=fingerprint(configuration)
    results=[];segments=[]
    if output.exists():
        saved=json.loads(output.read_text(encoding='utf-8'))
        if saved.get('configuration',{}).get('inference_fingerprint')!=digest:
            raise ValueError('Runtime, dataset or inference settings changed; preserve this artifact and choose a new output')
        results=saved['results'];segments=saved.get('segments',[])
        if [row['id'] for row in results]!=expected_ids[:len(results)]:
            raise ValueError('Saved rows are not the unchanged dataset prefix')
    boundaries={0};count=0
    for unit in units:
        count+=len(unit);boundaries.add(count)
    if len(results) not in boundaries:
        raise ValueError('Resume requires a complete conversation checkpoint')
    if len(results)==len(dataset):
        return saved['summary']
    if step==1:
        # Prompt-only baseline never constructs Agent/Resources or reads a KB
        # for generation. Only the public question is sent to src.llm.baseline.
        if baseline_fn is None or llm_factory is None:
            from src.llm import baseline,LLM
            baseline_fn=baseline_fn or baseline
            llm_factory=llm_factory or LLM
        baseline_client=llm_factory()
    else:
        if resources_factory is None or agent_factory is None:
            from src.agent import Agent,Resources
            resources_factory=resources_factory or Resources
            agent_factory=agent_factory or Agent
        resources=resources_factory()
    try:
        git_sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    except (OSError,subprocess.SubprocessError):
        git_sha='unavailable'
    segment={'started_at_utc':datetime.now(timezone.utc).isoformat(),'git_sha':git_sha,
        'reused_responses':len(results),'new_responses':0,'completed':False}
    segments.append(segment)
    skipped=len(results);new_units=0
    for unit in units:
        if skipped:
            skipped-=len(unit)
            continue
        if fingerprint(provenance_factory(step))!=digest:
            raise ValueError('Runtime inputs changed during evaluation; checkpoint remains preserved')
        if step!=1:
            agent=agent_factory(resources=resources,compose=True)
        pending=[]
        for row in unit:
            text=row['question'] if step in (1,2) else row['customer_message']
            began=time.perf_counter()
            prediction=baseline_fn(text,baseline_client) if step==1 else agent.respond(text)
            transcript=redact(text) if step==1 else prediction['transcript']
            pending.append({'id':_id(row,step),'question':transcript,'prediction':prediction,
                'checks':score(row,prediction,step==3),'latency_ms':round(1000*(time.perf_counter()-began),1)})
            print(pending[-1]['id'],pending[-1]['checks']['passed'],prediction.get('composition',prediction.get('mode')),flush=True)
        if fingerprint(provenance_factory(step))!=digest:
            raise ValueError('Runtime inputs changed before checkpoint; earlier checkpoints remain preserved')
        results.extend(pending);new_units+=1;segment['new_responses']+=len(pending)
        segment['checkpoint_at_utc']=datetime.now(timezone.utc).isoformat()
        segment['completed']=len(results)==len(dataset)
        summary=_write(output,results,step,configuration,len(dataset),segments)
        if max_new_units is not None and new_units>=max_new_units:
            break
    return summary


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--step',type=int,choices=(1,2,3),required=True)
    parser.add_argument('--output',type=Path)
    parser.add_argument('--max-new-units',type=int,help='Stop after this many new questions (steps1/2) or whole conversations (step3)')
    args=parser.parse_args()
    output=args.output or ROOT/'sample_outputs'/f'eval_step{args.step}_live_current.json'
    try:
        summary=run_evaluation(args.step,output,max_new_units=args.max_new_units)
    except (ValueError,OSError) as exc:
        print(str(exc),file=sys.stderr)
        return 2
    print(json.dumps(summary,indent=2),flush=True)
    success = summary['complete'] and (summary['passed']==summary['total'] or (args.step==1 and summary.get('errors')==0))
    return 0 if success else (1 if summary['complete'] else 2)


if __name__=='__main__':
    raise SystemExit(main())
