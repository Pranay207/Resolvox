"""Offline recovery-evidence tests; fake providers never count as live proof."""
import json
from types import SimpleNamespace
import wave

import pytest

from scripts.validate_voice_recovery import ObservedVoice, assess_recovery, create_silence, run_check


def write_reply(path, *, silent=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), 'wb') as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(16000)
        audio.writeframes((b'\x00\x00' if silent else b'\x01\x00') * 1600)


class FakeVoice:
    def __init__(self):
        self.session = SimpleNamespace(hooks={})

    def respond(self, path):
        for callback in self.session.hooks.get('response', []):
            callback(SimpleNamespace(url='https://api.vachana.ai' + path, status_code=200))

    def transcribe(self, path, language):
        from src.voice import VoiceError
        self.respond('/stt/v3')
        raise VoiceError('Gnani returned an empty or invalid transcript; please repeat clearly')

    def synthesize(self, text, path, language):
        self.respond('/api/v1/tts/inference')
        write_reply(path)


def batch_fixture(folder, *, transcript='', tool_calls=None, silent_reply=False):
    folder.mkdir(parents=True, exist_ok=True)
    prediction = {'transcript': transcript,
                  'answer': "Sorry, I couldn't understand that audio. Please record a short, clear clip.",
                  'intent': 'unclear_audio', 'decision': 'clarify', 'tool_calls': tool_calls or [],
                  'sources': [], 'voice_timings': {'stt_ms': 1, 'tts_ms': 2, 'total_ms': 3}}
    (folder / '001_silence.json').write_text(json.dumps(prediction), encoding='utf-8')
    write_reply(folder / '001_silence_reply.wav', silent=silent_reply)
    return {'total': 1, 'succeeded': 0, 'failed': 1,
            'entries': [{'input': 'silence.wav', 'status': 'error', 'output_prefix': '001_silence',
                         'audio': '001_silence_reply.wav'}]}


def observer_for_success():
    observer = ObservedVoice(FakeVoice())
    observer.stt_calls = 1
    observer.tts_calls = 1
    observer.stt_http_statuses = [200]
    observer.tts_http_statuses = [200]
    return observer


def test_generated_input_is_exactly_one_second_of_digital_silence(tmp_path):
    details = create_silence(tmp_path / 'silence.wav')
    assert details['seconds'] == 1 and details['frames'] == 16000
    assert details['channels'] == 1 and details['sample_width'] == 2
    assert details['sample_rate'] == 16000 and not details['non_silent_pcm']


def test_real_reply_recovery_can_pass_while_normal_transcription_batch_counts_failure(tmp_path):
    batch = batch_fixture(tmp_path)
    result = assess_recovery(batch, tmp_path, observer_for_success())
    assert result['passed'] and all(result['checks'].values())
    assert result['batch_counts']['failed'] == 1
    assert result['batch_entry_status'] == 'error'
    assert result['reply_audio']['non_silent_pcm']


def test_hallucinated_speech_never_passes_even_if_agent_later_clarifies(tmp_path):
    batch = batch_fixture(tmp_path, transcript='Please track my order')
    observer = observer_for_success()
    observer.recognized_speech_from_silence = True
    result = assess_recovery(batch, tmp_path, observer)
    assert not result['passed']
    assert not result['checks']['silence_not_hallucinated_as_speech']


def test_clarification_cannot_also_claim_a_ticket_was_created(tmp_path):
    batch = batch_fixture(tmp_path)
    path = tmp_path / '001_silence.json'
    prediction = json.loads(path.read_text(encoding='utf-8'))
    prediction['answer'] += ' I created a ticket.'
    path.write_text(json.dumps(prediction), encoding='utf-8')
    result = assess_recovery(batch, tmp_path, observer_for_success())
    assert not result['passed'] and not result['checks']['no_claimed_completed_action']


def test_recovery_must_actually_ask_for_a_clear_repeat(tmp_path):
    batch = batch_fixture(tmp_path)
    path = tmp_path / '001_silence.json'
    prediction = json.loads(path.read_text(encoding='utf-8'))
    prediction['answer'] = "I couldn't understand that audio."
    path.write_text(json.dumps(prediction), encoding='utf-8')
    result = assess_recovery(batch, tmp_path, observer_for_success())
    assert not result['passed'] and not result['checks']['clear_repeat_request']


@pytest.mark.parametrize('failure', ['silent_reply', 'private_action', 'no_stt_response', 'no_tts_response'])
def test_silence_recovery_requires_real_speech_and_no_actions(tmp_path, failure):
    batch = batch_fixture(tmp_path, silent_reply=failure == 'silent_reply',
                          tool_calls=[{'name': 'create_ticket'}] if failure == 'private_action' else None)
    observer = observer_for_success()
    if failure == 'no_stt_response':
        observer.stt_http_statuses = []
    if failure == 'no_tts_response':
        observer.tts_http_statuses = []
    assert not assess_recovery(batch, tmp_path, observer)['passed']


def test_runner_uses_rules_only_and_preserves_prior_attempts(tmp_path):
    observed = []

    def fake_batch(input_dir, output_dir, **kwargs):
        assert kwargs['compose'] is False
        assert kwargs['session_mode'] == 'independent'
        voice = kwargs['voice']
        from src.voice import VoiceError
        with pytest.raises(VoiceError):
            voice.transcribe(input_dir / 'silence.wav', 'en-IN')
        voice.synthesize('Please repeat clearly.', output_dir / 'temporary.wav', 'en')
        observed.append(input_dir)
        return batch_fixture(output_dir)

    options = dict(report_path=tmp_path / 'evidence.json', input_root=tmp_path / 'inputs',
                   output_root=tmp_path / 'outputs', voice_factory=FakeVoice, batch_runner=fake_batch)
    first = run_check(**options)
    second = run_check(**options)
    assert first['status'] == second['status'] == 'tested'
    assert len(second['attempt_history']) == 1
    assert first['assessment']['reply_audio']['path'] != second['assessment']['reply_audio']['path']
    assert len(observed) == 2
