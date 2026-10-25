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
    recovery=json.loads(next((tmp_path/'out').glob('*_bad.json')).read_text())
    assert recovery['answer'].startswith("I'm ZentroMart's AI support assistant.")
    assert recovery['decision']=='clarify' and not recovery['tool_calls']

def test_voice_formatting():
    text=for_ear('Order 12345678 costs 49 rupees on 24 October 2026.')
    assert '12345678' not in text and 'forty nine rupees' in text and 'two thousand twenty six' in text


def test_streaming_wav_header_finalized_without_altering_pcm(tmp_path,monkeypatch):
    import struct
    from src.voice import canonical_wav
    raw=bytearray(wav_bytes());struct.pack_into('<I',raw,4,0xffffffff);struct.pack_into('<I',raw,40,0xffffffff)
    fixed=canonical_wav(bytes(raw))
    assert fixed[44:]==wav_bytes()[44:]
    with wave.open(io.BytesIO(fixed),'rb') as f:assert f.getnframes()==1600 and f.getframerate()==16000
    voice=GnaniVoice('unit-test-placeholder');monkeypatch.setattr(voice.session,'post',lambda *a,**k:Response(200,bytes(raw)))
    voice.synthesize('Hello',tmp_path/'finite.wav')
    with wave.open(str(tmp_path/'finite.wav'),'rb') as f:assert f.getnframes()/f.getframerate()==.1

def test_truncated_wav_rejected():
    from src.voice import canonical_wav
    with pytest.raises(VoiceError):canonical_wav(wav_bytes()[:-20])

@pytest.mark.parametrize('heard',[None,[],{},'', '   ',123])
def test_invalid_transcript_is_not_a_success(tmp_path,monkeypatch,heard):
    voice=GnaniVoice('unit-test-placeholder');path=tmp_path/'input.wav';path.write_bytes(wav_bytes())
    monkeypatch.setattr(voice.session,'post',lambda *a,**k:Response(200,data={'success':True,'transcript':heard}))
    with pytest.raises(VoiceError):voice.transcribe(path)


def test_partial_pcm_frame_rejected():
    import struct
    from src.voice import canonical_wav
    blob=bytearray(wav_bytes()+b'1');struct.pack_into('<I',blob,4,len(blob)-8);struct.pack_into('<I',blob,40,3201)
    with pytest.raises(VoiceError):canonical_wav(bytes(blob))


# Explicit expected provider contracts, independent of the registry under test.
SPEECH_ROUTES = [
    ('en', 'en-IN', 'en-IN', 'Kaveri'),
    ('hi', 'hi-IN', 'hi-IN', 'Nalini'),
    ('ta', 'ta-IN', 'ta-IN', 'Asmita'),
    ('te', 'te-IN', 'te-IN', 'Suhana'),
    ('kn', 'kn-IN', 'kn-IN', 'Saanvi'),
    ('ml', 'ml-IN', 'ml-IN', 'Reshma'),
    ('mr', 'mr-IN', 'mr-IN', 'Zahira'),
    ('bn', 'bn-IN', 'bn-IN', 'Kirra'),
    ('gu', 'gu-IN', 'gu-IN', 'Falak'),
    ('pa', 'pa-IN', 'pa-IN', 'Mehuli'),
    ('hi-en', 'en-IN', 'hi-en', 'Poorvi'),
]

@pytest.mark.parametrize('code,stt_locale,tts_locale,preferred_voice', SPEECH_ROUTES)
def test_all_language_speech_requests_use_documented_routes(tmp_path,monkeypatch,code,stt_locale,tts_locale,preferred_voice):
    voice=GnaniVoice('unit-test-placeholder');clip=tmp_path/'input.wav';clip.write_bytes(wav_bytes());seen=[]
    monkeypatch.setenv('GNANI_TTS_MODEL','timbre-v2.5')
    def post(url,**kwargs):
        seen.append((url,kwargs))
        if url.endswith('/stt/v3'):
            return Response(200,data={'success':True,'transcript':'A spoken question'})
        return Response(200,wav_bytes())
    monkeypatch.setattr(voice.session,'post',post)
    assert voice.transcribe(clip,code)=='A spoken question'
    voice.synthesize('A reply',tmp_path/'reply.wav',code)
    assert seen[0][1]['data']['language_code']==stt_locale
    payload=seen[1][1]['json']
    assert payload['language']==tts_locale
    assert payload['voice']==preferred_voice
    assert payload['model']=='timbre-v2.5'
    assert (tmp_path/'reply.wav').read_bytes()==wav_bytes()

