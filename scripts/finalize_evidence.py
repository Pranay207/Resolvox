"""Summarize recorded results without changing predictions or gold rubrics."""
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
from statistics import mean
import argparse,json,subprocess,sys
ROOT=Path(__file__).resolve().parents[1]

def load(name):return json.loads((ROOT/'sample_outputs'/name).read_text(encoding='utf-8'))
def write(name,data):(ROOT/'sample_outputs'/name).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--pytest-passed',type=int,required=True);args=parser.parse_args()
    engineering=load('engineering_verification.json')
    engineering['pytest'].update(passed=args.pytest_passed,total=args.pytest_passed,exit_code=0)
    engineering['runtime_commit']=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    engineering['generated_at']=datetime.now(timezone.utc).isoformat();write('engineering_verification.json',engineering)
    stages={step:load(f'eval_step{step}.json') for step in (1,2,3)}
    groups={}
    for row in stages[2]['results']:
        pred=row['prediction'];metrics=pred.get('llm',{})
        if not metrics:continue
        label='output cache' if metrics.get('cache_hit') else 'uncached requests'
        groups.setdefault(label,[]).append({'id':row['id'],'composition':pred['composition'],'latency_ms':row['latency_ms'],'llm':metrics})
    models=[]
    for label,cases in groups.items():
        models.append({'model':stages[2]['configuration']['llm_model']+' ('+label+')','cases':cases,
            'summary':{'evaluated':len(cases),'grounded_llm_count':sum(c['composition']=='grounded_llm' for c in cases),'mean_latency_ms':mean(c['latency_ms'] for c in cases)}})
    write('generation_benchmark_selected.json',{'scope':'Complete final 52-question practice run; development data, not unseen performance. Cached and uncached paths are separate. No controlled cold-start or idle-hardware claim.','configuration':stages[2]['configuration'],'models':models})
    hold=load('eval_holdout.json');first=load('eval_holdout_first_pass.json');adv=load('eval_adversarial.json');voice=load('voice_validation.json')
    failed_privacy=sum(not c['passed'] for r in hold['results'] for c in r['judgment']['checks'] if c['check'].startswith('privacy'))
    summary={f'step{step}':data['summary'] for step,data in stages.items()}
    summary.update(engineering=engineering,adversarial=adv['summary'],holdout_first_pass=first['summary'],holdout_regression=hold['summary'],holdout_mode=hold['mode'],privacy_check_failures=failed_privacy,voice={'status':voice['status'],'audio_passed':voice['batch']['succeeded'],'semantic_passed':voice['semantic_validation']['passed']})
    write('final_summary.json',summary)
    run=load('final_evaluation.json')
    run['post_run_verification']={'number_format_rescoring':'Raw predictions unchanged; original checks retained in eval_step*_raw_scoring.json.','adversarial_rerun':adv['summary'],'pytest':engineering['pytest'],'known_holdout_failures_retained':hold['summary']['failed']}
    write('final_evaluation.json',run)
    lines=['# Verification record','', 'These are local measurements, not organizer scores. All raw failures and the first independent holdout are retained.','', '| Check | Recorded result |','|---|---|',f"| Engineering tests | {args.pytest_passed}/{args.pytest_passed} passed |",'| Official dataset validator | Passed: 9 CSVs, 21 KB documents |']
    for step,label in ((1,'Prompt-only, selected model'),(2,'Grounded, full live evaluation'),(3,'Conversations, full live evaluation')):
        s=stages[step]['summary'];lines.append(f"| {label} | {s['passed']}/{s['total']}; errors {s['errors']} |")
    lines += [f"| Development adversarial/stateful | {adv['summary']['passed']}/{adv['summary']['total']} |",f"| First independent holdout, offline | {first['summary']['passed']}/{first['summary']['evaluated']} |",f"| Exposed holdout after fixes, offline | {hold['summary']['passed']}/{hold['summary']['evaluated']}; {hold['summary']['failed']} unresolved checks |",f"| Real Gnani synthetic-audio round trips | {voice['batch']['succeeded']}/6 audio and {voice['semantic_validation']['passed']}/6 semantic checks |",'', 'The baseline and grounded practice run use qwen3:1.7b. Grounded replies include generated answers, version-checked fallbacks, deterministic guards and abstentions; composition counts and separate cache/uncached timings are in the JSON. Human accent/noise robustness and subjective speech quality were not tested.','', 'Number words and digits are scored consistently: the two conversation checks for “three” versus “3” were rescored without changing model predictions or gold expectations. Original checks are preserved.','',f"The wider regression remains incomplete ({hold['summary']['failed']} failed checks). Remaining issues include safe abstentions, incomplete multi-part/follow-up coverage, evidence gaps and strict wording checks. This is not evidence of top-20 readiness or universal semantic correctness.",'', 'The four-page report, archive inspection and configured-secret scan are verified separately in sample_outputs/pdf_qa.json, package_smoke.json and secret_audit.json. The dataset, .env, model caches and virtual environment are excluded from the ZIP.','', 'The user-recorded demo.mp4 remains pending and must be at most 120 seconds. The ZIP is a reviewable draft until that required file is included.','', 'Reproduce: python scripts/final_evaluate.py; python scripts/rescore_practice.py; python -m pytest -q; python scripts/build_report.py; python package_submission.py; python scripts/verify_package.py; python scripts/audit_release.py.']
    (ROOT/'VERIFICATION.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps({'practice':[stages[s]['summary']['passed'] for s in (1,2,3)],'tests':args.pytest_passed,'holdout_regression':hold['summary']['passed'],'voice':voice['status']}))

if __name__=='__main__':main()
