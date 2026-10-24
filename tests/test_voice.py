import io,json,wave
from pathlib import Path
import pytest
from src.voice import GnaniVoice,VoiceError,VoiceUnavailable,for_ear

def wav_bytes():
    stream=io.BytesIO()
    with wave.open(stream,'wb') as f:f.setnchannels(1);f.setsampwidth(2);f.setframerate(16000);f.writeframes(b'\0\0'*1600)
    return stream.getvalue()
class Response:
    def __init__(self,status,content=b'',data=None):self.status_code=status;self.content=content;self.data=data
    def json(self):return self.data

def test_gnani_retries_and_rewinds(tmp_path,monkeypatch):
    voice=GnaniVoice('unit-test-placeholder',sleep=lambda _:None);path=tmp_path/'clip.wav';path.write_bytes(wav_bytes());positions=[]
    def post(*args,**kwargs):
        file=kwargs['files']['audio_file'][1];positions.append(file.tell());file.read()
        return Response(429) if len(positions)<3 else Response(200,data={'success':True,'transcript':'refund question'})
    monkeypatch.setattr(voice.session,'post',post)
    assert voice.transcribe(path)=='refund question' and positions==[0,0,0]

def test_bad_tts_never_fakes_audio(tmp_path,monkeypatch):
    voice=GnaniVoice('unit-test-placeholder',sleep=lambda _:None)
    monkeypatch.setattr(voice.session,'post',lambda *a,**k:Response(200,b'not audio'))
    with pytest.raises(VoiceError):voice.synthesize('Hello',tmp_path/'reply.wav')
    assert not (tmp_path/'reply.wav').exists()

def test_valid_tts_wav(tmp_path,monkeypatch):
    voice=GnaniVoice('unit-test-placeholder');observed={}
    def post(*a,**kw):observed.update(kw['json']);return Response(200,wav_bytes())
    monkeypatch.setattr(voice.session,'post',post);voice.synthesize('Hello',tmp_path/'reply.wav')
    assert observed['model']=='timbre-v2.5' and observed['voice']=='Kaveri'
    assert (tmp_path/'reply.wav').is_file()

def test_permanent_403_is_bounded(monkeypatch):
    voice=GnaniVoice('unit-test-placeholder',sleep=lambda _:None);calls=[]
    def post(*a,**k):calls.append(1);return Response(403)
    monkeypatch.setattr(voice.session,'post',post)
    with pytest.raises(VoiceError):voice.synthesize('Hello',Path('unused.wav'))
    assert len(calls)==4

def test_missing_key_explicit(monkeypatch):
    monkeypatch.delenv('GNANI_API_KEY',raising=False)
    with pytest.raises(VoiceUnavailable):GnaniVoice().synthesize('Hello',Path('unused.wav'))

def test_batch_continues_after_bad_clip(tmp_path,monkeypatch):
    from run import run_batch
    class FakeVoice:
        def transcribe(self,path,language):
            if path.name=='bad.wav':raise VoiceError('Invalid clip')
            return 'What is the UPI refund timeline?'
        def synthesize(self,text,path,language):path.write_bytes(wav_bytes())
    folder=tmp_path/'inputs';folder.mkdir();(folder/'bad.wav').write_bytes(b'bad');(folder/'good.wav').write_bytes(wav_bytes())
    result=run_batch(folder,tmp_path/'out',compose=False,voice=FakeVoice())
    assert result['total']==2 and result['succeeded']==1 and result['failed']==1
    assert len(list((tmp_path/'out').glob('*.txt')))==2
    assert len(list((tmp_path/'out').glob('*_sources.json')))==2

def test_voice_formatting():
    text=for_ear('Order 12345678 costs 49 rupees on 24 October 2026.')
    assert '12345678' not in text and 'forty nine rupees' in text and 'two thousand twenty six' in text
