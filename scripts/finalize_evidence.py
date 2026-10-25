"""Summarize recorded results without changing predictions or gold rubrics."""
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
from statistics import mean
import argparse,json,re,subprocess,sys
ROOT=Path(__file__).resolve().parents[1]

def load(name):return json.loads((ROOT/'sample_outputs'/name).read_text(encoding='utf-8'))
def write(name,data):(ROOT/'sample_outputs'/name).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')

def optional(name):
    try:return load(name)
    except (OSError,ValueError):return {}


def live_complete(data):
    """Completion needs an explicit flag and matching planned/saved counts."""
    values=data.get('summary',{})
    total=values.get('total')
    return (values.get('complete') is True and data.get('complete') is not False
        and isinstance(total,int) and total>0 and values.get('planned')==total
        and len(data.get('results',[]))==total)


def select_current_live(step,reader=None):
    reader=reader or optional
    name=f'eval_step{step}_live_current.json'
    data=reader(name)
    mode=data.get('configuration',{}).get('evaluation_mode','')
    if not data.get('summary') or mode!='live_compose_true':
        return name,{}
    return name,data


def composition_text(data):
    counts=data.get('summary',{}).get('composition_counts',{})
    if not counts:
        counts=Counter(row.get('prediction',{}).get('composition','unrecorded') for row in data.get('results',[]))
    generated=counts.get('grounded_llm',0)
    clarifications=counts.get('grounded_clarification',0)
    excerpts=counts.get('document_excerpts',0)
    fallback=sum(value for key,value in counts.items() if 'fallback' in key)
    guards=counts.get('deterministic_guardrail',0)
    rules=counts.get('evidence_validated_rules',0)
    abstentions=sum(value for key,value in counts.items() if key.startswith('abstained'))
    known=generated+clarifications+excerpts+fallback+guards+rules+abstentions
    remaining=sum(counts.values())-known
    text=(f'generated {generated}; clarifications {clarifications}; document excerpts {excerpts}; '
          f'checked fallbacks {fallback}; guards {guards}; rules {rules}; abstentions {abstentions}')
    return text+(f'; other/unrecorded {remaining}' if remaining else '')


def live_result_text(data):
    if not data:
        return 'pending; no current live artifact recorded'
    values=data['summary'];total=values.get('total',0);planned=values.get('planned','?')
    return (f"{values.get('passed',0)}/{planned} planned; {total} evaluated; "
        f"complete={live_complete(data)}; errors {values.get('errors','?')}")


def live_narrative(live2,live3):
    source_only=any('src/document_answers.py' in data.get('configuration',{}).get('provenance',{}).get('runtime_source_sha256',{})
        for data in (live2,live3) if data)
    paths=('A source-driven run includes generated answers, clarifications, guards and abstentions; no authored policy answer fallback is used. '
        if source_only else 'A historical live run includes generated answers, checked fallbacks, guards and abstentions. ')
    return ('Current LLM-enabled grounded questions: '+live_result_text(live2)+'. '
        +'Current LLM-enabled conversation turns: '+live_result_text(live3)+'. '
        +paths+'A live result does not mean every reply was freshly generated. '
        +'Offline results remain separate. Earlier live runs are historical evidence, not substitutes for current completed runs.')


def regional_preview_text(data):
    if not data:
        return 'The optional regional-language preview has no completed quality evidence; additional languages remain experimental.'
    values=data.get('summary',{})
    return (f"Optional regional-language preview remains experimental. The saved synthetic language run passed {values.get('voice_passed',0)}/{values.get('planned','?')} voice cases; "
        f"{values.get('failed',0)} failed and {values.get('pending',0)} are pending. "
        +'This does not establish all ten languages as working; each language has only one refund-question check, and native intelligibility was not independently reviewed.')


