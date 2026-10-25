"""The document-only generation boundary uses model-selected source quotations.

Synthetic sections deliberately differ from the supplied capstone policies.
Clients are scripted, so these checks never call an inference API.
"""
import copy
import json

import pytest

from src.document_answers import document_reply
from src.llm import LLMUnavailable


POLICY = {
    'id': 'TEST-POLICY',
    'text': 'Orchid returns are accepted within 17 calendar days after delivery.',
    'doc_type': 'policy',
    'status': 'active',
    'version': 'synthetic-2',
    'effective_from': '2026-10-21',
}
OTHER = {
    'id': 'TEST-UNUSED',
    'text': 'Lilac pickups take 42 hours. The membership fee is 999 rupees.',
    'doc_type': 'policy',
    'status': 'active',
}
QUESTION = 'What is the Orchid return window?'


def answer(text=None, *, quote=None, source_id=None):
    return {
        'answer': text if text is not None else POLICY['text'],
        'decision': 'answer',
        'citations': [{
            'id': source_id if source_id is not None else POLICY['id'],
            'quote': quote if quote is not None else POLICY['text'],
        }],
    }


class ScriptedClient:
    def __init__(self, *values):
        self.values = list(values)
        self.calls = []

    def complete(self, system, user, json_mode=False, **options):
        self.calls.append({
            'system': system,
            'payload': json.loads(user),
            'json_mode': json_mode,
            'options': options,
        })
        assert self.values, 'Unexpected extra generation or repair call'
        value = self.values.pop(0)
        if isinstance(value, Exception):
            raise value
        return value if isinstance(value, str) else json.dumps(value)


def assert_rejected(value, *, sources=None, facts=None):
    client = ScriptedClient(value, value)
    with pytest.raises(ValueError):
        document_reply(client, QUESTION, 'en', sources or [POLICY], facts=facts)
    assert len(client.calls) == 2
    return client


def test_payload_is_document_text_without_an_authored_policy_answer(monkeypatch):
    monkeypatch.setenv('RAG_LLM_TIMEOUT', '7')
    client = ScriptedClient(answer())
    original = copy.deepcopy(POLICY)
    out = document_reply(client, QUESTION, 'en', [POLICY])

    assert POLICY == original
    payload = client.calls[0]['payload']
    assert payload['question'] == QUESTION
    assert payload['language'] == 'en'
    assert payload['source_text'] == [POLICY]
    assert payload.get('deterministic_facts', {}) == {}
    for key in ('verified_rule_summary', 'required_citations', 'required_ids',
                'plan', 'policy_plan', 'sentences', 'expected_answer'):
        assert key not in payload
    assert out['answer'] == POLICY['text']
    assert out['source_ids'] == [POLICY['id']]
    assert out['decision'] == 'answer'
    assert out['repair_attempted'] is False
    assert out['generation_attempts'] == 1
    call = client.calls[0]
    assert call['json_mode'] is True
    assert call['options']['attempts'] == 1
    assert call['options']['timeout'] == 7
    assert call['options']['cache'] is True
    assert {'answer', 'decision', 'citations'} <= set(call['options']['schema']['required'])


def test_changed_document_value_is_generated_without_a_reviewed_rule_binding():
    updated = dict(POLICY, text=POLICY['text'].replace('17', '23'), version='unreviewed-3')
    value = answer(updated['text'], quote=updated['text'])
    out = document_reply(ScriptedClient(value), QUESTION, 'en', [updated])
    assert '23 calendar days' in out['answer']
    assert out['citations'] == value['citations']


def test_only_model_selected_quotes_become_answer_provenance():
    value = answer()
    out = document_reply(ScriptedClient(value), QUESTION, 'en', [POLICY, OTHER])
    assert out['source_ids'] == [POLICY['id']]
    assert out['citations'] == value['citations']
    assert OTHER['id'] not in out['source_ids']


@pytest.mark.parametrize('citation', [
    {'id': 'MADE-UP', 'quote': POLICY['text']},
    {'id': POLICY['id'], 'quote': POLICY['text'].replace('17', '23')},
    {'id': POLICY['id'], 'quote': POLICY['text'] + ' invented policy'},
    {'id': POLICY['id'], 'quote': '17'},
    {'id': [POLICY['id']], 'quote': POLICY['text']},
    {'id': POLICY['id'], 'quote': None},
])
def test_forged_or_inexact_citations_fail_after_one_repair(citation):
    value = answer()
    value['citations'] = [citation]
    assert_rejected(value)


def test_missing_citations_are_not_replaced_with_all_retrieved_sections():
    value = answer()
    value['citations'] = []
    assert_rejected(value, sources=[POLICY, OTHER])


def test_uncited_candidate_cannot_authorize_a_number_in_the_answer():
    assert_rejected(answer('The return window is 42 calendar days.'), sources=[POLICY, OTHER])


def test_unquoted_part_of_a_cited_section_cannot_authorize_a_number():
    source = dict(POLICY, text=POLICY['text'] + ' The membership fee is 999 rupees.')
    assert_rejected(answer('The membership fee is 999 rupees.'), sources=[source])


