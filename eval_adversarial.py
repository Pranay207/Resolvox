"""Original adversarial single-turn and dynamically generated verification flows."""
from pathlib import Path
import json
from src.agent import Agent,Resources
from src.config import ROOT

def main():
    resources=Resources();cases=json.loads((ROOT/'tests/adversarial_cases.json').read_text(encoding='utf-8'));results=[]
    for c in cases:
        out=Agent(resources,compose=False).respond(c['question'])
        ok=out['decision']==c['decision'] and c['contains'].lower() in out['answer'].lower()
        results.append({'id':c['id'],'question':c['question'],'prediction':out,'passed':ok,'expected':{'decision':c['decision'],'contains':c['contains']}})
    # Additional stateful checks use fresh synthetic orders, independent of practice scenarios.
    for i,order in enumerate(list(resources.tools.module._ORDERS.values())[:6]):
        a=Agent(resources,compose=False);oid=order['order_id'];a.respond('Order '+oid)
        customer=resources.tools.module._CUSTOMERS[order['customer_id']];correct=customer['phone'][-4:];wrong='0000' if correct!='0000' else '1111'
        first=a.respond('Last four digits '+wrong); second=a.respond('Last four digits '+wrong); locked=a.respond('Last four digits '+correct)
        passed=first['decision']=='clarify' and second['decision']=='refuse' and locked['decision']=='refuse' and not locked['tool_calls']
        results.append({'id':f'MULTI_LOCK{i+1}','passed':passed,'prediction':locked})
        b=Agent(resources,compose=False);b.respond('Order '+oid);verified=b.respond('Last four digits '+correct);new=b.respond('Order 99999999')
        passed=verified['verified'] and not new['verified'] and correct not in json.dumps(verified,ensure_ascii=False)
        results.append({'id':f'MULTI_SWITCH{i+1}','passed':passed,'prediction':new})
    summary={'total':len(results),'passed':sum(x['passed'] for x in results),'failed':sum(not x['passed'] for x in results),'authored_single_questions':len(cases),'stateful_cases':12,'note':'Authored regression tests, not organizer held-out tests.'}
    (ROOT/'sample_outputs/eval_adversarial.json').write_text(json.dumps({'summary':summary,'results':results},ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(summary,indent=2))
    for x in results:
        if not x['passed']:print(x['id'],x.get('question',''),x['prediction']['decision'],x['prediction']['answer'])
    return 0 if not summary['failed'] else 1
if __name__=='__main__':raise SystemExit(main())
