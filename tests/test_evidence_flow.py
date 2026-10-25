"""Answers use fresh documents and honestly record the full generation context."""
from dataclasses import replace
import json

import pytest

from src.agent import Agent, Resources
from src.grounding import fingerprint


def test_missing_governing_chunk_cannot_restore_old_policy_answer_offline():
    r = Resources(dense=False)
    del r.kb.chunks['REF-2']
    out = Agent(r, compose=False).respond('How long do UPI refunds take?')
    assert out['composition'] == 'abstained_missing_evidence'
    assert '1 to 3' not in out['answer']
    assert 'REF-2' not in out['retrieved_chunk_ids']
    assert out['facts'] == {}
    assert all(c['quote'] in next(s['text'] for s in out['sources'] if s['id'] == c['id'])
               for c in out['citations'])


def test_changed_policy_offline_displays_fresh_source_without_static_wording():
    r = Resources(dense=False)
    chunk = r.kb.chunks['DWM-1']
    r.kb.chunks['DWM-1'] = replace(chunk, text=chunk.text.replace('48', '72'))
    out = Agent(r, compose=False).respond('My item arrived damaged. What is the reporting deadline?')
    assert out['composition'] == 'document_excerpts'
    assert out['evidence_supported']
    assert '72 hours' in out['answer'] and '48 hours' not in out['answer']
    assert any(c['id'] == 'DWM-1' and c['quote'] in r.kb.chunks['DWM-1'].text
               for c in out['citations'])


def test_empty_search_cannot_be_filled_with_planner_citations(monkeypatch):
    r = Resources(dense=False)
    monkeypatch.setattr(r.retriever, 'search', lambda *a, **k: [])
    out = Agent(r, compose=False).respond('What is the Plus membership fee?')
    assert out['composition'] == 'abstained_missing_evidence'
    assert '999' not in out['answer']
    assert set(out['retrieved_chunk_ids']) <= {'STY-1'}
    assert out['facts'] == {}


def test_real_source_text_reaches_model_and_actual_generation_context_is_recorded(monkeypatch):
    r = Resources(dense=False)
    seen = {}

    def complete(system, user, *args, **kwargs):
        payload = json.loads(user)
        seen.update(payload)
        sources = {s['id']: s for s in payload['source_text']}
        assert sources and all(s['text'] for s in sources.values())
        assert 'sentences' not in payload and 'verified_rule_summary' not in payload
        return json.dumps({
            'decision': 'answer',
            'answer': 'Report damage within 48 hours, with photos of the item and packaging. After verification, a free replacement or full refund including delivery fees is available, without a reverse pickup fee.',
            'covered': True,
        })

    monkeypatch.setattr(r.llm, 'complete', complete)
    out = Agent(r, compose=True).respond('My item arrived damaged. What should I do?')
    assert out['composition'] == 'grounded_llm'
    assert seen['question'] == 'My item arrived damaged. What should I do?'
    supplied = {source['id']: source for source in seen['source_text']}
    assert {'DWM-1', 'DWM-2'} <= set(supplied)
    assert set(out['retrieved_chunk_ids']) == {'STY-1'} | set(supplied)
    assert {'DWM-1', 'DWM-2'} <= {x['id'] for x in out['retrieval_candidates']}
    assert out['generation']['provenance_kind'] == 'generation_context'
    assert set(out['generation']['context_source_ids']) == set(supplied)
    assert out['citations'] == []
    context = {source['id']: source for source in out['generation_context_sources']}
    assert set(context) == set(supplied)
    assert all(context[cid]['text'] == source['text'] for cid, source in supplied.items())


def test_repeated_bare_proof_is_redacted_after_verification():
    r = Resources(dense=False)
    agent = Agent(r, compose=False)
    agent.respond('Order 89782837')
    agent.respond('Last four digits 4533')
    out = agent.respond('4533')
    assert '4533' not in json.dumps(out) + repr(agent.state.safe_history)


