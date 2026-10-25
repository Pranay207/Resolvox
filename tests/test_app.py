"""Offline UI checks for shared conversations, voice recovery and honest evidence."""
import io
import json
import wave

from streamlit.testing.v1 import AppTest

from src.agent import Agent
from src.voice import VoiceError


VOICE_SCRIPT = '''
import io
import runpy
import streamlit as st
ui = runpy.run_path('app.py')
if st.session_state.pop('_test_incoming_voice', False):
    clip = io.BytesIO(b'synthetic offline input')
    clip.name = 'question.wav'
    ui['process_voice'](clip, 'English / Hinglish')
    st.rerun()
'''


def start(script=None):
    app = (AppTest.from_string(script, default_timeout=40) if script
           else AppTest.from_file('app.py', default_timeout=40)).run()
    assert not app.exception
    app.toggle[0].set_value(False).run()
    assert not app.exception
    return app


def button(app, label):
    return next(item for item in app.button if item.label == label)


def wav_bytes():
    content = io.BytesIO()
    with wave.open(content, 'wb') as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(8000)
        writer.writeframes(b'\x00\x00' * 800)
    return content.getvalue()


def voice_double(monkeypatch, *, fail_audio=False):
    class FakeVoice:
        transcriptions = 0
        syntheses = 0
        fail = fail_audio

        def transcribe(self, path, language):
            assert path.exists()
            assert language == 'en-IN'
            type(self).transcriptions += 1
            # Exercise the real agent's proof redaction before UI persistence.
            return 'My phone last four digits are 1234'

        def synthesize(self, text, path, language):
            type(self).syntheses += 1
            if type(self).fail:
                raise VoiceError('Synthetic speech service interruption')
            path.write_bytes(wav_bytes())

    monkeypatch.setattr('src.voice.GnaniVoice', FakeVoice)
    calls = []
    respond = Agent.respond

    def tracked_respond(self, text, **kwargs):
        calls.append(text)
        return respond(self, text, **kwargs)

    monkeypatch.setattr(Agent, 'respond', tracked_respond)
    return FakeVoice, calls


def test_text_ui_and_source_panel():
    app = start()
    app.chat_input[0].set_value('UPI refund timing please').run()
    assert not app.exception
    assert any('1 to 3' in item.value for item in app.markdown)
    panels = [item for item in app.expander if item.label == 'Sources and actions']
    assert len(panels) == 2  # Both channels show the same single conversation.
    assert len(app.session_state.messages) == 1
    output = app.session_state.messages[0]['output']
    assert output['retrieved_chunk_ids']
    assert any(source['id'] == 'REF-2' for source in output['sources'])


def test_new_conversation_clears_private_context_and_history():
    app = start()
    app.chat_input[0].set_value('UPI refund timing please').run()
    previous = app.session_state.agent
    previous.state.order_id = '35061733'
    previous.state.order = {'private': 'verified order'}
    previous.state.attempts['35061733'] = 1
    previous.state.pending_issue = 'old complaint'
    app.session_state.voice_error = 'old speech error'
    epoch = app.session_state.voice_epoch
    next(item for item in app.button if 'New conversation' in item.label).click().run()
    assert not app.exception
    current = app.session_state.agent
    assert current is not previous
    assert current.state.order is None
    assert current.state.order_id is None
    assert current.state.attempts == {}
    assert current.state.pending_issue == ''
    assert current.state.safe_history == []
    assert current.compose is False
    assert app.session_state.messages == []
    assert app.session_state.voice_error is None
    assert app.session_state.voice_epoch == epoch + 1