@pytest.mark.parametrize('unsupported',['fr','fr-FR','en-US','auto',''])
def test_unsupported_language_fails_before_network_or_output(tmp_path,monkeypatch,unsupported):
    voice=GnaniVoice('unit-test-placeholder');clip=tmp_path/'input.wav';clip.write_bytes(wav_bytes());calls=[]
    monkeypatch.setattr(voice.session,'post',lambda *a,**k:calls.append(1))
    with pytest.raises(VoiceError,match='Unsupported language'):
        voice.transcribe(clip,unsupported)
    with pytest.raises(VoiceError,match='Unsupported language'):
        voice.synthesize('A reply',tmp_path/'reply.wav',unsupported)
    assert calls==[] and not (tmp_path/'reply.wav').exists()


NATIVE_CASES = [
    ('hi','आपके ऑर्डर','एक दो तीन चार, पाँच छह सात आठ'),
    ('hi-en','Aapka order','एक दो तीन चार, पाँच छह सात आठ'),
    ('ta','உங்கள் ஆர்டர்','ஒன்று இரண்டு மூன்று நான்கு, ஐந்து ஆறு ஏழு எட்டு'),
    ('te','మీ ఆర్డర్','ఒకటి రెండు మూడు నాలుగు, ఐదు ఆరు ఏడు ఎనిమిది'),
    ('kn','ನಿಮ್ಮ ಆರ್ಡರ್','ಒಂದು ಎರಡು ಮೂರು ನಾಲ್ಕು, ಐದು ಆರು ಏಳು ಎಂಟು'),
    ('ml','നിങ്ങളുടെ ഓർഡർ','ഒന്ന് രണ്ട് മൂന്ന് നാല്, അഞ്ച് ആറ് ഏഴ് എട്ട്'),
    ('mr','तुमची ऑर्डर','एक दोन तीन चार, पाच सहा सात आठ'),
    ('bn','আপনার অর্ডার','এক দুই তিন চার, পাঁচ ছয় সাত আট'),
    ('gu','તમારો ઓર્ડર','એક બે ત્રણ ચાર, પાંચ છ સાત આઠ'),
    ('pa','ਤੁਹਾਡਾ ਆਰਡਰ','ਇੱਕ ਦੋ ਤਿੰਨ ਚਾਰ, ਪੰਜ ਛੇ ਸੱਤ ਅੱਠ'),
]

@pytest.mark.parametrize('language,prefix,spoken_id',NATIVE_CASES)
def test_native_speech_preserves_language_and_groups_identifiers(language,prefix,spoken_id):
    actual=for_ear(f'**{prefix}** 1234-5678; ₹49; 24 October 2026.',language)
    assert actual==f'{prefix} {spoken_id}; ₹49; 24 October 2026.'
    assert 'one two' not in actual and 'two thousand' not in actual


def test_native_script_order_digits_are_spoken_in_selected_language():
    assert for_ear('ऑर्डर १२३४५६७८','hi-IN')=='ऑर्डर एक दो तीन चार, पाँच छह सात आठ'


def test_english_locale_keeps_clear_numbers_and_full_year():
    actual=for_ear('Order 1234 5678 costs 49 rupees on 24 October 2027.','en-IN')
    assert 'one two three four, five six seven eight' in actual
    assert 'forty nine rupees' in actual
    assert 'twenty four October two thousand twenty seven' in actual


def test_mismatched_model_catalog_is_rejected_before_network(tmp_path,monkeypatch):
    voice=GnaniVoice('unit-test-placeholder');calls=[]
    monkeypatch.setenv('GNANI_TTS_MODEL','timbre-v3.0')
    monkeypatch.setattr(voice.session,'post',lambda *a,**k:calls.append(1))
    with pytest.raises(VoiceError,match='require GNANI_TTS_MODEL=timbre-v2.5'):
        voice.synthesize('Hello',tmp_path/'reply.wav','te')
    assert calls==[]
