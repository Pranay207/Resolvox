"""Draft proposal checks with scripted clients only: no model or HTTP calls."""
import copy
import json

import pytest

from src.document_answers import document_reply

SOURCE = {'id': 'SYNTHETIC-REFUND',
          'text': 'Card refunds take 5 to 7 business days after initiation.',
          'doc_type': 'policy', 'status': 'current'}
CAL = {'id': 'SYNTHETIC-CALENDAR',
       'text': 'Business days exclude warehouse holidays.',
       'doc_type': 'meta', 'status': 'current'}
FACTS = {
    'reference_date': '2026-10-20',
    'calculations': [{'operation': 'refund_business_date_range',
                      'source_ids': [SOURCE['id'], CAL['id']],
                      'result': {'latest_date': '2026-10-27'}}],
    'answer_constraints': [{'kind': 'date', 'value': '2026-10-27',
                            'key': 'refund.latest_date',
                            'source_ids': [SOURCE['id'], CAL['id']],
                            'calculation_index': 0}],
    'date_labels': {'2026-10-27': '27 October 2026'},
}
WRONG = 'कार्ड रिफंड की अंतिम अनुमानित तारीख 27 अक्टूबर 2026 है।'
GOOD = 'Aapki di hui initiation date ke hisaab se card refund ki antim expected tareekh 27 October 2026 hai.'


def flags(answer, covered=True, needs=False):
    return {'answer': answer, 'covered': covered, 'needs_clarification': needs}


class Client:
    def __init__(self, *values):
        self.values = list(values)
        self.calls = []

    def complete(self, system, user, json_mode=False, **options):
        self.calls.append({'system': system, 'payload': json.loads(user),
                           'options': copy.deepcopy(options)})
        assert self.values, 'Unexpected third request'
        value = self.values.pop(0)
        return json.dumps(flags(value) if isinstance(value, str) else value,
                          ensure_ascii=False)


def reply(client, private=False):
    return document_reply(
        client, 'Card refund ki expected date kya hai?', 'hi-en', [SOURCE, CAL],
        facts=FACTS, private=private, context_provenance=True)


def test_existing_final_attempt_uses_focused_hinglish_translation_with_same_evidence():
    client = Client(WRONG, GOOD)
    out = reply(client)
    assert out['answer'] == GOOD and out['generation_attempts'] == 2
    assert out['model_flags'] == {'covered': True, 'needs_clarification': False}
    first, second = client.calls
    assert 'You are ZentroMart' in first['system']
    assert 'Aapka kaam sirf' in second['system']
    assert 'Latin aksharon' in second['system']
    assert second['payload']['repair_validation_error'] == 'wrong_output_language'
    assert 'Latin Hinglish' in second['payload']['repair_instruction']
    assert second['payload']['previous_response'] == flags(WRONG)
    assert second['payload']['language_repair_contract'] == {
        'covered': True, 'needs_clarification': False}
    assert first['payload']['source_text'] == second['payload']['source_text']
    assert first['payload']['deterministic_facts'] == second['payload']['deterministic_facts'] == FACTS
    assert first['options']['schema'] == second['options']['schema']
    assert second['options']['cache'] is False
    assert second['options']['attempts'] == 1
    assert len(client.calls) == 2


@pytest.mark.parametrize('translated', [
    WRONG,
    GOOD.replace('27 October', '28 October'),
    GOOD + ' I have issued your refund.',
    GOOD + ' Your email is synthetic@example.com.',
    GOOD + ' The fee is 9999 rupees.',
])
def test_translation_output_still_passes_all_script_date_action_private_numeric_checks(translated):
    client = Client(WRONG, translated)
    with pytest.raises(ValueError):
        reply(client)
    assert len(client.calls) == 2


@pytest.mark.parametrize('change', [
    {'covered': False},
    {'needs_clarification': True},
    {'covered': 1},
    {'covered': 'true'},
    {'needs_clarification': 0},
    {'needs_clarification': 'false'},
    {'decision': 'clarify'},
])
def test_control_fields_cannot_change_type_value_or_shape_during_translation(change):
    second = flags(GOOD)
    second.update(change)
    client = Client(WRONG, second)
    with pytest.raises(ValueError, match='language_repair_changed_control_fields'):
        reply(client)
    assert len(client.calls) == 2


def test_changing_to_clarification_cannot_skip_the_original_required_deadline():
    second = flags('Kaunsa payment method hai?', True, True)
    client = Client(WRONG, second)
    with pytest.raises(ValueError, match='language_repair_changed_control_fields'):
        reply(client)
    assert len(client.calls) == 2


def test_missing_control_field_is_not_reconstructed_by_the_host():
    client = Client(WRONG, {'answer': GOOD, 'covered': True})
    with pytest.raises(ValueError, match='language_repair_changed_control_fields'):
        reply(client)
    assert len(client.calls) == 2


