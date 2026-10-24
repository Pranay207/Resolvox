"""Generate five+ actual Gnani test clips and execute the real batch; no fake speech."""
import json,sys
from pathlib import Path
from src.config import ROOT
from src.voice import GnaniVoice,VoiceError,VoiceUnavailable
from run import run_batch
SAMPLES=[('01_en.wav','How long does a UPI refund take?','en'),('02_hi.wav','मेरा सामान खराब आया है, अब क्या करूँ?','hi'),('03_hinglish.wav','Mera net banking refund kab aayega?','hi-en'),('04_identity__01.wav','My order number is eight nine seven eight two eight three seven.','en'),('04_identity__02.wav','The last four digits are zero zero zero zero.','en'),('04_identity__03.wav','The last four digits are zero zero zero zero.','en')]
def main():
    folder=ROOT/'sample_outputs/voice_inputs';folder.mkdir(parents=True,exist_ok=True);voice=GnaniVoice();status=ROOT/'sample_outputs/voice_validation.json'
    try:
        mapping={}
        for name,text,lang in SAMPLES:
            voice.synthesize(text,folder/name,lang); mapping[name]={'language':'hi-IN' if lang=='hi' else 'en-IN'}
        (folder/'sessions.json').write_text(json.dumps(mapping,indent=2))
        result=run_batch(folder,ROOT/'sample_outputs/voice',compose=False,voice=voice)
        status.write_text(json.dumps({'status':'tested','synthetic_input':'Gnani TTS-generated; not human recordings','batch':result},indent=2),encoding='utf-8');return 0 if not result['failed'] else 1
    except (VoiceUnavailable,VoiceError) as error:
        status.write_text(json.dumps({'status':'blocked','reason':str(error),'clips_generated':len(list(folder.glob('*.wav'))),'required':'Participant-owned GNANI_API_KEY in .env','no_substitute_speech':True},indent=2),encoding='utf-8');print(str(error));return 2
if __name__=='__main__':sys.exit(main())