def update_readiness(text,stages,live2,live3,hold,tests):
    old=r'The implementation includes query-first hybrid retrieval,.*?(?=\n\n)'
    current=('The implementation includes query-first hybrid retrieval, source-text LLM generation, checked deterministic fallbacks, session verification, and the Gnani speech wrapper. '
        +'The selected local model is `qwen3:1.7b`. '
        +f"The latest broader offline regression passes **{hold['summary']['passed']}/{hold['summary']['evaluated']}**, with **{hold['summary']['failed']} remaining failures in these evaluated cases**; the engineering suite passes **{tests}/{tests}**. "
        +f"Offline practice remains {stages[2]['summary']['passed']}/{stages[2]['summary']['total']} questions and {stages[3]['summary']['passed']}/{stages[3]['summary']['total']} conversation turns with `compose=False`. "
        +live_narrative(live2,live3)+' '
        +'Actual composition, cache status, provenance and timings are recorded in `sample_outputs/`. Request timeout settings do not establish a hard end-to-end bound; neither offline passes nor synthetic voice checks establish human-speech performance.')
    text=re.sub(old,lambda match:current,text,count=1,flags=re.S)
    return text.replace('recorded evaluation clearly separates offline checks from the incomplete live subset.',
        'recorded evaluation separates offline checks, current live runs and historical results.')


def holdout_comparison(hold):
    old=optional('eval_holdout_before_normalization_v2.json')
    rescored=optional('eval_holdout_scorer_v2_same_predictions.json')
    provenance=rescored.get('rescoring',{})
    return {'original_product_score':old.get('summary',{}),'same_predictions_rescored':rescored.get('summary',{}),
            'current_product_score':hold['summary'],'original_scorer':old.get('scorer',{'version':'legacy_v1_unversioned'}),
            'rescored_scorer':rescored.get('scorer',{}),'current_scorer':hold.get('scorer',{}),
            'rescoring_provenance':provenance,'scorer_only_pass_delta':provenance.get('passed_delta'),
            'runtime_pass_delta_same_scorer':hold['summary']['passed']-rescored['summary']['passed'] if provenance.get('predictions_unchanged') and rescored.get('scorer',{}).get('version')==hold.get('scorer',{}).get('version') else None}

def regression_note(hold,comparison):
    count=hold['summary']['failed'];total=hold['summary']['evaluated'];passed=hold['summary']['passed']
    text=f'The latest exposed-set offline regression passed {passed}/{total}, with {count} remaining failures in the evaluated cases.'
    old=comparison.get('original_product_score',{});rescored=comparison.get('same_predictions_rescored',{})
    if comparison.get('rescoring_provenance',{}).get('predictions_unchanged'):
        text+=f" Old predictions scored {old.get('passed','?')}/{old.get('evaluated','?')} originally and {rescored.get('passed','?')}/{rescored.get('evaluated','?')} under scorer v2 without prediction changes: {comparison.get('scorer_only_pass_delta','?')} points came from scoring normalization, not product improvement."
    if comparison.get('runtime_pass_delta_same_scorer') is not None:
        text+=f" The current product improved from {rescored['passed']} to {passed} under that same scorer after runtime fixes."
    return text+' The first independent pass and original predictions remain preserved. Later results are exposed regressions, not a new blind holdout, live-generation test, organizer score, guarantee of placing or proof of universal semantic correctness.'

