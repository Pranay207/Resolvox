"""Three primary-language real Gnani round trips; synthetic inputs only."""
import argparse
from pathlib import Path
import sys,json,hashlib,datetime,shutil,wave,re,os
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
parser=argparse.ArgumentParser();parser.add_argument('--hosted',action='store_true',help='Use the explicit Groq application profile; Gnani remains the only speech provider.');parser.add_argument('--samples',nargs='+',choices=['01_en.wav','02_hi.wav','03_hinglish.wav']);parser.add_argument('--manifest',default='sample_outputs/targeted_voice_validation.json');args=parser.parse_args()
if args.hosted:
 from src.app_profile import hosted_environment
 os.environ.update(hosted_environment(ROOT,os.environ))
from src.voice import GnaniVoice,canonical_wav
from src.grounding import _numeric_text
from generate_voice_samples import SAMPLES,ObservedVoice,runtime_source_hashes
from run import run_batch
samples=[row for row in SAMPLES[:3] if args.samples is None or row[0] in args.samples]
stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ');started=runtime_source_hashes(ROOT)
inputs=ROOT/'tmp'/('targeted_voice_inputs_'+stamp);inputs.mkdir()
output=ROOT/'sample_outputs'/('targeted_voice_'+stamp);output.mkdir()
record={'status':'running','scope':str(len(samples))+' selected synthetic Gnani TTS inputs -> Gnani STT -> selected support agent -> Gnani TTS. Not human speech or a listening/noise study.','inference_profile':'hosted_application' if args.hosted else 'local_ollama','speech_provider':'Gnani only','live_llm_composition_enabled':True,'runtime_source_sha256':started,'started_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'input_provenance':[]}
path=ROOT/args.manifest
def save():path.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
save()
try:
 voice=GnaniVoice();mapping={}
 for name,text,language in samples:
  dest=inputs/name;existing=ROOT/'sample_outputs/voice_inputs'/name
  if existing.exists():dest.write_bytes(canonical_wav(existing.read_bytes()))
  else:voice.synthesize(text,dest,language)
  mapping[name]={'language':language}
  record['input_provenance'].append({'file':name,'sha256':hashlib.sha256(dest.read_bytes()).hexdigest(),'origin':'Gnani TTS-generated synthetic input'})
 (inputs/'sessions.json').write_text(json.dumps(mapping),encoding='utf-8');observer=ObservedVoice(voice)
 result=run_batch(inputs,output,compose=True,voice=observer);checks=[]
 for entry in result['entries']:
  prediction=json.loads((output/(entry['output_prefix']+'.json')).read_text(encoding='utf-8'));answer=_numeric_text(prediction.get('answer',''));ids=prediction.get('retrieved_chunk_ids',[]);name=entry['input'];language=mapping[name]['language']
  if name=='01_en.wav':semantic=prediction['decision']=='answer' and 'REF-2' in ids and bool(re.search(r'1\s*(?:to|[-–])\s*3',answer))
  elif name=='02_hi.wav':semantic=prediction['decision']=='answer' and 'DWM-1' in ids and '48' in answer and bool(re.search(r'photo|फोटो|तस्वीर',answer,re.I))
  else:semantic=prediction['decision']=='answer' and 'REF-2' in ids and bool(re.search(r'3\s*(?:to|se|से|[-–])\s*5',answer))
  audio=False;seconds=0
  if entry.get('audio'):
   with wave.open(str(output/entry['audio']),'rb') as f:seconds=f.getnframes()/f.getframerate();audio=seconds>0 and any(f.readframes(f.getnframes()))
  check={'case':name,'language':language,'actual_output_language':prediction.get('language'),'input_understood':observer.observed.get(name,False),'semantic_ok':bool(semantic),'speech_nonempty':audio,'reply_seconds':round(seconds,3)}
  check['passed']=entry['status']=='ok' and check['input_understood'] and check['semantic_ok'] and audio and prediction.get('language')==language
  checks.append(check)
 record.update(batch=result,semantic_validation={'passed':sum(c['passed'] for c in checks),'failed':sum(not c['passed'] for c in checks),'checks':checks})
 record['status']='tested' if result['failed']==0 and all(c['passed'] for c in checks) and len(checks)==len(samples) else 'failed'
except Exception as e:
 record.update(status='blocked',error_type=type(e).__name__,reason='Speech verification did not complete; no substitute provider was used.',no_substitute_speech=True)
finally:
 record.update(finished_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),runtime_source_sha256_finished=runtime_source_hashes(ROOT))
 record['source_runtime_unchanged']=started==record['runtime_source_sha256_finished']
 record['artifacts']={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in output.iterdir() if p.is_file()}
 save();print(json.dumps({'status':record['status'],'batch':{k:record.get('batch',{}).get(k) for k in ('total','succeeded','failed')},'semantic':record.get('semantic_validation',{}),'source_runtime_unchanged':record['source_runtime_unchanged']},ensure_ascii=True),flush=True)
raise SystemExit(0 if record['status']=='tested' and record['source_runtime_unchanged'] else 1)
