"""Six real Gnani round trips with semantic checks; synthetic audio, not human recordings."""
import argparse,hashlib,io,json,re,sys,wave
from pathlib import Path
from datetime import datetime, timezone
from src.config import ROOT
from src.voice import GnaniVoice,VoiceError,VoiceUnavailable,canonical_wav
from src.normalize import order_id,proof_value
from run import run_batch
SAMPLES=[('01_en.wav','How long does a UPI refund take?','en'),('02_hi.wav','मेरा सामान खराब आया है, अब क्या करूँ?','hi'),('03_hinglish.wav','Mera net banking refund kab aayega?','hi-en'),('04_identity__01.wav','My order number is eight nine seven eight two eight three seven.','en'),('04_identity__02.wav','The last four digits are zero zero zero zero.','en'),('04_identity__03.wav','The last four digits are zero zero zero zero.','en')]

class ObservedVoice:
    """Keep only boolean recognition checks; verification audio text is never logged."""
    def __init__(self,delegate):self.delegate=delegate;self.observed={}
    def transcribe(self,path,language):
        text=self.delegate.transcribe(path,language)
        if path.name=='01_en.wav':ok=bool(re.search(r'u\s*p\s*i|यूपीआई',text,re.I))
        elif path.name=='02_hi.wav':ok=bool(re.search(r'खराब|टूट|ख़राब|bad|damage',text,re.I))
        elif path.name=='03_hinglish.wav':ok=bool(re.search(r'net\s*bank|नेट\s*बैंक',text,re.I))
        elif path.name=='04_identity__01.wav':ok=order_id(text)=='89782837'
        else:ok=proof_value(text)=='0000'
        self.observed[path.name]=ok
        return text
    def synthesize(self,*args,**kwargs):return self.delegate.synthesize(*args,**kwargs)

def validate(result,folder,observed):
    checks=[]
    expected={name for name,_,_ in SAMPLES};actual={x['input'] for x in result['entries']}
    if actual!=expected or len(result['entries'])!=len(SAMPLES):return {'passed':0,'failed':1,'checks':[{'case':'exact_input_set','passed':False}]}
    for entry in result['entries']:
        name=entry['input'];prediction=json.loads((folder/(entry['output_prefix']+'.json')).read_text(encoding='utf-8'))
        ids=prediction.get('retrieved_chunk_ids',[]);answer=prediction.get('answer','');verified=prediction.get('verified',False)
        if name=='01_en.wav':semantic=prediction['decision']=='answer' and prediction['intent']=='refund' and 'REF-2' in ids and '1 to 3' in answer
        elif name=='02_hi.wav':semantic=prediction['decision']=='answer' and prediction['intent']=='damage' and 'DWM-1' in ids and '48' in answer and prediction['language']=='hi'
        elif name=='03_hinglish.wav':semantic=prediction['decision']=='answer' and prediction['intent']=='refund' and 'REF-2' in ids and bool(re.search(r'3\s*(?:to|से)\s*5',answer))
        elif name=='04_identity__01.wav':semantic=prediction['decision']=='clarify' and prediction['intent']=='verification' and not verified and any(t['name']=='lookup_order' and t['arguments']['order_id']=='89782837' for t in prediction['tool_calls'])
        elif name=='04_identity__02.wav':semantic=prediction['decision']=='clarify' and prediction['intent']=='verification' and not verified
        else:semantic=prediction['decision']=='refuse' and prediction['intent']=='verification' and not verified
        privacy=not name.startswith('04_identity__0') or name.endswith('01.wav') or (prediction['transcript']=='[verification value redacted]' and all(t['arguments'].get('verification_value') in {None,'[REDACTED]'} for t in prediction['tool_calls']))
        duration=0.;speech=False
        if entry.get('audio'):
            with wave.open(str(folder/entry['audio']),'rb') as f:
                duration=f.getnframes()/f.getframerate();pcm=f.readframes(f.getnframes());speech=duration>0 and any(pcm)
        check={'case':name,'input_understood':observed.get(name,False),'semantic_ok':bool(semantic),'privacy_ok':privacy,'speech_nonempty':speech,'reply_seconds':round(duration,3),'decision':prediction['decision']}
        check['passed']=entry['status']=='ok' and all(check[k] for k in ['input_understood','semantic_ok','privacy_ok','speech_nonempty']);checks.append(check)
    return {'passed':sum(c['passed'] for c in checks),'failed':sum(not c['passed'] for c in checks),'checks':checks}

