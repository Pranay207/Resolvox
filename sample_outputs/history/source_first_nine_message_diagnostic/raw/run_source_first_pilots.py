"""Genuine model diagnostics of inspected development paraphrases, not blind scoring."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,sys,time
ROOT=Path(__file__).resolve().parent.parent;sys.path.insert(0,str(ROOT))
from scripts.resume_live_practice import provenance,fingerprint
from src.agent import Agent,Resources
OUT=ROOT/'tmp/source_first_live_pilots.json'

def save(value):
    temporary=OUT.with_suffix('.json.pending');temporary.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n');temporary.replace(OUT)

def main():
    if OUT.exists():raise ValueError('Preserve prior pilot artifact before another run')
    before=provenance(2)
    cases=[
        ('jurisdiction','Which jurisdictions can you ship purchases to?','en'),
        ('merchant','Does buying from a third-party merchant change the return rules?','en'),
        ('warehouse-clock','After the warehouse inspects a return, when is the money sent?','en'),
        ('door-refusal','May I refuse the package at my doorstep once dispatch has happened?','en'),
        ('unknown-midnight-guarantee','Can you promise to deliver my order at exactly 2 a.m.?','en'),
        ('unknown-student-offer','Do students get an extra reduction in price just for being students?','en'),
        ('hinglish-date','Card refund 17 October 2026 ko shuru hua tha. Aap mere bataye date ke hisaab se last date bata sakte ho?','hi-en'),
    ]
    data={'scope':'Genuine current-model development diagnostics; exposed inspected paraphrases, not independent blind evaluation, organizer score or semantic certification',
          'started_at_utc':datetime.now(timezone.utc).isoformat(),'provenance_start':before,'results':[],'complete':False,'planned_messages':9}
    save(data);resources=Resources()
    for name,question,language in cases:
        assert fingerprint(provenance(2))==fingerprint(before),'runtime changed during diagnostic'
        began=time.perf_counter();answer=Agent(resources=resources,compose=True).respond(question,language)
        data['results'].append({'id':name,'question':question,'prediction':answer,'wall_seconds':round(time.perf_counter()-began,3),'assistant_source_review':'pending'})
        save(data);print(name,answer['decision'],answer['composition'],flush=True)
    agent=Agent(resources=resources,compose=True)
    for index,question in enumerate(('What is the deadline for returning my purchase?','Electronics'),1):
        began=time.perf_counter();answer=agent.respond(question,'en')
        data['results'].append({'id':'workflow-category-'+str(index),'question':question,'prediction':answer,'wall_seconds':round(time.perf_counter()-began,3),'assistant_source_review':'pending'})
        save(data);print('workflow-category-'+str(index),answer['decision'],answer['composition'],flush=True)
    after=provenance(2);assert fingerprint(after)==fingerprint(before)
    data.update(provenance_finish=after,source_runtime_unchanged=True,complete=True,finished_at_utc=datetime.now(timezone.utc).isoformat())
    save(data)

if __name__=='__main__':main()
