"""Source-semantic context and generation hooks; mocked clients, no inference."""
import json
from types import SimpleNamespace

import pytest

from src.document_answers import document_reply
from src.document_context import build_context
from src.source_semantics import derive_source_constraints

SOURCE = {'id': 'dynamic-delivery-permission',
          'text': 'A shipped order cannot be cancelled. The customer can refuse the parcel at the door.',
          'doc_type': 'policy', 'status': 'current'}
DATA = SimpleNamespace(products={}, holidays=[])


class Client:
    def __init__(self, *answers):
        self.answers = list(answers)
        self.calls = []

    def complete(self, system, user, **options):
        self.calls.append({'system': system, 'payload': json.loads(user), 'options': options})
        assert self.answers, 'Unexpected third request'
        return json.dumps({'answer': self.answers.pop(0), 'covered': True,
                           'needs_clarification': False}, ensure_ascii=False)


def reply(client, facts=None, language='en'):
    return document_reply(client, 'Can I refuse this delivery?', language, [SOURCE],
                          facts=facts, context_provenance=True)


def test_context_exposes_only_nonempty_source_derived_semantic_constraints():
    context = build_context('Can I refuse delivery?', [SOURCE], DATA)
    assert context['source_semantic_constraints'] == derive_source_constraints([SOURCE])
    empty = build_context('Hello', [], DATA)
    assert 'source_semantic_constraints' not in empty


def test_validator_rederives_constraints_and_does_not_trust_forged_or_omitted_facts():
    client = Client('You cannot refuse the parcel.', 'You cannot refuse the parcel.')
    with pytest.raises(ValueError, match='source_permission_reversed'):
        reply(client, {'source_semantic_constraints': []})
    assert len(client.calls) == 2
    repair = client.calls[1]['payload']
    assert repair['repair_source_constraints'] == derive_source_constraints([SOURCE])
    assert 'source-derived' in repair['repair_instruction']
    assert client.calls[0]['payload']['source_text'] == repair['source_text']
    assert client.calls[1]['options']['cache'] is False


def test_success_records_the_evaluated_constraint_provenance():
    client = Client('You can refuse the parcel at the door.')
    out = reply(client)
    assert out['evaluated_source_constraints'] == derive_source_constraints([SOURCE])
    assert out['generation_attempts'] == 1
    assert out['citations'] == []


def test_semantic_error_precedes_wrong_language_and_uses_the_existing_single_repair():
    wrong = 'दरवाजे पर पैकेट को रिफस नहीं कर सकते हैं।'
    correct = 'Aap darwaze par parcel refuse kar sakte hain.'
    client = Client(wrong, correct)
    out = reply(client, language='hi-en')
    assert out['answer'] == correct and out['generation_attempts'] == 2
    assert client.calls[1]['payload']['repair_validation_error'] == 'source_permission_reversed'
    assert client.calls[0]['system'] == client.calls[1]['system']
    assert 'language_repair_contract' not in client.calls[1]['payload']