@pytest.mark.parametrize('first,second', [
    (flags(WRONG), flags(GOOD)),
    (flags(WRONG, True, True), flags(GOOD, True, True)),
    (flags('कौन सा उत्पाद है?', False, True),
     flags('Kaunsa product hai?', False, True)),
    (flags('दस्तावेज़ों में जानकारी नहीं है।', False, False),
     flags('Mere paas iski jaankari nahi hai.', False, False)),
])
def test_all_previously_validated_boolean_combinations_are_preserved(first, second):
    client = Client(first, second)
    out = reply(client)
    assert out['model_flags'] == {
        key: first[key] for key in ('covered', 'needs_clarification')}
    assert client.calls[1]['payload']['language_repair_contract'] == out['model_flags']


@pytest.mark.parametrize('first,expected', [
    (WRONG.replace('27 अक्टूबर', '28 अक्टूबर'), 'answer_constraint_missing:refund.latest_date'),
    (WRONG + ' I have issued your refund.', 'unsupported_action'),
])
def test_bad_date_and_action_fail_before_language_check_and_keep_normal_repair(first, expected):
    client = Client(first, GOOD)
    out = reply(client)
    assert out['answer'] == GOOD
    assert client.calls[1]['payload']['repair_validation_error'] == expected
    assert client.calls[1]['system'] == client.calls[0]['system']
    assert 'language_repair_contract' not in client.calls[1]['payload']
    assert len(client.calls) == 2


@pytest.mark.parametrize('suffix', [
    ' The fee is 9999 rupees.',
    ' Your email is synthetic@example.com.',
])
def test_other_unsupported_claims_never_enter_language_only_repair(suffix):
    client = Client(WRONG + suffix, GOOD)
    out = reply(client)
    assert out['answer'] == GOOD
    assert client.calls[1]['payload']['repair_validation_error'] != 'wrong_output_language'
    assert client.calls[1]['system'] == client.calls[0]['system']
    assert 'language_repair_contract' not in client.calls[1]['payload']


def test_legacy_decision_is_preserved_instead_of_switching_constraint_branches():
    first = {'answer': WRONG, 'covered': True, 'decision': 'answer'}
    second = {'answer': 'Kaunsa product hai?', 'covered': True, 'decision': 'clarify'}
    client = Client(first, second)
    with pytest.raises(ValueError, match='language_repair_changed_control_fields'):
        reply(client)
    assert client.calls[1]['payload']['language_repair_contract'] == {
        'covered': True, 'decision': 'answer'}
    assert len(client.calls) == 2


def test_legacy_translation_with_same_control_fields_is_explicitly_legacy():
    client = Client(
        {'answer': WRONG, 'covered': True, 'decision': 'answer'},
        {'answer': GOOD, 'covered': True, 'decision': 'answer'})
    out = reply(client)
    assert out['answer'] == GOOD
    assert out['decision_origin'] == 'legacy_model_decision'
    assert out['model_flags'] == {'covered': True}


def test_private_translation_attempts_never_use_output_cache():
    client = Client(WRONG, GOOD)
    reply(client, private=True)
    assert all(call['options']['cache'] is False for call in client.calls)


def test_first_attempt_in_correct_hinglish_is_unchanged_and_never_translated():
    client = Client(GOOD)
    out = reply(client)
    assert out['answer'] == GOOD
    assert out['repair_attempted'] is False
    assert len(client.calls) == 1
    assert 'You are ZentroMart' in client.calls[0]['system']


def test_strict_quote_helper_uses_its_existing_system_on_both_attempts():
    def strict(answer):
        return {'answer': answer, 'decision': 'answer',
                'citations': [{'id': SOURCE['id'], 'quote': SOURCE['text']}]}
    client = Client(strict(WRONG), strict(GOOD))
    out = document_reply(
        client, 'Card refund ki expected date kya hai?', 'hi-en', [SOURCE, CAL],
        facts=FACTS, context_provenance=False)
    assert out['answer'] == GOOD
    assert len(client.calls) == 2
    assert client.calls[0]['system'] == client.calls[1]['system']
    assert 'language_repair_contract' not in client.calls[1]['payload']


def test_hindi_repair_instruction_is_real_utf8_and_preserves_the_control_contract():
    english = 'The expected card refund deadline is 27 October 2026.'
    client = Client(english, WRONG)
    out = document_reply(
        client, 'कार्ड रिफंड की तारीख क्या है?', 'hi', [SOURCE, CAL],
        facts=FACTS, context_provenance=True)
    assert out['answer'] == WRONG
    assert 'देवनागरी हिन्दी' in client.calls[1]['system']
    assert 'पिछले पूरे' in client.calls[1]['payload']['repair_instruction']
    assert client.calls[1]['payload']['language_repair_contract'] == {
        'covered': True, 'needs_clarification': False}
