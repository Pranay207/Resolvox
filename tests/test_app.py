"""Offline UI checks for shared conversations, voice recovery and honest evidence."""
import hashlib
import io
import json
import wave
from pathlib import Path

import pytest

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
    app.radio(key='input_mode').set_value('Type').run()
    app.chat_input[0].set_value('UPI refund timing please').run()
    assert not app.exception
    assert any('1 to 3' in item.value for item in app.markdown)
    panels = [item for item in app.expander if item.label == 'View supporting policy']
    assert len(panels) == 1  # One shared conversation renders each reply once.
    assert len(app.session_state.messages) == 1
    output = app.session_state.messages[0]['output']
    assert output['retrieved_chunk_ids']
    assert any(source['id'] == 'REF-2' for source in output['sources'])


def test_new_conversation_clears_private_context_and_history():
    app = start()
    app.radio(key='input_mode').set_value('Type').run()
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
    assert len(app.get('audio')) == 1
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
    app.button(key='support_retry_audio_0').click().run()
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


def test_speak_type_switch_keeps_one_conversation_and_secondary_upload():
    app = start()
    assert not app.tabs
    assert len(app.get('audio_input')) == 1
    assert len(app.get('file_uploader')) == 1
    assert any(x.label == 'Upload an audio clip' for x in app.expander)
    assert button(app, 'Send voice message').disabled
    app.radio(key='input_mode').set_value('Type').run()
    assert not app.exception
    assert not app.get('audio_input') and not app.get('file_uploader')
    app.chat_input[0].set_value('UPI refund timing please').run()
    saved = app.session_state.messages[0]['output']
    agent = app.session_state.agent
    app.radio(key='input_mode').set_value('Speak').run()
    assert not app.exception
    assert app.session_state.agent is agent
    assert app.session_state.messages[0]['output'] == saved
    assert len(app.get('chat_message')) == 2
    assert len(app.get('audio_input')) == 1
    assert button(app, 'Send voice message').disabled



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
    app.selectbox[0].set_value('Marathi').run()
    app.radio(key='input_mode').set_value('Type').run()
    app.chat_input[0].set_value('UPI परतावा कधी मिळेल?').run()
    assert not app.exception
    output = app.session_state.messages[0]['output']
    assert output['language'] == 'mr'
    assert output['localization']['status'] == 'unavailable_offline'
    assert output['decision'] == 'clarify'
    assert not output['tool_calls']


def test_workspace_keeps_evaluation_metrics_out_of_customer_ui():
    app = start()
    assert not app.tabs and not app.metric
    assert [item.value for item in app.title] == ['How can we help?']
    assert any(item.label == 'Your case' for item in app.expander)
    assert not any(item.value == 'Your next step' for item in app.subheader)
    assert not any('Tell us what happened' in item.value for item in app.markdown)
    assert len(app.get('column')) == 0
    assert not any('52' in item.value for item in app.info)


def snapshot_function():
    # Load the pure presentation helper without starting Streamlit/resources.
    import ast
    tree = ast.parse(Path('app.py').read_text(encoding='utf-8'))
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'case_snapshot')
    namespace = {}
    exec(compile(ast.Module(body=[node], type_ignores=[]), 'app.py', 'exec'), namespace)
    return namespace['case_snapshot']


def case_agent(oid='order-a', order=None):
    from types import SimpleNamespace
    return SimpleNamespace(state=SimpleNamespace(order_id=oid, order=order))


def output_message(calls=(), **extra):
    return {'output': {'tool_calls': list(calls), 'decision': 'answer', **extra}}


def lookup_call(oid='order-a', verified=True):
    return {'name': 'lookup_order', 'arguments': {'order_id': oid}, 'result': {'verified': verified}}


def test_case_panel_never_trusts_model_verified_flag_or_unverified_order_data():
    order = {'order_id': 'order-a', 'status': 'delivered', 'phone': 'private-phone',
             'delivery_pincode': 'private-proof', 'items': [{'sku': 'private-item'}]}
    for calls in [[], [lookup_call(verified=False)], [lookup_call('different-order')]]:
        view = snapshot_function()(case_agent(order=order), [output_message(calls, verified=True)])
        assert not view['verified']
        assert view['details'] == {} and view['items'] == []
        assert 'private' not in json.dumps(view)


def test_verified_case_allowlist_and_order_switch_hide_old_order():
    order = {'order_id': 'order-a', 'status': 'shipped', 'payment_method': 'upi',
             'phone': 'private-phone', 'delivery_pincode': 'private-proof',
             'items': [{'sku': 'ELE-1', 'qty': 1, 'proof': 'private-proof'}]}
    messages = [output_message([lookup_call()])]
    view = snapshot_function()(case_agent(order=order), messages)
    assert view['verified'] and view['details']['status'] == 'shipped'
    assert view['items'] == [{'sku': 'ELE-1', 'qty': 1}]
    assert 'private' not in json.dumps(view)
    switched = snapshot_function()(case_agent(oid='order-b', order=None), messages)
    assert not switched['verified'] and not switched['details'] and not switched['items']


