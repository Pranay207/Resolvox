"""Rescore unchanged raw predictions after number-format normalization.

No generation is rerun and no gold answers/decisions or source rules change.
Original checks remain in separate files and on any changed result rows.
"""
from pathlib import Path
import json,sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.evals import rows,score,save

def main():
    for step in (1,2,3):
        path=ROOT/'sample_outputs'/f'eval_step{step}.json'
        data=json.loads(path.read_text(encoding='utf-8'))
        raw=path.with_name(path.stem+'_raw_scoring.json')
        if not raw.exists():raw.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
        gold=rows('conversations.csv' if step==3 else 'questions.csv')
        by_id={(r['conversation_id']+'.'+r['turn'] if step==3 else r['id']):r for r in gold}
        changes=[]
        for row in data['results']:
            checks=score(by_id[row['id']],row['prediction'],step==3)
            if checks!=row['checks']:
                row.setdefault('checks_before_number_normalization',row['checks'])
                changes.append(row['id']);row['checks']=checks
        result=save(path,data['results'],str(step))
        final=json.loads(path.read_text(encoding='utf-8'))
        final['rescoring']={'reason':'Equivalent number words and digits are canonicalized. Gold expectations and raw predictions are unchanged.','changed_check_ids':changes,'raw_scoring_file':raw.name,'original_configuration':data.get('configuration',{})}
        path.write_text(json.dumps(final,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps({'step':step,'passed':result['passed'],'total':result['total'],'changed_check_ids':changes}),flush=True)

if __name__=='__main__':main()
