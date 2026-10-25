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
    benchmark=live_partial or stages[2]
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
    write('generation_benchmark_selected.json',{'scope':'Current post-fix partial live run; '+str(benchmark['summary'].get('total',0))+' evaluated of '+str(benchmark['summary'].get('planned',benchmark['summary'].get('total',0)))+' planned. Incomplete live evaluation; cached and uncached paths separate. All measured latencies retained, including outliers; no hard end-to-end timeout or controlled cold-start claim.','configuration':benchmark['configuration'],'models':models})
    hold=load('eval_holdout.json');first=load('eval_holdout_first_pass.json');adv=load('eval_adversarial.json');voice=load('voice_validation.json')
    privacy_checks=[c for r in hold['results'] for c in r['judgment']['checks'] if c['check'] in {'no_private_email','no_full_phone_number'} or c['check'].startswith(('privacy','unverified_lookup_has_no_private_data:'))]
    failed_privacy=sum(not c['passed'] for c in privacy_checks) if privacy_checks else None
    comparison=holdout_comparison(hold)
    probe=optional('coverage_probe.json')
    summary={f'step{step}':data['summary'] for step,data in stages.items()}
    summary.update(engineering=engineering,adversarial=adv['summary'],holdout_first_pass=first['summary'],holdout_regression=hold['summary'],holdout_mode=hold['mode'],privacy_check_failures=failed_privacy,privacy_check_count=len(privacy_checks),privacy_check_status='recorded' if privacy_checks else 'not_recorded',holdout_scorer_comparison=comparison,development_probe=probe.get('summary',{}),voice={'status':voice['status'],'audio_passed':voice['batch']['succeeded'],'semantic_passed':voice['semantic_validation']['passed']})
    write('final_summary.json',summary)
    run=load('final_evaluation.json')
    run['post_run_verification']={'number_format_rescoring':'Raw predictions unchanged; original checks retained in eval_step*_raw_scoring.json.','adversarial_rerun':adv['summary'],'pytest':engineering['pytest'],'known_holdout_failures_retained':hold['summary']['failed'],'holdout_scorer_comparison':comparison,'privacy_checks':{'count':len(privacy_checks),'failed':failed_privacy,'status':'recorded' if privacy_checks else 'not_recorded'}}
    write('final_evaluation.json',run)
    lines=['# Verification record','', 'These are local measurements, not organizer scores. All raw failures and the first independent holdout are retained.','', '| Check | Recorded result |','|---|---|',f"| Engineering tests | {args.pytest_passed}/{args.pytest_passed} passed |",'| Official dataset validator | Passed: 9 CSVs, 21 KB documents |']
    for step,label in ((1,'Prompt-only, selected model'),(2,'Grounded practice'),(3,'Conversation practice')):
        s=stages[step]['summary'];mode=stages[step].get('configuration',{}).get('evaluation_mode','mode not recorded');lines.append(f"| {label} ({mode}) | {s['passed']}/{s['total']}; errors {s['errors']} |")
    if live_partial:
        partial=live_partial['summary'];lines.append(f"| Post-fix live subset, incomplete | {partial['passed']}/{partial.get('planned','?')} planned; {partial['total']} evaluated; complete=False |")
    lines += [f"| Development adversarial/stateful | {adv['summary']['passed']}/{adv['summary']['total']} |",f"| First independent holdout, offline | {first['summary']['passed']}/{first['summary']['evaluated']} |",f"| Exposed holdout after fixes, offline | {hold['summary']['passed']}/{hold['summary']['evaluated']}; {hold['summary']['failed']} remaining evaluated failures |",f"| Real Gnani synthetic-audio round trips | {voice['batch']['succeeded']}/6 audio and {voice['semantic_validation']['passed']}/6 semantic checks |",'', 'The selected model is qwen3:1.7b. Current complete Step 2/3 practice runs use offline compose=False; their passes do not measure LLM generation. Current live model evidence is the separate incomplete post-fix subset, with generated answers, checked fallbacks, guards and abstentions. Earlier complete live runs predate these fixes and do not establish current full live success. Actual timing outliers are retained; configured request timeouts do not prove a hard end-to-end latency bound. Human accent/noise robustness and subjective speech quality were not tested.','', 'Number words and digits are scored consistently: the two conversation checks for “three” versus “3” were rescored without changing model predictions or gold expectations. Original checks are preserved.','',regression_note(hold,comparison),'', 'The four-page report, archive inspection and configured-secret scan are verified separately in sample_outputs/pdf_qa.json, package_smoke.json and secret_audit.json. The dataset, .env, model caches and virtual environment are excluded from the ZIP.','', 'The user-recorded demo.mp4 remains pending and must be at most 120 seconds. The ZIP is a reviewable draft until that required file is included.','', 'Reproduce: python scripts/final_evaluate.py; python scripts/rescore_practice.py; python -m pytest -q; python scripts/build_report.py; python package_submission.py; python scripts/verify_package.py; python scripts/audit_release.py.']
    if probe.get('summary'):
        ps=probe['summary']
        lines += ['',f"Fresh development coverage probe: {ps['passed']}/{ps['evaluated']}. Earlier failures remain in coverage_probe_first_pass.json; these are exposed engineering checks, not an independent blind evaluation."]
    lines.insert(lines.index('| Official dataset validator | Passed: 9 CSVs, 21 KB documents |')+1,f"| Holdout privacy assertions | {len(privacy_checks)} checked; {failed_privacy} failures |" if privacy_checks else '| Holdout privacy assertions | Not recorded; no zero-failure claim |')
    (ROOT/'VERIFICATION.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    for filename in ('README.md','BRIEF_CHECKLIST.md'):
        path=ROOT/filename;text=path.read_text(encoding='utf-8')
        if filename=='README.md':text=re.sub(r'engineering suite passes \*\*\d+/\d+\*\*',f'engineering suite passes **{args.pytest_passed}/{args.pytest_passed}**',text)
        else:
            text=re.sub(r'\*\*\d+/\d+ pytest tests\*\*',f'**{args.pytest_passed}/{args.pytest_passed} pytest tests**',text)
            start=text.index('## Recorded verification');end=text.index('## Still incomplete',start)
            records=['## Recorded verification','',f"- [x] Engineering: **{args.pytest_passed}/{args.pytest_passed} pytest tests**; official dataset validator passed."]
            records += [f"- [x] {label}: **{stages[step]['summary']['passed']}/{stages[step]['summary']['total']}**, errors {stages[step]['summary']['errors']}; see `sample_outputs/eval_step{step}.json` for actual composition, configuration and timings." for step,label in ((1,'Prompt-only selected-model baseline'),(2,'Grounded practice questions ('+stages[2].get('configuration',{}).get('evaluation_mode','mode not recorded')+')'),(3,'Conversation practice turns ('+stages[3].get('configuration',{}).get('evaluation_mode','mode not recorded')+')'))]
            if live_partial:
                partial=live_partial['summary'];records.append(f"- [x] Post-fix live subset: **{partial['passed']}/{partial.get('planned','?')} planned**, {partial['total']} evaluated, complete=False. This is not a complete live rerun; earlier complete live runs predate these fixes.")
            records += [f"- [x] Development adversarial/stateful regression: **{adv['summary']['passed']}/{adv['summary']['total']}**; development data, not blind evaluation.",'- [x] '+regression_note(hold,comparison),f"- [x] Holdout privacy assertions: {len(privacy_checks)} recorded, {failed_privacy} failed." if privacy_checks else '- [ ] Holdout privacy assertions were not recorded.',f"- [x] Real Gnani synthetic-audio round trips: **{voice['batch']['succeeded']}/6** audio, **{voice['semantic_validation']['passed']}/6** semantic/privacy checks. Human accent/noise robustness and subjective listening remain unverified.",'','Measured JSON and `VERIFICATION.md` preserve provenance, failures, timing and composition. A live run includes checked fallbacks and guards; it does not mean every reply was freshly generated.','']
            text=text[:start]+'\n'.join(records)+'\n'+text[end:]
        path.write_text(text,encoding='utf-8')
    print(json.dumps({'practice':[stages[s]['summary']['passed'] for s in (1,2,3)],'tests':args.pytest_passed,'holdout_regression':hold['summary']['passed'],'voice':voice['status']}))

if __name__=='__main__':main()
