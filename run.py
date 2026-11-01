"""Batch runner: python run.py --audio_dir <in> --out_dir <out>."""
from pathlib import Path
import argparse,json,re,sys,time,os
from src.agent import resources
from src.multilingual import MultilingualAgent as Agent
from src.languages import LANGUAGE_NAMES, STT_CODES, normalize_language
from src.normalize import redact
from src.voice import GnaniVoice,VoiceError,VoiceUnavailable

FORMATS={'.wav','.mp3','.ogg','.flac','.aac','.m4a'}

def run_batch(audio_dir:Path,out_dir:Path,language:str='en-IN',session_mode:str='auto',compose:bool=True,voice=None) -> dict:
    batch_started=time.perf_counter()
    language=normalize_language(language)
    if not audio_dir.is_dir():raise ValueError('Input audio directory does not exist')
    if audio_dir.resolve()==out_dir.resolve():raise ValueError('Input and output directories must differ')
    out_dir.mkdir(parents=True,exist_ok=True); voice=voice or GnaniVoice(); shared=resources(); sessions={}; entries=[]
    # Optional sidecar controls language/session IDs only, never answers or verification outcomes.
    sidecar=audio_dir/'sessions.json'; mapping=json.loads(sidecar.read_text(encoding='utf-8')) if sidecar.exists() else {}
    clips=sorted(p for p in audio_dir.iterdir() if p.is_file() and p.suffix.lower() in FORMATS)
    # Record setup and shared resource initialization once, outside individual clip latency.
    startup_ms=round(1000*(time.perf_counter()-batch_started),2)
    for index,path in enumerate(clips):
        started=time.perf_counter(); name=re.sub(r'[^A-Za-z0-9_.-]','_',path.stem); stem=f'{index+1:03d}_{name}'
        meta=mapping.get(path.name,{})
        sid=meta.get('session_id') or ('shared' if session_mode=='sequential' else path.stem.split('__',1)[0] if session_mode=='auto' and '__' in path.stem else path.name)
        agent=sessions.setdefault(sid,Agent(shared,compose=compose)); entry={'input':path.name,'output_prefix':stem,'session_id':sid,'status':'error'}
        result=None; durations={'stt_ms':0.,'agent_ms':0.,'tts_ms':0.}
        try:
            stage_started=time.perf_counter()
            try:
                selected=normalize_language(meta.get('language',language))
                transcript=voice.transcribe(path,STT_CODES[selected])
            finally:durations['stt_ms']+=1000*(time.perf_counter()-stage_started)
            stage_started=time.perf_counter()
            try:result=agent.respond(transcript) if selected == 'en' else agent.respond(transcript,language_hint=selected)
            finally:durations['agent_ms']+=1000*(time.perf_counter()-stage_started)
            entry['agent_succeeded']=True; entry['decision']=result['decision']
            try:
                stage_started=time.perf_counter()
                try:voice.synthesize(result['answer'],out_dir/(stem+'_reply.wav'),result['language'])
                finally:durations['tts_ms']+=1000*(time.perf_counter()-stage_started)
                entry['status']='ok'; entry['audio']=stem+'_reply.wav'
            except (VoiceError,VoiceUnavailable) as error:
                entry['status']='tts_error'; entry['error']=str(error); result['voice_error']=str(error)
        except (VoiceError,VoiceUnavailable) as error:
            entry['error']=str(error)
            # STT failure still attempts a real spoken recovery through Gnani, if available.
            first_reply=not getattr(getattr(agent,'state',None),'turn',0)
            recovery=("I'm ZentroMart's AI support assistant. " if first_reply else '')+"Sorry, I couldn't understand that audio. Please record a short, clear clip."
            result={'transcript':'','answer':recovery,'intent':'unclear_audio','decision':'clarify','retrieved_chunk_ids':[],'sources':[],'tool_calls':[],'error':str(error)}
            try:
                stage_started=time.perf_counter()
                try:voice.synthesize(result['answer'],out_dir/(stem+'_reply.wav'),'en')
                finally:durations['tts_ms']+=1000*(time.perf_counter()-stage_started)
                entry['audio']=stem+'_reply.wav'
            except (VoiceError,VoiceUnavailable):pass
        except Exception:
            # Sanitize unexpected exceptions: exception text may include request internals or secrets.
            entry['error']='Unexpected clip processing failure; remaining clips continue'
            result={'transcript':'','answer':'Unable to process this clip. Please try again.','intent':'error','decision':'error','retrieved_chunk_ids':[],'sources':[],'tool_calls':[],'error':entry['error']}
        durations={name:round(value,2) for name,value in durations.items()}
        durations['total_ms']=round(1000*(time.perf_counter()-started),2)
        entry.update(durations); entry['latency_ms']=durations['total_ms']
        # Keep the agent's own retrieval/LLM/validation timings intact.
        result['voice_timings']=durations.copy()
        (out_dir/(stem+'.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        (out_dir/(stem+'.txt')).write_text(result['answer'],encoding='utf-8')
        (out_dir/(stem+'_sources.json')).write_text(json.dumps(result.get('sources',[]),ensure_ascii=False,indent=2),encoding='utf-8')
        entries.append(entry)
        (out_dir/'manifest.json').write_text(json.dumps({'total':len(clips),'processed':len(entries),'startup_ms':startup_ms,'batch_wall_ms':round(1000*(time.perf_counter()-batch_started),2),'entries':entries},ensure_ascii=False,indent=2),encoding='utf-8')
    summary={'total':len(clips),'succeeded':sum(e['status']=='ok' for e in entries),'failed':sum(e['status']!='ok' for e in entries),'speech_provider':'Gnani only','startup_ms':startup_ms,'batch_wall_ms':round(1000*(time.perf_counter()-batch_started),2),'entries':entries}
    (out_dir/'manifest.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8');return summary

def main():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--audio_dir',required=True,type=Path);p.add_argument('--out_dir',required=True,type=Path);p.add_argument('--language',default='en-IN',help='Spoken language: '+', '.join(dict.fromkeys(STT_CODES.values()))+'; hi-en uses en-IN speech recognition');p.add_argument('--session_mode',choices=['auto','independent','sequential'],default='auto');group=p.add_mutually_exclusive_group();group.add_argument('--offline-rules',action='store_true');group.add_argument('--hosted',action='store_true',help='Use the explicit Groq answer profile from ignored .env.hosted; speech stays Gnani');a=p.parse_args()
    try:
        if a.hosted:
            from src.app_profile import hosted_environment
            os.environ.update(hosted_environment(Path(__file__).resolve().parent,os.environ))
        result=run_batch(a.audio_dir,a.out_dir,a.language,a.session_mode,not a.offline_rules)
    except (ValueError,OSError) as e:p.error(str(e))
    print(json.dumps({k:v for k,v in result.items() if k!='entries'},indent=2));return 0 if result['total'] and not result['failed'] else 1
if __name__=='__main__':sys.exit(main())