def test_uncovered_policy_uses_source_only_uncertainty_without_invented_restriction(monkeypatch):
    r = Resources(dense=False)
    seen = []

    def complete(system, user, *args, **kwargs):
        payload = json.loads(user)
        seen.append(payload)
        assert 'verified_rule_summary' not in payload
        return json.dumps({'decision': 'refuse',
                           'answer': 'I do not have enough supported information to answer that.',
                           'covered': False})

    monkeypatch.setattr(r.llm, 'complete', complete)
    out = Agent(r, compose=True).respond('Can I schedule a delivery at midnight?')
    assert len(seen) == 1 and seen[0]['source_text']
    assert out['decision'] == 'refuse' and 'enough supported information' in out['answer']
    assert 'cannot schedule' not in out['answer']
    assert out['composition'] == 'abstained_missing_evidence'
    assert not out['citations']
    assert out['generation']['provenance_kind'] == 'generation_context'
    assert {s['id'] for s in out['generation_context_sources']} == {s['id'] for s in seen[0]['source_text']}


def _fixed_retrieval(resources, monkeypatch, ids):
    """Keep stale index objects to exercise Agent's fresh source resolution."""
    rows = [{'chunk': resources.kb.chunks[cid], 'score': 1. - index / 100, 'dense_score': 0.}
            for index, cid in enumerate(ids)]
    monkeypatch.setattr(resources.retriever, 'search', lambda *args, **kwargs: rows)


def _fake_answer(payload, text):
    assert payload['source_text']
    return json.dumps({'decision': 'answer', 'answer': text, 'covered': True})


def test_composed_missing_policy_has_no_stale_rule_payload_and_rejects_old_value(monkeypatch):
    r = Resources(dense=False)
    _fixed_retrieval(r, monkeypatch, ['DWM-1', 'DWM-2'])
    del r.kb.chunks['DWM-1']
    seen = []

    def complete(system, user, *args, **kwargs):
        payload = json.loads(user)
        seen.append(payload)
        return _fake_answer(payload, 'Report the damage within 48 hours.')

    monkeypatch.setattr(r.llm, 'complete', complete)
    out = Agent(r, compose=True).respond('My item arrived damaged. What is the reporting deadline?')
    assert len(seen) == 2
    assert all('DWM-1' not in {s['id'] for s in payload['source_text']} for payload in seen)
    assert all('verified_rule_summary' not in payload for payload in seen)
    assert all(not payload.get('required_citations', []) for payload in seen)
    assert all(payload['deterministic_facts']['calculations'] == [] for payload in seen)
    assert out['composition'] == 'abstained_model_or_evidence'
    assert out['validation_error'].endswith('unsupported_number')
    assert '48' not in out['answer']


@pytest.mark.parametrize('hours,accepted', [(72, True), (48, False)])
def test_composed_changed_source_uses_new_text_and_rejects_stale_values(monkeypatch, hours, accepted):
    r = Resources(dense=False)
    _fixed_retrieval(r, monkeypatch, ['DWM-1', 'DWM-2'])
    old = r.kb.chunks['DWM-1']
    r.kb.chunks['DWM-1'] = replace(old, text=old.text.replace('48', '72'))
    seen = []

    def complete(system, user, *args, **kwargs):
        payload = json.loads(user)
        seen.append(payload)
        return _fake_answer(payload, f'Report the damage within {hours} hours, with photos of the item and packaging.')

    monkeypatch.setattr(r.llm, 'complete', complete)
    out = Agent(r, compose=True).respond('My item arrived damaged. What is the reporting deadline?')
    assert len(seen) == (1 if accepted else 2)
    for payload in seen:
        actual = next(s for s in payload['source_text'] if s['id'] == 'DWM-1')
        assert fingerprint(actual) == fingerprint(r.kb.chunks['DWM-1'].public())
        assert '72' in actual['text'] and '48' not in actual['text']
        assert payload['deterministic_facts']['calculations'] == []
        assert 'verified_rule_summary' not in payload
    if accepted:
        assert out['composition'] == 'grounded_llm'
        assert '72 hours' in out['answer'] and out['evidence_supported']
    else:
        assert out['composition'] == 'abstained_model_or_evidence'
        assert out['validation_error'].endswith('unsupported_number')
    assert '48' not in out['answer']


