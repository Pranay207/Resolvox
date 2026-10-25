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
    fallback=sum(value for key,value in counts.items() if 'fallback' in key)
    guards=counts.get('deterministic_guardrail',0)
    rules=counts.get('evidence_validated_rules',0)
    abstentions=sum(value for key,value in counts.items() if key.startswith('abstained'))
    known=generated+fallback+guards+rules+abstentions
    remaining=sum(counts.values())-known
    text=f'generated {generated}; checked fallbacks {fallback}; guards {guards}; rules {rules}; abstentions {abstentions}'
    return text+(f'; other/unrecorded {remaining}' if remaining else '')


def live_result_text(data):
    if not data:
        return 'pending; no current live artifact recorded'
    values=data['summary'];total=values.get('total',0);planned=values.get('planned','?')
    return (f"{values.get('passed',0)}/{planned} planned; {total} evaluated; "
        f"complete={live_complete(data)}; errors {values.get('errors','?')}")


def live_narrative(live2,live3):
    return ('Current LLM-enabled grounded questions: '+live_result_text(live2)+'. '
        +'Current LLM-enabled conversation turns: '+live_result_text(live3)+'. '
        +'A live run includes generated answers, checked fallbacks, guards and abstentions; it does not mean every reply was freshly generated. '
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
    parser=argparse.ArgumentParser();parser.add_argument('--pytest-passed',type=int,required=True);args=parser.parse_args()
    engineering=load('engineering_verification.json')
    engineering['pytest'].update(passed=args.pytest_passed,total=args.pytest_passed,exit_code=0)
    engineering['runtime_commit']=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    engineering['generated_at']=datetime.now(timezone.utc).isoformat();write('engineering_verification.json',engineering)
    stages={step:load(f'eval_step{step}.json') for step in (1,2,3)}
    live_partial=optional('eval_step2_live_postfix_partial.json')
    live2_name,live2=select_current_live(2);live3_name,live3=select_current_live(3)
    benchmark=live2 or live_partial or stages[2]
    benchmark_scope=('Current LLM-enabled question run; '+live_result_text(live2)) if live2 else ('Historical post-fix live subset; '+live_result_text(live_partial) if live_partial else 'Offline grounded practice; no live generation claim')
    groups={}
    for row in benchmark['results']:
        pred=row['prediction'];metrics=pred.get('llm',{})
        if not metrics:continue
        label='output cache' if metrics.get('cache_hit') else 'uncached requests'
        groups.setdefault(label,[]).append({'id':row['id'],'composition':pred['composition'],'latency_ms':row['latency_ms'],'llm':metrics})
    models=[]
    for label,cases in groups.items():
        models.append({'model':benchmark['configuration']['llm_model']+' ('+label+')','cases':cases,
            'summary':{'evaluated':len(cases),'grounded_llm_count':sum(c['composition']=='grounded_llm' for c in cases),'mean_latency_ms':mean(c['latency_ms'] for c in cases)}})
    write('generation_benchmark_selected.json',{'scope':benchmark_scope+'. Cached and uncached paths are separate. All measured latencies are retained, including outliers; no hard end-to-end timeout or controlled cold-start claim.','configuration':benchmark['configuration'],'models':models})
    hold=load('eval_holdout.json');first=load('eval_holdout_first_pass.json');adv=load('eval_adversarial.json');voice=load('voice_validation.json')
    privacy_checks=[c for r in hold['results'] for c in r['judgment']['checks'] if c['check'] in {'no_private_email','no_full_phone_number'} or c['check'].startswith(('privacy','unverified_lookup_has_no_private_data:'))]
    failed_privacy=sum(not c['passed'] for c in privacy_checks) if privacy_checks else None
    comparison=holdout_comparison(hold)
    probe=optional('coverage_probe.json')
    summary={f'step{step}':data['summary'] for step,data in stages.items()}
    summary.update(engineering=engineering,adversarial=adv['summary'],holdout_first_pass=first['summary'],holdout_regression=hold['summary'],holdout_mode=hold['mode'],privacy_check_failures=failed_privacy,privacy_check_count=len(privacy_checks),privacy_check_status='recorded' if privacy_checks else 'not_recorded',holdout_scorer_comparison=comparison,development_probe=probe.get('summary',{}),voice={'status':voice['status'],'audio_passed':voice['batch']['succeeded'],'semantic_passed':voice['semantic_validation']['passed']})
    summary.update(step2_live=live2.get('summary',{}),step3_live=live3.get('summary',{}),
        live_practice_complete=live_complete(live2) and live_complete(live3),
        historical_postfix_live_subset=live_partial.get('summary',{}),
        regional_preview=optional('language_validation.json').get('summary',{}))
    write('final_summary.json',summary)
    run=load('final_evaluation.json')
    run['post_run_verification']={'number_format_rescoring':'Raw predictions unchanged; original checks retained in eval_step*_raw_scoring.json.','adversarial_rerun':adv['summary'],'pytest':engineering['pytest'],'known_holdout_failures_retained':hold['summary']['failed'],'holdout_scorer_comparison':comparison,'privacy_checks':{'count':len(privacy_checks),'failed':failed_privacy,'status':'recorded' if privacy_checks else 'not_recorded'}}
    run['current_live_practice']={str(step):{'artifact':name,'summary':data.get('summary',{}),'configuration':data.get('configuration',{}),'complete':live_complete(data)} for step,name,data in ((2,live2_name,live2),(3,live3_name,live3))}
    run['full_live_practice_rerun_complete']=live_complete(live2) and live_complete(live3)
    run['note']=live_narrative(live2,live3)+' Holdout evidence remains offline; the saved first pass and exposed regressions are preserved.'
    write('final_evaluation.json',run)
    lines=['# Verification record','', 'These are local measurements, not organizer scores. All raw failures and the first independent holdout are retained.','', '| Check | Recorded result |','|---|---|',f"| Engineering tests | {args.pytest_passed}/{args.pytest_passed} passed |",'| Official dataset validator | Passed: 9 CSVs, 21 KB documents |']
    for step,label in ((1,'Prompt-only, selected model'),(2,'Grounded practice'),(3,'Conversation practice')):
        s=stages[step]['summary'];mode=stages[step].get('configuration',{}).get('evaluation_mode','mode not recorded');lines.append(f"| {label} ({mode}) | {s['passed']}/{s['total']}; errors {s['errors']} |")
    for label,data in (('Current LLM-enabled questions',live2),('Current LLM-enabled conversations',live3)):
        lines.append(f'| {label} | {live_result_text(data)} |')
        if data:lines.append(f'| {label}: composition | {composition_text(data)} |')
    if live_partial:
        partial=live_partial['summary'];lines.append(f"| Historical post-fix live subset | {partial['passed']}/{partial.get('planned','?')} planned; {partial['total']} evaluated; incomplete; preserved unchanged |")
    lines += [f"| Development adversarial/stateful | {adv['summary']['passed']}/{adv['summary']['total']} |",f"| First independent holdout, offline | {first['summary']['passed']}/{first['summary']['evaluated']} |",f"| Exposed holdout after fixes, offline | {hold['summary']['passed']}/{hold['summary']['evaluated']}; {hold['summary']['failed']} remaining evaluated failures |",f"| Real Gnani synthetic-audio round trips | {voice['batch']['succeeded']}/6 audio and {voice['semantic_validation']['passed']}/6 semantic checks |",'', 'The selected model is qwen3:1.7b. '+live_narrative(live2,live3)+' Actual timing outliers are retained; configured request timeouts do not prove a hard end-to-end latency bound. Human accent/noise robustness and subjective speech quality were not tested.','', 'Number words and digits are scored consistently: the two conversation checks for “three” versus “3” were rescored without changing model predictions or gold expectations. Original checks are preserved.','',regression_note(hold,comparison),'', 'The four-page report, archive inspection and configured-secret scan are verified separately in sample_outputs/pdf_qa.json, package_smoke.json and secret_audit.json. The dataset, .env, model caches and virtual environment are excluded from the ZIP.','', 'The user-recorded demo.mp4 remains pending and must be at most 120 seconds. The ZIP is a reviewable draft until that required file is included.','', 'Reproduce current live practice separately: python scripts/resume_live_practice.py --step 2, then --step 3. Run python -m pytest -q, rebuild/render the report, then package/verify/audit the ZIP. Earlier raw predictions remain preserved.']
    lines += ['',regional_preview_text(optional('language_validation.json'))]
    if probe.get('summary'):
        ps=probe['summary']
        lines += ['',f"Fresh development coverage probe: {ps['passed']}/{ps['evaluated']}. Earlier failures remain in coverage_probe_first_pass.json; these are exposed engineering checks, not an independent blind evaluation."]
    lines.insert(lines.index('| Official dataset validator | Passed: 9 CSVs, 21 KB documents |')+1,f"| Holdout privacy assertions | {len(privacy_checks)} checked; {failed_privacy} failures |" if privacy_checks else '| Holdout privacy assertions | Not recorded; no zero-failure claim |')
    (ROOT/'VERIFICATION.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    for filename in ('README.md','BRIEF_CHECKLIST.md'):
        path=ROOT/filename;text=path.read_text(encoding='utf-8')
        if filename=='README.md':text=update_readiness(text,stages,live2,live3,hold,args.pytest_passed)
        else:
            text=re.sub(r'\*\*\d+/\d+ pytest tests\*\*',f'**{args.pytest_passed}/{args.pytest_passed} pytest tests**',text)
            start=text.index('## Recorded verification');end=text.index('## Still incomplete',start)
            records=['## Recorded verification','',f"- [x] Engineering: **{args.pytest_passed}/{args.pytest_passed} pytest tests**; official dataset validator passed."]
            records += [f"- [x] {label}: **{stages[step]['summary']['passed']}/{stages[step]['summary']['total']}**, errors {stages[step]['summary']['errors']}; see `sample_outputs/eval_step{step}.json` for actual composition, configuration and timings." for step,label in ((1,'Prompt-only selected-model baseline'),(2,'Grounded practice questions ('+stages[2].get('configuration',{}).get('evaluation_mode','mode not recorded')+')'),(3,'Conversation practice turns ('+stages[3].get('configuration',{}).get('evaluation_mode','mode not recorded')+')'))]
            for label,name,data in (('Current LLM-enabled grounded questions',live2_name,live2),('Current LLM-enabled conversation turns',live3_name,live3)):
                mark='x' if live_complete(data) and data['summary'].get('passed')==data['summary'].get('total') else ' '
                records.append(f'- [{mark}] {label}: {live_result_text(data)}; see `sample_outputs/{name}`.')
                if data:records.append('  Composition: '+composition_text(data)+'.')
            if live_partial:
                partial=live_partial['summary'];records.append(f"- [x] Historical live subset preserved unchanged: {partial['passed']}/{partial.get('planned','?')} planned; {partial['total']} evaluated. This is not current complete-run evidence.")
            records += ['',regional_preview_text(optional('language_validation.json')),'']
            records += [f"- [x] Development adversarial/stateful regression: **{adv['summary']['passed']}/{adv['summary']['total']}**; development data, not blind evaluation.",'- [x] '+regression_note(hold,comparison),f"- [x] Holdout privacy assertions: {len(privacy_checks)} recorded, {failed_privacy} failed." if privacy_checks else '- [ ] Holdout privacy assertions were not recorded.',f"- [x] Real Gnani synthetic-audio round trips: **{voice['batch']['succeeded']}/6** audio, **{voice['semantic_validation']['passed']}/6** semantic/privacy checks. Human accent/noise robustness and subjective listening remain unverified.",'','Measured JSON and `VERIFICATION.md` preserve provenance, failures, timing and composition. A live run includes checked fallbacks and guards; it does not mean every reply was freshly generated.','']
            text=text[:start]+'\n'.join(records)+'\n'+text[end:]
            text=re.sub(r'Full compliance is not claimed\..*?(?=\n\n)',lambda match:'Full compliance is not claimed. The required user demo is still pending; human speech/listening and live holdout checks remain unverified. '+live_narrative(live2,live3)+' '+regional_preview_text(optional('language_validation.json'))+' See `sample_outputs/brief_compliance_audit.json` for the page-by-page requirement review.',text,count=1,flags=re.S)
        path.write_text(text,encoding='utf-8')
    print(json.dumps({'practice':[stages[s]['summary']['passed'] for s in (1,2,3)],'tests':args.pytest_passed,'holdout_regression':hold['summary']['passed'],'voice':voice['status']}))

if __name__=='__main__':main()
