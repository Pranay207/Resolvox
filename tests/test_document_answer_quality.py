"""Observed language and degenerate-answer failures, without model/API calls."""
import json

import pytest

from src.document_answers import SYSTEM, document_reply

SOURCE = {
    'id': 'SYNTHETIC-QUALITY',
    'text': 'Orchid returns allow 17 calendar days from delivery. Membership waives the collection fee.',
    'doc_type': 'policy', 'status': 'current',
}
EN = 'Orchid returns allow 17 calendar days from delivery.'
HI = 'रिटर्न की अवधि डिलीवरी से 17 कैलेंडर दिन है।'
HINGLISH = 'Delivery se return window 17 calendar days ki hai.'


class Client:
    def __init__(self, *answers):
        self.answers = list(answers)
        self.calls = []

    def complete(self, system, user, json_mode=False, **options):
        self.calls.append({'system': system, 'payload': json.loads(user), 'options': options})
        assert self.answers, 'Unexpected extra generation attempt'
        answer = self.answers.pop(0)
        return json.dumps(answer)


def value(text, decision='answer', covered=True):
    return {'answer': text, 'decision': decision, 'covered': covered}


def reply(client, language='en'):
    return document_reply(client, 'What is the return policy?', language, [SOURCE],
                          context_provenance=True)


@pytest.mark.parametrize('language,text,marker', [
    ('en', EN, 'Write the entire answer in English'),
    ('hi', HI, 'Write the entire answer in Devanagari Hindi'),
    ('hi-en', HINGLISH, 'Write the entire answer in Latin-script Hinglish'),
])
def test_context_system_resolves_the_specific_requested_language(language, text, marker):
    client = Client(value(text))
    out = reply(client, language)
    assert out['answer'] == text
    assert marker in client.calls[0]['system']
    assert 'Preserve English brand names' in client.calls[0]['system'] or language == 'en'


@pytest.mark.parametrize('language,corrected', [('hi', HI), ('hi-en', HINGLISH)])
def test_wrong_language_repair_explains_whole_answer_rewrite(language, corrected):
    client = Client(value(EN), value(corrected))
    out = reply(client, language)
    assert out['answer'] == corrected
    assert out['generation_attempts'] == 2
    repair = client.calls[1]
    assert repair['payload']['repair_validation_error'] == 'wrong_output_language'
    assert 'ENTIRE answer' in repair['payload']['repair_instruction']
    assert 'Preserve only facts supported' in repair['payload']['repair_instruction']
    assert repair['options']['cache'] is False
    assert client.calls[0]['payload']['source_text'] == [SOURCE]
    assert repair['payload']['source_text'] == [SOURCE]


@pytest.mark.parametrize('word', ['no', 'Yes.', 'नहीं', 'haan', '17-days'])
def test_one_word_covered_policy_reply_is_rejected_instead_of_rendered(word):
    client = Client(value(word), value(word))
    with pytest.raises(ValueError, match='incomplete_policy_answer'):
        reply(client)
    assert len(client.calls) == 2


def test_quality_repair_requests_an_explanation_without_an_authored_policy_answer():
    client = Client(value('no', decision='refuse'),
                    value('No collection fee applies because membership waives it.'))
    out = reply(client)
    assert out['decision'] == 'answer'
    assert out['generation_attempts'] == 2
    repair = client.calls[1]['payload']
    assert repair['repair_validation_error'] == 'incomplete_policy_answer'
    assert 'complete explanatory sentence' in repair['repair_instruction']
    assert 'verified_rule_summary' not in repair
    assert 'expected_answer' not in repair


def test_supported_negative_answer_is_not_defined_as_refusing_to_help():
    client = Client(value('No collection fee applies because membership waives it.'))
    out = reply(client)
    assert out['decision'] == 'answer'
    system = client.calls[0]['system']
    assert 'supported negative yes/no answer is still decision answer' in system
    assert 'declining an unsafe or prohibited request' in system
    assert 'never return just yes or no' in system


def test_general_policy_prompt_does_not_request_unnecessary_authentication():
    client = Client(value(EN))
    reply(client)
    system = client.calls[0]['system']
    assert 'Public policy questions do not require an order ID or identity proof' in system
    assert 'host already handles authentication' in system
    assert 'genuinely needed to apply the evidence' in system


def test_english_is_still_rejected_as_hinglish_after_the_instruction_change():
    client = Client(value(EN), value(EN))
    with pytest.raises(ValueError, match='wrong_output_language'):
        reply(client, 'hi-en')
    assert len(client.calls) == 2


@pytest.mark.parametrize('bad', [
    'The return period is 99 calendar days.',
    'I have issued your refund.',
    'Your contact email is synthetic@example.com.',
])
def test_language_quality_repair_does_not_relax_factual_action_or_privacy_checks(bad):
    client = Client(value(bad), value(bad))
    with pytest.raises(ValueError):
        reply(client)
    assert len(client.calls) == 2


def test_strict_helper_keeps_its_original_system_and_quote_contract():
    strict = {
        'answer': EN, 'decision': 'answer',
        'citations': [{'id': SOURCE['id'], 'quote': EN}],
    }
    client = Client(strict)
    out = document_reply(client, 'What is the return policy?', 'en', [SOURCE])
    assert out['citations'] == strict['citations']
    assert client.calls[0]['system'] == SYSTEM
    assert 'covered' not in client.calls[0]['options']['schema']['properties']
