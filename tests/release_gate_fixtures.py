"""Synthetic offline evidence builders; never predictions for a real evaluation."""
import copy, csv, hashlib, json
from pathlib import Path
from scripts import release_evidence as evidence

def write(root, file, value):
    path = root/'sample_outputs'/file; path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding='utf-8')

def bind_complete_sequence(root):
    root = Path(root)
    for name in (*evidence.DRIVERS, 'src/rule_bindings.json', 'tests/adversarial_cases.json', 'tests/holdout_cases.json'):
        path = root/name; path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():path.write_text('# synthetic test input ' + name, encoding='utf-8')
    dataset=root/'Capstone_Project_Dataset_FTTT_2026'
    for name in ('kb/current.md', 'tools/tools.py', 'data/records.csv'):
        path=dataset/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text('synthetic input',encoding='utf-8')
    (dataset/'practice').mkdir()
    with (dataset/'practice/questions.csv').open('w',newline='',encoding='utf-8') as handle:
        writer=csv.DictWriter(handle,fieldnames=['id','question']);writer.writeheader()
        writer.writerows({'id':str(index),'question':'Synthetic public query'} for index in range(52))
    with (dataset/'practice/conversations.csv').open('w',newline='',encoding='utf-8') as handle:
        writer=csv.DictWriter(handle,fieldnames=['conversation_id','turn','customer_message']);writer.writeheader()
        writer.writerows({'conversation_id':'session','turn':str(index),'customer_message':'Synthetic turn'} for index in range(96))
    frozen=evidence.snapshot(root)
    prefix=dataset.relative_to(root).as_posix()+'/'
    inputs={name[len(prefix):]:digest for name,digest in frozen['dataset_source_sha256'].items()}
    runtime=dict(frozen['runtime_source_sha256']);runtime['scripts/resume_live_practice.py']=frozen['driver_source_sha256']['scripts/resume_live_practice.py']
    inference={key:val for key,val in frozen['inference'].items() if key!='GNANI_TTS_MODEL'}
    for step,total in ((1,52),(2,52),(3,96)):
        mode='live_prompt_only' if step==1 else 'live_compose_true'
        prov={'step':step,'evaluation_mode':mode,'runtime_source_sha256':runtime,'dataset_sha256':inputs,'inference':inference}
        data={'configuration':{'evaluation_mode':mode,'provenance':copy.deepcopy(prov),'inference_fingerprint':hashlib.sha256(json.dumps(prov,sort_keys=True,separators=(',',':')).encode()).hexdigest()},
              'complete':True,'summary':{'planned':total,'total':total,'passed':0 if step==1 else total,'failed':total if step==1 else 0,'errors':0,'complete':True},
              'results':[{'id':str(index) if step in (1,2) else 'session.'+str(index),'prediction':{'mode':'prompt_only' if step==1 else 'grounded_llm','answer':'Synthetic fixture response','sources':[],'tool_calls':[]}} for index in range(total)]}
        write(root,f'eval_step{step}_live_current.json',data)
    for name,total,key,mode in (('adversarial',77,'total','live_compose_true'),('holdout',91,'evaluated','llm_compose_true')):
        write(root,evidence.STAGES[name],{'mode':mode,'summary':{'planned':total,key:total,'passed':total,'failed':0,'complete':True},'results':[{'id':str(index)} for index in range(total)]})
    voice=evidence.read(root/'sample_outputs/voice_validation.json');voice.setdefault('batch',{}).update(total=6,entries=[{} for _ in range(6)])
    write(root,evidence.STAGES['voice'],voice)
    write(root,evidence.STAGES['silence'],{'status':'tested','complete':True,'speech_provider':'Gnani only','summary':{'planned':1,'evaluated':1,'passed':1,'failed':0},'assessment':{'passed':True}})
    receipt={'complete':True,'all_frozen_inputs_unchanged':True,'snapshot_started':copy.deepcopy(frozen),'snapshot_finished':copy.deepcopy(frozen),'stages':[]}
    for name,file in evidence.STAGES.items():
        receipt['stages'].append({'stage':name,'exit_code':0,'execution_complete':True,'all_frozen_inputs_unchanged':True,'stopped_for_input_change':False,
            'snapshot_started':copy.deepcopy(frozen),'snapshot_finished':copy.deepcopy(frozen),'artifact':{'path':'sample_outputs/'+file,'sha256':evidence.sha(root/'sample_outputs'/file)}})
    write(root,'live_sequence_receipt.json',receipt)
    return frozen