@pytest.mark.parametrize('created,oid,expected', [(True,'order-a','T-1'), (False,'order-a',None), (True,'order-b',None)])
def test_ticket_status_requires_success_for_current_case(created, oid, expected):
    call = {'name': 'create_ticket', 'arguments': {'order_id': oid},
            'result': {'created': created, 'ticket_id': 'T-1'}}
    view = snapshot_function()(case_agent(), [output_message([call], decision='escalate')])
    assert view['ticket_id'] == expected
    assert ('Keep your ticket' in view['next_title']) == bool(expected)


def test_verified_lookup_renders_case_once_and_new_order_hides_it():
    app = start()
    app.radio(key='input_mode').set_value('Type').run()
    app.chat_input[0].set_value('Where is my order 89782837?').run()
    app.run()  # Settle the explicit UI rerun before submitting the next trigger.
    assert not app.exception
    assert not any('Order verified' in item.value for item in app.markdown)
    assert any('Verification needed' in item.value for item in app.markdown)
    app.chat_input[0].set_value('4533').run()  # Supplied fictional verification example.
    app.run()
    assert not app.exception
    assert any('Order verified' in item.value for item in app.markdown)
    assert app.session_state.messages[-1]['output']['transcript'] == '[verification value redacted]'
    assert '4533' not in '\n'.join(item.value for item in app.markdown)
    saved = list(app.session_state.messages)
    app.radio(key='input_mode').set_value('Speak').run()
    assert not app.exception
    assert app.session_state.messages == saved
    assert len(app.get('chat_message')) == 4
    app.radio(key='input_mode').set_value('Type').run()
    app.chat_input[0].set_value('Now check order 35061733').run()
    assert not app.exception
    assert app.session_state.agent.state.order is None
    assert not any('Order verified' in item.value for item in app.markdown)


def test_case_context_and_next_step_only_expand_when_action_is_needed():
    app = start()
    assert not any(x.value == 'Your next step' for x in app.subheader)
    app.radio(key='input_mode').set_value('Type').run()
    app.chat_input[0].set_value('Where is my order?').run()
    app.run()
    assert not app.exception
    assert any(x.value == 'Your next step' for x in app.subheader)
    assert any('Answer the question below' in x.value for x in app.markdown)
    button(app, 'New conversation').click().run()
    assert not any(x.value == 'Your next step' for x in app.subheader)


def test_policy_answer_does_not_add_a_generic_next_step_card():
    view = snapshot_function()(case_agent(oid=None), [output_message(decision='answer')])
    assert view['show_next_step'] is False
    for decision in ['clarify', 'escalate']:
        view = snapshot_function()(case_agent(oid=None), [output_message(decision=decision)])
        assert view['show_next_step'] is True


def policy_source_function():
    import ast
    tree = ast.parse(Path('app.py').read_text(encoding='utf-8'))
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'customer_policy_sources')
    namespace = {}
    exec(compile(ast.Module(body=[node], type_ignores=[]), 'app.py', 'exec'), namespace)
    return namespace['customer_policy_sources']


def test_policy_filter_keeps_customer_references_and_preserves_evidence():
    output = {'decision': 'answer', 'intent': 'refund',
              'retrieved_chunk_ids': ['STY-1', 'REF-2', 'KB-00', 'ORDER-1', 'MKT-1'],
              'sources': [{'id': 'STY-1', 'doc_type': 'agent_guide'},
                          {'id': 'REF-2', 'doc_type': 'policy', 'text': 'Policy text'},
                          {'id': 'KB-00', 'doc_type': 'meta'},
                          {'id': 'ORDER-1', 'doc_type': 'record'},
                          {'id': 'MKT-1', 'doc_type': 'marketing'},
                          {'id': 'UNUSED', 'doc_type': 'policy'}],
              'tool_calls': [{'name': 'lookup_order'}]}
    saved = json.dumps(output, sort_keys=True)
    assert [x['id'] for x in policy_source_function()(output)] == ['REF-2']
    assert json.dumps(output, sort_keys=True) == saved
    assert policy_source_function()({**output, 'decision': 'clarify'}) == []
    assert policy_source_function()({**output, 'intent': 'greeting'}) == []


def test_clarification_hides_internal_sources_and_empty_policy_panel():
    app = start()
    app.radio(key='input_mode').set_value('Type').run()
    app.chat_input[0].set_value('Where is my order?').run()
    app.run()
    assert not app.exception
    output = app.session_state.messages[0]['output']
    assert output['sources'] and output['decision'] == 'clarify'
    assert not any(x.label == 'View supporting policy' for x in app.expander)
    visible = '\n'.join(x.value for x in app.markdown) + '\n'.join(x.value for x in app.text)
    assert 'agent_conversation_style.md' not in visible
    assert 'STY-1' not in visible and 'STY-5' not in visible
