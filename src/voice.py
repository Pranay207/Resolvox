"""Gnani-only REST speech, explicit served model, bounded retries, validated WAV."""
from pathlib import Path
import os,re,time,wave
import requests
from .config import ROOT

class VoiceUnavailable(RuntimeError): pass
class VoiceError(RuntimeError): pass

UNITS=['zero','one','two','three','four','five','six','seven','eight','nine','ten','eleven','twelve','thirteen','fourteen','fifteen','sixteen','seventeen','eighteen','nineteen']
TENS=['','','twenty','thirty','forty','fifty','sixty','seventy','eighty','ninety']
def spoken_number(n:int) -> str:
    if n<20:return UNITS[n]
    if n<100:return TENS[n//10]+(' '+UNITS[n%10] if n%10 else '')
    if n<1000:return UNITS[n//100]+' hundred'+(' '+spoken_number(n%100) if n%100 else '')
    for scale,name in [(10000000,'crore'),(100000,'lakh'),(1000,'thousand')]:
        if n>=scale:return spoken_number(n//scale)+' '+name+(' '+spoken_number(n%scale) if n%scale else '')
    return str(n)

def for_ear(text:str,language:str='en') -> str:
    text=re.sub(r'[*_`#]','',text)
    text=re.sub(r'\b(\d{4})(\d{4})\b',lambda m:' '.join(UNITS[int(c)] for c in m[1])+', '+' '.join(UNITS[int(c)] for c in m[2]),text)
    text=re.sub(r'\b(\d{1,2}) ([A-Z][a-z]+) (2026)\b',lambda m:spoken_number(int(m[1]))+' '+m[2]+' two thousand twenty six',text)
    if language=='en':
        text=re.sub(r'(?:₹\s*)?(\d[\d,]*)\s*(rupees?|INR)',lambda m:spoken_number(int(m[1].replace(',','')))+' rupees',text,flags=re.I)
        text=re.sub(r'\b\d{1,5}\b',lambda m:spoken_number(int(m[0])),text)
    return re.sub(r'\s+',' ',text).strip()

class GnaniVoice:
    BASE='https://api.vachana.ai'
    def __init__(self,key:str|None=None,sleep=time.sleep):
        self.key=key or os.getenv('GNANI_API_KEY',''); self.sleep=sleep; self.session=requests.Session()
    def _request(self,path:str,**kwargs) -> requests.Response:
        if not self.key: raise VoiceUnavailable('GNANI_API_KEY is missing. Add your own key to .env; no alternate speech service is used.')
        last=None
        for attempt in range(4):
            try:
                # Rewind multipart files for every retry.
                for value in kwargs.get('files',{}).values():
                    handle=value[1] if isinstance(value,tuple) else value
                    if hasattr(handle,'seek'):handle.seek(0)
                response=self.session.post(self.BASE+path,headers={'X-API-Key-ID':self.key},timeout=(15,90),**kwargs)
                if response.status_code in {403,429,500,502,503,504}:
                    last=response.status_code
                    if attempt<3:self.sleep(min(2**attempt,8));continue
                if response.status_code!=200:raise VoiceError(f'Gnani request failed with HTTP {response.status_code}; check key, credits, format, and limits.')
                return response
            except requests.RequestException:
                if attempt==3:raise VoiceError('Gnani network request failed after bounded retries') from None
                self.sleep(2**attempt)
        raise VoiceError(f'Gnani retry limit reached (HTTP {last})')
    def transcribe(self,path:Path,language:str='en-IN') -> str:
        if not path.exists() or path.stat().st_size==0:raise VoiceError('Empty or missing audio file')
        if path.suffix.lower()=='.wav':
            try:
                with wave.open(str(path),'rb') as f:
                    if f.getnframes()/f.getframerate()>60:raise VoiceError('STT clip exceeds the 60-second REST limit')
            except (wave.Error,EOFError):raise VoiceError('Invalid WAV file') from None
        with path.open('rb') as f:
            response=self._request('/stt/v3',files={'audio_file':(path.name,f)},data={'language_code':language,'format':'transcribe'})
        try:
            data=response.json()
            if data.get('success') is False:raise VoiceError('Gnani transcription reported failure')
            return str(data['transcript']).strip()
        except (ValueError,KeyError):raise VoiceError('Gnani returned an invalid transcription response') from None
    def synthesize(self,text:str,path:Path,language:str='en') -> None:
        lang={'en':'en-IN','hi':'hi-IN','hi-en':'hi-en'}.get(language,language)
        voice={'en-IN':'Kaveri','hi-IN':'Nalini','hi-en':'Poorvi'}.get(lang,'Kaveri')
        payload={'text':for_ear(text,language),'voice':voice,'language':lang,'model':os.getenv('GNANI_TTS_MODEL','timbre-v2.5'),'speed':1.0,'audio_config':{'encoding':'linear_pcm','container':'wav','sample_rate':48000,'sample_width':2,'num_channels':1}}
        response=self._request('/api/v1/tts/inference',json=payload)
        content=response.content
        if content[:4]!=b'RIFF' or content[8:12]!=b'WAVE':raise VoiceError('Gnani TTS did not return a WAV; output not fabricated')
        path.parent.mkdir(parents=True,exist_ok=True); temporary=path.with_suffix('.part'); temporary.write_bytes(content)
        try:
            with wave.open(str(temporary),'rb') as f:
                if f.getnframes()==0:raise VoiceError('Gnani returned empty speech')
        except wave.Error:temporary.unlink(missing_ok=True);raise VoiceError('Invalid synthesized WAV') from None
        temporary.replace(path)