def test_new_current_version_is_not_rejected_for_lacking_static_rule_fingerprint(monkeypatch):
    r = Resources(dense=False)
    query = 'Can I return electronics delivered on 2026-10-10?'
    _fixed_retrieval(r, monkeypatch, ['RET-2', 'RET-3'])
    old = r.kb.chunks['RET-3']
    r.kb.chunks['RET-3'] = replace(old, version='new-source-version')
    seen = []

    def complete(system, user, *args, **kwargs):
        payload = json.loads(user)
        seen.append(payload)
        return json.dumps({'decision': 'answer', 'answer': 'Electronics have a 7 day return window from delivery.',
                           'covered': True})

    monkeypatch.setattr(r.llm, 'complete', complete)
    out = Agent(r, compose=True).respond(query)
    assert len(seen) == 1
    assert 'verified_rule_summary' not in seen[0]
    assert any(s['id'] == 'RET-3' and s['version'] == 'new-source-version' for s in seen[0]['source_text'])
    assert 'return_days' not in seen[0]['deterministic_facts']
    assert out['composition'] == 'grounded_llm'
    assert out['generation']['generation_attempts'] == 1
    assert out['generation']['provenance_kind'] == 'generation_context'
    assert out['citations'] == []


def test_source_authority_filters_stale_superseded_index_objects_before_generation(monkeypatch):
    r = Resources(dense=False)
    _fixed_retrieval(r, monkeypatch, ['DWM-1', 'DWM-2'])
    old = r.kb.chunks['DWM-1']
    r.kb.chunks['DWM-1'] = replace(old, status='superseded')
    seen = []

    def complete(system, user, *args, **kwargs):
        payload = json.loads(user)
        seen.append(payload)
        return json.dumps({'decision': 'refuse', 'answer': 'I cannot confirm the reporting deadline from these documents.', 'covered': False})

    monkeypatch.setattr(r.llm, 'complete', complete)
    out = Agent(r, compose=True).respond('What is the damaged-item reporting deadline?')
    assert seen and all('DWM-1' not in {s['id'] for s in p['source_text']} for p in seen)
    assert '48' not in out['answer']
    assert 'DWM-1' not in out['retrieved_chunk_ids']


def test_verified_order_composition_and_proof_resumption_are_private_and_cache_disabled(monkeypatch):
    r = Resources(dense=False)
    _fixed_retrieval(r, monkeypatch, ['TRK-1', 'DEL-1', 'IDV-2'])
    seen, lookups = [], []
    proof = '4381'

    def lookup(order_id, value=None):
        lookups.append((order_id, value is not None))
        verified = value == proof
        order = {'order_id': order_id, 'status': 'Processing', 'promised_date': '2026-10-22'} if verified else {}
        arguments = {'order_id': order_id}
        if value is not None:
            arguments['verification_value'] = '[REDACTED]'
        return order, {'name': 'lookup_order', 'arguments': arguments,
                       'result': {'verified': verified, 'verification_required': not verified}}

    def complete(system, user, *args, **kwargs):
        seen.append({'system': system, 'payload': json.loads(user), 'options': kwargs})
        return json.dumps({'decision': 'refuse', 'answer': 'I cannot confirm the order status from these documents.', 'covered': False})

    monkeypatch.setattr(r.tools, 'lookup', lookup)
    monkeypatch.setattr(r.llm, 'complete', complete)
    agent = Agent(r, compose=True)
    pending_question = 'Where is order 11112222?'
    pending = agent.respond(pending_question)
    assert not seen and not pending['verified']
    resumed = agent.respond('Last four digits ' + proof)
    assert resumed['verified'] and len(seen) == 1
    assert seen[0]['payload']['question'] == pending_question
    assert not agent.state.pending_issue and not agent.state.pending_intent
    following = agent.respond('What is my order status?')
    assert following['verified'] and len(seen) == 2
    assert all(call['options']['cache'] is False for call in seen)
    assert seen[1]['payload']['question'] == 'What is my order status?'
    assert lookups == [('11112222', False), ('11112222', True)]
    dump = json.dumps({'calls': seen, 'pending': pending, 'resumed': resumed, 'following': following,
                       'history': agent.state.safe_history, 'order': agent.state.order}, ensure_ascii=False)
    assert proof not in dump
    assert 'phone_last4' not in agent.state.order and 'delivery_pincode' not in agent.state.order
    for call in seen:
        facts = json.dumps(call['payload']['deterministic_facts'])
        assert 'phone_last4' not in facts and 'delivery_pincode' not in facts
        assert call['payload']['deterministic_facts']['verified_order']['status'] == 'Processing'
