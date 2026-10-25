"""Actual source context cannot replace strict uncertainty with unsupported claims."""
import json
import re

import pytest

from src.agent import Agent, Resources
from src.answering import Plan, Policy


@pytest.mark.parametrize('question', [
    'Can I schedule a delivery at midnight?',
    'Is there a student discount?',
])
def test_uncovered_question_retains_actual_context_and_strict_fake_uncertainty(monkeypatch, question):
    resources = Resources(dense=False)
    seen = []
    uncertainty = 'I do not have enough supported information to answer that question.'

    def complete(system, user, *args, **kwargs):
        seen.append(json.loads(user))
        return json.dumps({'answer': uncertainty, 'covered': False, 'needs_clarification': False})

    monkeypatch.setattr(resources.llm, 'complete', complete)
    out = Agent(resources, compose=True).respond(question)
    assert len(seen) == 1 and seen[0]['source_text']
    assert out['composition'] == 'abstained_missing_evidence'
    assert out['answer'].endswith(uncertainty)
    assert 'business hours' not in out['answer']
    assert out['retrieval_candidates'] and out['evidence_supported'] is False
    assert out['generation']['model_flags'] == {'covered': False, 'needs_clarification': False}
    assert out['generation']['provenance_kind'] == 'generation_context'
    recorded = {s['id']: s for s in out['generation_context_sources']}
    assert set(recorded) == {s['id'] for s in seen[0]['source_text']}
    assert all({key: recorded[s['id']][key] for key in s} == s for s in seen[0]['source_text'])
    assert all(s['text'] == resources.kb.chunks[s['id']].text for s in seen[0]['source_text'])
    assert not out['citations'] and not out['tool_calls']
    assert set(out['retrieved_chunk_ids']) <= {'STY-1'}


def test_unsupported_plan_cannot_enter_payload_or_render_authored_prose(monkeypatch):
    resources = Resources(dense=False)
    poison = 'AUTHORED_POLICY_MUST_NEVER_BE_RETURNED'
    seen = []
    uncertainty = 'I do not have enough supported information to answer that question.'

    def unsupported(self, question, intent, order=None):
        return Plan('unsupported', 'answer', poison, poison, poison,
                    ids=['DEL-1'], facts={'invented_fee_inr': 999})

    def complete(system, user, *args, **kwargs):
        payload = json.loads(user)
        seen.append(payload)
        assert poison not in system + user
        assert 'invented_fee_inr' not in payload['deterministic_facts']
        assert 'verified_rule_summary' not in payload and 'sentences' not in payload
        assert all(s['text'] == resources.kb.chunks[s['id']].text for s in payload['source_text'])
        return json.dumps({'answer': uncertainty, 'covered': False, 'needs_clarification': False})

    monkeypatch.setattr(Policy, 'plan', unsupported)
    monkeypatch.setattr(resources.llm, 'complete', complete)
    out = Agent(resources, compose=True).respond('Explain standard delivery charges.')
    assert len(seen) == 1 and out['retrieval_candidates']
    assert 'DEL-1' in {s['id'] for s in seen[0]['source_text']}
    assert out['composition'] == 'abstained_missing_evidence'
    assert poison not in out['answer'] and '999' not in out['answer']
    assert out['answer'].endswith(uncertainty)
    assert 'invented_fee_inr' not in out['facts']
    assert out['generation']['model_flags']['covered'] is False
    recorded = {s['id']: s for s in out['generation_context_sources']}
    assert set(recorded) == {s['id'] for s in seen[0]['source_text']}
    assert all({key: recorded[s['id']][key] for key in s} == s for s in seen[0]['source_text'])
    assert set(out['retrieved_chunk_ids']) <= {'STY-1'}


@pytest.mark.parametrize('unsupported_claim', [
    'Deliveries are limited to business hours.',
    'Student discounts are unavailable.',
])
def test_uncovered_flag_does_not_authorize_an_invented_restriction(monkeypatch, unsupported_claim):
    resources = Resources(dense=False)
    seen = []

    def complete(system, user, *args, **kwargs):
        seen.append(json.loads(user))
        return json.dumps({'answer': 'I cannot confirm that from these documents. But ' + unsupported_claim,
                           'covered': False, 'needs_clarification': False})

    monkeypatch.setattr(resources.llm, 'complete', complete)
    out = Agent(resources, compose=True).respond('Can I schedule a delivery at midnight?')
    assert len(seen) == 2
    assert seen[0]['source_text'] == seen[1]['source_text']
    assert out['composition'] == 'abstained_model_or_evidence'
    assert unsupported_claim not in out['answer']
    assert out['validation_error'].endswith('uncited_substantive_refusal')
    assert not out['evidence_supported'] and not out['citations']


def test_known_policy_still_uses_document_only_generation(monkeypatch):
    resources = Resources(dense=False)
    seen = []

    def complete(system, user, *args, **kwargs):
        payload = json.loads(user)
        seen.append(payload)
        assert 'verified_rule_summary' not in payload
        source = next(row for row in payload['source_text'] if row['id'] == 'REF-2')
        span = re.search(r'\|\s*UPI\s*\|\s*([^|]+)\|', source['text'])[1].strip()
        return json.dumps({'answer': f'UPI refunds take {span} after initiation.',
                           'decision': 'answer', 'covered': True})

    monkeypatch.setattr(resources.llm, 'complete', complete)
    out = Agent(resources, compose=True).respond('How long do UPI refunds take?')
    assert len(seen) == 1
    assert out['composition'] == 'grounded_llm' and out['decision'] == 'answer'
    assert '1 to 3 business days' in out['answer']
    assert out['generation']['provenance_kind'] == 'generation_context'
    assert out['citations'] == []
