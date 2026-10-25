"""Standard RAG records actual context without claiming model-selected quotes."""
import copy
import json

import pytest

from src.document_answers import document_reply
from src.llm import LLMUnavailable

SOURCE = {
    'id': 'SYNTHETIC-POLICY',
    'text': 'Orchid returns allow 17 calendar days from delivery.',
    'doc_type': 'policy', 'status': 'current',
}
OTHER = {
    'id': 'SYNTHETIC-OTHER',
    'text': 'Lilac membership does not include free replacement. Its fee is 999 rupees.',
    'doc_type': 'policy', 'status': 'current',
}


class Client:
    def __init__(self, *values):
        self.values = list(values)
        self.calls = []

    def complete(self, system, user, json_mode=False, **options):
        self.calls.append({'system': system, 'payload': json.loads(user), 'options': options})
        assert self.values, 'Unexpected extra generation attempt'
        value = self.values.pop(0)
        if isinstance(value, Exception):
            raise value
        return value if isinstance(value, str) else json.dumps(value)


def value(answer=None, *, decision='answer', covered=True):
    return {'answer': SOURCE['text'] if answer is None else answer,
            'decision': decision, 'covered': covered}


def run(client, *, sources=None, facts=None, private=False, language='en'):
    return document_reply(
        client, 'What is the Orchid return window?', language,
        [SOURCE] if sources is None else sources, facts=facts,
        private=private, context_provenance=True)


def rejects(candidate, **kwargs):
    client = Client(candidate, candidate)
    with pytest.raises(ValueError):
        run(client, **kwargs)
    assert len(client.calls) == 2


def test_host_records_the_actual_context_without_model_citation_claims():
    original = copy.deepcopy([SOURCE, OTHER])
    client = Client(value())
    out = run(client, sources=original)

    assert original == [SOURCE, OTHER]
    assert out['answer'] == SOURCE['text']
    assert out['source_ids'] == sorted([SOURCE['id'], OTHER['id']])
    assert out['context_source_ids'] == out['source_ids']
    assert out['citations'] == []
    assert out['provenance_kind'] == 'generation_context'
    assert out['covered'] is True
    assert out['generation_attempts'] == 1
    assert client.calls[0]['payload']['source_text'] == sorted(original, key=lambda s: s['id'])
    schema = client.calls[0]['options']['schema']
    assert set(schema['required']) == {'answer', 'covered', 'needs_clarification'}
    assert set(schema['properties']) == {'answer', 'covered', 'needs_clarification'}
    for key in ('verified_rule_summary', 'plan', 'policy_plan', 'required_ids',
                'expected_answer', 'required_citations', 'sentences'):
        assert key not in client.calls[0]['payload']


def test_unrelated_retrieved_exclusions_and_numbers_are_not_answer_obligations():
    out = run(Client(value()), sources=[SOURCE, OTHER])
    assert out['answer'] == SOURCE['text']
    assert '999' not in out['answer']
    assert 'replacement' not in out['answer']


@pytest.mark.parametrize('answer', [
    'The return window is 92 calendar days.',
    'The return window is 17 business days.',
    'I have issued your refund.',
    'Your ticket has been created.',
    'Your pickup was scheduled.',
    'Your contact email is synthetic@example.com.',
    'Your phone number is 9876543210.',
])
def test_unsupported_quantities_operations_and_private_data_fail_closed(answer):
    rejects(value(answer))


def test_a_failed_validation_has_only_one_uncached_repair():
    client = Client(value('The return window is 92 calendar days.'), value())
    out = run(client)
    assert out['answer'] == SOURCE['text']
    assert out['repair_attempted'] is True
    assert out['generation_attempts'] == 2
    assert client.calls[0]['options']['cache'] is True
    assert client.calls[1]['options']['cache'] is False
    assert client.calls[1]['payload']['repair_validation_error'] == 'unsupported_number'
    assert client.calls[1]['payload']['source_text'] == [SOURCE]


def test_provider_outage_does_not_return_a_policy_template_or_make_an_extra_call():
    client = Client(LLMUnavailable('synthetic outage'))
    with pytest.raises(LLMUnavailable):
        run(client)
    assert len(client.calls) == 1


@pytest.mark.parametrize('decision,answer', [
    ('clarify', 'Which product category would you like to return?'),
    ('refuse', 'I do not have enough supported information to answer that.'),
])
def test_uncovered_uncertainty_has_no_fake_answer_sources(decision, answer):
    out = run(Client(value(answer, decision=decision, covered=False)))
    assert out['answer'] == answer
    assert out['covered'] is False
    assert out['source_ids'] == []
    assert out['citations'] == []
    assert out['context_source_ids'] == [SOURCE['id']]
    assert out['provenance_kind'] == 'generation_context'


@pytest.mark.parametrize('candidate', [
    value('I do not have enough information.', covered=False),
    value('The return window is 17 calendar days.', decision='refuse', covered=False),
    value('Which product is this? Returns take 17 calendar days.', decision='clarify', covered=False),
    value('I do not have enough information, but returns are free.', decision='refuse', covered=False),
    {'answer': SOURCE['text'], 'decision': 'answer', 'covered': 1},
    {'answer': SOURCE['text'], 'decision': 'answer', 'covered': True, 'citations': []},
])
def test_false_coverage_and_invalid_schema_cannot_hide_substantive_answers(candidate):
    rejects(candidate)


def test_no_context_cannot_be_reported_as_a_covered_answer():
    rejects(value(), sources=[])
    out = run(Client(value('Which product category would you like to return?',
                           decision='clarify', covered=False)), sources=[])
    assert out['source_ids'] == [] and out['context_source_ids'] == []


def test_changed_source_content_needs_no_authored_answer_or_reviewed_sha():
    changed = dict(SOURCE, text=SOURCE['text'].replace('17', '23'))
    out = run(Client(value(changed['text'])), sources=[changed])
    assert '23 calendar days' in out['answer']


FACTS = {
    'verified_order': {
        'status': 'Delivered', 'return_rrn': '123456789012',
        'return_refund_completed_on': '2026-10-18',
    },
    'date_labels': {'2026-10-18': '18 October 2026'},
}


@pytest.mark.parametrize('answer', [
    'The order record lists status as Delivered.',
    'The order record lists refund completed on 18 October 2026.',
    'RRN: 123456789012.',
])
def test_authenticated_record_readings_work_in_context_mode(answer):
    client = Client(value(answer))
    out = run(client, facts=FACTS, private=True)
    assert out['answer'] == answer
    assert client.calls[0]['options']['cache'] is False
    assert client.calls[0]['payload']['deterministic_facts'] == FACTS


@pytest.mark.parametrize('answer', [
    'The order record lists status as Cancelled.',
    'The order record lists refund completed on 19 October 2026.',
    'RRN: 999999999999.',
    'The phone number is 123456789012.',
])
def test_context_mode_does_not_relax_false_or_mislabelled_record_claims(answer):
    rejects(value(answer), facts=FACTS, private=True)


def test_an_unverified_turn_cannot_use_an_authenticated_reference_exception():
    rejects(value('RRN: 123456789012.'), facts=FACTS, private=False)


def test_private_repair_disables_cache_on_both_attempts():
    client = Client('not JSON', value('RRN: 123456789012.'))
    out = run(client, facts=FACTS, private=True)
    assert out['generation_attempts'] == 2
    assert all(call['options']['cache'] is False for call in client.calls)
