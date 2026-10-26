"""Exact-path projection with real generation validation and host binding checks."""
import copy
import hashlib
import json
import socket

import pytest
import requests
import src.document_answers as document
from src.inference_facts import project_inference_facts
from src.personal_money import derive_personal_money_bindings


SOURCE = {'id': 'SYNTHETIC-PROJECTION',
          'text': 'Orchid returns allow 17 calendar days from delivery.',
          'doc_type': 'policy', 'status': 'current', 'effective_from': '2031-01-01', 'version': 'synthetic-v3'}
HASHES = {SOURCE['id']: hashlib.sha256(SOURCE['text'].encode()).hexdigest()}


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def denied(*a, **k):
        pytest.fail('No network permitted in projection checks')
    monkeypatch.setattr(socket, 'create_connection', denied)
    monkeypatch.setattr(requests.sessions.Session, 'request', denied)


def test_only_explicit_reserved_valid_maps_are_removed_without_aliasing():
    authority = {SOURCE['id']: {key: SOURCE[key] for key in ('doc_type', 'status', 'effective_from', 'version')}}
    facts = {
        'reference_date': '2031-05-01', 'calculation_source_sha256': copy.deepcopy(HASHES),
        'calculations': [{'key': 'duration', 'value': 17, 'unit': 'calendar_days', 'source_ids': [SOURCE['id']]}],
        'source_semantic_constraints': [{'kind': 'synthetic', 'source_ids': [SOURCE['id']],
            'source_sha256': copy.deepcopy(HASHES), 'source_provenance_sha256': copy.deepcopy(HASHES),
            'source_authority': authority, 'effective_after': '2030-09-01', 'required_condition': 'inspection',
            'business': {'source_sha256': copy.deepcopy(HASHES)}}],
        'return_condition_policy': {'source_sha256': copy.deepcopy(HASHES), 'requirements': ['unused'],
                                    'scope': 'ordinary', 'source_ids': [SOURCE['id']]},
        'warranty_duration': {branch: {'source_sha256': copy.deepcopy(HASHES), 'duration_months': 19,
                                      'source_ids': [SOURCE['id']], 'catalog_column': 'warranty_months'}
                             for branch in ('assured', 'brand')},
        'operational_escalation': {'source_sha256': copy.deepcopy(HASHES), 'reason': 'synthetic_reason',
                                  'source_ids': [SOURCE['id']], 'binding_status': 'bound',
                                  'facts': {'paid_amount_inr': 321}, 'calculations': []},
        'source_sha256': copy.deepcopy(HASHES),
        'business_sha256': 'business text',
        'verified_order': {'sku': 'SYNTHETIC-SKU', 'source_sha256': copy.deepcopy(HASHES)},
    }
    original = copy.deepcopy(facts); expected = copy.deepcopy(facts)
    del expected['calculation_source_sha256']
    for item in expected['source_semantic_constraints']:
        del item['source_sha256']; del item['source_provenance_sha256']
    del expected['return_condition_policy']['source_sha256']
    del expected['operational_escalation']['source_sha256']
    for branch in ('assured', 'brand'):
        del expected['warranty_duration'][branch]['source_sha256']
    projected = project_inference_facts(facts)
    assert projected == expected and facts == original
    projected['source_semantic_constraints'][0]['source_authority'][SOURCE['id']]['status'] = 'changed copy'
    projected['calculations'][0]['value'] = 999
    assert facts == original


@pytest.mark.parametrize('record', [{}, {'source': 'not-a-digest'}, {'source': 123}, {'': 'a' * 64}, ['a' * 64]])
def test_malformed_or_empty_reserved_maps_are_preserved(record):
    facts = {'calculation_source_sha256': record, 'source_semantic_constraints': [{'source_sha256': record}]}
    assert project_inference_facts(facts) == facts


@pytest.mark.parametrize('context', [False, True])
@pytest.mark.parametrize('private', [False, True])
def test_generation_projects_both_attempts_but_validates_original_facts(monkeypatch, context, private):
    facts = {'calculation_source_sha256': copy.deepcopy(HASHES), 'calculations': [],
             'verified_order': {'sku': 'SYNTHETIC-SKU'}, 'business_sha256': 'preserved business value'}
    originals = copy.deepcopy(([SOURCE], facts)); seen = []
    validator_name = '_validate_context' if context else '_validate'
    actual_validator = getattr(document, validator_name)
    def validate(value, sources, validation_facts, *args, **kwargs):
        assert validation_facts is facts and validation_facts['calculation_source_sha256'] == HASHES
        seen.append(copy.deepcopy(validation_facts))
        return actual_validator(value, sources, validation_facts, *args, **kwargs)
    monkeypatch.setattr(document, validator_name, validate)
    class Client:
        def __init__(self): self.calls = []
        def complete(self, system, user, **options):
            payload = json.loads(user); self.calls.append((system, payload, options))
            assert payload['source_text'] == [SOURCE]
            assert payload['deterministic_facts'] == {k: v for k, v in facts.items() if k != 'calculation_source_sha256'}
            assert 'private_proof' not in payload and 'credentials' not in payload
            if len(self.calls) == 1: return 'not JSON'
            if context:
                return json.dumps({'answer': SOURCE['text'], 'covered': True, 'needs_clarification': False})
            return json.dumps({'answer': SOURCE['text'], 'decision': 'answer',
                               'citations': [{'id': SOURCE['id'], 'quote': SOURCE['text']}]})
    client = Client()
    result = document.document_reply(client, 'What is the return window?', 'en', [SOURCE], facts=facts,
                                     private=private, context_provenance=context)
    assert result['answer'] == SOURCE['text'] and result['generation_attempts'] == 2
    assert result['repair_errors'] == ['invalid_json']
    assert [call[2]['cache'] for call in client.calls] == [not private, False]
    assert all(call[2]['max_tokens'] == 700 and call[2]['attempts'] == 1 for call in client.calls)
    assert len(seen) == 1 and ([SOURCE], facts) == originals
    if context:
        assert result['context_source_ids'] == [SOURCE['id']]


def test_host_source_hash_binding_survives_projection_and_rejects_mutated_source():
    source = {'id': 'SYNTHETIC-MONEY', 'text': 'A refund is the paid amount less the documented fee.'}
    facts = {'calculations': [{'source_ids': [source['id']], 'inputs': {'paid_amount_inr': 321}}],
             'calculation_source_sha256': {source['id']: hashlib.sha256(source['text'].encode()).hexdigest()}}
    original = copy.deepcopy(facts); query = 'I paid 321 rupees for my return.'
    projected = project_inference_facts(facts)
    assert 'calculation_source_sha256' not in projected and facts == original
    before = derive_personal_money_bindings(query, facts, [source])
    assert len(before['calculation_inputs']) == 1
    changed = dict(source, text='Changed actual source with the same ID.')
    after = derive_personal_money_bindings(query, facts, [changed])
    assert after['calculation_inputs'] == [] and facts == original
    projected['calculations'][0]['inputs']['paid_amount_inr'] = 999
    assert facts == original