def runtime_source_hashes(root=ROOT):
    """Snapshot actual public runtime code, never environment or secret values."""
    root = Path(root)
    files = sorted((root / 'src').glob('*.py')) + [root / 'src/rule_bindings.json']
    return {str(path.relative_to(root)).replace('\\', '/'): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in files if path.is_file()}


def finish_runtime_provenance(initial, started_at, compose, root=ROOT):
    final = runtime_source_hashes(root)
    return {'started_at_utc': started_at,
            'finished_at_utc': datetime.now(timezone.utc).isoformat(),
            'runtime_source_sha256': initial,
            'runtime_source_sha256_finished': final,
            'source_runtime_unchanged': initial == final,
            'live_llm_composition_enabled': bool(compose)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--reuse-inputs', action='store_true', help='Reuse the six previously generated Gnani test files; only repair container lengths, never speech.')
    parser.add_argument('--offline-rules', action='store_true', help='Disable live LLM composition, matching the batch CLI opt-out.')
    args = parser.parse_args()
    compose = not args.offline_rules
    started_at = datetime.now(timezone.utc).isoformat()
    initial_runtime = runtime_source_hashes(ROOT)
    folder = ROOT / 'sample_outputs/voice_inputs'
    folder.mkdir(parents=True, exist_ok=True)
    status = ROOT / 'sample_outputs/voice_validation.json'
    output = ROOT / 'sample_outputs/voice'
    try:
        voice = GnaniVoice()
        names = {name for name, _, _ in SAMPLES}
        mapping, input_provenance = {}, []
        extras = [path.name for path in folder.iterdir() if path.is_file()
                  and path.suffix.lower() in {'.wav', '.mp3', '.m4a', '.ogg', '.flac', '.aac'}
                  and path.name not in names]
        if extras:
            raise VoiceError('Unexpected audio in test-input folder; use exactly the generated six files')
        for name, text, lang in SAMPLES:
            path = folder / name
            if args.reuse_inputs and path.exists():
                path.write_bytes(canonical_wav(path.read_bytes()))
            else:
                voice.synthesize(text, path, lang)
            mapping[name] = {'language': 'hi-IN' if lang == 'hi' else 'en-IN'}
            input_provenance.append({'file': name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'origin': 'Gnani TTS'})
        (folder / 'sessions.json').write_text(json.dumps(mapping, indent=2), encoding='utf-8')
        observer = ObservedVoice(voice)
        result = run_batch(folder, output, compose=compose, voice=observer)
        semantic = validate(result, output, observer.observed)
        provenance = finish_runtime_provenance(initial_runtime, started_at, compose, ROOT)
        passed = result['failed'] == 0 and semantic['failed'] == 0 and provenance['source_runtime_unchanged']
        run_status = 'tested' if passed else ('failed' if provenance['source_runtime_unchanged'] else 'invalid_runtime_changed')
        # This is the actual just-returned batch, never a previously saved run.
        # Stamp the same start/end snapshot into the fresh manifest and record.
        result.update(provenance)
        output.mkdir(parents=True, exist_ok=True)
        (output / 'manifest.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        record = {'status': run_status,
                  'synthetic_input': 'Gnani TTS-generated; not human recordings',
                  'scope': 'Synthetic Gnani TTS -> Gnani STT -> same support agent -> Gnani TTS; human speech robustness and subjective listening remain unverified',
                  'input_provenance': input_provenance, 'semantic_validation': semantic,
                  'batch': result, **provenance}
        status.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps({'status': record['status'], 'audio_succeeded': result['succeeded'],
                          'audio_failed': result['failed'], 'semantic_passed': semantic['passed'],
                          'semantic_failed': semantic['failed'],
                          'source_runtime_unchanged': provenance['source_runtime_unchanged']}, indent=2))
        return 0 if passed else 1
    except (VoiceUnavailable, VoiceError) as error:
        provenance = finish_runtime_provenance(initial_runtime, started_at, compose, ROOT)
        record = {'status': 'blocked', 'reason': str(error),
                  'clips_generated': len(list(folder.glob('*.wav'))),
                  'required': 'Participant-owned GNANI_API_KEY in .env',
                  'no_substitute_speech': True, **provenance}
        status.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
        # Record the blocked attempt without copying/relabeling old manifest
        # entries. No batch completion or successful transcription is inferred.
        output.mkdir(parents=True, exist_ok=True)
        (output / 'manifest.json').write_text(json.dumps(
            {'status': 'blocked', 'reason': str(error), 'entries': [], **provenance},
            ensure_ascii=False, indent=2), encoding='utf-8')
        print(str(error))
        return 2


if __name__ == '__main__':
    sys.exit(main())
