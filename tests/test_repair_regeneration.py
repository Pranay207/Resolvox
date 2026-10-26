"""Actual-module repair regeneration contracts; scripted clients, no live calls."""
import copy
import json
import socket
import pytest
import requests
from src import document_answers as document
from src.llm import LLMUnavailable

@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def denied(*args, **kwargs):
        raise AssertionError('Network forbidden during scripted checks')
    monkeypatch.setattr(requests.sessions.Session, 'request', denied)
    monkeypatch.setattr(socket, 'create_connection', denied)


SOURCE = {'id': 'SYNTHETIC-ROUTE', 'text': 'Requests are raised in the app under Service Requests.',
          'doc_type': 'policy', 'status': 'current'}


def flags(answer, covered=True, needs=False):
    return {'answer': answer, 'covered': covered, 'needs_clarification': needs}


class Client:
    def __init__(self, *values):
        self.values = list(values)
        self.calls = []
        self.last_metrics = {}
    def complete(self, system, user, **options):
        self.calls.append({'system': system, 'user': user, 'payload': json.loads(user),
                           'options': copy.deepcopy(options)})
        assert self.values, 'Unexpected extra model invocation'
        self.last_metrics = {'cache_hit': False, 'attempts': 1}
        value = self.values.pop(0)
        if isinstance(value, Exception):
            raise value
        return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)


def run(client, *, module=document, sources=None, facts=None, language='en', question='How can I submit a request?'):
    return module.document_reply(client, question, language, sources or [SOURCE],
                                 facts=facts or {}, context_provenance=True)


def test_invalid_json_regenerates_from_original_inputs_without_rejected_text():
    facts={'public_context':{'sku':'SYN-001'}}
    client=Client('not JSON',flags('Raise the request in the app under Service Requests.'))
    out=run(client,facts=facts)
    primary,repair=client.calls
    assert 'previous_response' not in primary['payload'] and 'previous_response' not in repair['payload']
    assert primary['payload']['source_text']==repair['payload']['source_text']==[SOURCE]
    assert primary['payload']['deterministic_facts']==repair['payload']['deterministic_facts']==facts
    assert repair['payload']['repair_validation_error']=='invalid_json'
    assert primary['options']['cache'] is True and repair['options']['cache'] is False
    assert all(call['options']['attempts']==1 for call in client.calls)
    assert len(client.calls)==out['generation_attempts']==2


def test_navigation_regeneration_keeps_source_derived_fields_and_one_retry():
    client=Client(flags('Click the Claim button in the app.'),flags('Raise the request in the app under Service Requests.'))
    run(client)
    repair=client.calls[1]['payload']
    assert 'previous_response' not in repair
    assert repair['repair_validation_error']=='unsupported_navigation_label'
    assert repair['documented_navigation_labels'] and 'documented_navigation_steps' in repair
    assert len(client.calls)==2


def test_absence_repair_retains_strict_uncertainty_flags():
    client = Client(flags('An Aster pass is not available because the policy contains no reference to it.'),
                    flags('I cannot confirm information from the supplied documents.', False))
    out = run(client, question='Explain the Aster pass policy.')
    repair = client.calls[1]['payload']
    assert 'previous_response' not in repair
    assert repair['repair_validation_error'] == 'absence_causal_policy_denial'
    assert out['model_flags'] == {'covered': False, 'needs_clarification': False}
    assert out['reply_kind'] == 'uncertainty' and out['source_ids'] == []


@pytest.mark.parametrize('text', [
    'I cannot confirm information. Your refund has been issued.',
    'I cannot confirm the 99-day deadline.',
    'I cannot confirm information; contact aster@example.com.',
])
def test_uncertainty_repair_cannot_hide_actions_numbers_or_contact_data(text):
    client = Client(flags('An Aster pass is not available because the policy contains no reference to it.'), flags(text, False))
    with pytest.raises(ValueError):
        run(client, question='Explain the Aster pass policy.')
    assert len(client.calls) == 2 and 'previous_response' not in client.calls[1]['payload']


def test_source_input_clarification_contract_survives_regeneration():
    table = {**SOURCE, 'text': '| Orchid | 17 calendar days | orchid |\n| Iris | 21 calendar days | iris |'}
    facts = {'required_application_inputs': [{'key': 'return_category', 'source_ids': [table['id']], 'allowed_rows': [
        {'return_category': 'orchid', 'return_window': '17 calendar days'},
        {'return_category': 'iris', 'return_window': '21 calendar days'}]}]}
    client = Client(flags('The window depends on the product category.'), flags('Which product category are you asking about?', False, True))
    out = run(client, sources=[table], facts=facts, question='How long can I return it?')
    repair = client.calls[1]['payload']
    assert 'previous_response' not in repair
    assert repair['repair_validation_error'] == 'missing_required_input:return_category'
    assert repair['repair_required_inputs'] == facts['required_application_inputs']
    assert out['decision'] == 'clarify' and out['covered'] is False


def test_other_requested_factual_constraints_still_apply_after_repair():
    source = {**SOURCE, 'text': SOURCE['text'] + ' The return window is 19 calendar days.'}
    facts = {'return_policy': {'window': 19}, 'answer_constraints': [
        {'kind': 'quantity', 'value': 19, 'unit': 'calendar_day', 'key': 'return_policy.window', 'source_ids': [SOURCE['id']]}]}
    client = Client(flags('Click the Claim button in the app.'), flags('Raise the request in the app under Service Requests.'))
    with pytest.raises(ValueError, match='document_generation_failed:answer_constraint_missing'):
        run(client, sources=[source], facts=facts)
    assert len(client.calls) == 2


def wrong_language():
    return flags('\u0905\u0928\u0941\u0930\u094b\u0927 Service Requests \u092e\u0947\u0902 \u0926\u0930\u094d\u091c \u0915\u0930\u0947\u0902\u0964')


def test_language_only_repair_keeps_prior_json_and_control_contract():
    client=Client(wrong_language(),flags('Request app mein Service Requests se raise karein.'))
    out=run(client,language='hi-en')
    repair=client.calls[1]['payload']
    assert repair['previous_response']==wrong_language()
    assert repair['language_repair_contract']==out['model_flags']=={'covered':True,'needs_clarification':False}
    assert len(client.calls)==2 and client.calls[1]['options']['cache'] is False


def test_language_repair_cannot_change_control_flags():
    client = Client(wrong_language(), flags('Mere paas jaankari nahi hai.', False))
    with pytest.raises(ValueError, match='language_repair_changed_control_fields'):
        run(client, language='hi-en')
    assert client.calls[1]['payload']['previous_response'] == wrong_language() and len(client.calls) == 2


def test_strict_mode_preserves_its_previous_response_and_citations_contract():
    response={'answer':'Raise the request in the app under Service Requests.','decision':'answer',
              'citations':[{'id':SOURCE['id'],'quote':SOURCE['text']}]}
    client=Client('not JSON',response)
    out=document.document_reply(client,'How can I submit a request?','en',[SOURCE],facts={})
    assert client.calls[1]['payload']['previous_response']=='not JSON'
    assert out['decision']=='answer' and len(client.calls)==2
    assert client.calls[0]['options']['cache'] is True and client.calls[1]['options']['cache'] is False


def test_provider_failure_during_regeneration_does_not_add_a_third_call():
    client = Client('not JSON', LLMUnavailable('synthetic offline'))
    with pytest.raises(LLMUnavailable):
        run(client)
    assert len(client.calls) == 2 and 'previous_response' not in client.calls[1]['payload']

