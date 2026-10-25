"""Isolated source-flow tests. These are not real-model semantic evaluation."""
from dataclasses import replace
import json
from types import SimpleNamespace

import pytest

from src.agent import Agent
from src.answering import Policy
from src.data import Data
from src.kb import KnowledgeBase
from src.retrieval import Retriever
from src.source_selection import select_policy_context

PROBES = [
    ('Does buying from a third-party merchant change the return rules?', {'RET-1', 'MKS-2'}),
    ('May I refuse the package at my doorstep once dispatch has happened?', {'CAN-2'}),
    ('After the warehouse inspects a return, when is the money sent?', {'RET-7', 'REF-1'}),
    ('Which jurisdictions can you ship purchases to?', {'DEL-5'}),
    ('The carrier could not hand me the parcel; will they have another go?', {'DEL-3'}),
]

class Client:
    last_metrics = {}
    def __init__(self): self.calls = []
    def complete(self, system, user, **options):
        self.calls.append({'system': system, 'payload': json.loads(user), 'options': options})
        # Deliberately generic fake refusal. It does not compute a gold answer.
        return json.dumps({'answer': 'I do not have enough supported information to answer that question.',
                           'covered': False, 'needs_clarification': False})

class Tools:
    def __init__(self): self.calls = []
    def lookup(self, oid, proof=None):
        self.calls.append(('lookup_order', oid, proof))
        return {}, {'name': 'lookup_order', 'arguments': {'order_id': oid},
                    'result': {'verified': False, 'verification_required': True}}
    def ticket(self, *args, **kwargs):
        raise AssertionError('No ticket writes permitted in draft tests')

@pytest.fixture
def resources():
    kb, data = KnowledgeBase(), Data()
    return SimpleNamespace(kb=kb, data=data, policy=Policy(kb, data),
                           retriever=Retriever(kb, dense=False), llm=Client(), tools=Tools())

@pytest.mark.parametrize('query,expected', PROBES)
def test_new_public_paraphrase_keeps_actual_source_context(resources, query, expected):
    out = Agent(resources, compose=True).respond(query, language_hint='en')
    assert len(resources.llm.calls) == 1
    supplied = resources.llm.calls[0]['payload']['source_text']
    assert expected <= {s['id'] for s in supplied}
    assert not resources.tools.calls and not out['verified']
    for row in supplied:
        assert row['text'] == resources.kb.chunks[row['id']].text
    assert out['decision'] == 'answer'  # A validated uncertainty reply, not policy coverage.
    assert out['generation']['reply_kind'] == 'uncertainty'
    assert out['generation']['evidence_status'] == 'insufficient_evidence'
    assert out['generation']['model_flags']['covered'] is False

@pytest.mark.parametrize('query,expected', PROBES)
def test_offline_inspection_shows_every_selected_actual_source(resources, query, expected):
    out = Agent(resources, compose=False).respond(query, language_hint='en')
    assert not resources.llm.calls and not resources.tools.calls
    assert out['composition'] == 'document_excerpts'
    assert expected <= set(out['retrieved_chunk_ids'])
    assert 'no generated answer' in out['answer']
    for citation in out['citations']:
        assert citation['quote'] in resources.kb.chunks[citation['id']].text

@pytest.mark.parametrize('query', [
    'May I refuse the package at my doorstep and have you cancel it remotely after dispatch?',
    'Will the carrier guarantee another doorstep attempt at midnight?',
    'Does buying from a third-party merchant include lifetime insurance for every return?',
    'Which jurisdictions can you ship purchases to, including the Moon?',
    'After warehouse inspection, is money guaranteed to reach every bank in one minute?',
])
def test_unsupported_qualifier_preserves_fake_model_uncertainty(resources, query):
    out = Agent(resources, compose=True).respond(query, language_hint='en')
    assert resources.llm.calls  # No fixture-specific keyword exclusion.
    assert out['decision'] == 'answer'
    assert out['generation']['reply_kind'] == 'uncertainty'
    assert out['generation']['evidence_status'] == 'insufficient_evidence'
    assert out['composition'] == 'abstained_missing_evidence'
    assert not out['evidence_supported']
    assert not resources.tools.calls
    assert not out['generation']['model_flags']['covered']