def main():
    """Summarize actual receipts; never run checks or improve their scores."""
    import hashlib

    parser=argparse.ArgumentParser(description='Summarize current recorded validation without rewriting tests or documents.')
    parser.add_argument('--pytest-passed',type=int,help='Optional assertion against the actual engineering receipt; never changes its count.')
    args=parser.parse_args()
    engineering=optional('engineering_verification.json')
    pytest=engineering.get('pytest',{})
    if not isinstance(pytest,dict):pytest={}
    if args.pytest_passed is not None and (type(pytest.get('passed')) is not int or args.pytest_passed!=pytest['passed']):
        parser.error('--pytest-passed must match the recorded engineering passed count')
    expected={path.relative_to(ROOT).as_posix():hashlib.sha256(path.read_bytes()).hexdigest()
              for path in sorted((ROOT/'src').glob('*.py')) if path.is_file()}
    required={'src/agent.py','src/document_answers.py','src/document_context.py'}

    def fresh(record,*,finished=False):
        if not required<=set(expected):return False
        if finished:
            candidates=[record.get('runtime_source_sha256_finished',{})]
        else:
            candidates=[record.get('runtime_source_sha256',{})]
            for parent in (record.get('provenance',{}),record.get('configuration',{}).get('provenance',{})
                           if isinstance(record.get('configuration',{}),dict) else {}):
                if isinstance(parent,dict):candidates.append(parent.get('runtime_source_sha256',{}))
        return any(isinstance(hashes,dict) and all(hashes.get(name)==digest for name,digest in expected.items())
                   for hashes in candidates)

    def receipt(name):
        path=ROOT/'sample_outputs'/name
        return {'artifact':'sample_outputs/'+name,'present':path.is_file(),
                'artifact_sha256':hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None}

    engineering_current=fresh(engineering)
    engineering_complete=(engineering_current and type(pytest.get('total')) is int and pytest['total']>0
                          and type(pytest.get('exit_code')) is int)
    engineering_passed=(engineering_complete and type(pytest.get('passed')) is int
                        and pytest['passed']==pytest['total'] and pytest['exit_code']==0)
    engineering_record={**receipt('engineering_verification.json'),'runtime_current':engineering_current,
        'pytest':pytest,'dataset_validation':engineering.get('dataset_validation',{}),
        'runtime_commit':engineering.get('runtime_commit'),'complete':engineering_complete,'passed':engineering_passed}
    live_records={}
    blockers=[]
    if not engineering_passed:blockers.append('Current engineering verification is missing, stale, incomplete or failing')
    for step,planned in ((2,52),(3,96)):
        name=f'eval_step{step}_live_current.json'
        data=optional(name);config=data.get('configuration',{})
        if not isinstance(config,dict):config={}
        actual_summary=data.get('summary',{})
        if not isinstance(actual_summary,dict):actual_summary={}
        eligible=fresh(data) and config.get('evaluation_mode')=='live_compose_true'
        complete=(eligible and live_complete(data) and actual_summary.get('planned')==planned)
        passed=(complete and actual_summary.get('passed')==planned
                and actual_summary.get('failed',0)==0 and actual_summary.get('errors')==0)
        results=data.get('results',[])
        if not isinstance(results,list):results=[]
        predictions=[row.get('prediction',{}) for row in results if isinstance(row,dict)]
        predictions=[value for value in predictions if isinstance(value,dict)]
        counts=Counter(value.get('composition','unrecorded') for value in predictions)
        providers=Counter((value.get('llm',{}).get('provider') if isinstance(value.get('llm',{}),dict) else None)
                          or value.get('provider','unrecorded') for value in predictions)
        live_records[str(step)]={**receipt(name),'runtime_current':eligible,'complete':complete,'passed':passed,
            'configuration':config,'summary':actual_summary if eligible else {},
            'rejected_recorded_summary':actual_summary if not eligible else {},
            'composition_counts':dict(counts) if eligible else {},
            'actual_provider_counts':dict(providers) if eligible else {},
            'cache_hits':sum(value.get('llm',{}).get('cache_hit') is True for value in predictions
                             if isinstance(value.get('llm',{}),dict)) if eligible else 0}
        if not eligible:blockers.append(f'Current live step {step} evidence is missing or stale')
        elif not complete:blockers.append(f'Current live step {step} is incomplete')
        elif not passed:blockers.append(f'Current live step {step} contains failed or erroneous responses')
    voice=optional('voice_validation.json')
    batch=voice.get('batch',{});semantic=voice.get('semantic_validation',{})
    if not isinstance(batch,dict):batch={}
    if not isinstance(semantic,dict):semantic={}
    total=batch.get('total',0);checks=semantic.get('checks',[])
    entries=batch.get('entries',[])
    voice_current=fresh(voice) and fresh(voice,finished=True) and voice.get('source_runtime_unchanged') is True
    voice_complete=(voice_current and voice.get('status') in {'tested','failed'}
        and type(total) is int and total>0 and isinstance(entries,list) and len(entries)==total
        and isinstance(checks,list) and len(checks)==total
        and type(batch.get('succeeded')) is int and type(batch.get('failed')) is int
        and batch['succeeded']+batch['failed']==total)
    voice_passed=(voice_complete and voice.get('live_llm_composition_enabled') is True
        and voice.get('status')=='tested' and batch.get('failed')==0 and batch.get('succeeded')==total
        and semantic.get('failed')==0 and semantic.get('passed')==total
        and all(isinstance(check,dict) and check.get('passed') is True for check in checks))
    voice_record={**receipt('voice_validation.json'),'runtime_current':voice_current,
        'status':voice.get('status','pending'),'complete':voice_complete,'passed':voice_passed,
        'live_llm_composition_enabled':voice.get('live_llm_composition_enabled'),
        'started_at_utc':voice.get('started_at_utc'),'finished_at_utc':voice.get('finished_at_utc'),
        'source_runtime_unchanged':voice.get('source_runtime_unchanged'),
        'batch':batch,'semantic_validation':semantic,'reason':voice.get('reason')}
    if not voice_passed:blockers.append('Current Gnani speech verification is missing, stale, incomplete or failing')
    complete=engineering_complete and all(row['complete'] for row in live_records.values()) and voice_complete
    validation_passed=engineering_passed and all(row['passed'] for row in live_records.values()) and voice_passed
    release_path=ROOT/'SUBMISSION_STATUS.json'
    try:release=json.loads(release_path.read_text(encoding='utf-8'))
    except (OSError,ValueError):release={}
    if not isinstance(release,dict):release={}
    submission_ready=validation_passed and fresh(release) and release.get('ready_to_submit') is True
    historical_names=('eval_step1.json','eval_step2.json','eval_step3.json','eval_step2_live_postfix_partial.json',
                      'eval_adversarial.json','eval_holdout_first_pass.json','eval_holdout.json','language_validation.json')
    historical=['sample_outputs/'+name for name in historical_names if (ROOT/'sample_outputs'/name).is_file()]
    history=ROOT/'sample_outputs/history'
    historical+=sorted(path.relative_to(ROOT).as_posix() for path in history.rglob('*.json') if path.is_file())
    run={'generated_at_utc':datetime.now(timezone.utc).isoformat(),'answer_path':'document_context_generation',
        'scope':'Summary of actual current validation receipts; no tests, inference, speech or scoring are executed here.',
        'runtime_source_sha256':expected,'complete':complete,'validation_passed':validation_passed,
        'ready':submission_ready,'ready_to_submit':submission_ready,'validation_blockers':blockers,
        'submission_status':{'artifact':'SUBMISSION_STATUS.json','runtime_current':fresh(release),
            'ready_to_submit':release.get('ready_to_submit') is True,
            'blockers':release.get('blockers',['Final submission readiness has not been verified'])},
        'engineering':engineering_record,'current_live_practice':live_records,
        'full_live_practice_rerun_complete':all(row['complete'] for row in live_records.values()),
        'voice':voice_record,'historical_evidence_paths':historical,
        'historical_evidence_note':'Earlier scores and predictions are preserved separately and are never promoted to current validation.',
        'limitations':'Mechanical local checks do not establish organizer scores, unseen semantic correctness or human-speech quality. The own-voice rehearsal and user demo remain separate final steps.'}
    write('final_evaluation.json',run)
    print(json.dumps({'complete':complete,'validation_passed':validation_passed,'ready_to_submit':submission_ready,
        'current_live':{step:{'complete':row['complete'],'passed':row['passed'],'summary':row['summary']}
                        for step,row in live_records.items()},'voice_status':voice_record['status'],
        'validation_blockers':blockers},indent=2))
    return 0

if __name__=='__main__':main()
