"""Answers must depend on the retrieved version, not post-hoc citations."""
from dataclasses import replace
import json

import pytest

from src.agent import Agent, Resources
from src.grounding import fingerprint


def test_missing_governing_chunk_blocks_old_policy_answer():
    r=Resources(dense=False)
    del r.kb.chunks['REF-2']
    out=Agent(r,compose=False).respond('How long do UPI refunds take?')
    assert out['composition']=='abstained_missing_evidence'
    assert '1 to 3' not in out['answer']
    assert 'REF-2' not in out['retrieved_chunk_ids']
    assert out['facts']=={}


def test_changed_policy_cannot_use_stale_static_wording():
    r=Resources(dense=False)
    chunk=r.kb.chunks['DWM-1']
    r.kb.chunks['DWM-1']=replace(chunk,text=chunk.text.replace('48','72'))
    out=Agent(r,compose=False).respond('My item arrived damaged. What is the reporting deadline?')
    assert not out['evidence_supported']
    assert '48' not in out['answer']
    assert out['facts']=={}


def test_empty_search_cannot_be_filled_with_planner_citations(monkeypatch):
    r=Resources(dense=False)
    monkeypatch.setattr(r.retriever,'search',lambda *a,**k:[])
    out=Agent(r,compose=False).respond('What is the Plus membership fee?')
    assert out['composition']=='abstained_missing_evidence'
    assert '999' not in out['answer']
    assert set(out['retrieved_chunk_ids'])<= {'STY-1'}


def test_real_source_text_reaches_model_and_output_is_generated(monkeypatch):
    r=Resources(dense=False)
    seen={}
    def complete(system,user,*args,**kwargs):
        payload=json.loads(user);seen.update(payload)
        sources=payload['source_text']
        assert sources and all(s['text'] for s in sources)
        assert 'sentences' not in payload
        return json.dumps({'covered':True,'answer':'Report damage within 48 hours, with photos of the item and packaging. After verification, replacement or a full refund including delivery fees is available, without a pickup fee.',
                           'citations':[{'id':s['id'],'quote':s['text']} for s in sources]})
    monkeypatch.setattr(r.llm,'complete',complete)
    out=Agent(r,compose=True).respond('My item arrived damaged. What should I do?')
    assert out['composition']=='grounded_llm'
    assert seen['question']=='My item arrived damaged. What should I do?'
    assert set(out['retrieved_chunk_ids'])-{'STY-1'} <= {x['id'] for x in out['retrieval_candidates']}


def test_repeated_bare_proof_is_redacted_after_verification():
    r=Resources(dense=False);a=Agent(r,compose=False)
    a.respond('Order 89782837');a.respond('Last four digits 4533')
    out=a.respond('4533')
    assert '4533' not in json.dumps(out)+repr(a.state.safe_history)


def test_uncovered_policy_never_invites_model_to_invent_a_restriction(monkeypatch):
    r=Resources(dense=False)
    def forbidden(*args,**kwargs):raise AssertionError('No generation for an uncovered policy')
    monkeypatch.setattr(r.llm,'complete',forbidden)
    out=Agent(r,compose=True).respond('Can I schedule a delivery at midnight?')
    assert out['intent']=='unsupported' and "don't have" in out['answer']
    assert 'cannot schedule' not in out['answer']


def _fixed_retrieval(resources, monkeypatch, ids):
    """Keep stale index objects to exercise Agent's fresh source resolution."""
    rows = [{'chunk': resources.kb.chunks[cid], 'score': 1. - index / 100, 'dense_score': 0.}
            for index, cid in enumerate(ids)]
    monkeypatch.setattr(resources.retriever, 'search', lambda *args, **kwargs: rows)


def _fake_answer(payload, answer):
    return json.dumps({'covered': True, 'answer': answer, 'citations': [
        {'id': source['id'], 'quote': source['text']} for source in payload['source_text']]})


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

    assert len(seen) == 1
    assert 'DWM-1' not in {source['id'] for source in seen[0]['source_text']}
    assert seen[0]['deterministic_facts'] == {}
    assert 'verified_rule_summary' not in seen[0]
    assert not seen[0].get('required_citations', [])
    assert out['composition'] == 'abstained_model_or_evidence'
    assert out['validation_error'] == 'unsupported_number'
    assert '48' not in out['answer']
    assert out['facts'] == {}


@pytest.mark.parametrize('hours,accepted', [(72, True), (48, False)])
def test_composed_changed_source_uses_new_text_and_rejects_stale_quoted_values(monkeypatch, hours, accepted):
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

    assert len(seen) == 1
    actual = next(source for source in seen[0]['source_text'] if source['id'] == 'DWM-1')
    assert fingerprint(actual) == fingerprint(r.kb.chunks['DWM-1'].public())
    assert '72' in actual['text'] and '48' not in actual['text']
    assert seen[0]['deterministic_facts'] == {}
    assert 'verified_rule_summary' not in seen[0]
    assert out['facts'] == {} and not out['evidence_supported']
    if accepted:
        assert out['composition'] == 'grounded_llm'
        assert '72 hours' in out['answer']
    else:
        assert out['composition'] == 'abstained_model_or_evidence'
        assert out['validation_error'] == 'unsupported_number'
    assert '48' not in out['answer']


def test_incompatible_rule_metadata_discards_computed_facts_before_composition(monkeypatch):
    r = Resources(dense=False)
    query = 'Can I return electronics delivered on 2026-10-10?'
    prior = r.policy.plan(query, 'return')
    assert prior.facts['return_days'] == 7 and prior.facts['deadline'] == '2026-10-17'
    _fixed_retrieval(r, monkeypatch, ['RET-2', 'RET-3'])
    old = r.kb.chunks['RET-3']
    r.kb.chunks['RET-3'] = replace(old, version='unreviewed-rule-version')
    seen = []

    def complete(system, user, *args, **kwargs):
        seen.append(json.loads(user))
        return json.dumps({'covered': False, 'answer': '', 'citations': []})

    monkeypatch.setattr(r.llm, 'complete', complete)
    out = Agent(r, compose=True).respond(query)

    assert len(seen) == 1
    assert seen[0]['deterministic_facts'] == {}
    assert 'verified_rule_summary' not in seen[0]
    assert not seen[0].get('required_citations', [])
    assert any(source['id'] == 'RET-3' and source['version'] == 'unreviewed-rule-version'
               for source in seen[0]['source_text'])
    assert out['facts'] == {} and not out['evidence_supported']
    assert '17 October' not in out['answer']


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
        return json.dumps({'covered': False, 'answer': '', 'citations': []})

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
