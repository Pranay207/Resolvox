"""Run the complete live evaluation and preserve each stage's real outcome."""
from datetime import datetime,timezone
from pathlib import Path
import json,subprocess,sys,time

ROOT=Path(__file__).resolve().parents[1]
COMMANDS=[['eval_step2.py','--live'],['eval_step3.py','--live'],
          ['eval_adversarial.py'],['eval_holdout.py','--offline'],
          ['generate_voice_samples.py','--reuse-inputs']]

def main():
    results=[]
    for args in COMMANDS:
        print('Running '+' '.join(args),flush=True)
        start=time.perf_counter()
        result=subprocess.run([sys.executable,'-X','utf8']+args,cwd=ROOT)
        results.append({'command':args,'exit_code':result.returncode,'seconds':round(time.perf_counter()-start,3)})
        (ROOT/'sample_outputs/final_evaluation.json').write_text(json.dumps({
            'recorded_at_utc':datetime.now(timezone.utc).isoformat(),
            'complete':len(results)==len(COMMANDS),'stages':results,
            'note':'Held-out first-pass results are preserved separately. The later holdout run is a regression after fixes.'},indent=2),encoding='utf-8')
    return int(any(r['exit_code'] for r in results))

if __name__=='__main__':raise SystemExit(main())