@pytest.mark.parametrize('text', [
    'Orchid returns are accepted within 17 business days after delivery.',
    'The return window is 17 hours after delivery.',
    'The membership fee is 17 rupees.',
])
def test_matching_digits_cannot_authorize_a_different_quantity_unit(text):
    assert_rejected(answer(text))


@pytest.mark.parametrize('text', [
    'Your order has been cancelled.',
    'I have issued your refund.',
    'Your pickup was scheduled.',
    'Your ticket is created.',
    'After the return is initiated, I have processed your refund.',
])
def test_model_cannot_claim_a_completed_operation(text):
    assert_rejected(answer(text))


def test_invalid_json_gets_exactly_one_repair_then_validated_output():
    client = ScriptedClient('{broken JSON', answer())
    out = document_reply(client, QUESTION, 'en', [POLICY])
    assert len(client.calls) == 2
    assert out['answer'] == POLICY['text']
    assert out['repair_attempted'] is True
    assert out['generation_attempts'] == 2
    for call in client.calls:
        assert call['options']['attempts'] == 1
        assert call['payload']['source_text'] == [POLICY]
        assert 'verified_rule_summary' not in call['payload']


def test_invalid_repair_raises_instead_of_returning_a_policy_template():
    client = ScriptedClient('not JSON', 'still not JSON')
    with pytest.raises(ValueError):
        document_reply(client, QUESTION, 'en', [POLICY])
    assert len(client.calls) == 2


def test_provider_failure_propagates_without_a_policy_template_or_second_call():
    client = ScriptedClient(LLMUnavailable('synthetic outage'))
    with pytest.raises(LLMUnavailable):
        document_reply(client, QUESTION, 'en', [POLICY])
    assert len(client.calls) == 1


def test_provider_failure_during_repair_does_not_trigger_a_third_attempt():
    client = ScriptedClient('not JSON', LLMUnavailable('repair outage'))
    with pytest.raises(LLMUnavailable):
        document_reply(client, QUESTION, 'en', [POLICY])
    assert len(client.calls) == 2


def test_private_generation_and_repair_both_disable_output_caching():
    client = ScriptedClient('not JSON', answer())
    document_reply(client, QUESTION, 'en', [POLICY], private=True)
    assert len(client.calls) == 2
    assert all(call['options']['cache'] is False for call in client.calls)


def test_verified_computed_fact_can_support_a_typed_amount_without_answer_prose():
    facts = {'pickup_fee_inr': 64}
    client = ScriptedClient(answer('The pickup fee is 64 rupees.'))
    out = document_reply(client, QUESTION, 'en', [POLICY], facts=facts)
    assert out['answer'] == 'The pickup fee is 64 rupees.'
    assert client.calls[0]['payload']['deterministic_facts'] == facts


@pytest.mark.parametrize('decision,text', [
    ('clarify', 'Which payment method did you use?'),
    ('refuse', "I do not have enough information in the supplied documents to answer that."),
])
def test_honest_clarification_or_uncertainty_needs_no_fabricated_citations(decision, text):
    value = {'decision': decision, 'answer': text, 'citations': []}
    out = document_reply(ScriptedClient(value), QUESTION, 'en', [POLICY])
    assert out['decision'] == decision
    assert out['answer'] == text
    assert out['source_ids'] == [] and out['citations'] == []


@pytest.mark.parametrize('decision,text', [
    ('clarify', 'Which method did you use? Your refund takes 90 days.'),
    ('refuse', 'I cannot check, but your refund has been issued.'),
    ('clarify', 'Is your contact email synthetic@example.com?'),
    ('refuse', 'I do not know your policy, but the pickup fee is 999 rupees.'),
])
def test_no_citation_decisions_cannot_hide_policy_private_or_action_claims(decision, text):
    assert_rejected({'decision': decision, 'answer': text, 'citations': []})

@pytest.mark.parametrize('value', [
    None,
    [],
    {'decision': 'answer', 'answer': 17, 'citations': []},
    {'decision': 'escalate', 'answer': POLICY['text'], 'citations': []},
    {'decision': 'answer', 'answer': POLICY['text'], 'citations': POLICY['id']},
])
def test_invalid_response_shapes_get_no_more_than_one_repair(value):
    assert_rejected(value)


def test_quoted_personal_contact_data_is_not_repeated_as_an_answer():
    source = dict(POLICY, text='The contact email is synthetic@example.com.')
    value = answer(source['text'], quote=source['text'])
    assert_rejected(value, sources=[source])


def test_repair_disables_cache_even_for_a_public_question():
    client = ScriptedClient('not JSON', answer())
    document_reply(client, QUESTION, 'en', [POLICY])
    assert client.calls[0]['options']['cache'] is True
    assert client.calls[1]['options']['cache'] is False


def test_answer_cannot_reverse_a_condition_in_its_own_selected_quote():
    source = dict(POLICY, text='Orchid membership does not extend return windows.')
    value = answer('Orchid membership extends return windows.', quote=source['text'])
    assert_rejected(value, sources=[source])


def test_answer_can_preserve_a_quoted_negative_condition():
    source = dict(POLICY, text='Orchid membership does not extend return windows.')
    value = answer('Orchid membership does not extend return windows.', quote=source['text'])
    out = document_reply(ScriptedClient(value), QUESTION, 'en', [source])
    assert out['answer'] == value['answer']
