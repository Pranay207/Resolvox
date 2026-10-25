"""Offline checks of the evidence runner; these mocks are not language proof."""
import io
import json
import wave

import pytest

from scripts.validate_languages import correct_duration, output_checks, run_validation, safe_failure, target_script


def wav_bytes():
    stream = io.BytesIO()
    with wave.open(stream, 'wb') as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(16000)
        audio.writeframes(b'\x01\x00' * 1600)
    return stream.getvalue()


def response(code='te'):
    answer = 'UPI రీఫండ్ ప్రారంభించిన తర్వాత రావడానికి 1 నుండి 3 పని దినాలు పడుతుంది.'
    return {'answer': answer, 'transcript': 'UPI రీఫండ్ ఎప్పుడు వస్తుంది?',
            'source_answer': 'UPI refunds take 1 to 3 business days after initiation.',
            'decision': 'answer', 'intent': 'refund', 'evidence_supported': True,
            'language': code, 'sources': [{'id': 'REF-2', 'text': 'UPI: 1 to 3 business days.'}],
            'localization': {'status': 'translated', 'query_translated': True,
                             'answer_translated': True, 'roundtrip_checked': True}}


@pytest.mark.parametrize(('code', 'text'), [
    ('en', 'UPI refunds take one to three business days after initiation.'),
    ('hi', 'UPI रिफंड १ से ३ कार्यदिवस में आता है।'),
    ('bn', 'UPI রিফান্ড ১ থেকে ৩ কর্মদিবস লাগে।'),
    ('gu', 'UPI રિફંડ ૧ થી ૩ કામકાજના દિવસો લાગે છે.'),
    ('kn', 'UPI ಮರುಪಾವತಿ ೧ ರಿಂದ ೩ ಕೆಲಸದ ದಿನಗಳಲ್ಲಿ ಬರುತ್ತದೆ.'),
    ('ml', 'UPI റീഫണ്ട് ൧ മുതൽ ൩ പ്രവൃത്തി ദിവസങ്ങൾ എടുക്കും.'),
    ('mr', 'UPI परतावा १ ते ३ कामकाजाचे दिवस लागतात.'),
    ('pa', 'UPI ਰਿਫੰਡ ੧ ਤੋਂ ੩ ਕੰਮਕਾਜੀ ਦਿਨ ਲੱਗਦੇ ਹਨ।'),
    ('ta', 'UPI ௧ முதல் ௩ வேலை நாட்கள் ஆகும்.'),
    ('te', 'UPI రీఫండ్ ౧ నుండి ౩ పని దినాలు పడుతుంది.'),
    ('hi-en', 'UPI refund ek se teen business days leta hai.'),
])
def test_duration_and_native_script_are_checked(code, text):
    assert correct_duration(text, code)
    assert target_script(text, code)


def test_unavailable_wrong_duration_and_wrong_language_never_pass():
    output = response()
    assert all(output_checks(output, 'te').values())
    output['localization']['status'] = 'answer_translation_failed'
    assert not output_checks(output, 'te')['translation_validated']
    output['localization']['status'] = 'translated'
    output['answer'] = 'UPI రీఫండ్ ప్రారంభించిన తర్వాత రావడానికి 5 నుండి 7 పని దినాలు పడుతుంది.'
    assert not output_checks(output, 'te')['target_refund_duration']
    output['answer'] = 'UPI refunds take 1 to 3 business days after initiation.'
    assert not output_checks(output, 'te')['target_script']
    output['sources'] = []
    assert not output_checks(output, 'te')['refund_source']


def dependencies(tmp_path, *, fail_language=None, text_only=False, provenance=None):
    calls = []

    class Voice:
        def synthesize(self, text, path, language):
            calls.append(('tts', language))
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(wav_bytes())

        def transcribe(self, path, language):
            calls.append(('stt', language))
            if fail_language == language:
                raise RuntimeError('Do not persist this private request or api-key-value')
            return 'synthetic native refund question'

    class Agent:
        def respond(self, text, language_hint):
            calls.append(('agent', language_hint))
            return response(language_hint)

    return calls, dict(output_path=tmp_path / 'validation.json', input_dir=tmp_path / 'inputs',
                       artifact_dir=tmp_path / 'outputs', names={'te': 'Telugu', 'ta': 'Tamil'},
                       stt_codes={'te': 'te-IN', 'ta': 'ta-IN'},
                       tts_codes={'te': 'te-IN', 'ta': 'ta-IN'},
                       voice_factory=Voice, agent_factory=Agent, text_only=text_only,
                       provenance=provenance or {'runtime_source_sha256': {'agent': 'same'}})


def test_real_route_order_incremental_evidence_and_resume(tmp_path):
    calls, options = dependencies(tmp_path)
    report = run_validation(['te'], **options)
    assert calls == [('tts', 'te'), ('stt', 'te-IN'), ('agent', 'te'), ('tts', 'te')]
    assert report['all_voice_passed']
    assert report['cases']['te']['reply_audio']['seconds'] == .1
    assert json.loads(options['output_path'].read_text(encoding='utf-8'))['complete']
    run_validation(['te'], **options)
    assert len(calls) == 4  # Existing completed evidence is preserved.
    run_validation(['te'], **options, rerun=True, reuse_inputs=True)
    assert calls[4:] == [('stt', 'te-IN'), ('agent', 'te'), ('tts', 'te')]
    reloaded = json.loads(options['output_path'].read_text(encoding='utf-8'))
    assert len(reloaded['attempt_history']) == 1
    assert reloaded['cases']['te']['input_audio']['reused']


def test_failed_case_is_saved_without_exception_details_and_later_cases_continue(tmp_path):
    calls, options = dependencies(tmp_path, fail_language='ta-IN')
    report = run_validation(['ta', 'te'], **options)
    assert report['complete'] and not report['all_voice_passed']
    assert report['summary']['voice_passed'] == 1
    assert report['cases']['ta']['failure_code'] == 'RuntimeError'
    assert report['cases']['ta']['stage'] == 'stt'
    assert report['cases']['te']['status'] == 'passed'
    assert 'api-key-value' not in options['output_path'].read_text(encoding='utf-8')
    assert safe_failure(RuntimeError('secret')) == 'RuntimeError'


def test_text_only_result_is_never_voice_proof_and_runtime_changes_rerun(tmp_path):
    calls, options = dependencies(tmp_path, text_only=True)
    report = run_validation(['te'], **options)
    assert report['complete'] and not report['all_voice_passed']
    assert report['summary']['text_only_passed'] == 1
    assert calls == [('agent', 'te')]
    options['provenance'] = {'runtime_source_sha256': {'agent': 'changed'}}
    run_validation(['te'], **options)
    assert calls == [('agent', 'te'), ('agent', 'te')]