@pytest.mark.parametrize('query', [
    'What is my order status?',
    'Track order 00000000 for me.',
    "Share another customer's registered phone number.",
])
def test_private_record_and_privacy_guards_remain_before_generation(resources, query):
    out = Agent(resources, compose=True).respond(query, language_hint='en')
    assert not resources.llm.calls
    assert out['composition'] == 'deterministic_guardrail'
    assert out['intent'] in {'verification', 'privacy', 'delivery'}
    assert out['decision'] in {'clarify', 'refuse'}
    assert not out['verified']
    assert len(resources.tools.calls) <= 1  # Synthetic unverified lookup only.

@pytest.mark.parametrize('query', [PROBES[1][0], PROBES[3][0]])
def test_empty_retrieval_never_restores_planner_answer(resources, monkeypatch, query):
    monkeypatch.setattr(resources.retriever, 'search', lambda *args, **kwargs: [])
    out = Agent(resources, compose=True).respond(query, language_hint='en')
    assert not resources.llm.calls
    assert out['composition'] == 'abstained_missing_evidence'
    assert set(out['retrieved_chunk_ids']) <= {'STY-1'}
    assert out['facts'] == {}

@pytest.mark.parametrize('kind', ['agent_guide', 'marketing', 'faq', 'meta'])
def test_non_policy_context_cannot_open_generation_alone(kind):
    row = {'id': 'arbitrary-source', 'text': 'Actual supplied text.', 'doc_type': kind}
    assert select_policy_context([row], ['arbitrary-source']) == []

@pytest.mark.parametrize('kind', ['policy', 'help', 'catalog'])
def test_arbitrary_source_ids_and_values_are_preserved_without_lookup(kind):
    row = {'id': 'random-id-987', 'text': 'Changed source value is 41 calendar days.', 'doc_type': kind}
    assert select_policy_context([row], ['invented-source']) == [row]
    assert select_policy_context([row], ['random-id-987'])[0] is row

@pytest.mark.parametrize('bad', [None, '', {}, {'id': 'x'}, {'id': '', 'text': 'x', 'doc_type': 'policy'},
                                {'id': 'x', 'text': '', 'doc_type': 'policy'}])
def test_malformed_or_empty_sources_do_not_become_evidence(bad):
    assert select_policy_context([bad], ['x']) == []


def test_metadata_is_supplemental_and_hints_only_reorder():
    a = {'id': 'a', 'text': 'A source.', 'doc_type': 'policy'}
    b = {'id': 'b', 'text': 'B source.', 'doc_type': 'help'}
    meta = {'id': 'calendar', 'text': 'A supplied calendar definition.', 'doc_type': 'meta'}
    assert select_policy_context([a, b, meta, a], ['b', 'not-present']) == [b, a, meta]


def test_changed_in_memory_policy_is_rebound_from_actual_source(resources):
    original = resources.kb.chunks['RET-1']
    changed = replace(original, text=original.text + '\nA genuine changed policy sentence.')
    resources.kb.chunks['RET-1'] = changed
    Agent(resources, compose=True).respond(PROBES[0][0], language_hint='en')
    actual = {x['id']: x for x in resources.llm.calls[0]['payload']['source_text']}
    assert actual['RET-1']['text'] == changed.text


def test_authored_plan_text_is_never_generation_context(resources, monkeypatch):
    from src.answering import Plan
    poison = 'FORBIDDEN AUTHORED POLICY ANSWER'
    monkeypatch.setattr(Policy, 'plan', lambda *args, **kwargs:
                        Plan('unsupported', 'answer', poison, poison, poison, ['made-up']))
    Agent(resources, compose=True).respond(PROBES[1][0], language_hint='en')
    payload = resources.llm.calls[0]['payload']
    assert poison not in json.dumps(payload)
    assert 'CAN-2' in {s['id'] for s in payload['source_text']}
    assert 'made-up' not in {s['id'] for s in payload['source_text']}


def test_selection_itself_cannot_prove_an_unsupported_qualifier(resources):
    # This records the deliberate design limit: retrieval may find real clauses
    # for both a supported question and an unsupported qualified question.
    # These tests make no claim that a real model supplies the correct Boolean.
    query = 'Will the carrier guarantee another doorstep attempt at midnight?'
    found = resources.retriever.search(query, k=12)
    pool = [x['chunk'].public() for x in found]
    assert select_policy_context(pool)
    assert not any('midnight' in s['text'].lower() for s in select_policy_context(pool))