def test_voice_reply_is_redacted_and_survives_reruns(monkeypatch):
    voice, calls = voice_double(monkeypatch)
    app = start(VOICE_SCRIPT)
    app.session_state._test_incoming_voice = True
    app.run()
    assert not app.exception
    entry = app.session_state.messages[0]
    assert entry['output']['transcript'] == '[verification value redacted]'
    assert entry['audio'] == wav_bytes()
    assert entry['audio_error'] is None
    assert len(app.get('audio')) == 2
    app.selectbox[0].set_value('Hindi').run()
    assert not app.exception
    assert app.session_state.messages[0]['audio'] == wav_bytes()
    assert voice.transcriptions == 1
    assert voice.syntheses == 1
    assert len(calls) == 1
    assert '1234' not in json.dumps([item['output'] for item in app.session_state.messages])
    assert '1234' not in '\n'.join(item.value for item in app.markdown)


def test_audio_retry_preserves_text_without_repeating_agent(monkeypatch):
    voice, calls = voice_double(monkeypatch, fail_audio=True)
    app = start(VOICE_SCRIPT)
    app.session_state._test_incoming_voice = True
    app.run()
    assert not app.exception
    entry = app.session_state.messages[0]
    saved_output = dict(entry['output'])
    assert entry['audio'] is None
    assert entry['audio_error']
    assert entry['output']['transcript'] == '[verification value redacted]'
    assert any('Your text answer is saved' in item.value for item in app.warning)
    voice.fail = False
    app.button(key='voice_retry_audio_0').click().run()
    assert not app.exception
    assert len(app.session_state.messages) == 1
    recovered = app.session_state.messages[0]
    assert recovered['output'] == saved_output
    assert recovered['audio'] == wav_bytes()
    assert recovered['audio_error'] is None
    assert voice.transcriptions == 1
    assert voice.syntheses == 2
    assert len(calls) == 1
    assert not app.warning


def test_record_and_upload_show_only_selected_input():
    app = start()
    assert len(app.get('audio_input')) == 1
    assert not app.get('file_uploader')
    assert button(app, 'Send voice message').disabled
    app.radio[0].set_value('Upload').run()
    assert not app.exception
    assert not app.get('audio_input')
    assert len(app.get('file_uploader')) == 1
    assert button(app, 'Send voice message').disabled
    app.radio[0].set_value('Record').run()
    assert not app.exception
    assert len(app.get('audio_input')) == 1
    assert not app.get('file_uploader')


def test_partial_live_evaluation_is_clearly_incomplete(monkeypatch):
    from pathlib import Path

    read_text = Path.read_text

    def report_text(path, *args, **kwargs):
        if path.name in {'eval_step2_live_current.json', 'eval_step3_live_current.json'}:
            return '{}'
        if path.name == 'eval_step2_live_postfix_partial.json':
            return json.dumps({'summary': {'passed': 32, 'total': 32,
                                          'planned': 52, 'complete': False}})
        return read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, 'read_text', report_text)
    app = start()
    status = next(item.value for item in app.info if 'Live model subset' in item.value)
    assert '32 passed, 32 checked of 52 planned' in status
    assert 'incomplete' in status
    assert 'Complete recorded run' not in status

def test_all_ten_voice_languages_are_available_as_optional_preview():
    app = start()
    assert set(app.selectbox[0].options) == {'English / Hinglish', 'Hindi'}
    app.toggle[1].set_value(True).run()
    languages = set(app.selectbox[0].options)
    assert languages == {'English / Hinglish', 'Hindi', 'Tamil', 'Telugu', 'Kannada',
                         'Malayalam', 'Marathi', 'Bengali', 'Gujarati', 'Punjabi'}
    app.selectbox[0].set_value('Telugu').run()
    assert not app.exception
    assert app.selectbox[0].value == 'Telugu'


def test_marathi_text_choice_does_not_become_hindi():
    app = start()
    app.toggle[1].set_value(True).run()
    app.selectbox[1].set_value('Marathi').run()
    app.chat_input[0].set_value('UPI परतावा कधी मिळेल?').run()
    assert not app.exception
    output = app.session_state.messages[0]['output']
    assert output['language'] == 'mr'
    assert output['localization']['status'] == 'unavailable_offline'
    assert output['decision'] == 'clarify'
    assert not output['tool_calls']
