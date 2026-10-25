"""Uncovered routes abstain before merely related context can invite guessing."""
import json
import re

import pytest

from src.agent import Agent, Resources
from src.answering import Plan, Policy


@pytest.mark.parametrize('question', [
    'Can I schedule a delivery at midnight?',
    'Is there a student discount?',
])
def test_uncovered_question_keeps_retrieval_trace_but_never_calls_llm(monkeypatch, question):
    resources = Resources(dense=False)

    def forbidden(*args, **kwargs):
        pytest.fail('Unsupported policy routing must not invite model guessing')

    monkeypatch.setattr(resources.llm, 'complete', forbidden)
    out = Agent(resources, compose=True).respond(question)
    assert out['composition'] == 'abstained_missing_evidence'
    assert out['decision'] == 'answer'
    assert 'enough supported information' in out['answer']
    assert 'business hours' not in out['answer']
    assert out['retrieval_candidates']
    assert out['facts'] == {} and out['evidence_supported'] is False
    assert out['generation_context_sources'] == [] and out['generation'] == {}
    assert out['citations'] == [] and out['llm'] == {}
    assert set(out['retrieved_chunk_ids']) <= {'STY-1'}


def test_unsupported_plan_cannot_render_authored_prose_even_with_a_retrieved_preferred_id(monkeypatch):
    resources = Resources(dense=False)
    poison = 'AUTHORED_POLICY_MUST_NEVER_BE_RETURNED'

    def unsupported(self, question, intent, order=None):
        return Plan('unsupported', 'answer', poison, poison, poison,
                    ids=['DEL-1'], facts={'invented_fee_inr': 999})

    monkeypatch.setattr(Policy, 'plan', unsupported)
    monkeypatch.setattr(resources.llm, 'complete', lambda *a, **k: pytest.fail('Unexpected model call'))
    out = Agent(resources, compose=True).respond('Explain standard delivery charges.')
    assert out['retrieval_candidates']
    assert out['composition'] == 'abstained_missing_evidence'
    assert poison not in out['answer'] and '999' not in out['answer']
    assert 'enough supported information' in out['answer']
    assert out['facts'] == {} and out['generation_context_sources'] == []


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
