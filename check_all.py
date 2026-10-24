"""One command for all local checks; speech is explicitly gated on a real key."""
import argparse,json,subprocess,sys
from pathlib import Path
from src.config import ROOT

def main():
    p=argparse.ArgumentParser();p.add_argument('--live',action='store_true');p.add_argument('--voice',action='store_true');a=p.parse_args()
    commands=[[str(ROOT/'Capstone_Project_Dataset_FTTT_2026/validate_dataset.py')],['-m','pytest','-q'],['eval_step1.py'],['eval_step2.py']+(['--live'] if a.live else []),['eval_step3.py']+(['--live'] if a.live else []),['eval_adversarial.py']]
    if a.voice:commands.append(['generate_voice_samples.py'])
    results=[]
    for cmd in commands:
        result=subprocess.run([sys.executable,'-X','utf8']+cmd,cwd=ROOT);results.append({'command':cmd,'exit_code':result.returncode})
    (ROOT/'sample_outputs/check_all.json').write_text(json.dumps(results,indent=2))
    return 1 if any(x['exit_code'] for x in results) else 0
if __name__=='__main__':raise SystemExit(main())
